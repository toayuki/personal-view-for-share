"""
FastAPI を用いた Web フロントエンド用エントリーポイントモジュール。

- HTML テンプレートのレンダリング
- 静的ファイルの配信
"""

import asyncio
import json
import os
import secrets
import shutil
import smtplib
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, TypedDict, cast
from urllib.parse import quote

import anyio
import jwt
import requests
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.services import (
    convert_to_bg_mp4,
    convert_to_hls,
    create_random_file_name,
    get_file_type,
    save_image_as_webp,
)

from src import audit_logger, create_thumbnail

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
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 180
EXPO_URL = os.getenv("EXPO_URL", "http://localhost:8081")


class _JWTPayload(TypedDict, total=False):
    user_id: int
    role: str
    exp: datetime


class _RegistrationEntry(TypedDict):
    email: str
    expires: datetime
    invite_token: str | None


class _InviteEntry(TypedDict):
    category_id: str
    expires: datetime


def _create_jwt(user_id: int, role: str) -> str:
    """JWT トークンを生成して返す。"""
    payload: _JWTPayload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)  # pyright: ignore[reportArgumentType, reportUnknownMemberType] -- PyJWT stubs: payload typed as dict[str, Any]


def _decode_token(token: str) -> _JWTPayload:
    """JWT トークンをデコードしてペイロードを返す。無効な場合は空 dict を返す。"""
    try:
        return cast(_JWTPayload, jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM]))  # pyright: ignore[reportUnknownMemberType] -- PyJWT stubs include Unknown in key param
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return {}
    except Exception as e:
        print(f"Unexpected error in _decode_token: {e}")
        return {}


def _decode_session(request: Request) -> _JWTPayload:
    """リクエストの session Cookie を JWT デコードして返す。"""
    token = request.cookies.get("session")
    return _decode_token(token) if token else {}


# {user_id: (category_ids, expires_at)}
_viewable_cache: dict[str, tuple[list[str], datetime]] = {}
_CACHE_TTL = timedelta(minutes=30)

# (categories, expires_at)
_all_categories_cache: tuple[list[dict[str, Any]], datetime] | None = None
_ALL_CATEGORIES_TTL = timedelta(minutes=30)


def _get_all_categories() -> list[dict[str, Any]]:
    """全カテゴリをキャッシュ付きで取得する。"""
    global _all_categories_cache
    if _all_categories_cache and datetime.now(tz=timezone.utc) < _all_categories_cache[1]:
        return _all_categories_cache[0]
    try:
        res = requests.get(f"{API_URL}/categories", timeout=10)
        if res.status_code == 200:
            categories: list[dict[str, Any]] = res.json().get("categories", [])
            expires = datetime.now(tz=timezone.utc) + _ALL_CATEGORIES_TTL
            _all_categories_cache = (categories, expires)
            return categories
    except Exception:
        pass
    return []


def _invalidate_all_categories_cache() -> None:
    """全カテゴリキャッシュを破棄する。"""
    global _all_categories_cache
    _all_categories_cache = None


def _get_viewable_category_ids(user_id: object) -> list[str] | None:
    """ユーザーが閲覧可能なカテゴリ ID リストをキャッシュ付きで返す。取得失敗時は None。"""
    key = str(user_id)
    cached = _viewable_cache.get(key)
    if cached and datetime.now(tz=timezone.utc) < cached[1]:
        return cached[0]
    try:
        res = requests.get(f"{API_URL}/users/{user_id}/viewable-categories", timeout=10)
        if res.status_code == 200:
            ids: list[str] = res.json().get("category_ids", [])
            _viewable_cache[key] = (ids, datetime.now(tz=timezone.utc) + _CACHE_TTL)
            return ids
    except Exception:
        pass
    return None


def _invalidate_viewable_cache(user_id: object) -> None:
    """指定ユーザーの閲覧可能カテゴリキャッシュを破棄する。"""
    _viewable_cache.pop(str(user_id), None)


# 一時登録トークン {token: {"email": str, "expires": datetime}}
pending_registrations: dict[str, _RegistrationEntry] = {}

# 招待トークン {token: {"category_id": str, "expires": datetime}}
invite_tokens: dict[str, _InviteEntry] = {}


async def _cleanup_expired_tokens() -> None:
    while True:
        await asyncio.sleep(3600)
        now = datetime.now(tz=timezone.utc)
        for token in [t for t, e in pending_registrations.items() if now > e["expires"]]:
            pending_registrations.pop(token, None)
        for token in [t for t, e in invite_tokens.items() if now > e["expires"]]:
            invite_tokens.pop(token, None)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    task = asyncio.create_task(_cleanup_expired_tokens())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[u for u in [EXPO_URL] if u],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_PUBLIC_PATHS = {
    "/login",
    "/signup",
    "/signup/details",
    "/signup/complete",
    "/invite",
    "/invite/accept",
    "/forgot-password",
    "/reset-password",
    "/favicon.ico",
}


