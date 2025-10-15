import sqlite3
from datetime import datetime

DB_NAME = "cooknet.db"

def _connect():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        title TEXT,
        desc TEXT,
        photo_id TEXT,
        photo_url TEXT,
        ai_caption TEXT,
        likes INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    # попытка добавить отсутствующие колонки (мягкая миграция)
    try:
        c.execute("ALTER TABLE recipes ADD COLUMN photo_url TEXT")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE recipes ADD COLUMN ai_caption TEXT")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE recipes ADD COLUMN created_at TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()

def add_recipe(username, title, desc, photo_id=None, photo_url=None, ai_caption=None):
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO recipes (username, title, desc, photo_id, photo_url, ai_caption, likes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
    """, (username, title, desc, photo_id, photo_url, ai_caption, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def _rows_to_dicts(rows):
    keys = ["id","username","title","desc","photo_id","photo_url","ai_caption","likes","created_at"]
    out = []
    for r in rows:
        d = {k: r[i] if i < len(r) else None for i, k in enumerate(keys)}
        out.append(d)
    return out

def get_recipes(limit=20):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT id, username, title, desc, photo_id, photo_url, ai_caption, likes, created_at FROM recipes ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return _rows_to_dicts(rows)

def like_recipe(recipe_id: int):
    conn = _connect()
    c = conn.cursor()
    c.execute("UPDATE recipes SET likes = COALESCE(likes,0) + 1 WHERE id=?", (recipe_id,))
    conn.commit()
    conn.close()

def get_top_recipes(limit=5):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT id, username, title, desc, photo_id, photo_url, ai_caption, likes, created_at FROM recipes ORDER BY likes DESC, id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return _rows_to_dicts(rows)
