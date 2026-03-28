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
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    email_address TEXT UNIQUE NOT NULL, 
    role TEXT DEFAULT 'user',
    status INTEGER DEFAULT 1,
    last_login_at DATETIME,
    login_fail_count INTEGER DEFAULT 0,
    password_reset_token TEXT,
    password_reset_expires_at DATETIME
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

# 接続を閉じる
conn.close()

print("テーブルの作成が完了しました。")
