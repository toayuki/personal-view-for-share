
import random
import string
from pathlib import Path
import json
from datetime import datetime
import os
from PIL import Image

TARGET_DIR=Path("/Volumes/SSD/-/shiro")

##### 必ず指定 ####
contentsType="shiro"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",".dng",".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"}

def make_square_thumbnail(input_path, output_path, size=300):
    # 画像を開く
    img = Image.open(input_path)
    w, h = img.size
    print("実行中",img)
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
    img_resized = img_cropped.resize((size, size), Image.LANCZOS)

    # 保存
    img_resized.save(output_path,format="JPEG")

file_list = []
output_dir = "thumbnails"
os.makedirs(output_dir, exist_ok=True) 

for path in TARGET_DIR.iterdir():
    if path.is_file():
        stat = path.stat()
        ext = path.suffix.lower()

        if ext in IMAGE_EXTENSIONS:
            file_type = "image"
        elif ext in VIDEO_EXTENSIONS:
            file_type = "video"
        else:
            file_type = "other"

        fileNameWords=20
        newFileName = ''.join(
            random.choices(string.ascii_letters + string.digits, k=fileNameWords)
        )+ path.suffix.lower()

        new_path = path.with_name(newFileName)
        path.rename(new_path)
        thumbnailFileName = ''.join(
            random.choices(string.ascii_letters + string.digits, k=fileNameWords)
        )+ ".jpg"
        thumb_path = os.path.join(output_dir, thumbnailFileName)

        if ext in VIDEO_EXTENSIONS:
            cmd = [
                "ffmpeg",
                "-i", new_path,
                "-ss", "00:00:03",
                "-vframes", "1",
                "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=300:300",
                thumb_path
            ]
            # subprocess.run(cmd, check=True)
        elif ext in IMAGE_EXTENSIONS:
            make_square_thumbnail(new_path,thumb_path,300)
            
        file_list.append({
            "file_name": newFileName,
            "thumbnail_file_name": thumbnailFileName,
            "original_file_name": path.name,
            "duration_ms": None,
            "contents_type": contentsType,
            "title": path.name,
            "file_type": file_type,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

with open("files_info.json", "w", encoding="utf-8") as f:
    json.dump(file_list, f, ensure_ascii=False, indent=2)