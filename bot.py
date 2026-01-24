import asyncio
import logging
import sqlite3
from datetime import datetime, date
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== SOZLAMALAR ==================

TOKEN = "8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI"
GROUP_ID = -1001877019294  # HISOBOT TASHLANADIGAN GURUH ID

ADMINS = [
    5732350707,
    2624538,
    6991673998,
    1432810519
]

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To'lqin",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ruziboev Sardor",
    "Samandar Foto",
    "Mustafoev Abdullo",
    "Rajabboev Pulat"
]

CATEGORIES = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Счет ТСД",
    "Фасовка",
    "Услуга",
    "Доставка",
    "Переоценка",
    "Акт пересортица",
    "Пересчет товаров"
]

# ================== BOT ==================

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

logging.basicConfig(level=logging.INFO)

# ================== DATABASE ==================

conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    day TEXT,
    employee TEXT,
    category TEXT,
    value INTEGER
)
""")

conn.commit()

# ================== KLAVIATURALAR ==================

def employees_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=e)] for e in EMPLOYEES],
        resize_keyboard=True
    )

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CATEGORIES],
        resize_keyboard=True
    )

# ================== STATES ==================

user_state = {}

# ================== START ==================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "✅ Bot ishlayapti.\n\nXodimni tanlang:",
        reply_markup=employees_kb()
    )

# ================== EMPLOYEE TANLASH ==================

@dp.message(lambda m: m.text in EMPLOYEES)
async def select_employee(message: Message):
    user_state[message.from_user.id] = {
        "employee": message.text
    }
    await message.answer(
        "📌 Ish turini tanlang:",
        reply_markup=categories_kb()
    )

# ================== CATEGORY TANLASH ==================

@dp.message(lambda m: m.text in CATEGORIES)
async def select_category(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        return

    state["category"] = message.text
    await message.answer("✍️ Raqam kiriting:")

# ================== RAQAM KIRITISH ==================

@dp.message(lambda m: m.text.isdigit())
async def save_number(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        return

    today = date.today().isoformat()

    cur.execute(
        "INSERT INTO reports VALUES (?, ?, ?, ?)",
        (today, state["employee"], state["category"], int(message.text))
    )
    conn.commit()

    await message.answer("✅ Saqlandi. /start bilan davom eting.")

    user_state.pop(message.from_user.id, None)

# ================== HISOBOTLAR ==================

async def send_evening_report(chat_id: int):
    today = date.today().isoformat()

    text = f"📊 KUNLIK HISOBOT\n🕢 19:30\n🗓 {today}\n\n"

    for emp in EMPLOYEES:
        text += f"👤 {emp}\n"
        for cat in CATEGORIES:
            cur.execute("""
            SELECT SUM(value) FROM reports
            WHERE day = ? AND employee = ? AND category = ?
            """, (today, emp, cat))
            val = cur.fetchone()[0] or ""
            text += f"  • {cat}: ({val})\n"
        text += "\n"

    await bot.send_message(chat_id, text)

async def send_morning_report(chat_id: int):
    cur.execute("""
    SELECT employee, category, SUM(value)
    FROM reports
    GROUP BY employee, category
    """)

    rows = cur.fetchall()

    text = "📈 JAMLANGAN HISOBOT\n🕢 07:30\n\n"

    for emp in EMPLOYEES:
        text += f"👤 {emp}\n"
        for cat in CATEGORIES:
            val = next((r[2] for r in rows if r[0] == emp and r[1] == cat), "")
            text += f"  • {cat}: ({val})\n"
        text += "\n"

    await bot.send_message(chat_id, text)

# ================== TEST BUYRUQLAR ==================

@dp.message(Command("test1"))
async def test1(message: Message):
    if message.from_user.id not in ADMINS:
        return
    await send_evening_report(message.chat.id)

@dp.message(Command("test2"))
async def test2(message: Message):
    if message.from_user.id not in ADMINS:
        return
    await send_morning_report(message.chat.id)

# ================== OY BOSHI TOZALASH ==================

async def reset_month():
    if datetime.now().day == 3:
        cur.execute("DELETE FROM reports")
        conn.commit()

# ================== SCHEDULER ==================

scheduler.add_job(send_evening_report, "cron", hour=19, minute=30, args=[GROUP_ID])
scheduler.add_job(send_morning_report, "cron", hour=7, minute=30, args=[GROUP_ID])
scheduler.add_job(reset_month, "cron", hour=0, minute=0)

# ================== MAIN ==================

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
