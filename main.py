import asyncio
import os
import random
import sqlite3
from contextlib import closing
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "pokura.db")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Add BOT_TOKEN in Railway Variables.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(db()) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            chat_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(chat_id, name)
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            chat_id INTEGER PRIMARY KEY,
            last_winner TEXT
        )
        """)
        conn.commit()


def normalize_name(name: str) -> str:
    return " ".join((name or "").strip().split())[:40]


def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить", callback_data="spin")],
        [InlineKeyboardButton(text="👥 Участники", callback_data="list"), InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="➕ Как добавить", callback_data="help_add"), InlineKeyboardButton(text="🧹 Сброс рейтинга", callback_data="reset_rating")],
    ])


def confirm_reset_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сбросить рейтинг", callback_data="reset_rating_confirm")],
        [InlineKeyboardButton(text="↩️ Отмена", callback_data="menu")],
    ])


def get_participants(chat_id: int):
    with closing(db()) as conn:
        return conn.execute(
            "SELECT name, wins FROM participants WHERE chat_id=? ORDER BY name COLLATE NOCASE",
            (chat_id,),
        ).fetchall()


def add_participant(chat_id: int, name: str):
    name = normalize_name(name)
    if not name:
        return False, "Напиши имя: /add Вася"
    with closing(db()) as conn:
        try:
            conn.execute(
                "INSERT INTO participants(chat_id, name, wins) VALUES(?, ?, 0)",
                (chat_id, name),
            )
            conn.commit()
            return True, f"Добавил: <b>{name}</b>"
        except sqlite3.IntegrityError:
            return False, f"<b>{name}</b> уже есть в списке."


def remove_participant(chat_id: int, name: str):
    name = normalize_name(name)
    if not name:
        return False
    with closing(db()) as conn:
        cur = conn.execute(
            "DELETE FROM participants WHERE chat_id=? AND lower(name)=lower(?)",
            (chat_id, name),
        )
        conn.commit()
        return cur.rowcount > 0


def list_text(chat_id: int) -> str:
    rows = get_participants(chat_id)
    if not rows:
        return "👥 Участников пока нет.\n\nДобавь так: <code>/add Вася</code>"
    lines = [f"👥 <b>Участники:</b> {len(rows)}"]
    for i, row in enumerate(rows, 1):
        lines.append(f"{i}. {row['name']}")
    return "\n".join(lines)


def rating_text(chat_id: int) -> str:
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT name, wins FROM participants WHERE chat_id=? ORDER BY wins DESC, name COLLATE NOCASE",
            (chat_id,),
        ).fetchall()
        last = conn.execute("SELECT last_winner FROM meta WHERE chat_id=?", (chat_id,)).fetchone()
    if not rows:
        return "🏆 Рейтинг пуст.\n\nДобавь участников: <code>/add Имя</code>"
    lines = ["🏆 <b>Рейтинг «Колесо Покура»</b>"]
    if last and last["last_winner"]:
        lines.append(f"Последний победитель: 🥇 <b>{last['last_winner']}</b>\n")
    for i, row in enumerate(rows, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
        lines.append(f"{medal} {row['name']} — <b>{row['wins']}</b>")
    return "\n".join(lines)


async def spin_and_answer(message: Message):
    rows = get_participants(message.chat.id)
    if len(rows) < 2:
        await message.answer("Нужно минимум 2 участника.\n\nДобавь: <code>/add Имя</code>", reply_markup=menu())
        return
    winner = random.choice([row["name"] for row in rows])
    with closing(db()) as conn:
        conn.execute("UPDATE participants SET wins=wins+1 WHERE chat_id=? AND name=?", (message.chat.id, winner))
        conn.execute(
            """
            INSERT INTO meta(chat_id, last_winner) VALUES(?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET last_winner=excluded.last_winner
            """,
            (message.chat.id, winner),
        )
        conn.commit()
    await message.answer(f"🎰 <b>Колесо Покура</b>\n\n🥇 Выпало: <b>{winner}</b>", reply_markup=menu())


async def home(message: Message):
    await message.answer(
        "🎰 <b>Колесо Покура</b>\n\n"
        "Общий список и общий рейтинг для этого Telegram-чата.\n\n"
        "➕ Добавить: <code>/add Имя</code>\n"
        "➖ Удалить: <code>/remove Имя</code>\n"
        "🎰 Крутить: <code>/spin</code>",
        reply_markup=menu(),
    )


@dp.message(Command("start", "menu"))
async def cmd_start(message: Message):
    await home(message)


@dp.message(Command("add"))
async def cmd_add(message: Message):
    ok, text = add_participant(message.chat.id, message.text.partition(" ")[2])
    await message.answer(("✅ " if ok else "⚠️ ") + text, reply_markup=menu())


@dp.message(Command("remove", "del"))
async def cmd_remove(message: Message):
    name = message.text.partition(" ")[2]
    if not normalize_name(name):
        await message.answer("Напиши так: <code>/remove Вася</code>", reply_markup=menu())
        return
    ok = remove_participant(message.chat.id, name)
    await message.answer("✅ Удалил." if ok else "⚠️ Не нашёл такое имя.", reply_markup=menu())


@dp.message(Command("list"))
async def cmd_list(message: Message):
    await message.answer(list_text(message.chat.id), reply_markup=menu())


@dp.message(Command("rating"))
async def cmd_rating(message: Message):
    await message.answer(rating_text(message.chat.id), reply_markup=menu())


@dp.message(Command("spin"))
async def cmd_spin(message: Message):
    await spin_and_answer(message)


@dp.message(Command("reset_rating"))
async def cmd_reset(message: Message):
    await message.answer("Сбросить рейтинг? Участники останутся.", reply_markup=confirm_reset_menu())


@dp.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    await home(call.message)
    await call.answer()


@dp.callback_query(F.data == "help_add")
async def cb_help_add(call: CallbackQuery):
    await call.message.answer("Добавить участника:\n<code>/add Вася</code>\n\nУдалить:\n<code>/remove Вася</code>", reply_markup=menu())
    await call.answer()


@dp.callback_query(F.data == "list")
async def cb_list(call: CallbackQuery):
    await call.message.answer(list_text(call.message.chat.id), reply_markup=menu())
    await call.answer()


@dp.callback_query(F.data == "rating")
async def cb_rating(call: CallbackQuery):
    await call.message.answer(rating_text(call.message.chat.id), reply_markup=menu())
    await call.answer()


@dp.callback_query(F.data == "spin")
async def cb_spin(call: CallbackQuery):
    await spin_and_answer(call.message)
    await call.answer()


@dp.callback_query(F.data == "reset_rating")
async def cb_reset(call: CallbackQuery):
    await call.message.answer("Сбросить рейтинг? Участники останутся.", reply_markup=confirm_reset_menu())
    await call.answer()


@dp.callback_query(F.data == "reset_rating_confirm")
async def cb_reset_confirm(call: CallbackQuery):
    with closing(db()) as conn:
        conn.execute("UPDATE participants SET wins=0 WHERE chat_id=?", (call.message.chat.id,))
        conn.execute(
            """
            INSERT INTO meta(chat_id, last_winner) VALUES(?, NULL)
            ON CONFLICT(chat_id) DO UPDATE SET last_winner=NULL
            """,
            (call.message.chat.id,),
        )
        conn.commit()
    await call.message.answer("✅ Рейтинг сброшен. Участники остались.", reply_markup=menu())
    await call.answer()


async def health(request):
    return web.Response(text="Колесо Покура bot is running")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Health server started on port {PORT}", flush=True)


async def main():
    init_db()
    print("DB initialized", flush=True)
    me = await bot.get_me()
    print(f"Bot started: @{me.username}", flush=True)
    await start_web_server()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
