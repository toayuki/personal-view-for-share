"""
共通関数を管理するモジュール
"""

import io
from pathlib import Path
import random
import string
import subprocess
from PIL import Image
from typing import Literal

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


def convert_to_hls(input_path: Path, output_dir: Path) -> None:
    """動画ファイルをHLS形式（m3u8 + tsセグメント）に変換する"""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-c:v", "copy",
        "-c:a", "copy",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-hls_segment_filename", str(output_dir / "seg%03d.ts"),
        str(output_dir / "index.m3u8"),
    ]
    subprocess.run(cmd, check=True)
