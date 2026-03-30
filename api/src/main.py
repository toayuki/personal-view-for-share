import hashlib
import sqlite3

from dotenv import load_dotenv
from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@app.get("/{contents_type}/getList")
def get_list(contents_type: str):
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM contents WHERE contents_type=? AND deleted_at IS NULL",
        (contents_type,),
    )
    rows = cur.fetchall()
    conn.close()
    return {"items": [dict(row) for row in rows]}


@app.get("/getItem/{target_id}")
def get_item(target_id: str):
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM contents WHERE id=? AND deleted_at IS NULL", (target_id,)
    )
    row = cur.fetchone()
    conn.close()
    return {"item": row}


@app.post("/upload")
def upload(data: dict = Body(...)):
    print("受信", data, data["thumbnail_file_name"])
    conn = sqlite3.connect("main.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
    INSERT INTO contents (
    thumbnail_file_name, duration_ms, title, file_name, original_file_name,
    stored_file_name, contents_type, file_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            data["thumbnail_file_name"],
            data["duration_ms"],
            data["title"],
            data["file_name"],
            data["original_file_name"],
            data["stored_file_name"],
            data["contents_type"],
            data["file_type"],
        ),
    )
    conn.commit()
    conn.close()


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
        "SELECT id FROM users WHERE (user_name=? OR email_address=?) AND password_hash=? AND deleted_at IS NULL",
        (username, username, password_hash),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {"ok": True}
    return JSONResponse(status_code=401, content={"error": "invalid credentials"})


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
    try:
        cur.execute(
            "INSERT INTO users (user_name, password_hash, email_address) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse(status_code=409, content={"error": "username or email already exists"})
    conn.close()
    return {"ok": True}
