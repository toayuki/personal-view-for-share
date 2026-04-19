"""
監査ログ・ログインアクセスログの記録モジュール。

- ユーザー操作の監査ログ（ユーザーごとのテキストファイル + DB）
- ログインページアクセスの専用ログ
- ログインジェクション対策（制御文字のサニタイズ）
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests as http_requests
from dotenv import load_dotenv  # type: ignore
from fastapi import Request

load_dotenv()

LOG_DIR = (
    Path(os.getenv("LOG_DIR"))
    if os.getenv("LOG_DIR")
    else Path(__file__).parent.parent.parent / "logs"
)
_LOGIN_ACCESS_LOG = LOG_DIR / "login_access.log"

_CTRL_CHARS = str.maketrans({c: " " for c in "\r\n\t\x00\x1b"})

# (HTTPメソッド, パスのパターン, アクション名) のリスト
# パターン内の名前付きグループがそのまま details に入る
AUDIT_ROUTES = [
    ("POST",   re.compile(r"^/login$"),                                                                       "login"),
    ("POST",   re.compile(r"^/logout$"),                                                                      "logout"),
    ("POST",   re.compile(r"^/signup$"),                                                                      "signup_request"),
    ("POST",   re.compile(r"^/signup/complete$"),                                                             "signup_complete"),
    ("GET",    re.compile(r"^/$"),                                                                            "index_view"),
    ("GET",    re.compile(r"^/howToUse\.html$"),                                                              "howto_view"),
    ("POST",   re.compile(r"^/categories$"),                                                                  "category_create"),
    ("DELETE", re.compile(r"^/categories/(?P<category_id>[^/]+)$"),                                          "category_delete"),
    ("GET",    re.compile(r"^/(?P<category_id>[^/]+)\.html$"),                                               "category_view"),
    ("POST",   re.compile(r"^/upload/(?P<category_id>[^/]+)$"),                                              "upload"),
    ("POST",   re.compile(r"^/start-conversion$"),                                                            "conversion_start"),
    ("GET",    re.compile(r"^/delete/(?P<target_id>[^/]+)$"),                                                "delete"),
    ("GET",    re.compile(r"^/forceDelete/(?P<target_id>[^/]+)$"),                                           "force_delete"),
    ("GET",    re.compile(r"^/download/(?P<content_id>[^/]+)$"),                                             "download"),
    # .m3u8 のみ記録（.ts セグメントは除外）
    ("GET",    re.compile(r"^/personal-web/contents/(?P<category_id>[^/]+)/video/(?P<file_path>.+\.m3u8)$"), "video_play"),
]


def sanitize(value: str) -> str:
    """ログインジェクション対策：改行・制御文字をスペースに置換する"""
    return value.translate(_CTRL_CHARS).strip()


def get_client_ip(request: Request) -> str:
    """グローバルIPを優先して取得する（プロキシ経由の場合は X-Forwarded-For を使用）"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "-"


def log_login_access(
    event: str,
    ip: str,
    user_agent: str = "-",
    referer: str = "-",
    accept_language: str = "-",
    username: str | None = None,
    email: str | None = None,
) -> None:
    """ログイン・サインアップ関連アクセスを専用ファイルに記録する

    event: "page_access" | "attempt_success" | "attempt_failed"
          | "signup_request" | "signup_request_failed"
          | "signup_complete" | "signup_failed" | "signup_invalid_token"
    """
    try:
        LOG_DIR.mkdir(exist_ok=True)
        entry: dict = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            "ip": ip,
            "referer": sanitize(referer),
            "lang": sanitize(accept_language),
            "user_agent": sanitize(user_agent),
        }
        if username is not None:
            entry["username"] = sanitize(username)
        if email is not None:
            entry["email"] = sanitize(email)
        with _LOGIN_ACCESS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def log_action(
    user_id: str | None,
    action: str,
    api_url: str,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    """操作ログをDBとテキストファイルに記録する（失敗しても握りつぶす）"""
    try:
        http_requests.post(
            f"{api_url}/audit/log",
            json={"user_id": user_id, "action": action, "details": details or {}, "ip_address": ip},
            timeout=5,
        )
    except Exception:
        pass
    try:
        LOG_DIR.mkdir(exist_ok=True)
        log_file = LOG_DIR / f"{user_id or 'anonymous'}.log"
        safe_details = {k: sanitize(v) if isinstance(v, str) else v for k, v in (details or {}).items()}
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "ip": ip or "-",
            "details": safe_details,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def make_audit_middleware(active_sessions: dict, api_url: str):
    """audit_middleware のファクトリ関数。active_sessions と api_url をクロージャで保持する。"""

    async def audit_middleware(request: Request, call_next):
        """リクエストのメソッド・パスからユーザー操作を自動記録するミドルウェア"""
        method = request.method
        path = request.url.path
        ip = get_client_ip(request)

        if method == "GET" and path == "/login":
            log_login_access(
                event="page_access",
                ip=ip,
                user_agent=request.headers.get("user-agent", "-"),
                referer=request.headers.get("referer", "-"),
                accept_language=request.headers.get("accept-language", "-"),
            )

        # ログアウトはエンドポイント実行後にセッションが消えるため、呼び出し前に取得
        token = request.cookies.get("session")
        pre_user_id = active_sessions.get(token, {}).get("user_id")

        response = await call_next(request)

        for route_method, pattern, action in AUDIT_ROUTES:
            if method != route_method:
                continue
            m = pattern.match(path)
            if not m:
                continue
            details = m.groupdict()
            if action == "login":
                if response.status_code == 302:
                    # レスポンスの Set-Cookie から新しいセッショントークンを取得
                    set_cookie = response.headers.get("set-cookie", "")
                    new_token = next(
                        (p.strip()[len("session="):] for p in set_cookie.split(";") if p.strip().startswith("session=")),
                        None,
                    )
                    user_id = active_sessions.get(new_token, {}).get("user_id")
                    log_action(user_id, "login", api_url, details, ip)
                else:
                    log_action(None, "login_failed", api_url, details, ip)
            elif action == "logout":
                log_action(pre_user_id, "logout", api_url, details, ip)
            else:
                user_id = active_sessions.get(token, {}).get("user_id")
                log_action(user_id, action, api_url, details, ip)
            break

        return response

    return audit_middleware
