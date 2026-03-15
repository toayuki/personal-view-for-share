import sqlite3
import json

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
    original_file_name TEXT,
    duration_ms INTEGER,
    contents_type TEXT,
    file_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
""")

# データ挿入
for item in data_list:
    cursor.execute("""
    INSERT INTO contents (thumbnail_file_name, duration_ms, title,file_name,original_file_name,contents_type,file_type)
    VALUES (?, ?, ?, ?, ? ,? ,?)
    """, (item["thumbnail_file_name"], item["duration_ms"], item["title"],item["file_name"] ,item["original_file_name"], item["contents_type"],item["file_type"]))

# コミットして保存
conn.commit()

# 接続を閉じる
conn.close()

print("SQLiteへの登録が完了しました。")
