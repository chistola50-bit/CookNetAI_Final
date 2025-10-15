import logging
import asyncio
from datetime import datetime, timedelta, time
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

from config import TOKEN, COOKNET_URL
from database import (
    init_db, upsert_user,
    add_recipe, get_recipes, like_recipe, get_random_recipe,
    set_chat_sub, set_daily_sub,
    get_chat_subscribers_chat_ids, get_daily_subscribers_chat_ids,
    save_chat_message, get_recent_chat_messages
)

# Настройка логов
logging.basicConfig(level=logging.INFO)

# --- Настройки ---
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

# URL для Render (замени, если нужно)
WEBHOOK_HOST = "https://cooknet-ai.onrender.com"  # сюда впиши адрес Render
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# --- Клавиатуры ---
def main_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🍳 Открыть CookNet", url=COOKNET_URL),
        InlineKeyboardButton("🏆 Топ рецептов", callback_data="top"),
        InlineKeyboardButton("💬 Общий чат", callback_data="chat_on")
    )
    return kb

# --- Команды ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    upsert_user(message.from_user.id, message.from_user.username, message.chat.id)
    await message.answer(
        "👋 Привет, шеф!\n\n"
        "Добро пожаловать в CookNet AI 🍳\n"
        "Здесь можно делиться рецептами, лайкать и общаться с другими поварами!",
        reply_markup=main_keyboard()
    )

@dp.message_handler(commands=['add'])
async def cmd_add(message: types.Message):
    await message.answer("📸 Отправь фото блюда для добавления рецепта.")
    dp.register_message_handler(handle_photo_step, content_types=['photo'], chat_id=message.chat.id, once=True)

async def handle_photo_step(message: types.Message):
    if not message.photo:
        await message.answer("Нужно фото 📷. Введите /add ещё раз.")
        return
    photo_id = message.photo[-1].file_id
    await message.answer("✏️ Теперь отправь название блюда.")
    dp.register_message_handler(lambda m: handle_title_step(m, photo_id), chat_id=message.chat.id, once=True)

async def handle_title_step(message: types.Message, photo_id):
    title = message.text.strip()
    await message.answer("📝 Отправь описание блюда.")
    dp.register_message_handler(lambda m: handle_desc_step(m, photo_id, title), chat_id=message.chat.id, once=True)

async def handle_desc_step(message: types.Message, photo_id, title):
    desc = message.text.strip()
    add_recipe(message.from_user.id, message.from_user.username, title, desc, photo_id)
    await message.answer("✅ Рецепт сохранён! Спасибо, шеф 👨‍🍳")

# --- Топ рецептов ---
async def show_top(chat_id):
    recipes = get_recipes(limit=5)
    if not recipes:
        await bot.send_message(chat_id, "Пока нет рецептов 😅 Добавь свой с помощью /add")
        return
    for r in recipes:
        recipe_id, user_id, username, title, description, photo, likes = r
        caption = f"🍽 {title}\n👤 @{username or 'anon'}\n❤️ {likes}\n\n{description}"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❤️ Лайк", callback_data=f"like_{recipe_id}"))
        await bot.send_photo(chat_id, photo, caption=caption, reply_markup=kb)

@dp.message_handler(commands=['top'])
async def cmd_top(message: types.Message):
    await show_top(message.chat.id)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("like_"))
async def cb_like(call: types.CallbackQuery):
    recipe_id = int(call.data.split("_")[1])
    like_recipe(recipe_id)
    await call.answer("❤️ Лайк засчитан!")

# --- Чат ---
@dp.callback_query_handler(lambda c: c.data == "chat_on")
async def cb_chat_on(call: types.CallbackQuery):
    set_chat_sub(call.from_user.id, True)
    await call.message.answer("✅ Вы вошли в общий чат.\nНапишите команду:\n/chat ваш_текст")
    await call.answer()

@dp.message_handler(commands=['chat'])
async def cmd_chat(message: types.Message):
    upsert_user(message.from_user.id, message.from_user.username, message.chat.id)
    text = message.text.replace("/chat", "", 1).strip()
    if not text:
        await message.answer("Напиши так: /chat ваш_текст")
        return

    save_chat_message(message.from_user.id, message.from_user.username, text)
    subscribers = get_chat_subscribers_chat_ids(exclude_user_id=message.from_user.id)
    if not subscribers:
        await message.answer("Пока в чате никого нет. Пригласите друзей 😉")
        return

    out = f"👤 @{message.from_user.username or 'user'}:\n{text}"
    for chat_id in subscribers:
        try:
            await bot.send_message(chat_id, out)
        except Exception:
            pass
    await message.answer("✅ Отправлено в общий чат")

# --- Webhook сервер ---
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(app):
    logging.warning("Shutting down...")
    await bot.delete_webhook()
    await bot.session.close()

async def handle_webhook(request):
    update = await request.json()
    update = types.Update(**update)
    await dp.process_update(update)
    return web.Response()

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=10000)