def _get_user_categories(user_id: object, role: str) -> list[dict[str, Any]]:
    """ユーザー権限に応じたカテゴリ一覧を返す"""
    all_categories = _get_all_categories()
    if role == "admin":
        return all_categories
    viewable_category_ids = _get_viewable_category_ids(user_id)
    if viewable_category_ids is not None:
        return [c for c in all_categories if c["id"] in viewable_category_ids]
    return []


def _check_category_access(request: Request, category_id: str) -> None:
    """カテゴリへのアクセス権限を検証する。権限がなければ 403 を返す。"""
    session = _decode_session(request)
    role = session.get("role", "user")
    if role == "admin":
        return
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    viewable = _get_viewable_category_ids(user_id)
    if viewable is None or category_id not in viewable:
        raise HTTPException(status_code=403, detail="Access denied")


@app.middleware("http")  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator] -- Starlette stubs return Unknown; unavoidable
async def auth_middleware(request: Request, call_next: Any) -> Any:
    """未認証リクエストを /login にリダイレクトする"""
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/static") or path.startswith("/invite/"):
        response = await call_next(request)
    else:
        token = request.cookies.get("session")
        if token and _decode_token(token).get("user_id"):
            response = await call_next(request)
        else:
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                return RedirectResponse(url="/login", status_code=302)
            return Response(status_code=401)
    if IS_DEBUG_MODE:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.middleware("http")(audit_logger.make_audit_middleware(_decode_token, API_URL))  # pyright: ignore[reportUnknownMemberType] -- Starlette stubs return Unknown; unavoidable


# HLS変換状態を管理するメモリストア
# {stored_file_name: {"status": "converting"|"done"|"error", "progress": 0-100}}
conversion_tasks: dict[str, dict[str, Any]] = {}

# 同時HLS変換数の上限（ffmpegはメモリを大量消費するため並列数を制限する）
# BackgroundTasks ではなく専用 executor を使うことで anyio スレッドプールを枯渇させない
_conversion_executor = ThreadPoolExecutor(max_workers=3)

# 変換保留中のタスク {stored_file_name: (stored_file_path, hls_output_dir)}
_pending_conversions: dict[str, tuple[Path, Path]] = {}

html: Any = Jinja2Templates(directory="src/html")
GLOBAL_API_URL = os.getenv("GLOBAL_API_URL", "")
html.env.globals["api_url"] = API_URL
html.env.globals["global_api_url"] = GLOBAL_API_URL


def _convert_to_hls_tracked(stored_file_name: str, input_path: Path, output_dir: Path) -> None:
    """HLS変換を実行し、変換状態・進捗率を更新する"""
    # executor のキューから取り出され実行が始まった時点で converting に遷移
    conversion_tasks[stored_file_name] = {"status": "converting", "progress": 0}

    def on_progress(pct: int) -> None:
        """変換進捗率を conversion_tasks に記録する。"""
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
async def login_page(request: Request, invite: str = ""):
    """ログインページを返す。ログイン済みの場合はトップページへリダイレクト。"""
    token = request.cookies.get("session")
    if token and _decode_token(token).get("user_id"):
        if invite and invite in invite_tokens:
            return RedirectResponse(url=f"/invite?token={invite}", status_code=302)
        return RedirectResponse(url="/", status_code=302)
    return html.TemplateResponse("login.html", {"request": request, "invite": invite})


@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    invite: str = Form(""),
):
    """ログインフォームを処理し、認証成功時に session Cookie をセットする。"""
    print("Login attempt:", username)
    ip = audit_logger.get_client_ip(request)
    common: dict[str, str] = {
        "ip": ip,
        "username": username,
        "user_agent": request.headers.get("user-agent", "-"),
        "referer": request.headers.get("referer", "-"),
        "accept_language": request.headers.get("accept-language", "-"),
    }
    if not username.strip() or not password.strip():
        return html.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error_msg": "ユーザー名とパスワードを入力してください",
                "invite": invite,
            },
        )
    res = requests.post(
        f"{API_URL}/login/verify", json={"username": username, "password": password}, timeout=10
    )
    if res.status_code == 200:
        data = res.json()
        token = _create_jwt(data["user_id"], data.get("role", "user"))
        audit_logger.log_login_access(event="attempt_success", **common)
        redirect_url = f"/invite?token={invite}" if invite and invite in invite_tokens else "/"
        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie("session", token, httponly=True, samesite="lax", max_age=86400 * 180)
        return response
    audit_logger.log_login_access(event="attempt_failed", **common)
    return html.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error_msg": "ユーザー名またはパスワードが正しくありません",
            "invite": invite,
        },
    )


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """パスワード再設定リクエストページを返す。"""
    return html.TemplateResponse("forgot_password.html", {"request": request})


