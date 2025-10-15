import logging
import os
import asyncio
from flask import Flask, render_template_string, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import Executor
from database import (
    init_db, upsert_user,
    add_recipe, get_recipes, like_recipe, get_random_recipe,
    set_chat_sub, set_daily_sub,
    get_chat_subscribers_chat_ids, get_daily_subscribers_chat_ids,
    save_chat_message, get_recent_chat_messages
)
from config import TOKEN, COOKNET_URL

# === ИНИЦИАЛИЗАЦИЯ ===
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

# === Flask сервер ===
app = Flask(__name__)

@app.route('/')
def index():
    recipes = get_recipes(limit=5)
    html = """
    <h1>🍳 CookNet AI</h1>
    <p>Добро пожаловать, шеф!</p>
    <a href="https://t.me/cooknet_ai_bot">Открыть Telegram-бота</a>
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

# === Интеграция Flask + Aiogram ===
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = f"{os.getenv('RENDER_EXTERNAL_URL', 'https://cooknetai-final.onrender.com')}/webhook/{TOKEN}"

executor = Executor(dp)

@app.post(f"/webhook/{TOKEN}")
async def webhook():
    update = types.Update(**await request.json)
    await dp.process_update(update)
    return "OK", 200

@executor.on_startup
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")

@executor.on_shutdown
async def on_shutdown(dp):
    await bot.delete_webhook()
    logging.warning("Webhook удалён")

if __name__ == "__main__":
    # Flask + Aiogram на одном порту
    loop = asyncio.get_event_loop()
    executor.loop = loop
    executor.start_polling(dp, skip_updates=True)
    app.run(host=WEBAPP_HOST, port=WEBAPP_PORT)
