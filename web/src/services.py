"""
共通関数を管理するモジュール
"""

import io
from pathlib import Path
import random
import re
import string
import subprocess
import threading
from PIL import Image
from typing import Callable, Literal

import pillow_heif
import rawpy


def create_random_file_name(file_name_words: int) -> str:
    """指定した長さのランダム文字列を生成する"""
    return "".join(
        random.choices(string.ascii_letters + string.digits, k=file_name_words)
    )


def get_file_type(file_path: Path) -> Literal["image", "video", "other"]:
    """file種別を返す"""
    ext = file_path.suffix.lower()
    image_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tiff",
        ".dng",
        ".heic",
    }

    video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"}
    if ext in image_extensions:
        return "image"
    if ext in video_extensions:
        return "video"
    return "other"


def convert_to_jpg(file_bytes: bytes, ext: str) -> Image.Image:
    """画像ファイルをjpgに変換する"""
    if ext in [".heic"]:
        heif_file = pillow_heif.read_heif(file_bytes)
        image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
        return image

    if ext in [".dng"]:
        with rawpy.imread(file_bytes) as raw:
            rgb = raw.postprocess()
            image = Image.fromarray(rgb)
            return image

    if ext in [".bmp", ".tiff"]:
        image = Image.open(io.BytesIO(file_bytes))
        return image.convert("RGB")

    return file_bytes

def convert_mov_to_mp4(input_path:Path, output_path:Path):
    """movファイルをmp4に変換する"""
    cmd = [
        "ffmpeg",
        "-y",  # 上書き
        "-i",
        str(input_path),  # 入力
        "-c:v",
        "libx264",  # 映像コーデック（ブラウザ互換）
        "-pix_fmt",
        "yuv420p",  # Safari / Chrome 対応
        "-profile:v",
        "high",
        "-level",
        "4.2",
        "-movflags",
        "+faststart",  # Web再生最適化
        "-c:a",
        "aac",  # 音声
        "-b:a",
        "128k",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def convert_to_hls(
    input_path: Path,
    output_dir: Path,
    on_progress: Callable[[int], None] | None = None,
) -> None:
    """動画ファイルをHLS形式（m3u8 + tsセグメント）に変換する。
    再エンコードにより回転メタデータを映像フレームに焼き込む。
    on_progress が指定された場合、0〜100 の進捗率を逐次コールバックする。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",                                                        # 出力ファイルが既存でも確認なしで上書き
        "-i", str(input_path),                                       # 入力ファイル
        "-c:v", "libx264",                                           # 映像コーデック（ブラウザ互換性が高いH.264）
        "-pix_fmt", "yuv420p",                                       # ピクセルフォーマット（Safari/Chrome対応に必須）
        "-profile:v", "high",                                        # H.264プロファイル（画質・圧縮効率のバランス）
        "-level", "4.2",                                             # H.264レベル（最大解像度・ビットレートの上限規定）
        "-crf", "18",                                                # 品質指定（0=無劣化〜51=最低画質、18は高画質）
        "-metadata:s:v:0", "rotate=0",                              # 回転メタデータをリセット（フレームへの焼き込み後に不要なので除去）
        "-c:a", "aac",                                               # 音声コーデック
        "-b:a", "128k",                                              # 音声ビットレート
        "-hls_time", "10",                                           # 1セグメントあたりの秒数（10秒ごとに.tsファイルを分割）
        "-hls_list_size", "0",                                       # プレイリストに全セグメントを記載（0=削除しない）
        "-hls_segment_filename", str(output_dir / "seg%03d.ts"),    # セグメントファイルの命名規則（seg001.ts, seg002.ts ...）
        str(output_dir / "index.m3u8"),                              # 出力プレイリストファイル
    ]

    if on_progress is None:
        subprocess.run(cmd, check=True)
        return

    # ffmpegのstderrから総再生時間を取得する正規表現
    # 例: "Duration: 00:01:23.45, start: ..."
    _DURATION_RE = re.compile(rb"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
    # ffmpegのstderrから現在のエンコード位置を取得する正規表現
    # 例: "frame= 100 fps=25 ... time=00:00:04.00 ..."
    _TIME_RE = re.compile(rb"time=(\d+):(\d+):(\d+\.\d+)")

    def _to_ms(h: str, m: str, s: str) -> float:
        # HH:MM:SS.ms 形式をミリ秒に変換
        return (float(h) * 3600 + float(m) * 60 + float(s)) * 1000

    # stderrをパイプで受け取るためPopen（非同期起動）を使用
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    # total_ms をリストで持つのは、クロージャ内から書き換えるための回避策
    total_ms: list[float | None] = [None]

    def _parse_stderr() -> None:
        buf = b""
        while True:
            # 256バイトずつ読み込む（read はデータが来るまでブロックし、EOFで空バイトを返す）
            chunk = proc.stderr.read(256)
            if not chunk:
                break
            buf += chunk
            # ffmpegは進捗を \r（キャリッジリターン）で同一行に上書き出力するため、\r と \n 両方で分割
            parts = re.split(rb"[\r\n]", buf)
            buf = parts[-1]  # 末尾の未完行は次のチャンクと結合するために保持
            for part in parts[:-1]:
                if total_ms[0] is None:
                    m = _DURATION_RE.search(part)
                    if m:
                        total_ms[0] = _to_ms(m.group(1), m.group(2), m.group(3))
                if total_ms[0]:
                    m = _TIME_RE.search(part)
                    if m:
                        # 進捗率を計算し、完了前に100%になるのを防ぐため上限を99%に制限
                        pct = min(int(_to_ms(m.group(1), m.group(2), m.group(3)) / total_ms[0] * 100), 99)
                        on_progress(pct)

    # stderrのパースをメインスレッドと並行して実行（daemon=True でメインプロセス終了時に自動終了）
    t = threading.Thread(target=_parse_stderr, daemon=True)
    t.start()
    proc.wait()  # ffmpegプロセスの終了を待機
    t.join()     # stderrパーススレッドの終了を待機

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    on_progress(100)  # 正常終了時に確実に100%を通知
