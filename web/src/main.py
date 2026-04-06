"""
FastAPI を用いた Web フロントエンド用エントリーポイントモジュール。

- HTML テンプレートのレンダリング
- 静的ファイルの配信
"""

import anyio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from datetime import datetime
import json
import os
from urllib.parse import quote
import secrets
import shutil
from pathlib import Path
from email.mime.text import MIMEText
import requests
import smtplib
from dotenv import load_dotenv  # type: ignore
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import create_thumbnail
from src.services import convert_to_hls, save_image_as_webp, create_random_file_name, get_file_type

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
# {token: {"user_id": int, "role": str, "viewable_category_ids": list[str] | None}}
active_sessions: dict[str, dict] = {}

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

# 変換保留中のタスク {stored_file_name: (stored_file_path, hls_output_dir)}
_pending_conversions: dict[str, tuple] = {}

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
        data = res.json()
        raw_vc = data.get("viewable_category_ids")
        print(raw_vc)
        viewable = json.loads(raw_vc) if isinstance(raw_vc, str) else None
        token = secrets.token_urlsafe(32)
        active_sessions[token] = {
            "user_id": data["user_id"],
            "role": data.get("role", "user"),
            "viewable_category_ids": viewable,
        }
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
    active_sessions.pop(token, None)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """トップページを返す（ユーザーの閲覧権限に応じたカテゴリのみ表示）"""
    token = request.cookies.get("session")
    session_user = active_sessions.get(token, {})
    role = session_user.get("role", "user")
    viewable_category_ids = session_user.get("viewable_category_ids")

    api_res = requests.get(f"{API_URL}/categories", timeout=10)
    all_categories = api_res.json().get("categories", []) if api_res.status_code == 200 else []

    if role == "admin":
        categories = all_categories
    elif viewable_category_ids is not None:
        categories = [c for c in all_categories if c["id"] in viewable_category_ids]
    else:
        categories = []

    context = {"request": request, "main_class": "main-content", "categories": categories, "is_admin": role == "admin"}
    return html.TemplateResponse("index.html", context)

@app.get("/confirmModal.html", response_class=HTMLResponse)
async def confirm_modal(request: Request):
    """confirmモーダルを返す"""
    return html.TemplateResponse("confirmModal.html", {"request": request})


@app.get("/editModal.html", response_class=HTMLResponse)
async def edit_modal(request: Request):
    """editモーダルを返す"""
    return html.TemplateResponse("editModal.html", {"request": request})


@app.get("/categoryModal.html", response_class=HTMLResponse)
async def category_modal(request: Request):
    """カテゴリ追加モーダルを返す"""
    return html.TemplateResponse("categoryModal.html", {"request": request})


@app.get("/personal-web/categories/{category_id}/img/{file_name}")
def get_category_img(category_id: str, file_name: str):
    """カテゴリ画像を返す"""
    file_path = BASE_DIR / category_id / "images" / file_name
    return FileResponse(file_path)


@app.post("/categories")
async def create_category(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    image: UploadFile = File(None),
):
    """カテゴリ登録（画像オプション）をAPIに委譲する"""
    token = request.cookies.get("session")
    user_id = active_sessions.get(token, {}).get("user_id")
    # 1. カテゴリ登録（画像なし）→ category_id を取得
    res = requests.post(
        f"{API_URL}/categories",
        json={"name": name, "description": description, "user_id": user_id},
        timeout=10,
    )
    if res.status_code != 200:
        return Response(content=res.text, status_code=res.status_code, media_type="application/json")

    category_id = res.json()["id"]

    # 2. ディレクトリ作成
    for sub in ("images", "originals", "thumbnails", "videos"):
        (BASE_DIR / category_id / sub).mkdir(parents=True, exist_ok=True)

    # 3. 画像があれば category_id/images/ に保存し、API を PATCH で更新
    image_file_name = None
    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        content = await image.read()
        image_file_name = create_random_file_name(20) + ".webp"
        save_image_as_webp(content, ext, BASE_DIR / category_id / "images" / image_file_name, max_px=1000, max_kb=150)
        requests.patch(
            f"{API_URL}/categories/{category_id}",
            json={"image_file_name": image_file_name},
            timeout=10,
        )

    # セッションの viewable_category_ids を更新
    if token and token in active_sessions:
        ids = active_sessions[token].get("viewable_category_ids") or []
        active_sessions[token]["viewable_category_ids"] = ids + [category_id]

    result = {"ok": True, "id": category_id}
    if image_file_name:
        result["image_file_name"] = image_file_name
    return Response(content=json.dumps(result), status_code=200, media_type="application/json")


