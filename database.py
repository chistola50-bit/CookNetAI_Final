import sqlite3

DB_NAME = "cooknet.db"

def _get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    # Рецепты
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            title TEXT,
            description TEXT,
            photo TEXT,
            likes INTEGER DEFAULT 0
        )
    """)
    # Пользователи
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            chat_id INTEGER,
            chat_sub INTEGER DEFAULT 0,   -- подписка на общий чат
            daily_sub INTEGER DEFAULT 1   -- подписка на "рецепт дня"
        )
    """)
    # Сообщения общего чата (история)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            text TEXT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ---------- Рецепты ----------
def add_recipe(user_id, username, title, description, photo):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO recipes (user_id, username, title, description, photo) VALUES (?, ?, ?, ?, ?)",
        (user_id, username or "", title, description, photo)
    )
    conn.commit()
    conn.close()

def get_recipes(limit=None):
    conn = _get_conn()
    cur = conn.cursor()
    q = "SELECT * FROM recipes ORDER BY likes DESC, id DESC"
    if limit:
        q += " LIMIT ?"
        cur.execute(q, (limit,))
    else:
        cur.execute(q)
    rows = cur.fetchall()
    conn.close()
    return rows

def like_recipe(recipe_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE recipes SET likes = likes + 1 WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()

def get_random_recipe():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row

# ---------- Пользователи ----------
def upsert_user(user_id, username, chat_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, chat_id)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            chat_id=excluded.chat_id
    """, (user_id, username or "", chat_id))
    conn.commit()
    conn.close()

def set_chat_sub(user_id, is_on: bool):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET chat_sub=? WHERE user_id=?", (1 if is_on else 0, user_id))
    conn.commit()
    conn.close()

def set_daily_sub(user_id, is_on: bool):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET daily_sub=? WHERE user_id=?", (1 if is_on else 0, user_id))
    conn.commit()
    conn.close()

def get_chat_subscribers_chat_ids(exclude_user_id=None):
    conn = _get_conn()
    cur = conn.cursor()
    if exclude_user_id is None:
        cur.execute("SELECT chat_id FROM users WHERE chat_sub=1 AND chat_id IS NOT NULL")
    else:
        cur.execute("SELECT chat_id FROM users WHERE chat_sub=1 AND chat_id IS NOT NULL AND user_id<>?", (exclude_user_id,))
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

def get_daily_subscribers_chat_ids():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users WHERE daily_sub=1 AND chat_id IS NOT NULL")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

# ---------- Общий чат ----------
def save_chat_message(user_id, username, text):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO chat_messages (user_id, username, text) VALUES (?, ?, ?)",
                (user_id, username or "", text))
    conn.commit()
    conn.close()

def get_recent_chat_messages(limit=30):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, text, ts FROM chat_messages ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    rows.reverse()  # старые наверх
    return rows
