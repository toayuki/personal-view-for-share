"""
共通関数を管理するモジュール
"""

import io
import random
import re
import string
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Literal, cast

import numpy as np
import pillow_heif  # pyright: ignore[reportMissingTypeStubs]
import rawpy  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image, ImageOps


def create_random_file_name(file_name_words: int) -> str:
    """指定した長さのランダム文字列を生成する"""
    return "".join(random.choices(string.ascii_letters + string.digits, k=file_name_words))


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


def save_image_as_webp(
    file_bytes: bytes,
    ext: str,
    path: Path,
    max_px: int | None = None,
    max_kb: int | None = None,
    quality: int = 85,
    lossless: bool = False,
) -> None:
    """画像をWebPに変換して保存する。max_px/max_kbを指定すると解像度・容量を制限する。"""
    if ext == ".heic":
        heif_file: Any = pillow_heif.read_heif(file_bytes)  # pyright: ignore[reportUnknownMemberType] -- pillow_heif has no stubs
        image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
    elif ext == ".dng":
        with rawpy.imread(file_bytes) as raw:  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType] -- rawpy has no stubs
            rgb = cast(np.ndarray, raw.postprocess())  # pyright: ignore[reportUnknownMemberType] -- rawpy has no stubs
            image = Image.fromarray(rgb)
    else:
        image = Image.open(io.BytesIO(file_bytes))
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    if max_px:
        image.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    if max_kb:
        buf = io.BytesIO()
        for q in range(quality, 9, -5):
            buf = io.BytesIO()
            image.save(buf, "WEBP", quality=q)
            if buf.tell() <= max_kb * 1024:
                path.write_bytes(buf.getvalue())
                return
        path.write_bytes(buf.getvalue())
    elif lossless:
        image.save(path, "WEBP", lossless=True)
    else:
        image.save(path, "WEBP", quality=quality)


def convert_to_bg_mp4(input_path: Path, output_path: Path, max_seconds: int | None = None):
    """任意の動画を MP4（ブラウザ互換）に変換する。max_seconds 指定時はその秒数で切り詰める"""
    # fmt: off
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        *(["-t", str(max_seconds)] if max_seconds is not None else []),  # 秒数指定時のみ付加
        "-c:v", "libx264",           # H.264（ブラウザ互換）
        "-pix_fmt", "yuv420p",       # Safari/Chrome 対応に必須
        "-profile:v", "high",
        "-level", "4.2",
        "-movflags", "+faststart",   # moov atom を先頭に移動してストリーミング再生を高速化
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_path),
    ]
    # fmt: on
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
    # fmt: off
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-c:v", "libx264",                                               # H.264（ブラウザ互換）
        "-pix_fmt", "yuv420p",                                           # Safari/Chrome 対応に必須
        "-profile:v", "high",
        "-level", "4.2",
        "-crf", "18",                                # 高画質（0=無劣化〜51=最低）
        "-metadata:s:v:0", "rotate=0",              # 回転メタをリセット（焼き込み済みのため不要）
        "-c:a", "aac",
        "-b:a", "128k",
        "-hls_time", "10",                          # 1セグメント = 10秒
        "-hls_list_size", "0",                      # プレイリストに全セグメントを保持
        "-hls_segment_filename", str(output_dir / "seg%03d.ts"),        # seg000.ts, seg001.ts ...
        str(output_dir / "index.m3u8"),
    ]
    # fmt: on

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
    assert proc.stderr is not None
    stderr = proc.stderr
    # total_ms をリストで持つのは、クロージャ内から書き換えるための回避策
    total_ms: list[float | None] = [None]

    def _parse_stderr() -> None:
        buf = b""
        while True:
            chunk = stderr.read(256)
            if not chunk:
                break
            buf += chunk
            parts = re.split(rb"[\r\n]", buf)
            buf = parts[-1]  # 末尾の未完行は次のチャンクと結合するために保持
            for part in parts[:-1]:
                if total_ms[0] is None:
                    m = _DURATION_RE.search(part)
                    if m:
                        total_ms[0] = _to_ms(
                            m.group(1).decode(), m.group(2).decode(), m.group(3).decode()
                        )
                if total_ms[0]:
                    m = _TIME_RE.search(part)
                    if m:
                        # 進捗率を計算し、完了前に100%になるのを防ぐため上限を99%に制限
                        pct = min(
                            int(
                                _to_ms(
                                    m.group(1).decode(), m.group(2).decode(), m.group(3).decode()
                                )
                                / total_ms[0]
                                * 100
                            ),
                            99,
                        )
                        on_progress(pct)

    # stderrのパースをメインスレッドと並行して実行（daemon=True でメインプロセス終了時に自動終了）
    t = threading.Thread(target=_parse_stderr, daemon=True)
    t.start()
    proc.wait()  # ffmpegプロセスの終了を待機
    t.join()  # stderrパーススレッドの終了を待機

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    on_progress(100)  # 正常終了時に確実に100%を通知
