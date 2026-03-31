"""
FastAPI を用いた Web フロントエンド用エントリーポイントモジュール。

- HTML テンプレートのレンダリング
- 静的ファイルの配信
"""

from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from datetime import datetime
import os
from urllib.parse import quote
import secrets
import shutil
from pathlib import Path
from email.mime.text import MIMEText
import requests
import smtplib
from dotenv import load_dotenv  # type: ignore
from fastapi import BackgroundTasks, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import create_thumbnail
from src.services import convert_to_hls, convert_to_jpg, create_random_file_name, get_file_type

load_dotenv()
BASE_DIR = Path(os.getenv("CONTENTS_SAVE_DIR", ""))
API_URL = os.getenv("API_URL", "")
LOGIN_USER = os.getenv("LOGIN_USER", "admin")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "password")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# 一時登録トークン {token: {"email": str, "expires": datetime}}
pending_registrations: dict[str, dict] = {}

app = FastAPI()

is_debug_mode = True

# 有効なセッショントークンを管理するメモリストア
active_sessions: set[str] = set()

_PUBLIC_PATHS = {"/login", "/signup", "/signup/details", "/signup/complete", "/favicon.ico"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """未認証リクエストを /login にリダイレクトする"""
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/static"):
        response =  await call_next(request)
    else:
        token = request.cookies.get("session")
        if token and token in active_sessions:
            response =  await call_next(request)
        else:
            return RedirectResponse(url="/login", status_code=302)
    if is_debug_mode:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# HLS変換状態を管理するメモリストア
# {stored_file_name: {"status": "converting"|"done"|"error", "progress": 0-100}}
conversion_tasks: dict[str, dict] = {}

# 同時HLS変換数の上限（ffmpegはメモリを大量消費するため並列数を制限する）
# BackgroundTasks ではなく専用 executor を使うことで anyio スレッドプールを枯渇させない
_conversion_executor = ThreadPoolExecutor(max_workers=3)

html = Jinja2Templates(directory="src/html")

def _convert_to_hls_tracked(stored_file_name: str, input_path, output_dir):
    """HLS変換を実行し、変換状態・進捗率を更新する"""
    # executor のキューから取り出され実行が始まった時点で converting に遷移
    conversion_tasks[stored_file_name] = {"status": "converting", "progress": 0}

    def on_progress(pct: int) -> None:
        if stored_file_name in conversion_tasks:
            conversion_tasks[stored_file_name]["progress"] = pct

    try:
        convert_to_hls(input_path, output_dir, on_progress=on_progress)
    except Exception:
        conversion_tasks[stored_file_name] = {"status": "error", "progress": 0}
        return
    conversion_tasks.pop(stored_file_name, None)

app.mount(path="/static", app=StaticFiles(directory="src/static"), name="static")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return html.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    res = requests.post(f"{API_URL}/login/verify", json={"username": username, "password": password}, timeout=10)
    if res.status_code == 200:
        token = secrets.token_urlsafe(32)
        active_sessions.add(token)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("session", token, httponly=True, samesite="lax")
        return response
    return html.TemplateResponse("login.html", {"request": request, "error": True})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return html.TemplateResponse("signup.html", {"request": request})


@app.post("/signup")
async def signup_post(request: Request):
    data = await request.json()
    email = data.get("email", "").strip()
    if not email:
        return Response(status_code=400, content='{"error":"email is required"}', media_type="application/json")
    token = secrets.token_urlsafe(32)
    pending_registrations[token] = {
        "email": email,
        "expires": datetime.now() + timedelta(hours=24),
    }
    origin = request.headers.get("origin", str(request.base_url).rstrip("/"))
    confirm_url = f"{origin}/signup/details?token={token}"
    try:
        msg = MIMEText(
            f"以下のリンクから登録を完了してください（24時間有効）\n\n{confirm_url}",
            "plain",
            "utf-8",
        )
        msg["Subject"] = "【PERSONAL WEB】登録確認メール"
        msg["From"] = SMTP_USER
        msg["To"] = email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return Response(content='{"ok":true}', media_type="application/json")
    except Exception as e:
        pending_registrations.pop(token, None)
        print(f"メール送信エラー: {e}")
        return Response(status_code=500, content='{"error":"failed to send email"}', media_type="application/json")


@app.get("/signup/details", response_class=HTMLResponse)
async def signup_details(request: Request, token: str = ""):
    entry = pending_registrations.get(token)
    if not entry or datetime.now() > entry["expires"]:
        pending_registrations.pop(token, None)
        return html.TemplateResponse("signupDetails.html", {"request": request, "invalid": True})
    return html.TemplateResponse("signupDetails.html", {"request": request, "email": entry["email"], "token": token})


@app.post("/signup/complete", response_class=HTMLResponse)
async def signup_complete(request: Request, token: str = Form(...), username: str = Form(...), password: str = Form(...)):
    entry = pending_registrations.get(token)
    if not entry or datetime.now() > entry["expires"]:
        pending_registrations.pop(token, None)
        return html.TemplateResponse("signupDetails.html", {"request": request, "invalid": True})
    if not username or not password:
        return html.TemplateResponse("signupDetails.html", {
            "request": request, "email": entry["email"], "token": token,
            "error": "ユーザー名とパスワードを入力してください",
        })
    res = requests.post(f"{API_URL}/register", json={"username": username, "password": password, "email": entry["email"]}, timeout=10)
    if res.status_code != 200:
        return html.TemplateResponse("signupDetails.html", {
            "request": request, "email": entry["email"], "token": token,
            "error": "登録に失敗しました。ユーザー名が既に使用されています。",
        })
    pending_registrations.pop(token, None)
    return html.TemplateResponse("signupDetails.html", {"request": request, "done": True, "username": username})


@app.post("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    active_sessions.discard(token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


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


@app.get("/editModal.html", response_class=HTMLResponse)
async def edit_modal(request: Request):
    """editモーダルを返す"""
    return html.TemplateResponse("editModal.html", {"request": request})


@app.get("/latte.html", response_class=HTMLResponse)
async def latte_page(request: Request):
    """latteページを返す"""
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "latte",
        "title_name": "PERSONAL - latte",
    }
    return html.TemplateResponse("base.html", context)


@app.get("/shiro.html", response_class=HTMLResponse)
async def shiro_page(request: Request):
    """shiroページを返す"""
    context = {
        "request": request,
        "body_class": "sub_page",
        "body_id": "shiro",
        "title_name": "PERSONAL - shiro",
    }
    return html.TemplateResponse("base.html", context)

@app.get("/howToUse.html", response_class=HTMLResponse)
async def how_to_use_page(request: Request):
    """howToUseページを返す"""
    context = {
        "request": request,
    }
    return html.TemplateResponse("howToUse.html", context)

@app.get("/download/{item_id}")
def download_original(item_id: int):
    """オリジナルファイルをダウンロードする"""
    res = requests.get(f"{API_URL}/getItem/{item_id}", timeout=10)
    item = res.json()["item"]
    file_path = BASE_DIR / item["contents_type"] / "originals" / item["stored_file_name"]
    return FileResponse(
        file_path,
        filename=item["original_file_name"],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(item['original_file_name'])}"},
    )