@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_post(request: Request, email: str = Form("")):
    """メールアドレスを受け取り、パスワード再設定リンクをメール送信する。"""
    if not email.strip():
        return html.TemplateResponse(
            "forgot_password.html",
            {"request": request, "error_msg": "メールアドレスを入力してください"},
        )
    res = requests.post(
        f"{API_URL}/password-reset/request", json={"email": email.strip()}, timeout=10
    )
    if res.status_code == 404:
        # メール列挙攻撃を防ぐため、未登録でも送信済みとして扱う
        return html.TemplateResponse("forgot_password.html", {"request": request, "sent": True})
    if res.status_code != 200:
        return html.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "error_msg": "エラーが発生しました。しばらくしてから再試行してください",
            },
        )
    token = res.json().get("token")
    origin = request.headers.get("origin", str(request.base_url).rstrip("/"))
    reset_url = f"{origin}/reset-password?token={token}"
    try:
        msg = MIMEText(
            f"以下のリンクからパスワードを変更してください（1時間有効）\n\n{reset_url}",
            "plain",
            "utf-8",
        )
        msg["Subject"] = "【PERSONAL WEB】パスワード再設定"
        msg["From"] = SMTP_USER
        msg["To"] = email.strip()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"メール送信エラー: {e}")
        return html.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "error_msg": "メール送信に失敗しました。しばらくしてから再試行してください",
            },
        )
    return html.TemplateResponse("forgot_password.html", {"request": request, "sent": True})


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    """パスワード再設定フォームページを返す。"""
    if not token:
        return html.TemplateResponse("reset_password.html", {"request": request, "invalid": True})
    return html.TemplateResponse("reset_password.html", {"request": request, "token": token})


@app.post("/reset-password", response_class=HTMLResponse)
async def reset_password_post(
    request: Request,
    token: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
):
    """パスワード再設定フォームを処理し、API に新しいパスワードを送信する。"""
    if not token:
        return html.TemplateResponse("reset_password.html", {"request": request, "invalid": True})
    if not password.strip():
        return html.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "error_msg": "パスワードを入力してください"},
        )
    if password != password_confirm:
        return html.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "error_msg": "パスワードが一致しません"},
        )
    res = requests.post(
        f"{API_URL}/password-reset/complete",
        json={"token": token, "password": password},
        timeout=10,
    )
    if res.status_code == 400:
        detail = res.json().get("error", "")
        expired_msg = "リンクの有効期限が切れています。再度手続きをしてください"
        msg = expired_msg if "expired" in detail else "無効なリンクです"
        return html.TemplateResponse(
            "reset_password.html",
            {"request": request, "invalid": True, "error_msg": msg},
        )
    if res.status_code != 204:
        return html.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "error_msg": "エラーが発生しました。しばらくしてから再試行してください",
            },
        )
    return html.TemplateResponse("reset_password.html", {"request": request, "done": True})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, invite: str = ""):
    """ユーザー登録（メール入力）ページを返す。"""
    return html.TemplateResponse("signup.html", {"request": request, "invite": invite})


