import asyncio
import logging
from datetime import datetime, time
import pytz
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

# ================== CONFIG ==================
BOT_TOKEN = "8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI"
GROUP_ID = -1001877019294  # GURUH ID
TIMEZONE = pytz.timezone("Asia/Tashkent")

ADMINS = {
    5732350707,
    2624538,
    6991673998,
    1432810519
}

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To‘lqin",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ruziboev Sardor",
    "Samandar Foto",
    "Mustafoev Abdullo",
    "Rajabboev Pulat"
]

WORKS = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Счет ТСД",
    "Фасовка",
    "Услуга",
    "Доставка",
    "Переоценка",
    "Акт пересортица",
    "Пересчет товаров",
]

DB = "data.db"

# ================== INIT ==================
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ================== DB ==================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            date TEXT,
            employee TEXT,
            work TEXT,
            value INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        await db.commit()

async def save_value(date, employee, work, value):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO stats VALUES (?,?,?,?)",
            (date, employee, work, value)
        )
        await db.commit()

async def get_sum(from_date):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT employee, work, SUM(value)
        FROM stats
        WHERE date >= ?
        GROUP BY employee, work
        """, (from_date,))
        return await cur.fetchall()

# ================== REPORT ==================
async def build_report(from_date):
    data = await get_sum(from_date)
    report = {}
    for emp, work, val in data:
        report.setdefault(emp, {})[work] = val

    text = f"📊 <b>JAMLANGAN HISOBOT</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for w in WORKS:
            v = report.get(emp, {}).get(w, 0)
            text += f"{w}: ({v})\n"
        text += "\n"
    return text

# ================== KEYBOARDS ==================
def employee_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=e, callback_data=f"emp:{e}")]
            for e in EMPLOYEES
        ]
    )

def works_kb(emp):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=w, callback_data=f"work:{emp}:{w}")]
            for w in WORKS
        ]
    )

# ================== HANDLERS ==================
@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("Xodimni tanlang:", reply_markup=employee_kb())

@dp.callback_query(F.data.startswith("emp:"))
async def choose_emp(c):
    emp = c.data.split(":")[1]
    await c.message.edit_text(
        f"<b>{emp}</b>\nIsh turini tanlang:",
        reply_markup=works_kb(emp)
    )

@dp.callback_query(F.data.startswith("work:"))
async def choose_work(c):
    _, emp, work = c.data.split(":")
    await c.message.edit_text(
        f"{emp}\n<b>{work}</b>\nRaqam kiriting:"
    )
    dp.fsm.storage.data[c.from_user.id] = (emp, work)

@dp.message(F.text.regexp(r"^\d+$"))
async def save_number(m: Message):
    if m.from_user.id not in dp.fsm.storage.data:
        return
    emp, work = dp.fsm.storage.data.pop(m.from_user.id)
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    await save_value(today, emp, work, int(m.text))
    await m.answer("✅ Saqlandi.\n/start bilan davom eting")

# ================== SCHEDULER ==================
async def scheduler():
    sent_message_id = None
    while True:
        now = datetime.now(TIMEZONE)

        if now.time() == time(19, 30):
            msg = await bot.send_message(
                GROUP_ID,
                "📝 <b>YANGI KUNLIK HISOBOT BOSHLANDI</b>\nTo‘ldirish 07:29 gacha"
            )
            sent_message_id = msg.message_id

        if now.time() == time(7, 30):
            month_start = now.replace(day=3).strftime("%Y-%m-%d")
            text = await build_report(month_start)
            await bot.send_message(GROUP_ID, text)

        await asyncio.sleep(60)

# ================== TEST ==================
@dp.message(Command("test1"))
async def test1(m: Message):
    await scheduler()

@dp.message(Command("test2"))
async def test2(m: Message):
    month_start = datetime.now(TIMEZONE).replace(day=3).strftime("%Y-%m-%d")
    await m.answer(await build_report(month_start))

# ================== RUN ==================
async def main():
    await init_db()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
