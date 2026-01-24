import asyncio
import logging
import sqlite3
from datetime import datetime, date, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= CONFIG =================
BOT_TOKEN = "PUT_BOT_TOKEN_HERE"
GROUP_ID = -1001234567890

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
    "Rajabboev Pulat",
]

TASKS = [
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

# ================= INIT =================
logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# ================= DATABASE =================
db = sqlite3.connect("reports.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    work_date TEXT,
    employee TEXT,
    task TEXT,
    value INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

db.commit()

def set_meta(key, value):
    cur.execute("REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))
    db.commit()

def get_meta(key):
    cur.execute("SELECT value FROM meta WHERE key=?", (key,))
    r = cur.fetchone()
    return r[0] if r else None

# ================= FSM =================
class InputFSM(StatesGroup):
    waiting_value = State()

# ================= HELPERS =================
def current_work_date():
    now = datetime.now()
    if now.time() < datetime.strptime("07:30", "%H:%M").time():
        return (date.today() - timedelta(days=1)).isoformat()
    return date.today().isoformat()

def build_report(for_date):
    text = f"📊 <b>HISOBOT — {for_date}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for task in TASKS:
            cur.execute(
                "SELECT value FROM reports WHERE work_date=? AND employee=? AND task=?",
                (for_date, emp, task)
            )
            r = cur.fetchone()
            text += f"{task}: ({r[0] if r else ''})\n"
        text += "\n"
    return text

def build_month_sum(year_month):
    text = f"📈 <b>OY JAMLANMASI — {year_month}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for task in TASKS:
            cur.execute("""
            SELECT SUM(value) FROM reports
            WHERE employee=? AND task=? AND substr(work_date,1,7)=?
            """, (emp, task, year_month))
            s = cur.fetchone()[0]
            text += f"{task}: ({s if s else 0})\n"
        text += "\n"
    return text

def employee_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=e, callback_data=f"emp|{e}")]
        for e in EMPLOYEES
    ])

def task_kb(emp):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=f"task|{emp}|{t}")]
        for t in TASKS
    ])

# ================= USER FLOW =================
@dp.message(F.text == "/start")
async def start(m: Message):
    await m.answer(
        "📝 Hisobot kiritish uchun xodimni tanlang:",
        reply_markup=employee_kb()
    )

@dp.callback_query(F.data.startswith("emp|"))
async def choose_emp(c: CallbackQuery, state: FSMContext):
    emp = c.data.split("|")[1]
    await state.update_data(emp=emp)
    await c.message.edit_text(
        f"<b>{emp}</b>\nIshni tanlang:",
        reply_markup=task_kb(emp)
    )

@dp.callback_query(F.data.startswith("task|"))
async def choose_task(c: CallbackQuery, state: FSMContext):
    _, emp, task = c.data.split("|")
    await state.update_data(task=task)
    await state.set_state(InputFSM.waiting_value)
    await c.message.answer(
        f"{emp}\n<b>{task}</b>\nRaqam kiriting:"
    )

@dp.message(InputFSM.waiting_value)
async def save_value(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("❌ Faqat raqam kiriting")
        return

    data = await state.get_data()
    work_date = current_work_date()

    cur.execute("""
    DELETE FROM reports WHERE work_date=? AND employee=? AND task=?
    """, (work_date, data["emp"], data["task"]))

    cur.execute("""
    INSERT INTO reports VALUES (?,?,?,?)
    """, (work_date, data["emp"], data["task"], int(m.text)))

    db.commit()
    await state.clear()
    await m.answer("✅ Saqlandi. /start bosib davom etishingiz mumkin.")

# ================= SCHEDULE =================
async def morning_report():
    wd = (date.today() - timedelta(days=1)).isoformat()
    ym = wd[:7]
    text = build_report(wd) + "\n\n" + build_month_sum(ym)
    await bot.send_message(GROUP_ID, text)

async def open_new_day():
    set_meta("current_day", date.today().isoformat())

async def reset_month():
    today = date.today()
    if today.day == 3:
        cur.execute("DELETE FROM reports")
        db.commit()

scheduler.add_job(open_new_day, "cron", hour=19, minute=30)
scheduler.add_job(morning_report, "cron", hour=7, minute=30)
scheduler.add_job(reset_month, "cron", hour=0, minute=0)

# ================= MAIN =================
async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
