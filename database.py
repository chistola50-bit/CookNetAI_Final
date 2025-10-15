import sqlite3
from datetime import datetime

DB_NAME = "cooknet.db"

def _connect():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

def init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute("""    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        title TEXT,
        description TEXT,
        photo_id TEXT,
        photo_url TEXT,
        ai_caption TEXT,
        likes INTEGER DEFAULT 0,
        created_at TEXT
    )"""
    )
    # Soft migrations
    c.execute("PRAGMA table_info(recipes)")
    cols = {row[1] for row in c.fetchall()}
    def add_col(name, ddl):
        if name not in cols:
            c.execute(f"ALTER TABLE recipes ADD COLUMN {ddl}")
    add_col("photo_url", "photo_url TEXT")
    add_col("ai_caption", "ai_caption TEXT")
    add_col("created_at", "created_at TEXT")
    # Legacy 'desc' -> 'description'
    c.execute("PRAGMA table_info(recipes)")
    cols = {row[1] for row in c.fetchall()}
    if "desc" in cols:
        c.execute("UPDATE recipes SET description = COALESCE(description, desc) WHERE desc IS NOT NULL")
    conn.commit()
    conn.close()

def add_recipe(username, title, description, photo_id=None, photo_url=None, ai_caption=None):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO recipes (username, title, description, photo_id, photo_url, ai_caption, likes, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
        (username, title, description, photo_id, photo_url, ai_caption, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

def _rows_to_dicts(rows):
    keys = ["id","username","title","description","photo_id","photo_url","ai_caption","likes","created_at"]
    return [dict(zip(keys, r)) for r in rows]

def get_recipes(limit=36):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT id, username, title, description, photo_id, photo_url, ai_caption, likes, created_at FROM recipes ORDER BY id DESC LIMIT ?", (limit,))
    out = _rows_to_dicts(c.fetchall())
    conn.close()
    return out

def get_recipe(recipe_id:int):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT id, username, title, description, photo_id, photo_url, ai_caption, likes, created_at FROM recipes WHERE id=?", (recipe_id,))
    row = c.fetchone()
    conn.close()
    if not row: return None
    keys = ["id","username","title","description","photo_id","photo_url","ai_caption","likes","created_at"]
    return dict(zip(keys, row))

def like_recipe(recipe_id:int):
    conn = _connect()
    c = conn.cursor()
    c.execute("UPDATE recipes SET likes = COALESCE(likes,0)+1 WHERE id=?", (recipe_id,))
    conn.commit()
    conn.close()

def get_top_recipes(limit=5):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT id, username, title, description, photo_id, photo_url, ai_caption, likes, created_at FROM recipes ORDER BY likes DESC, id DESC LIMIT ?", (limit,))
    out = _rows_to_dicts(c.fetchall())
    conn.close()
    return out
