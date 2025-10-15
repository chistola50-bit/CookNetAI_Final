import os
import logging
import asyncio
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from config import TOKEN
from database import get_recipes, init_db

# === Настройки ===
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://cooknetai-final.onrender.com") + WEBHOOK_PATH

# === Главная страница ===
@app.route("/")
def home():
    return "<h1>🍳 CookNet AI работает!</h1><p>Бот и вебхук активны.</p>"

# === Обработка Telegram webhook ===
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    data = request.get_json()
    update = types.Update(**data)
    asyncio.get_event_loop().create_task(dp.process_update(update))
    return "OK", 200

# === Запуск web-сервера и настройка webhook ===
async def setup_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")

def start_app():
    asyncio.get_event_loop().run_until_complete(setup_webhook())
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    start_app()
