import hashlib
import json
import secrets
import sqlite3
import string

from dotenv import load_dotenv
from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_ID_ALPHABET = string.ascii_letters + string.digits


def _generate_id(length: int = 20) -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(length))

load_dotenv()

app = FastAPI()
webUrl = "https://192.168.0.7:3000"
globalUrl = "https://share.toa-yuki.com"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        webUrl,
        globalUrl
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/message")
def get_message():
    return {"message": "APIから来た文字列です"}


@app.get("/{category_id}/getList")
def get_list(category_id: str):
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT con.*
        FROM contents con
        JOIN contents_categories cc ON con.id = cc.content_id
        JOIN categories cat ON cc.category_id = cat.id
        WHERE cat.id = ? AND con.deleted_at IS NULL AND cat.deleted_at IS NULL
        """,
        (category_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return {"items": [dict(row) for row in rows]}


@app.get("/getContent/{target_id}")
def get_item(target_id: str):
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT con.*, cat.name as category_name, cat.id as category_id
        FROM contents con
        LEFT JOIN contents_categories cc ON con.id = cc.content_id
        LEFT JOIN categories cat ON cc.category_id = cat.id
        WHERE con.id = ? AND con.deleted_at IS NULL
        """,
        (target_id,),
    )
    row = cur.fetchone()
    conn.close()
    return {"content": dict(row) if row else None}


@app.post("/upload")
def upload(data: dict = Body(...)):
    print("受信", data, data["thumbnail_file_name"])
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    content_id = _generate_id()
    cur.execute(
        """
        INSERT INTO contents (
        id, thumbnail_file_name, duration_ms, title, file_name, original_file_name,
        stored_file_name, file_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_id,
            data["thumbnail_file_name"],
            data["duration_ms"],
            data["title"],
            data["file_name"],
            data["original_file_name"],
            data["stored_file_name"],
            data["file_type"],
        ),
    )

    category_id = data["category_id"]

    cur.execute(
        "SELECT COALESCE(MAX(sort_order) + 1, 0) FROM contents_categories WHERE category_id = ?",
        (category_id,),
    )
    next_order = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO contents_categories (content_id, category_id, sort_order) VALUES (?, ?, ?)",
        (content_id, category_id, next_order),
    )
    conn.commit()
    conn.close()
    return {"id": content_id}


@app.post("/update/{target_id}")
def update(target_id: str, data: dict = Body(...)):
    """タイトル更新"""
    conn = sqlite3.connect("main.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE contents SET title=?, update_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL",
        (data["title"], target_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/delete/{target_id}")
def delete(target_id: str):
    """削除機能"""
    print("削除受信", target_id)
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE contents
        SET deleted_at = CURRENT_TIMESTAMP
        WHERE id = ?
        AND deleted_at IS NULL
        """,
        (target_id,)
    )
    conn.commit()
    conn.close()


@app.post("/categories")
def create_category(data: dict = Body(...)):
    """カテゴリ登録"""
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name is required"})
    description = data.get("description", "")
    image_file_name = data.get("image_file_name")
    conn = sqlite3.connect("main.db")
    cur = conn.cursor()
    category_id = _generate_id()
    try:
        cur.execute(
            "INSERT INTO categories (id, name, description, image_file_name, created_by) VALUES (?, ?, ?, ?, ?)",
            (category_id, name, description, image_file_name, data.get("user_id")),
        )
        # 作成者の viewable_category_ids に新カテゴリを追加
        user_id = data.get("user_id")
        if user_id:
            cur.execute("SELECT viewable_category_ids FROM users WHERE id=? AND deleted_at IS NULL", (user_id,))
            row = cur.fetchone()
            if row:
                ids = json.loads(row[0]) if row[0] else []
                ids.append(category_id)
                cur.execute(
                    "UPDATE users SET viewable_category_ids=? WHERE id=?",
                    (json.dumps(ids), user_id),
                )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse(status_code=500, content={"error": "failed to create category"})
    conn.close()
    return {"ok": True, "id": category_id}


