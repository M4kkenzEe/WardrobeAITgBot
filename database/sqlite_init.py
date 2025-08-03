import sqlite3
from contextlib import contextmanager
from typing import Optional
import os

DB_PATH = "storage/users.sqlite3"
os.makedirs("storage", exist_ok=True)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            description TEXT,
            season TEXT,
            sex TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)


def add_user(user_id: int, username: Optional[str] = None, language: Optional[str] = None):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, language) VALUES (?, ?, ?)",
            (user_id, username, language)
        )


def add_clothing_item(user_id: int, filename: str, description: str, season: str, sex: str, image_path: str):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO clothes (user_id, filename, description, season, sex, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, filename, description, season, sex, image_path)
        )


def get_user_clothes(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename, description, season, sex, image_path FROM clothes WHERE user_id = ?",
                       (user_id,))
        return cursor.fetchall()


def print_users_and_clothes():
    with get_db() as conn:
        cursor = conn.cursor()

        print("\n📍 USERS:")
        for row in cursor.execute("SELECT id, username, language, created_at FROM users"):
            print(row)

        print("\n👕 CLOTHES:")
        for row in cursor.execute(
                "SELECT id, user_id, filename, description, season, sex, image_path, created_at FROM clothes"):
            print(row)


# Инициализация базы данных при запуске
init_db()
