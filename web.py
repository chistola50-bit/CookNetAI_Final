import os
import logging
import asyncio
from flask import Flask, request, render_template
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, COOKNET_URL
from database import init_db, get_recipes

# === Настройки приложения ===
app = Flask(__name__, template_folder="templates", static_folder="static")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://cooknetai-final.onrender.com") + WEBHOOK_PATH


# === Главное меню ===
def main_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🍳 Открыть сайт", url=COOKNET_URL),
        InlineKeyboardButton("🏆 Топ рецептов", callback_data="top")
    )
    return kb


# === Команды Telegram ===
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет, шеф!\n\nДобро пожаловать в *CookNet AI* — соцсеть кулинаров 🍲",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


@dp.callback_query_handler(lambda c: c.data == "top")
async def show_top(call: types.CallbackQuery):
    recipes = get_recipes(limit=3)
    if not recipes:
        await call.message.answer("Пока нет рецептов 😅")
        return
    for r in recipes:
        recipe_id, _, username, title, desc, photo, likes = r
        caption = f"🍽 {title}\n👤 @{username or 'anon'}\n❤️ {likes}\n\n{desc}"
        await bot.send_photo(call.message.chat.id, photo, caption=caption)
    await call.answer()


# === Страницы сайта ===
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/top")
def top_page():
    return "<h2>🏆 Рейтинг рецептов появится здесь!</h2>"


@app.route("/daily")
def daily_page():
    return "<h2>🍲 Рецепт дня в разработке...</h2>"


# === Webhook ===
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = types.Update(**data)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dp.process_update(update))
        loop.close()
        return "OK", 200
    except Exception as e:
        logging.exception(e)
        return "Ошибка обработки вебхука", 500


# === Настройка вебхука при старте ===
async def setup_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")


def start_app():
    asyncio.run(setup_webhook())
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    start_app()
