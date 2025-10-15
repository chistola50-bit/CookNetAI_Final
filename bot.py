import logging
import os
import asyncio
from flask import Flask, render_template_string, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook
from database import (
    init_db, upsert_user,
    add_recipe, get_recipes, like_recipe,
    save_chat_message, get_recent_chat_messages
)
from config import TOKEN, COOKNET_URL

# === НАСТРОЙКА ===
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

# === Flask приложение ===
app = Flask(__name__)

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

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        user = request.form.get('user', 'anon')
        msg = request.form.get('msg', '').strip()
        if msg:
            save_chat_message(0, user, msg)
    messages = get_recent_chat_messages(30)
    html = """
    <h1>💬 Общий чат</h1>
    <form method="POST">
      <input name="user" placeholder="Имя" required>
      <input name="msg" placeholder="Сообщение" required>
      <button type="submit">Отправить</button>
    </form><hr>
    {% for u, t, ts in messages %}
      <p><b>{{u}}</b>: {{t}} <i>{{ts}}</i></p>
    {% endfor %}
    """
    return render_template_string(html, messages=messages)

# === Telegram ===
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

# === Настройки Render и Webhook ===
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "https://cooknetai-final.onrender.com")
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 10000))

@app.post(WEBHOOK_PATH)
async def telegram_webhook():
    data = await request.get_json()
    update = types.Update(**data)
    await dp.process_update(update)
    return "OK", 200

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown(dp):
    logging.warning("Удаляем webhook...")
    await bot.delete_webhook()

# === Запуск ===
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    async def start_bot():
        await on_startup(dp)
        from threading import Thread
        Thread(target=lambda: app.run(host=WEBAPP_HOST, port=WEBAPP_PORT, debug=False)).start()
        while True:
            await asyncio.sleep(3600)

    try:
        loop.run_until_complete(start_bot())
    except (KeyboardInterrupt, SystemExit):
        loop.run_until_complete(on_shutdown(dp))