@app.delete("/categories/{category_id}")
def delete_category(category_id: str):
    """カテゴリを削除する"""
    res = requests.delete(f"{API_URL}/categories/{category_id}", timeout=10)
    return Response(content=res.text, status_code=res.status_code, media_type="application/json")


@app.get("/howToUse.html", response_class=HTMLResponse)
async def how_to_use_page(request: Request):
    """howToUseページを返す"""
    context = {
        "request": request,
    }
    return html.TemplateResponse("howToUse.html", context)


@app.get("/{category_id}.html", response_class=HTMLResponse)
async def category_page(request: Request, category_id: str):
    """カテゴリページを動的に返す（全固定ルートより後に定義）"""
    category_name = None
    category_image = None
    try:
        res = requests.get(f"{API_URL}/categories/{category_id}", timeout=10)
        if res.status_code == 200:
            category = res.json().get("category")
            if category:
                category_name = category.get("name")
                category_image = category.get("image_file_name")
    except Exception:
        pass

    context = {
        "request": request,
        "body_class": "sub_page",
        "category_name": category_name,
        "title_name": f"PERSONAL - {category_name}",
        "category_image": category_image,
        "category_id": category_id,
    }
    return html.TemplateResponse("base.html", context)

@app.get("/download/{content_id}")
def download_original(content_id: str):
    """オリジナルファイルをダウンロードする"""
    res = requests.get(f"{API_URL}/getContent/{content_id}", timeout=10)
    content = res.json()["content"]
    file_path = BASE_DIR / content["category_id"] / "originals" / content["stored_file_name"]
    return FileResponse(
        file_path,
        filename=content["original_file_name"],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(content['original_file_name'])}"},
    )


@app.get("/personal-web/contents/{category_id}/img/{file_name}")
def get_img_file(category_id: str, file_name: str):
    """imgファイルを返す"""
    file_path = BASE_DIR / category_id / "images" / file_name
    return FileResponse(file_path)


@app.get("/personal-web/contents/{category_id}/video/{file_path:path}")
def get_video_file(category_id: str, file_path: str):
    """videoファイルを返す（HLS対応）"""
    full_path = BASE_DIR / category_id / "videos" / file_path
    ext = Path(file_path).suffix.lower()
    if ext == ".m3u8":
        return FileResponse(full_path, media_type="application/vnd.apple.mpegurl")
    if ext == ".ts":
        return FileResponse(full_path, media_type="video/mp2t")
    return FileResponse(full_path)


@app.get("/personal-web/contents/{category_id}/thumbnail/{file_name}")
def get_thumbnail_file(category_id: str, file_name: str):
    """thumbnailファイルを返す"""
    file_path = BASE_DIR / category_id / "thumbnails" / file_name
    return FileResponse(file_path)


