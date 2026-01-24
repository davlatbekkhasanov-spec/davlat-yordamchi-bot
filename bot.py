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
BOT_TOKEN = "PUT_YOUR_BOT_TOKEN"
GROUP_ID = -1001234567890   # guruh ID

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

DB_PATH = "reports.db"

# ================= INIT =================
logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# ================= DATABASE =================
def db_exec(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query, params)
    data = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return data

def init_db():
    db_exec("""
    CREATE TABLE IF NOT EXISTS reports (
        work_date TEXT,
        employee TEXT,
        task TEXT,
        value INTEGER
    )
    """)
    db_exec("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

# ================= FSM =================
class InputFSM(StatesGroup):
    waiting_value = State()

# ================= HELPERS =================
def get_work_date(now=None):
    now = now or datetime.now()
    if now.time() < datetime.strptime("07:30", "%H:%M").time():
        return (date.today() - timedelta(days=1)).isoformat()
    return date.today().isoformat()

def build_day_report(work_date):
    text = f"📊 <b>KUNLIK HISOBOT — {work_date}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for task in TASKS:
            r = db_exec(
                "SELECT value FROM reports WHERE work_date=? AND employee=? AND task=?",
                (work_date, emp, task),
                fetch=True
            )
            text += f"{task}: ({r[0][0] if r else ''})\n"
        text += "\n"
    return text

def build_month_report(year_month):
    text = f"📈 <b>OY JAMLANMASI — {year_month}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for task in TASKS:
            r = db_exec(
                "SELECT SUM(value) FROM reports WHERE employee=? AND task=? AND substr(work_date,1,7)=?",
                (emp, task, year_month),
                fetch=True
            )
            total = r[0][0] if r and r[0][0] else 0
            text += f"{task}: ({total})\n"
        text += "\n"
    return text

def emp_kb():
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
    await m.answer("📝 Xodimni tanlang:", reply_markup=emp_kb())

@dp.message(F.text == "/today")
async def today(m: Message):
    wd = get_work_date()
    await m.answer(build_day_report(wd))

@dp.message(F.text == "/test_open")
async def test_open(m: Message):
    await m.answer("🧪 TEST: Yangi kun ochildi (19:30)")
    await open_new_day()

@dp.message(F.text == "/test_close")
async def test_close(m: Message):
    await m.answer("🧪 TEST: Kun yopildi (07:30)")
    await morning_report()

@dp.callback_query(F.data.startswith("emp|"))
async def choose_emp(c: CallbackQuery, state: FSMContext):
    emp = c.data.split("|")[1]
    await state.update_data(emp=emp)
    await c.message.edit_text(f"<b>{emp}</b>\nIshni tanlang:", reply_markup=task_kb(emp))

@dp.callback_query(F.data.startswith("task|"))
async def choose_task(c: CallbackQuery, state: FSMContext):
    _, emp, task = c.data.split("|")
    await state.update_data(task=task)
    await state.set_state(InputFSM.waiting_value)
    await c.message.answer(f"{emp}\n<b>{task}</b>\nRaqam kiriting:")

@dp.message(InputFSM.waiting_value)
async def save_value(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("❌ Faqat raqam")
        return

    data = await state.get_data()
    wd = get_work_date()

    db_exec(
        "DELETE FROM reports WHERE work_date=? AND employee=? AND task=?",
        (wd, data["emp"], data["task"])
    )
    db_exec(
        "INSERT INTO reports VALUES (?,?,?,?)",
        (wd, data["emp"], data["task"], int(m.text))
    )

    await state.clear()
    await m.answer("✅ Saqlandi. /start bilan davom eting.")

# ================= SCHEDULE =================
async def open_new_day():
    pass  # logika get_work_date orqali yuradi

async def morning_report():
    wd = (date.today() - timedelta(days=1)).isoformat()
    ym = wd[:7]
    text = build_day_report(wd) + "\n\n" + build_month_report(ym)
    await bot.send_message(GROUP_ID, text)

async def reset_month():
    today = date.today()
    if today.day == 3:
        db_exec("DELETE FROM reports")

scheduler.add_job(open_new_day, "cron", hour=19, minute=30)
scheduler.add_job(morning_report, "cron", hour=7, minute=30)
scheduler.add_job(reset_month, "cron", hour=0, minute=0)

# ================= MAIN =================
async def main():
    init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