@app.get("/personal-web/contents/{contents_type}/img/{file_name}")
def get_img_file(contents_type: str, file_name: str):
    print("xxxxxここ")
    """imgファイルを返す"""
    file_path = BASE_DIR / contents_type / "images" / file_name
    return FileResponse(file_path)


@app.get("/personal-web/contents/{contents_type}/video/{file_path:path}")
def get_video_file(contents_type: str, file_path: str):
    """videoファイルを返す（HLS対応）"""
    full_path = BASE_DIR / contents_type / "videos" / file_path
    ext = Path(file_path).suffix.lower()
    if ext == ".m3u8":
        return FileResponse(full_path, media_type="application/vnd.apple.mpegurl")
    if ext == ".ts":
        return FileResponse(full_path, media_type="video/mp2t")
    return FileResponse(full_path)


@app.get("/personal-web/contents/{contents_type}/thumbnail/{file_name}")
def get_thumbnail_file(contents_type: str, file_name: str):
    """thumbnailファイルを返す"""
    file_path = BASE_DIR / contents_type / "thumbnails" / file_name
    return FileResponse(file_path)


@app.post("/upload/{contents_type}")
async def upload_file(contents_type: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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
    thumbnail_file_name = create_random_file_name(20) + ".jpg"

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
        create_thumbnail.create_thumbnail(
            stored_file_path,
            target_dir_path / "thumbnails" / thumbnail_file_name,
        )
    elif original_file_type == "video":
        hls_dir_name = view_file_name_without_ext
        hls_output_dir = target_dir_path / "videos" / hls_dir_name
        view_file_name = f"{hls_dir_name}/index.m3u8"
        # HLS変換は専用 executor でキューイング（anyio スレッドプールを圧迫しない）
        conversion_tasks[stored_file_name] = {"status": "waiting", "progress": 0}
        _conversion_executor.submit(_convert_to_hls_tracked, stored_file_name, stored_file_path, hls_output_dir)
        background_tasks.add_task(
            create_thumbnail.create_thumbnail,
            stored_file_path,
            target_dir_path / "thumbnails" / thumbnail_file_name,
        )
    elif original_file_type == "other":
        view_file_path = target_dir_path / "others" / view_file_name
        with view_file_path.open("wb") as buffer:
            buffer.write(file_bytes)
        create_thumbnail.create_thumbnail(
            stored_file_path,
            target_dir_path / "thumbnails" / thumbnail_file_name,
        )

    stat = stored_file_path.stat()
    name_without_ext = Path(file.filename).stem
    requests.post(
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

@app.get("/conversion-status/{stored_file_name}")
def get_conversion_status(stored_file_name: str):
    """HLS変換の状態と進捗率を返す。完了・エラー時はエントリを削除する"""
    info = conversion_tasks.get(stored_file_name)
    if info is None:
        return {"status": "done", "progress": 100}
    return {"status": info["status"], "progress": info["progress"]}


@app.get("/conversion-status")
def get_conversion_status_batch(names: list[str] = Query(default=[])):
    """複数のHLS変換状態を一括取得する"""
    result = {}
    for name in names:
        info = conversion_tasks.get(name)
        if info is None:
            result[name] = {"status": "done", "progress": 100}
        else:
            result[name] = {"status": info["status"], "progress": info["progress"]}
    return result


@app.get("/delete/{target_id}")
def delete(target_id: str):
    """表示用データだけ削除を実施する"""
    print("削除受信", target_id)
    response = requests.get(f"{API_URL}/getItem/{target_id}", timeout=10).json()
    item = response.get("item")
    if item:
        contents_type = item["contents_type"]
        file_type = item["file_type"]

        # 表示用ファイル削除
        if file_type == "video":
            view_path = BASE_DIR / contents_type / "videos" / item["file_name"]
            hls_dir = view_path.parent
            videos_root = BASE_DIR / contents_type / "videos"
            if hls_dir != videos_root and hls_dir.exists():
                shutil.rmtree(hls_dir)
            elif view_path.exists():
                view_path.unlink()
        else:
            view_path = BASE_DIR / contents_type / "images" / item["file_name"]
            if view_path.exists():
                view_path.unlink()

        # サムネイル削除
        if item.get("thumbnail_file_name"):
            thumb_path = BASE_DIR / contents_type / "thumbnails" / item["thumbnail_file_name"]
            if thumb_path.exists():
                thumb_path.unlink()

    requests.post(f"{API_URL}/delete/{target_id}", timeout=10)
    return {"ok": True}

@app.get("/forceDelete/{target_id}")
def force_delete(target_id: str):
    """関連ファイルを含めて全削除する"""
    response = requests.get(f"{API_URL}/getItem/{target_id}", timeout=10).json()
    item = response.get("item")
    if item:
        contents_type = item["contents_type"]
        file_type = item["file_type"]

        # 表示用ファイル削除
        if file_type == "video":
            view_path = BASE_DIR / contents_type / "videos" / item["file_name"]
            hls_dir = view_path.parent
            videos_root = BASE_DIR / contents_type / "videos"
            if hls_dir != videos_root and hls_dir.exists():
                shutil.rmtree(hls_dir)
            elif view_path.exists():
                view_path.unlink()
        else:
            view_path = BASE_DIR / contents_type / "images" / item["file_name"]
            if view_path.exists():
                view_path.unlink()

        # サムネイル削除
        if item.get("thumbnail_file_name"):
            thumb_path = BASE_DIR / contents_type / "thumbnails" / item["thumbnail_file_name"]
            if thumb_path.exists():
                thumb_path.unlink()

        # オリジナルファイル削除
        if item.get("stored_file_name"):
            orig_path = BASE_DIR / contents_type / "originals" / item["stored_file_name"]
            if orig_path.exists():
                orig_path.unlink()

    requests.post(f"{API_URL}/delete/{target_id}", timeout=10)
    return {"ok": True}
