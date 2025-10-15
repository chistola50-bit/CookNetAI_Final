import os
import logging
import threading
import asyncio
import time
from flask import Flask, request, render_template, redirect, url_for, abort
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_recipe, get_recipes, get_recipe, like_recipe, get_top_recipes
from utils import generate_caption

# ---------------- НАСТРОЙКИ ----------------
logging.basicConfig(level=logging.INFO)
app = Flask(__name__, template_folder="templates", static_folder="static")

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or "8335733549:AAFMpqifzGVVAPb_IeTpWMy8IhvSiTZEsuo"
SITE_URL = (os.getenv("COOKNET_URL") or "https://cooknetai-final.onrender.com").strip()

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{SITE_URL.rstrip('/')}{WEBHOOK_PATH}"

# ---------------- ИНИЦИАЛИЗАЦИЯ ----------------
init_db()
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------------- АНТИСПАМ + FSM АВТОСБРОС ----------------
user_last_action = {}
SPAM_DELAY = 3
STATE_TIMEOUT = 300


def is_spamming(user_id: int) -> bool:
    """Проверка на слишком частые действия"""
    now = time.time()
    last = user_last_action.get(user_id, 0)
    if now - last < SPAM_DELAY:
        return True
    user_last_action[user_id] = now
    return False


async def reset_state_if_expired(user_id, state: FSMContext):
    """Автоматический сброс FSM, если зависла"""
    data = await state.get_data()
    start_time = data.get("_start_time")
    now = time.time()
    if start_time and now - start_time > STATE_TIMEOUT:
        await state.finish()
        logging.info(f"FSM сброшено по таймауту для {user_id}")


def clean_url(url: str) -> str:
    """Удаляет пробелы и переносы"""
    return url.replace(" ", "").replace("\n", "").replace("\r", "")


# ---------------- СОСТОЯНИЯ ----------------
class AddRecipeFSM(StatesGroup):
    photo = State()
    title = State()
    desc = State()


# ---------------- КНОПКИ ----------------
def main_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    site_link = clean_url(f"{SITE_URL.rstrip('/')}/recipes")
    kb.add(
        InlineKeyboardButton("➕ Добавить рецепт", callback_data="add"),
        InlineKeyboardButton("🏆 Топ недели", callback_data="top"),
        InlineKeyboardButton("🌐 Открыть сайт", url=site_link),
    )
    return kb


# ---------------- КОМАНДЫ ----------------
@dp.message_handler(commands=['ping'])
async def cmd_ping(message: types.Message):
    await message.answer("✅ Бот активен и отвечает! 🚀")


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Это CookNet AI — делись рецептами и вдохновляйся 🍳", reply_markup=main_kb())


@dp.callback_query_handler(lambda c: c.data == "add")
async def add_start(call: types.CallbackQuery, state: FSMContext):
    if is_spamming(call.from_user.id):
        await call.answer("⏳ Подожди немного...", show_alert=True)
        return
    await call.answer()
    await state.finish()
    await AddRecipeFSM.photo.set()
    await state.update_data(_start_time=time.time())
    await bot.send_message(call.message.chat.id, "📸 Отправь фото блюда.\nЕсли передумал — /cancel")


@dp.message_handler(commands=['cancel'], state='*')
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Добавление отменено.", reply_markup=main_kb())


@dp.message_handler(content_types=['photo'], state=AddRecipeFSM.photo)
async def fsm_photo(message: types.Message, state: FSMContext):
    if is_spamming(message.from_user.id):
        return
    await reset_state_if_expired(message.from_user.id, state)
    file_id = message.photo[-1].file_id
    try:
        file = await bot.get_file(file_id)
        photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    except Exception:
        photo_url = None
    await state.update_data(photo_id=file_id, photo_url=photo_url)
    await AddRecipeFSM.next()
    await state.update_data(_start_time=time.time())
    await message.answer("🍽 Введи название блюда:")


@dp.message_handler(lambda m: not m.photo, state=AddRecipeFSM.photo, content_types=types.ContentTypes.ANY)
async def require_photo(message: types.Message):
    await message.answer("Нужно фото 📷. Отправь фото или /cancel")


@dp.message_handler(state=AddRecipeFSM.title)
async def fsm_title(message: types.Message, state: FSMContext):
    await reset_state_if_expired(message.from_user.id, state)
    title = (message.text or '').strip()
    if not title:
        await message.answer("Название не должно быть пустым. Введи название блюда.")
        return
    await state.update_data(title=title, _start_time=time.time())
    await AddRecipeFSM.next()
    await message.answer("✍️ Опиши рецепт (кратко):")


@dp.message_handler(state=AddRecipeFSM.desc)
async def fsm_desc(message: types.Message, state: FSMContext):
    if is_spamming(message.from_user.id):
        return
    await reset_state_if_expired(message.from_user.id, state)
    data = await state.get_data()
    title = data.get('title')
    description = (message.text or '').strip()
    photo_id = data.get('photo_id')
    photo_url = data.get('photo_url')
    ai_caption = generate_caption(title, description)

    add_recipe(
        username=message.from_user.username or "anon",
        title=title,
        description=description,
        photo_id=photo_id,
        photo_url=photo_url,
        ai_caption=ai_caption
    )

    await message.answer(f"✅ Рецепт сохранён!\n✨ AI-подпись: {ai_caption}", reply_markup=main_kb())
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "top")
async def cb_top(call: types.CallbackQuery):
    if is_spamming(call.from_user.id):
        await call.answer("⏳ Подожди немного...", show_alert=True)
        return
    top = get_top_recipes(limit=5)
    if not top:
        await call.message.answer("Пока нет рецептов. Добавь свой через «➕ Добавить рецепт».")
        return
    for r in top:
        caption = f"🍽 {r['title']}\n👤 @{r['username']}\n❤️ {r['likes']}\n\n{(r['ai_caption'] or r['description'] or '')[:200]}"
        if r.get("photo_id"):
            try:
                await bot.send_photo(call.message.chat.id, r['photo_id'], caption=caption)
            except Exception:
                await bot.send_message(call.message.chat.id, caption)
        else:
            await bot.send_message(call.message.chat.id, caption)


# ---------------- FLASK ----------------
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/recipes')
def recipes_page():
    return render_template('recipes.html', recipes=get_recipes(limit=60))


@app.route('/recipe/<int:rid>')
def recipe_page(rid):
    r = get_recipe(rid)
    if not r:
        abort(404)
    return render_template('recipe.html', r=r)


@app.route('/top')
def top_page():
    return render_template('top.html', recipes=get_top_recipes(limit=20))


@app.post('/like/<int:rid>')
def like_route(rid):
    like_recipe(rid)
    ref = request.referrer or url_for('recipes_page')
    return redirect(ref)


# ---------------- WEBHOOK ----------------
_loop = asyncio.new_event_loop()


def _run_loop():
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


threading.Thread(target=_run_loop, daemon=True).start()


async def _setup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")


asyncio.run_coroutine_threadsafe(_setup(), _loop)


@app.post(f"{WEBHOOK_PATH}")
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        asyncio.run_coroutine_threadsafe(_process_update(data), _loop)
        return "OK", 200
    except Exception as e:
        logging.exception(e)
        return "FAIL", 500


async def _process_update(data):
    try:
        update = types.Update(**data)
        from aiogram import Bot, Dispatcher
        Bot.set_current(bot)
        Dispatcher.set_current(dp)
        await dp.process_update(update)
    except Exception as ex:
        logging.exception(f"Ошибка обработки апдейта: {ex}")


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
