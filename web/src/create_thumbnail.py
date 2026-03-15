"""
サムネイルを作成するモジュール。
"""

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
import pillow_heif
from src.services import get_file_type

load_dotenv()
BASE_DIR = os.getenv("CONTENTS_SAVE_DIR", "")


def create_thumbnail(input_file_path: Path, output_file_path: Path) -> str:
    """サムネイルを作成する"""
    if get_file_type(input_file_path) == "video":
        cmd = [
            "ffmpeg",
            "-i",
            input_file_path,
            "-ss",
            "00:00:03",
            "-vframes",
            "1",
            "-vf",
            "crop='min(iw,ih)':'min(iw,ih)',scale=300:300",
            output_file_path,
        ]
        subprocess.run(cmd, check=True)
    elif get_file_type(input_file_path) == "image":
        make_square_thumbnail_for_image(input_file_path, output_file_path, 300)
    else:
        raise ValueError("エラーが発生しました")


def make_square_thumbnail_for_image(input_path: Path, output_path: Path, size=300):
    """画像ファイルからサムネを作成する"""
    # 画像を開く
    if input_path.suffix.lower() == ".heic":
        heif_file = pillow_heif.read_heif(input_path)
        img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
    else:
        img = Image.open(input_path)
    w, h = img.size
    # PNG の場合は RGB に変換（透過情報を無視）
    if img.mode != "RGB":
        img = img.convert("RGB")
    # 正方形にクロップ（中央部分）
    min_side = min(w, h)
    left = (w - min_side) / 2
    top = (h - min_side) / 2
    right = (w + min_side) / 2
    bottom = (h + min_side) / 2

    img_cropped = img.crop((left, top, right, bottom))

    # リサイズ
    img_resized = img_cropped.resize((size, size), Image.Resampling.LANCZOS)
    # 保存
    img_resized.save(output_path, format="JPEG")