@app.post("/signup")
async def signup_post(request: Request):
    """メールアドレスを受け取り、確認メールを送信して一時登録トークンを保存する。"""
    data = await request.json()
    email = data.get("email", "").strip()
    ip = audit_logger.get_client_ip(request)
    common: dict[str, str] = {
        "ip": ip,
        "email": email,
        "user_agent": request.headers.get("user-agent", "-"),
        "referer": request.headers.get("referer", "-"),
        "accept_language": request.headers.get("accept-language", "-"),
    }
    invite = data.get("invite", "").strip()
    if not email:
        return Response(
            status_code=400, content='{"error":"email is required"}', media_type="application/json"
        )
    token = secrets.token_urlsafe(32)
    pending_registrations[token] = {
        "email": email,
        "expires": datetime.now(tz=timezone.utc) + timedelta(hours=24),
        "invite_token": invite if invite and invite in invite_tokens else None,
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
        audit_logger.log_login_access(event="signup_request", **common)
        return Response(content='{"ok":true}', media_type="application/json")
    except Exception as e:
        pending_registrations.pop(token, None)
        print(f"メール送信エラー: {e}")
        audit_logger.log_login_access(event="signup_request_failed", **common)
        return Response(
            status_code=500,
            content='{"error":"failed to send email"}',
            media_type="application/json",
        )


@app.get("/signup/details", response_class=HTMLResponse)
async def signup_details(request: Request, token: str = ""):
    """メール確認後のユーザー情報入力ページを返す。トークン無効時はエラー表示。"""
    entry = pending_registrations.get(token)
    if not entry or datetime.now(tz=timezone.utc) > entry["expires"]:
        pending_registrations.pop(token, None)
        return html.TemplateResponse("signupDetails.html", {"request": request, "invalid": True})
    return html.TemplateResponse(
        "signupDetails.html", {"request": request, "email": entry["email"], "token": token}
    )


@app.post("/signup/complete", response_class=HTMLResponse)
async def signup_complete(
    request: Request,
    token: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
):
    """ユーザー情報を受け取り、API にユーザー登録を完了させる。"""
    ip = audit_logger.get_client_ip(request)
    common: dict[str, str] = {
        "ip": ip,
        "username": username,
        "user_agent": request.headers.get("user-agent", "-"),
        "referer": request.headers.get("referer", "-"),
        "accept_language": request.headers.get("accept-language", "-"),
    }
    entry = pending_registrations.get(token)
    if not entry or datetime.now(tz=timezone.utc) > entry["expires"]:
        pending_registrations.pop(token, None)
        audit_logger.log_login_access(event="signup_invalid_token", **common)
        return html.TemplateResponse("signupDetails.html", {"request": request, "invalid": True})
    if not username or not password:
        return html.TemplateResponse(
            "signupDetails.html",
            {
                "request": request,
                "email": entry["email"],
                "token": token,
                "error": "ユーザー名とパスワードを入力してください",
            },
        )
    res = requests.post(
        f"{API_URL}/register",
        json={"username": username, "password": password, "email": entry["email"]},
        timeout=10,
    )
    if res.status_code != 200:
        audit_logger.log_login_access(event="signup_failed", email=entry["email"], **common)
        return html.TemplateResponse(
            "signupDetails.html",
            {
                "request": request,
                "email": entry["email"],
                "token": token,
                "error": "登録に失敗しました。ユーザー名が既に使用されています。",
            },
        )
    user_id = res.json().get("user_id")
    invite_token = entry.get("invite_token")
    if user_id and invite_token:
        invite_entry = invite_tokens.get(invite_token)
        if invite_entry and datetime.now(tz=timezone.utc) <= invite_entry["expires"]:
            requests.post(
                f"{API_URL}/users/{user_id}/viewable-categories",
                json={"category_id": invite_entry["category_id"]},
                timeout=10,
            )
            _invalidate_viewable_cache(user_id)
        invite_tokens.pop(invite_token, None)
    pending_registrations.pop(token, None)
    audit_logger.log_login_access(event="signup_complete", email=entry["email"], **common)
    return html.TemplateResponse(
        "signupDetails.html", {"request": request, "done": True, "username": username}
    )


@app.post("/invite")
async def create_invite(request: Request):
    """招待URLを発行する"""
    session = _decode_session(request)
    if not session.get("user_id"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    category_id = data.get("category_id")
    if not category_id:
        raise HTTPException(status_code=400, detail="category_id required")
    invite_token = secrets.token_urlsafe(32)
    invite_tokens[invite_token] = {
        "category_id": category_id,
        "expires": datetime.now(tz=timezone.utc) + timedelta(hours=24),
    }
    origin = request.headers.get("origin", str(request.base_url).rstrip("/"))
    return {"url": f"{origin}/invite?token={invite_token}"}


@app.get("/invite/{token}/preview-image")
def invite_preview_image(token: str):
    """招待トークンでカテゴリ画像を公開する（未ログインでもアクセス可）"""
    entry = invite_tokens.get(token)
    if not entry or datetime.now(tz=timezone.utc) > entry["expires"]:
        raise HTTPException(status_code=404)
    category_id = entry["category_id"]
    try:
        res = requests.get(f"{API_URL}/categories/{category_id}", timeout=10)
        if res.status_code == 200:
            cat = res.json().get("category")
            if cat and cat.get("image_file_name"):
                file_path = BASE_DIR / category_id / "bg" / cat["image_file_name"]
                if file_path.exists():
                    return FileResponse(file_path)
    except Exception:
        pass
    raise HTTPException(status_code=404)


@app.get("/invite", response_class=HTMLResponse)
async def signup_invite_page(request: Request, token: str = ""):
    """招待リンクの確認ページ"""
    entry = invite_tokens.get(token)
    if not entry or datetime.now(tz=timezone.utc) > entry["expires"]:
        invite_tokens.pop(token, None)
        return html.TemplateResponse("inviteConfirm.html", {"request": request, "invalid": True})
    category_id = entry["category_id"]
    category_name = None
    has_image = False
    try:
        res = requests.get(f"{API_URL}/categories/{category_id}", timeout=10)
        if res.status_code == 200:
            cat = res.json().get("category")
            if cat:
                category_name = cat.get("name")
                has_image = bool(cat.get("image_file_name"))
    except Exception:
        pass
    is_logged_in = bool(_decode_session(request).get("user_id"))
    return html.TemplateResponse(
        "inviteConfirm.html",
        {
            "request": request,
            "token": token,
            "category_name": category_name,
            "image_url": f"/invite/{token}/preview-image" if has_image else None,
            "is_logged_in": is_logged_in,
        },
    )


@app.post("/invite/accept")
async def signup_invite_accept(request: Request, token: str = Form(...)):
    """ログイン済みユーザーが招待を受け入れてカテゴリ閲覧権限を付与する"""
    user_id = _decode_session(request).get("user_id")
    if not user_id:
        return RedirectResponse(url=f"/invite?token={token}", status_code=302)
    entry = invite_tokens.get(token)
    if not entry or datetime.now(tz=timezone.utc) > entry["expires"]:
        invite_tokens.pop(token, None)
        return RedirectResponse(url="/", status_code=302)
    category_id = entry["category_id"]
    requests.post(
        f"{API_URL}/users/{user_id}/viewable-categories",
        json={"category_id": category_id},
        timeout=10,
    )
    _invalidate_viewable_cache(user_id)
    invite_tokens.pop(token, None)
    return RedirectResponse(url="/", status_code=302)


@app.post("/logout")
async def logout():
    """session Cookie を削除してログアウトし、ログインページへリダイレクトする。"""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


@app.get("/favicon.ico")
def favicon():
    """favicon リクエストに 204 No Content を返す。"""
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """トップページを返す（ユーザーの閲覧権限に応じたカテゴリのみ表示）"""
    session = _decode_session(request)
    role = session.get("role", "user")
    user_id = session.get("user_id")
    categories = _get_user_categories(user_id, role)
    context: dict[str, Any] = {
        "request": request,
        "categories": categories,
        "role": role,
        "user_id": str(user_id or ""),
    }
    return html.TemplateResponse("index.html", context)


@app.api_route("/personal-web/categories/{category_id}/bg/{file_name}", methods=["GET", "HEAD"])
def get_category_bg(category_id: str, file_name: str):
    """カテゴリ背景画像・動画を返す"""
    file_path = BASE_DIR / category_id / "bg" / file_name
    return FileResponse(file_path)


@app.post("/categories")
async def create_category(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    image: UploadFile = File(None),
    video: UploadFile = File(None),
):
    """カテゴリ登録（画像・動画オプション）をAPIに委譲する"""
    user_id = _decode_session(request).get("user_id")
    # 1. カテゴリ登録（画像なし）→ category_id を取得
    res = requests.post(
        f"{API_URL}/categories",
        json={"name": name, "description": description, "user_id": user_id},
        timeout=10,
    )
    if res.status_code != 200:
        return Response(
            content=res.text, status_code=res.status_code, media_type="application/json"
        )

    category_id = res.json()["id"]

    # 2. ディレクトリ作成
    for sub in ("images", "originals", "thumbnails", "videos", "bg"):
        (BASE_DIR / category_id / sub).mkdir(parents=True, exist_ok=True)

    # 3. 画像があれば保存
    image_file_name = None
    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        content = await image.read()
        assert isinstance(content, bytes)
        image_file_name = create_random_file_name(20) + ".webp"
        save_image_as_webp(
            content, ext, BASE_DIR / category_id / "bg" / image_file_name, max_px=1000, max_kb=150
        )
        requests.patch(
            f"{API_URL}/categories/{category_id}",
            json={"image_file_name": image_file_name},
            timeout=10,
        )

    # 4. 背景動画があれば保存
    video_file_name = None
    if video and video.filename:
        ext = Path(video.filename).suffix.lower()
        video_file_name = create_random_file_name(20) + ".mp4"
        video_content = await video.read()
        assert isinstance(video_content, bytes)
        tmp_path = BASE_DIR / category_id / "bg" / (create_random_file_name(10) + ext)
        tmp_path.write_bytes(video_content)
        out_path = BASE_DIR / category_id / "bg" / video_file_name

        def _convert_bg(tmp: Path = tmp_path, out: Path = out_path) -> None:
            convert_to_bg_mp4(tmp, out, 60)
            tmp.unlink()

        _conversion_executor.submit(_convert_bg)
        requests.patch(
            f"{API_URL}/categories/{category_id}",
            json={"video_file_name": video_file_name},
            timeout=10,
        )

    _invalidate_all_categories_cache()
    result: dict[str, str] = {"id": category_id}
    if image_file_name:
        result["image_file_name"] = image_file_name
    if video_file_name:
        result["video_file_name"] = video_file_name
    return Response(content=json.dumps(result), status_code=200, media_type="application/json")


@app.patch("/categories/{category_id}")
async def update_category(
    request: Request,
    category_id: str,
    name: str = Form(...),
    description: str = Form(""),
    image: UploadFile = File(None),
    video: UploadFile = File(None),
):
    """カテゴリ更新（admin または作成者のみ）"""
    session = _decode_session(request)
    role = session.get("role", "user")
    user_id = session.get("user_id")

    cat_res = requests.get(f"{API_URL}/categories/{category_id}", timeout=10)
    if cat_res.status_code != 200:
        return Response(
            content=cat_res.text, status_code=cat_res.status_code, media_type="application/json"
        )
    category = cat_res.json().get("category")
    if not category:
        return Response(
            content='{"error":"not found"}', status_code=404, media_type="application/json"
        )
    if role != "admin" and str(user_id) != str(category.get("created_by")):
        return Response(
            content='{"error":"forbidden"}', status_code=403, media_type="application/json"
        )

    res = requests.patch(
        f"{API_URL}/categories/{category_id}",
        json={"name": name, "description": description},
        timeout=10,
    )
    if res.status_code != 204:
        return Response(
            content=res.text, status_code=res.status_code, media_type="application/json"
        )

    result: dict[str, str] = {}
    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        content = await image.read()
        assert isinstance(content, bytes)
        image_file_name = create_random_file_name(20) + ".webp"
        (BASE_DIR / category_id / "bg").mkdir(parents=True, exist_ok=True)
        save_image_as_webp(
            content, ext, BASE_DIR / category_id / "bg" / image_file_name, max_px=1000, max_kb=150
        )
        requests.patch(
            f"{API_URL}/categories/{category_id}",
            json={"image_file_name": image_file_name},
            timeout=10,
        )
        result["image_file_name"] = image_file_name

    if video and video.filename:
        ext = Path(video.filename).suffix.lower()
        video_file_name = create_random_file_name(20) + ".mp4"
        (BASE_DIR / category_id / "bg").mkdir(parents=True, exist_ok=True)
        video_content = await video.read()
        assert isinstance(video_content, bytes)
        tmp_path = BASE_DIR / category_id / "bg" / (create_random_file_name(10) + ext)
        tmp_path.write_bytes(video_content)
        out_path = BASE_DIR / category_id / "bg" / video_file_name

        def _convert_bg(tmp: Path = tmp_path, out: Path = out_path) -> None:
            convert_to_bg_mp4(tmp, out, 60)
            tmp.unlink()

        _conversion_executor.submit(_convert_bg)
        requests.patch(
            f"{API_URL}/categories/{category_id}",
            json={"video_file_name": video_file_name},
            timeout=10,
        )
        result["video_file_name"] = video_file_name

    _invalidate_all_categories_cache()
    return Response(content=json.dumps(result), status_code=200, media_type="application/json")


@app.delete("/categories/{category_id}")
def delete_category(request: Request, category_id: str):
    """カテゴリを削除する（admin または作成者のみ）"""
    session = _decode_session(request)
    role = session.get("role", "user")
    user_id = session.get("user_id")

    cat_res = requests.get(f"{API_URL}/categories/{category_id}", timeout=10)
    if cat_res.status_code != 200:
        return Response(
            content=cat_res.text, status_code=cat_res.status_code, media_type="application/json"
        )
    category = cat_res.json().get("category")
    if not category:
        return Response(
            content='{"error":"not found"}', status_code=404, media_type="application/json"
        )

    if role != "admin" and str(user_id) != str(category.get("created_by")):
        return Response(
            content='{"error":"forbidden"}', status_code=403, media_type="application/json"
        )

    res = requests.delete(f"{API_URL}/categories/{category_id}", timeout=10)
    if res.status_code == 204:
        _invalidate_all_categories_cache()
    return Response(content=res.text, status_code=res.status_code, media_type="application/json")


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """ログ閲覧ページ（admin 限定）"""
    if _decode_session(request).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    log_files = (
        sorted(
            [f.name for f in audit_logger.LOG_DIR.iterdir() if f.suffix == ".log"],
            key=lambda x: (x != "login_access.log", x),
        )
        if audit_logger.LOG_DIR.exists()
        else []
    )
    return html.TemplateResponse("logs.html", {"request": request, "log_files": log_files})


@app.get("/logs/ip-list")
async def logs_ip_list(request: Request) -> dict[str, Any]:
    """login_access.log からIPアドレス統計を返す（admin 限定）"""
    if _decode_session(request).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    log_path = audit_logger.LOG_DIR / "login_access.log"
    if not log_path.exists():
        return {"ips": []}

    ip_stats: dict[str, dict[str, Any]] = {}
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parts: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = parts.get("timestamp", "")
            ip = parts.get("ip")
            if not ip:
                continue
            event = parts.get("event", "unknown")
            lang = parts.get("lang", "-")
            if ip not in ip_stats:
                ip_stats[ip] = {"count": 0, "events": {}, "first": ts, "last": ts, "lang": lang}
            ip_stats[ip]["count"] += 1
            ip_stats[ip]["events"][event] = ip_stats[ip]["events"].get(event, 0) + 1
            if ts > ip_stats[ip]["last"]:
                ip_stats[ip]["last"] = ts
                ip_stats[ip]["lang"] = lang

    result: list[dict[str, Any]] = sorted(
        [{"ip": ip, **stats} for ip, stats in ip_stats.items()],
        key=lambda x: x["last"],
        reverse=True,
    )
    return {"ips": result}


@app.get("/logs/stream")
async def logs_stream(request: Request, file: str = "login_access.log"):
    """SSE でログファイルをリアルタイム配信する（admin 限定）"""
    if _decode_session(request).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    # パストラバーサル対策：ファイル名のみ使用し LOG_DIR 内に限定
    log_path = audit_logger.LOG_DIR / Path(file).name
    if not log_path.exists() or log_path.parent != audit_logger.LOG_DIR:
        raise HTTPException(status_code=404, detail="Log file not found")

    async def generate():
        try:
            with log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip()
                    if line:
                        yield f"data: {line}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    line = f.readline()
                    if line:
                        yield f"data: {line.rstrip()}\n\n"
                    else:
                        await anyio.sleep(1)
        except Exception:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/howToUse.html", response_class=HTMLResponse)
async def how_to_use_page(request: Request):
    """howToUseページを返す"""
    session = _decode_session(request)
    role = session.get("role", "user")
    context: dict[str, Any] = {
        "request": request,
        "role": role,
        "categories": _get_user_categories(session.get("user_id"), role),
    }
    return html.TemplateResponse("howToUse.html", context)


@app.get("/{category_id}.html", response_class=HTMLResponse)
async def category_page(request: Request, category_id: str):
    """カテゴリページを動的に返す（全固定ルートより後に定義）"""
    _check_category_access(request, category_id)
    category_name = None
    category_image = None
    category_video = None
    try:
        res = requests.get(f"{API_URL}/categories/{category_id}", timeout=10)
        if res.status_code == 200:
            category = res.json().get("category")
            if category:
                category_name = category.get("name")
                category_image = category.get("image_file_name")
                category_video = category.get("video_file_name")
    except Exception:
        pass

    session = _decode_session(request)
    role = session.get("role", "user")
    context: dict[str, Any] = {
        "request": request,
        "body_class": "sub_page",
        "category_name": category_name,
        "title_name": f"PERSONAL - {category_name}",
        "category_image": category_image,
        "category_video": category_video,
        "categories": _get_user_categories(session.get("user_id"), role),
        "category_id": category_id,
        "role": role,
    }
    return html.TemplateResponse("category.html", context)


@app.get("/download/{content_id}")
def download_original(request: Request, content_id: str):
    """オリジナルファイルをダウンロードする"""
    res = requests.get(f"{API_URL}/getContent/{content_id}", timeout=10)
    content = res.json()["content"]
    _check_category_access(request, content["category_id"])
    file_path = BASE_DIR / content["category_id"] / "originals" / content["stored_file_name"]
    disposition = f"attachment; filename*=UTF-8''{quote(content['original_file_name'])}"
    return FileResponse(
        file_path,
        filename=content["original_file_name"],
        headers={"Content-Disposition": disposition},
    )


@app.api_route("/personal-web/contents/{category_id}/img/{file_name}", methods=["GET", "HEAD"])
def get_img_file(request: Request, category_id: str, file_name: str):
    """imgファイルを返す"""
    _check_category_access(request, category_id)
    file_path = BASE_DIR / category_id / "images" / file_name
    return FileResponse(file_path)


@app.api_route(
    "/personal-web/contents/{category_id}/video/{file_path:path}", methods=["GET", "HEAD"]
)
def get_video_file(request: Request, category_id: str, file_path: str):
    """videoファイルを返す（HLS対応）"""
    _check_category_access(request, category_id)
    full_path = BASE_DIR / category_id / "videos" / file_path
    ext = Path(file_path).suffix.lower()
    if ext == ".m3u8":
        return FileResponse(full_path, media_type="application/vnd.apple.mpegurl")
    if ext == ".ts":
        return FileResponse(full_path, media_type="video/mp2t")
    return FileResponse(full_path)


@app.api_route(
    "/personal-web/contents/{category_id}/thumbnail/{file_name}", methods=["GET", "HEAD"]
)
def get_thumbnail_file(request: Request, category_id: str, file_name: str):
    """thumbnailファイルを返す"""
    _check_category_access(request, category_id)
    file_path = BASE_DIR / category_id / "thumbnails" / file_name
    return FileResponse(file_path)


@app.post("/upload/{category_id}")
async def upload_file(
    category_id: str, file: UploadFile = File(...), defer_conversion: bool = Form(False)
):
    """ファイルのアップロードを行う"""
    if not (BASE_DIR / category_id).exists():
        raise HTTPException(status_code=500, detail="category directory not found")
    target_dir_path = BASE_DIR / category_id
    original_ext = Path(file.filename).suffix.lower()
    stored_file_name = create_random_file_name(20) + original_ext
    stored_file_path = target_dir_path / "originals" / stored_file_name

    file_bytes = await file.read()
    assert isinstance(file_bytes, bytes)
    with stored_file_path.open("wb") as buffer:
        buffer.write(file_bytes)

    view_file_name_without_ext = create_random_file_name(20)
    view_file_name = view_file_name_without_ext + original_ext.lower()
    original_file_type = get_file_type(stored_file_path)
    thumbnail_file_name = create_random_file_name(20) + ".webp"

    if original_file_type == "image":
        view_file_name = f"{view_file_name_without_ext}.webp"
        save_image_as_webp(
            file_bytes, original_ext, target_dir_path / "images" / view_file_name, lossless=True
        )
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
            _conversion_executor.submit(
                _convert_to_hls_tracked, stored_file_name, stored_file_path, hls_output_dir
            )
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


@app.post("/start-conversion", status_code=204)
async def start_conversion(data: dict[str, Any] = Body(...)) -> Response:
    """保留中のHLS変換を一括開始する"""
    for name in data.get("stored_file_names", []):
        params = _pending_conversions.pop(name, None)
        if params:
            stored_file_path, hls_output_dir = params
            _conversion_executor.submit(
                _convert_to_hls_tracked, name, stored_file_path, hls_output_dir
            )
    return Response(status_code=204)


@app.get("/conversion-status")
def get_conversion_status_batch(names: list[str] = Query(default=[])) -> dict[str, Any]:
    """複数のHLS変換状態を一括取得する"""
    result: dict[str, Any] = {}
    for name in names:
        info = conversion_tasks.get(name)
        if info is None:
            result[name] = {"status": "done", "progress": 100}
        else:
            result[name] = {"status": info["status"], "progress": info["progress"]}
    return result


@app.delete("/delete/{target_id}", status_code=204)
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

    requests.delete(f"{API_URL}/delete/{target_id}", timeout=10)
    return Response(status_code=204)


@app.delete("/forceDelete/{target_id}", status_code=204)
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

    requests.delete(f"{API_URL}/delete/{target_id}", timeout=10)
    return Response(status_code=204)


# --- Debug ---
IS_DEBUG_MODE = True

app.mount(path="/debug-assets", app=StaticFiles(directory=BASE_DIR / "debug"), name="debug-assets")


@app.get("/debug", response_class=HTMLResponse)
async def debug_page(request: Request):
    """デバッグページを返す（デバッグモード有効かつ admin 限定）。"""
    if not IS_DEBUG_MODE:
        return HTMLResponse(status_code=404)
    if _decode_session(request).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    debug_dir = BASE_DIR / "debug"
    context: dict[str, Any] = {
        "request": request,
        "debug_image": "/debug-assets/debug.jpg" if (debug_dir / "debug.jpg").exists() else None,
        "debug_bg": "/debug-assets/bg.jpg" if (debug_dir / "bg.jpg").exists() else None,
    }
    return html.TemplateResponse("debug.html", context)
