import sqlite3

# SQLite データベースファイル名
db_file = "main.db"

# SQLite に接続（存在しなければ作成される）
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# 外部キー制約を有効化
cursor.execute("PRAGMA foreign_keys = OFF")

# 全テーブル削除
cursor.execute("DROP TABLE IF EXISTS contents_categories")
cursor.execute("DROP TABLE IF EXISTS contents")
cursor.execute("DROP TABLE IF EXISTS categories")
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("DROP TABLE IF EXISTS audit_logs")

cursor.execute("PRAGMA foreign_keys = ON")

# テーブル作成
cursor.execute("""
CREATE TABLE contents (
    id TEXT PRIMARY KEY,
    title TEXT,
    file_name TEXT,
    thumbnail_file_name TEXT,
    stored_file_name TEXT,
    original_file_name TEXT,
    duration_ms INTEGER,
    file_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

cursor.execute("""
CREATE TABLE categories (
    id TEXT PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    image_file_name TEXT,
    video_file_name TEXT,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

cursor.execute("""
CREATE TABLE contents_categories (
    content_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (content_id, category_id),
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
)
""")

cursor.execute("""
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email_address TEXT UNIQUE NOT NULL, 
    password_hash TEXT NOT NULL,
    user_name TEXT,
    role TEXT DEFAULT 'user',
    status INTEGER DEFAULT 1,
    last_login_at DATETIME,
    login_fail_count INTEGER DEFAULT 0,
    password_reset_token TEXT,
    password_reset_expires_at DATETIME,
    viewable_category_ids TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

cursor.execute("""
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# 接続を閉じる
conn.close()

print("テーブルの作成が完了しました。")
