import sqlite3

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
    contents_type TEXT,
    file_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

# 接続を閉じる
conn.close()

print("テーブルの作成が完了しました。")
