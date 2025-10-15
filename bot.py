import logging
import os
import asyncio
from flask import Flask, render_template_string, request, redirect, url_for
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook
from database import (
    init_db, upsert_user,
    add_recipe, get_recipes, like_recipe, get_random_recipe,
    set_chat_sub, set_daily_sub,
    get_chat_subscribers_chat_ids, get_daily_subscribers_chat_ids,
    save_chat_message, get_recent_chat_messages
)
from config import TOKEN, COOKNET_URL

logging.basicConfig(level=logging.INFO)

# === Telegram Bot ===
bot = Bot(token=TOKEN)
bot.set_current(bot)
dp = Dispatcher(bot)
init_db()

# === Flask Web App ===
app = Flask(__name__)

# Главная страница
@app.route('/')
def index():
    recipes = get_recipes(limit=5)
    html = """
    <h1>🍳 CookNet AI</h1>
    <p>Добро пожаловать, шеф!</p>
    <p><a href="https://t.me/cooknet_ai_bot">Открыть Telegram-бота</a></p>
    <h2>🔥 Топ рецептов:</h2>
    {% for r in recipes %}
      <div style="border:1px solid #ccc; padding:10px; margin:10px;">
        <b>{{r[3]}}</b> — ❤️ {{r[6]}} лайков<br>
        👤 @{{r[2] or 'anon'}}<br>
        <p>{{r[4]}}</p>
      </div>
    {% endfor %}
    """
    return render_template_string(html, recipes=recipes)

# Профиль пользователя
@app.route('/user/<username>')
def user_profile(username):
    recipes = [r for r in get_recipes(limit=50) if r[2] == username]
    html = """
    <h1>👤 Профиль @{{username}}</h1>
    {% if recipes %}
      {% for r in recipes %}
        <div style="border:1px solid #ccc; padding:10px; margin:10px;">
          <b>{{r[3]}}</b> — ❤️ {{r[6]}} лайков<br>
          <p>{{r[4]}}</p>
        </div>
      {% endfor %}
    {% else %}
      <p>Нет рецептов 😔</p>
    {% endif %}
    """
    return render_template_string(html, username=username, recipes=recipes)

# Общий чат (веб)
@app.route('/chat', methods=['GET', 'POST'])
def web_chat():
    if request.method == 'POST':
        user = request.form.get('user', 'anon')
        msg = request.form.get('msg', '').strip()
        if msg:
            save_chat_message(0, user, msg)
    messages = get_recent_chat_messages(30)
    html = """
    <h1>💬 Общий чат CookNet</h1>
    <form method="POST">
      <input name="user" placeholder="Ваше имя" required>
      <input name="msg" placeholder="Сообщение" required>
      <button type="submit">Отправить</button>
    </form>
    <hr>
    {% for u, t, ts in messages %}
      <p><b>{{u}}</b>: {{t}} <i>{{ts}}</i></p>
    {% endfor %}
    """
    return render_template_string(html, messages=messages)

# Простая админка
@app.route('/admin')
def admin_panel():
    recipes = get_recipes(limit=50)
    html = """
    <h1>🛠 Админ-панель CookNet</h1>
    <p>Всего рецептов: {{recipes|length}}</p>
    {% for r in recipes %}
      <div style="border:1px solid #ccc; padding:10px; margin:10px;">
        <b>{{r[3]}}</b> — ❤️ {{r[6]}} лайков<br>
        👤 @{{r[2] or 'anon'}}
      </div>
    {% endfor %}
    """
    return render_template_string(html, recipes=recipes)

# === Telegram Webhook ===
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "https://cooknetai-final.onrender.com")
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 10000))

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    upsert_user(message.from_user.id, message.from_user.username, message.chat.id)
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🍳 Открыть сайт", url=COOKNET_URL)
    )
    await message.answer("👋 Привет, шеф! Добро пожаловать в CookNet AI 🍲", reply_markup=kb)

@dp.message_handler(commands=['top'])
async def cmd_top(message: types.Message):
    recipes = get_recipes(limit=5)
    if not recipes:
        await message.answer("Пока нет рецептов 😅")
        return
    for r in recipes:
        caption = f"🍽 {r[3]}\n👤 @{r[2] or 'anon'}\n❤️ {r[6]}\n\n{r[4]}"
        await bot.send_message(message.chat.id, caption)

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Запуск Flask и Aiogram вместе
    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=WEBAPP_PORT, debug=False)).start()

    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT + 1,
    )
