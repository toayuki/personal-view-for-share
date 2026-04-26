import hashlib
import secrets
import sqlite3
import string

_ID_ALPHABET = string.ascii_letters + string.digits

def _generate_id(length: int = 20) -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(length))

USERS = [
    {"user_name": "user1",   "email": "user1@gmail.com",   "password": "user123",   "role": "user"},
    {"user_name": "user2",   "email": "user2@gmail.com",   "password": "user123",   "role": "user"},
    {"user_name": "user3",   "email": "user3@gmail.com",   "password": "user123",   "role": "user"},
    {"user_name": "admin",   "email": "admin@gmail.com",   "password": "Admin1234",   "role": "admin"},
]

conn = sqlite3.connect("main.db")
cur = conn.cursor()

for u in USERS:
    user_id = _generate_id()
    password_hash = hashlib.sha256(u["password"].encode()).hexdigest()
    try:
        cur.execute(
            "INSERT INTO users (id, user_name, email_address, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            (user_id, u["user_name"], u["email"], password_hash, u["role"]),
        )
        print(f"作成: {u['user_name']} / {u['email']} / pw: {u['password']} / role: {u['role']}")
    except Exception as e:
        print(f"スキップ ({u['user_name']}): {e}")

conn.commit()
conn.close()
print("完了")
