from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

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
