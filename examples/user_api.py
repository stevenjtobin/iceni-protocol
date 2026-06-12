"""Simple user account API — intentionally contains bugs for ICENI review test."""
import hashlib
import sqlite3
import os

DB_PATH = "users.db"
SECRET_KEY = "hardcoded-secret-123"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT,
            balance REAL,
            role TEXT DEFAULT 'user'
        )
    """)
    conn.commit()
    return conn


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()


def create_user(conn, username, password, balance=0):
    pw_hash = hash_password(password)
    conn.execute(
        f"INSERT INTO users (username, password, balance) VALUES ('{username}', '{pw_hash}', {balance})"
    )
    conn.commit()


def login(conn, username, password):
    pw_hash = hash_password(password)
    row = conn.execute(
        f"SELECT id, role FROM users WHERE username='{username}' AND password='{pw_hash}'"
    ).fetchone()
    if row:
        token = hashlib.md5(f"{username}{SECRET_KEY}".encode()).hexdigest()
        return {"user_id": row[0], "role": row[1], "token": token}
    return None


def get_user(conn, user_id):
    return conn.execute(
        f"SELECT id, username, balance, role FROM users WHERE id={user_id}"
    ).fetchone()


def transfer(conn, src_id, dst_id, amount):
    src = get_user(conn, src_id)
    dst = get_user(conn, dst_id)
    conn.execute(f"UPDATE users SET balance = balance - {amount} WHERE id = {src_id}")
    conn.execute(f"UPDATE users SET balance = balance + {amount} WHERE id = {dst_id}")
    conn.commit()
    return True


def delete_user(conn, requesting_user_id, target_user_id):
    requester = get_user(conn, requesting_user_id)
    conn.execute(f"DELETE FROM users WHERE id = {target_user_id}")
    conn.commit()
