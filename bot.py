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

# ---------- CONFIG ----------
TOKEN = "8335733549:AAFMpqifzGVVAPb_IeTpWMy8IhvSiTZEsuo"
SITE_URL = "https://cooknetai-final.onrender.com"

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = SITE_URL.rstrip("/") + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO)

# ---------- AIOGRAM ----------
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
init_db()

# ---------- FSM ----------
class AddRecipe(StatesGroup):
    waiting_for_photo = State()
    waiting_for_title = State()
    waiting_for_desc = State()

def main_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Добавить рецепт", callback_data="add"),
        InlineKeyboardButton("🏆 Топ недели", callback_data="top"),
        InlineKeyboardButton("🌐 Открыть сайт", url=SITE_URL + "/recipes")
    )
    return kb

# ---------- HANDLERS ----------

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет, шеф!\nCookNet AI — делись рецептами и вдохновляйся 🍳",
        reply_markup=main_keyboard()
    )

# === Добавление рецепта ===
@dp.callback_query_handler(lambda c: c.data == "add")
async def cb_add_recipe(call: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await call.message.answer("⚠️ Ты уже добавляешь рецепт. Сначала закончи предыдущий.")
        return
    await call.message.answer("📸 Отправь фото блюда для добавления рецепта.")
    await AddRecipe.waiting_for_photo.set()

@dp.message_handler(content_types=["photo"], state=AddRecipe.waiting_for_photo)
async def add_recipe_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        photo_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    except Exception:
        photo_url = None
    await state.update_data(photo_id=file_id, photo_url=photo_url)
    await message.answer("✏️ Теперь отправь название блюда.")
    await AddRecipe.waiting_for_title.set()

@dp.message_handler(state=AddRecipe.waiting_for_title)
async def add_recipe_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("📝 Отправь описание блюда.")
    await AddRecipe.waiting_for_desc.set()

@dp.message_handler(state=AddRecipe.waiting_for_desc)
async def add_recipe_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    desc = message.text.strip()
    ai_caption = generate_caption(data["title"], desc)
    add_recipe(
        username=message.from_user.username or "anon",
        title=data["title"],
        desc=desc,
        photo_id=data["photo_id"],
        photo_url=data.get("photo_url"),
        ai_caption=ai_caption
    )
    await message.answer("✅ Рецепт успешно добавлен! 👨‍🍳")
    await state.finish()

# === Топ недели ===
@dp.callback_query_handler(lambda c: c.data == "top")
async def cb_top(call: types.CallbackQuery):
    top = get_top_recipes(limit=5)
    if not top:
        await call.message.answer("Пока нет рецептов. Добавь свой через «➕ Добавить рецепт».")
        return
    for r in top:
        caption = f"🍽 {r['title']}\n👤 @{r['username']}\n❤️ {r['likes']}\n\n{r['ai_caption'] or r['desc'][:120]}"
        if r["photo_id"]:
            try:
                await bot.send_photo(call.message.chat.id, r["photo_id"], caption=caption)
            except Exception:
                await bot.send_message(call.message.chat.id, caption)
        else:
            await bot.send_message(call.message.chat.id, caption)

# ---------- FLASK ----------
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
