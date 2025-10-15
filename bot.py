import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, render_template, redirect, url_for
from database import init_db, add_recipe, get_recipes, like_recipe, get_top_recipes
from utils import generate_caption

# ---------- Config ----------
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or "PUT_YOUR_TOKEN_HERE"
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000")
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = RENDER_EXTERNAL_URL.rstrip("/") + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO)

# aiogram
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# db
init_db()

# ---------- FSM for adding a recipe ----------
class RecipeForm(StatesGroup):
    photo = State()
    title = State()
    desc = State()

def main_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Добавить рецепт", callback_data="add"),
        InlineKeyboardButton("🏆 Топ недели", callback_data="top"),
        InlineKeyboardButton("🌐 Открыть сайт", url=RENDER_EXTERNAL_URL + "/recipes")
    )
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет, шеф!\nCookNet AI — делись рецептами и вдохновляйся 🍳",
        reply_markup=main_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == "add")
async def cb_add(call: types.CallbackQuery):
    await call.message.answer("📸 Отправь фото блюда:")
    await RecipeForm.photo.set()

@dp.message_handler(content_types=['photo'], state=RecipeForm.photo)
async def fsm_photo(message: types.Message, state: FSMContext):
    # Save Telegram file_id and also get a public photo_url to render on the site
    file_id = message.photo[-1].file_id
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        photo_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    except Exception:
        photo_url = None
    await state.update_data(photo_id=file_id, photo_url=photo_url)
    await RecipeForm.next()
    await message.answer("🍽 Введи название блюда:")

@dp.message_handler(state=RecipeForm.title)
async def fsm_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await RecipeForm.next()
    await message.answer("✍️ Опиши рецепт (кратко):")

@dp.message_handler(state=RecipeForm.desc)
async def fsm_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title")
    desc = message.text.strip()
    photo_id = data.get("photo_id")
    photo_url = data.get("photo_url")
    # AI caption (safe fallback if no key)
    ai_caption = generate_caption(title, desc)
    add_recipe(
        username=message.from_user.username or "anon",
        title=title,
        desc=desc,
        photo_id=photo_id,
        photo_url=photo_url,
        ai_caption=ai_caption
    )
    await message.answer(f"✅ Рецепт сохранён!\n✨ AI-подпись: {ai_caption}")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "top")
async def cb_top(call: types.CallbackQuery):
    top = get_top_recipes(limit=5)
    if not top:
        await call.message.answer("Пока нет рецептов. Добавь свой через «➕ Добавить рецепт».")
        return
    for r in top:
        # r = dict row
        caption = f"🍽 {r['title']}\n👤 @{r['username']}\n❤️ {r['likes']}\n\n{r['ai_caption'] or r['desc'][:120]}"
        if r['photo_id']:
            try:
                await bot.send_photo(call.message.chat.id, r['photo_id'], caption=caption)
            except Exception:
                await bot.send_message(call.message.chat.id, caption)
        else:
            await bot.send_message(call.message.chat.id, caption)

# ---------- Flask Site + Webhook ----------
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/recipes")
def recipes_page():
    recipes = get_recipes(limit=36)
    return render_template("recipes.html", recipes=recipes)

@app.route("/like/<int:recipe_id>", methods=["POST"])
def like(recipe_id: int):
    like_recipe(recipe_id)
    return redirect(url_for("recipes_page"))

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = types.Update(**data)
        # important for aiogram v2 context
        Bot.set_current(bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dp.process_update(update))
        loop.close()
        return "OK", 200
    except Exception as e:
        logging.exception(e)
        return "ERROR", 500

async def setup_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")

def start_app():
    asyncio.run(setup_webhook())
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    start_app()
