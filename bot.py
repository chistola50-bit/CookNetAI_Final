import logging
import os
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

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

# === URL и PORT для Render ===
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "https://cooknetai-final.onrender.com")
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 10000))

# === КНОПКИ ===
def main_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🍳 Открыть CookNet", url=COOKNET_URL),
        InlineKeyboardButton("➕ Добавить рецепт", callback_data="add"),
        InlineKeyboardButton("🏆 Топ рецептов", callback_data="top"),
        InlineKeyboardButton("💬 Общий чат", callback_data="chat_on"),
        InlineKeyboardButton("🔔 Рецепт дня", callback_data="daily_on")
    )
    return kb

# === КОМАНДЫ ===
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    upsert_user(message.from_user.id, message.from_user.username, message.chat.id)
    await message.answer(
        "👋 Привет, шеф!\n\n"
        "CookNet помогает находить и делиться рецептами с другими кулинарами.",
        reply_markup=main_keyboard()
    )

@dp.message_handler(commands=['top'])
async def cmd_top(message: types.Message):
    recipes = get_recipes(limit=5)
    if not recipes:
        await message.answer("Пока нет рецептов 😅 Добавь свой с помощью кнопки ➕")
        return
    for r in recipes:
        recipe_id, _, username, title, desc, photo, likes = r
        caption = f"🍽 {title}\n👤 @{username or 'anon'}\n❤️ {likes}\n\n{desc}"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❤️ Лайк", callback_data=f"like_{recipe_id}"))
        await bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("like_"))
async def cb_like(call: types.CallbackQuery):
    recipe_id = int(call.data.split("_")[1])
    like_recipe(recipe_id)
    await call.answer("❤️ Лайк засчитан!")

# === СТАРТ WEBHOOK ===
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(dp):
    logging.warning("Удаляем webhook...")
    await bot.delete_webhook()

if __name__ == "__main__":
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
