"""
FastAPI を用いた Web フロントエンド用エントリーポイントモジュール。

- HTML テンプレートのレンダリング
- 静的ファイルの配信
"""

from datetime import datetime
import os
import shutil
from pathlib import Path
import requests
from dotenv import load_dotenv  # type: ignore
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import create_thumbnail
from src.services import convert_mov_to_mp4, convert_to_jpg, create_random_file_name, get_file_type

load_dotenv()
BASE_DIR = Path(os.getenv("CONTENTS_SAVE_DIR", ""))
API_URL = os.getenv("API_URL", "")
app = FastAPI()
app.mount(path="/static", app=StaticFiles(directory="src/static"), name="static")
html = Jinja2Templates(directory="src/html")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """トップページを返す"""
    context = {"request": request, "main_class": "main-content"}
    return html.TemplateResponse("index.html", context)

@app.get("/confirmModal.html", response_class=HTMLResponse)
async def confirm_modal(request: Request):
    """confirmモーダルを返す"""
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "shiro",
        "title_name": "PERSONAL - shiro",
    }
    return html.TemplateResponse("confirmModal.html", context)


@app.get("/shiro.html", response_class=HTMLResponse)
async def shiro_page(request: Request):
    """shiroページを返す"""
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "shiro",
        "title_name": "PERSONAL - shiro",
    }
    return html.TemplateResponse("shiro.html", context)


@app.get("/texture.html", response_class=HTMLResponse)
async def texture_page(request: Request):
    """textureページを返す"""
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "texture",
        "title_name": "texture",
    }
    return html.TemplateResponse("texture.html", context)


@app.get("/utopia.html", response_class=HTMLResponse)
async def utopia_page(request: Request):
    "utopiaページを返す"
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "utopia",
        "title_name": "utopia",
    }
    return html.TemplateResponse("utopia.html", context)


@app.get("/drawing.html", response_class=HTMLResponse)
async def drawing_page(request: Request):
    """drawingページを返す"""
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "drawing",
        "title_name": "drawing",
    }
    return html.TemplateResponse("drawing.html", context)


@app.get("/fantasy.html", response_class=HTMLResponse)
async def fantasy_page(request: Request):
    """fantasyページを返す"""
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "fantasy",
        "title_name": "fantasy",
    }
    return html.TemplateResponse("fantasy.html", context)


@app.get("/personal-web/contents/{contents_type}/img/{file_name}")
def get_img_file(contents_type: str, file_name: str):
    print("xxxxxここ")
    """imgファイルを返す"""
    file_path = BASE_DIR / contents_type / "images" / file_name
    return FileResponse(file_path)


@app.get("/personal-web/contents/{contents_type}/video/{file_name}")
def get_video_file(contents_type: str, file_name: str):
    """videoファイルを返す"""
    print("xxxxxここ2")
    file_path = BASE_DIR / contents_type / "videos" / file_name
    return FileResponse(file_path)


@app.get("/personal-web/contents/{contents_type}/thumbnail/{file_name}")
def get_thumbnail_file(contents_type: str, file_name: str):
    """thumbnailファイルを返す"""
    file_path = BASE_DIR / contents_type / "thumbnails" / file_name
    return FileResponse(file_path)


@app.post("/upload/{contents_type}")
async def upload_file(contents_type: str, file: UploadFile = File(...)):
    """ファイルのアップロードを行う"""
    target_dir_path = BASE_DIR / contents_type
    original_ext = Path(file.filename).suffix.lower()
    stored_file_name = create_random_file_name(20) + original_ext
    stored_file_path = target_dir_path / "originals" / stored_file_name
    file_bytes = await file.read()
    with stored_file_path.open("wb") as buffer:
        buffer.write(file_bytes)

    view_file_name_without_ext = create_random_file_name(20)
    view_file_name = view_file_name_without_ext + original_ext.lower()
    original_file_type = get_file_type(stored_file_path)
    if original_file_type == "image":
        if original_ext in [".bmp", ".tiff", ".dng", ".heic"]:
            img = convert_to_jpg(file_bytes, original_ext)
            view_file_name = f"{view_file_name_without_ext}.jpg"
            converted_view_file_path = target_dir_path / "images" / view_file_name
            img.save(converted_view_file_path, "JPEG", quality=85)  # quality 調整可
        else:
            view_file_path = target_dir_path / "images" / view_file_name
            with view_file_path.open("wb") as buffer:
                buffer.write(file_bytes)
    elif original_file_type == "video":
        if original_ext == ".mov":
            view_file_name = f"{view_file_name_without_ext}.mp4"
            converted_view_file_path = target_dir_path / "videos" / view_file_name
            convert_mov_to_mp4(stored_file_path,converted_view_file_path)
        else:
            view_file_path = target_dir_path / "videos" / view_file_name
            with view_file_path.open("wb") as buffer:
                buffer.write(file_bytes)
    elif original_file_type == "other":
        view_file_path = target_dir_path / "others" / view_file_name
        with view_file_path.open("wb") as buffer:
            buffer.write(file_bytes)

    thumbnail_file_name = create_random_file_name(20) + ".jpg"
    create_thumbnail.create_thumbnail(
        stored_file_path,
        target_dir_path / "thumbnails" / thumbnail_file_name,
    )
    stat = stored_file_path.stat()
    name_without_ext = Path(file.filename).stem
    res = requests.post(
        f"{API_URL}/upload",
        json={
            "file_name": view_file_name,
            "thumbnail_file_name": thumbnail_file_name,
            "original_file_name": file.filename,
            "stored_file_name": stored_file_name,
            "duration_ms": None,
            "contents_type": contents_type,
            "title": name_without_ext,
            "file_type": original_file_type,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        },
        timeout=10,
    )
    return {"filename": file.filename}

@app.get("/delete/{target_id}")
def delete(target_id: str):
    """表示用データだけ削除を実施する"""
    print("削除受信", target_id)
    response = requests.get(f"{API_URL}/getItem/{target_id}",timeout=10).json()
    requests.post(f"{API_URL}/delete/{target_id}",timeout=10)
    print("item",response)
    # conn = sqlite3.connect("main.db")
    # conn.row_factory = sqlite3.Row
    # cur = conn.cursor()
    # cur.execute(
    #     """
    # delete from contents where id = ?
    # """,(target_id,))
    # conn.commit()
    # conn.close()

@app.get("/forceDelete/{target_id}")
def force_delete(target_id: str):
    """オリジナルデータも含めて削除を実施する"""
    print("削除受信", target_id)
    response = requests.get(f"{API_URL}/getItem/{target_id}",timeout=10).json()
    requests.post(f"{API_URL}/delete/{target_id}",timeout=10)
    print("item",response)
    # conn = sqlite3.connect("main.db")
    # conn.row_factory = sqlite3.Row
    # cur = conn.cursor()
    # cur.execute(
    #     """
    # delete from contents where id = ?
    # """,(target_id,))
    # conn.commit()
    # conn.close()
