import os
import logging
import asyncio
from flask import Flask, render_template, request
from aiogram import Bot, Dispatcher, types
from database import get_recipes, init_db
from config import TOKEN

# === Flask приложение ===
app = Flask(__name__)

# === Настройка бота ===
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

# === Webhook ===
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://cooknetai-final.onrender.com") + WEBHOOK_PATH


# === Главная страница ===
@app.route("/")
def index():
    recipes = get_recipes(limit=5)
    return render_template("index.html", recipes=recipes, token=TOKEN)


# === Обработчик Telegram webhook ===
@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    update = types.Update(**data)
    asyncio.get_event_loop().create_task(dp.process_update(update))
    return "OK", 200


# === При запуске сайта ===
@app.before_first_request
def on_startup():
    asyncio.get_event_loop().create_task(bot.set_webhook(WEBHOOK_URL))
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
