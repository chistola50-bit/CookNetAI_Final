import os
import logging
import asyncio
from flask import Flask, request, render_template
from aiogram import Bot, Dispatcher, types
from config import TOKEN
from database import init_db

# === Настройки приложения ===
app = Flask(__name__, template_folder="templates", static_folder="static")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://cooknetai-final.onrender.com") + WEBHOOK_PATH

# === Главная страница сайта ===
@app.route("/")
def home():
    return render_template("index.html")

# === Страница рейтинга (заглушка пока) ===
@app.route("/top")
def top_page():
    return "<h2>🏆 Рейтинг рецептов появится здесь!</h2>"

# === Страница рецепта дня (заглушка пока) ===
@app.route("/daily")
def daily_page():
    return "<h2>🍲 Рецепт дня в разработке...</h2>"

# === Webhook для Telegram ===
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = types.Update(**data)

        # отдельный event loop для aiogram
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dp.process_update(update))
        loop.close()
        return "OK", 200

    except Exception as e:
        logging.exception(e)
        return "Ошибка обработки вебхука", 500

# === Установка webhook при старте ===
async def setup_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")

def start_app():
    asyncio.run(setup_webhook())
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    start_app()