@app.post("/upload/{category_id}")
async def upload_file(category_id: str, file: UploadFile = File(...), defer_conversion: bool = Form(False)):
    """ファイルのアップロードを行う"""
    if not (BASE_DIR / category_id).exists():
        raise HTTPException(status_code=500, detail="category directory not found")
    target_dir_path = BASE_DIR / category_id
    original_ext = Path(file.filename).suffix.lower()
    stored_file_name = create_random_file_name(20) + original_ext
    stored_file_path = target_dir_path / "originals" / stored_file_name

    file_bytes = await file.read()
    with stored_file_path.open("wb") as buffer:
        buffer.write(file_bytes)

    view_file_name_without_ext = create_random_file_name(20)
    view_file_name = view_file_name_without_ext + original_ext.lower()
    original_file_type = get_file_type(stored_file_path)
    thumbnail_file_name = create_random_file_name(20) + ".webp"

    if original_file_type == "image":
        view_file_name = f"{view_file_name_without_ext}.webp"
        save_image_as_webp(file_bytes, original_ext, target_dir_path / "images" / view_file_name, lossless=True)
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
        if defer_conversion:
            _pending_conversions[stored_file_name] = (stored_file_path, hls_output_dir)
        else:
            _conversion_executor.submit(_convert_to_hls_tracked, stored_file_name, stored_file_path, hls_output_dir)
        await anyio.to_thread.run_sync(
            lambda: create_thumbnail.create_thumbnail(
                stored_file_path,
                target_dir_path / "thumbnails" / thumbnail_file_name,
            )
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
    upload_res = requests.post(
        f"{API_URL}/upload",
        json={
            "file_name": view_file_name,
            "thumbnail_file_name": thumbnail_file_name,
            "original_file_name": file.filename,
            "stored_file_name": stored_file_name,
            "duration_ms": None,
            "category_id": category_id,
            "title": name_without_ext,
            "file_type": original_file_type,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        },
        timeout=10,
    )
    content_id = upload_res.json().get("id")
    content_res = requests.get(f"{API_URL}/getContent/{content_id}", timeout=10)
    return {"content": content_res.json().get("content")}

@app.post("/start-conversion")
async def start_conversion(data: dict = Body(...)):
    """保留中のHLS変換を一括開始する"""
    for name in data.get("stored_file_names", []):
        params = _pending_conversions.pop(name, None)
        if params:
            stored_file_path, hls_output_dir = params
            _conversion_executor.submit(_convert_to_hls_tracked, name, stored_file_path, hls_output_dir)
    return {"ok": True}


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
    response = requests.get(f"{API_URL}/getContent/{target_id}", timeout=10).json()
    content = response.get("content")
    if content:
        cid = content["category_id"]
        file_type = content["file_type"]

        # 表示用ファイル削除
        if file_type == "video":
            view_path = BASE_DIR / cid / "videos" / content["file_name"]
            hls_dir = view_path.parent
            videos_root = BASE_DIR / cid / "videos"
            if hls_dir != videos_root and hls_dir.exists():
                shutil.rmtree(hls_dir)
            elif view_path.exists():
                view_path.unlink()
        else:
            view_path = BASE_DIR / cid / "images" / content["file_name"]
            if view_path.exists():
                view_path.unlink()

        # サムネイル削除
        if content.get("thumbnail_file_name"):
            thumb_path = BASE_DIR / cid / "thumbnails" / content["thumbnail_file_name"]
            if thumb_path.exists():
                thumb_path.unlink()

    requests.post(f"{API_URL}/delete/{target_id}", timeout=10)
    return {"ok": True}

@app.get("/forceDelete/{target_id}")
def force_delete(target_id: str):
    """関連ファイルを含めて全削除する"""
    response = requests.get(f"{API_URL}/getContent/{target_id}", timeout=10).json()
    content = response.get("content")
    if content:
        cid = content["category_id"]
        file_type = content["file_type"]

        # 表示用ファイル削除
        if file_type == "video":
            view_path = BASE_DIR / cid / "videos" / content["file_name"]
            hls_dir = view_path.parent
            videos_root = BASE_DIR / cid / "videos"
            if hls_dir != videos_root and hls_dir.exists():
                shutil.rmtree(hls_dir)
            elif view_path.exists():
                view_path.unlink()
        else:
            view_path = BASE_DIR / cid / "images" / content["file_name"]
            if view_path.exists():
                view_path.unlink()

        # サムネイル削除
        if content.get("thumbnail_file_name"):
            thumb_path = BASE_DIR / cid / "thumbnails" / content["thumbnail_file_name"]
            if thumb_path.exists():
                thumb_path.unlink()

        # オリジナルファイル削除
        if content.get("stored_file_name"):
            orig_path = BASE_DIR / cid / "originals" / content["stored_file_name"]
            if orig_path.exists():
                orig_path.unlink()

    requests.post(f"{API_URL}/delete/{target_id}", timeout=10)
    return {"ok": True}