@app.patch("/categories/{category_id}")
def update_category(category_id: str, data: dict = Body(...)):
    """カテゴリを更新する"""
    conn = sqlite3.connect("main.db")
    cur = conn.cursor()
    updates = []
    values = []
    if "name" in data:
        updates.append("name=?")
        values.append(data["name"])
    if "description" in data:
        updates.append("description=?")
        values.append(data["description"])
    if "image_file_name" in data:
        updates.append("image_file_name=?")
        values.append(data["image_file_name"])
    if not updates:
        conn.close()
        return {"ok": True}
    updates.append("updated_at=CURRENT_TIMESTAMP")
    values.append(category_id)
    cur.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id=?", values)
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/categories/{category_id}")
def delete_category(category_id: str):
    """カテゴリを論理削除する"""
    conn = sqlite3.connect("main.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE categories SET deleted_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL",
        (category_id,),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/categories/{category_id}")
def get_category(category_id: str):
    """カテゴリを1件返す"""
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, description, image_file_name, created_by FROM categories WHERE id=? AND deleted_at IS NULL",
        (category_id,),
    )
    row = cur.fetchone()
    conn.close()
    return {"category": dict(row) if row else None}


@app.get("/categories")
def list_categories():
    """全カテゴリ一覧を返す"""
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, image_file_name, created_by FROM categories WHERE deleted_at IS NULL ORDER BY created_at")
    rows = cur.fetchall()
    conn.close()
    return {"categories": [dict(row) for row in rows]}


@app.post("/login/verify")
def login_verify(data: dict = Body(...)):
    """ユーザー名・パスワードを検証する"""
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return JSONResponse(status_code=400, content={"error": "invalid input"})
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """SELECT id, role, viewable_category_ids FROM users
           WHERE (user_name=? OR email_address=?) AND password_hash=? AND deleted_at IS NULL""",
        (username, username, password_hash),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {"ok": True, "user_id": row["id"], "role": row["role"], "viewable_category_ids": row["viewable_category_ids"]}
    return JSONResponse(status_code=401, content={"error": "invalid credentials"})


@app.post("/audit/log")
def audit_log(data: dict = Body(...)):
    """操作ログを記録する"""
    conn = sqlite3.connect("main.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_logs (id, user_id, action, details, ip_address) VALUES (?, ?, ?, ?, ?)",
        (
            _generate_id(),
            data.get("user_id"),
            data.get("action", "unknown"),
            json.dumps(data.get("details")) if data.get("details") is not None else None,
            data.get("ip_address"),
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/register")
def create_user(data: dict = Body(...)):
    """ユーザー登録"""
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()
    if not username or not password or not email:
        return JSONResponse(status_code=400, content={"error": "invalid input"})
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect("main.db")
    cur = conn.cursor()
    user_id = _generate_id()
    try:
        cur.execute(
            "INSERT INTO users (id, user_name, password_hash, email_address) VALUES (?, ?, ?, ?)",
            (user_id, username, password_hash, email),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse(status_code=409, content={"error": "username or email already exists"})
    conn.close()
    return {"ok": True, "user_id": user_id}


@app.post("/users/{user_id}/viewable-categories")
def add_viewable_category(user_id: str, data: dict = Body(...)):
    """ユーザーの閲覧可能カテゴリにIDを追加する"""
    category_id = data.get("category_id")
    if not category_id:
        return JSONResponse(status_code=400, content={"error": "category_id required"})
    conn = sqlite3.connect("main.db")
    cur = conn.cursor()
    cur.execute("SELECT viewable_category_ids FROM users WHERE id=? AND deleted_at IS NULL", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(status_code=404, content={"error": "user not found"})
    ids = json.loads(row[0]) if row[0] else []
    if category_id not in ids:
        ids.append(category_id)
        cur.execute("UPDATE users SET viewable_category_ids=? WHERE id=?", (json.dumps(ids), user_id))
        conn.commit()
    conn.close()
    return {"ok": True}
