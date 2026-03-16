import secrets
import sqlite3
import string
import json

_ID_ALPHABET = string.ascii_letters + string.digits

def _generate_id(length: int = 20) -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(length))

# サンプルデータ（実際はJSONから読み込んだ配列を使用）
json_file = "files_info.json"
with open(json_file, "r", encoding="utf-8") as f:
    data_list = json.load(f)
print(data_list)
# SQLite データベースファイル名
db_file = "main.db"

# SQLite に接続（存在しなければ作成される）
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# テーブル作成（存在しなければ）
cursor.execute("""
CREATE TABLE IF NOT EXISTS contents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    file_name TEXT,
    thumbnail_file_name TEXT,
    stored_file_name TEXT,
    original_file_name TEXT,
    duration_ms INTEGER,
    file_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

# データ挿入
for item in data_list:
    content_id = _generate_id()
    cursor.execute(
        """
        INSERT INTO contents (
            id, thumbnail_file_name, duration_ms, title,
            file_name, original_file_name, file_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_id,
            item["thumbnail_file_name"],
            item["duration_ms"],
            item["title"],
            item["file_name"],
            item["original_file_name"],
            item["file_type"],
        ),
    )

    contents_type = item["contents_type"]
    cursor.execute("SELECT id FROM categories WHERE name = ?", (contents_type,))
    category_row = cursor.fetchone()
    if category_row:
        category_id = category_row[0]
    else:
        category_id = _generate_id()
        cursor.execute("INSERT INTO categories (id, name) VALUES (?, ?)", (category_id, contents_type))

    cursor.execute(
        "SELECT COALESCE(MAX(sort_order) + 1, 0) FROM contents_categories WHERE category_id = ?",
        (category_id,),
    )
    next_order = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO contents_categories (content_id, category_id, sort_order) VALUES (?, ?, ?)",
        (content_id, category_id, next_order),
    )

# コミットして保存
conn.commit()

# 接続を閉じる
conn.close()

print("SQLiteへの登録が完了しました。")
