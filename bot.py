import os
import asyncio
import logging
import sqlite3
from datetime import datetime, date, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


# ============================================================
# CONFIG
# ============================================================

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI")

GROUP_ID = int(os.getenv("GROUP_ID", "-1001877019294"))

ADMINS = {5732350707, 2624538, 6991673998, 1432810519}

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To'lqin",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ravshanov Ziyodullo",
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
    "Пересчет товаров",
    "Места хр"
]

# PINлар (ходимларга берилади)
EMPLOYEE_PINS = {
    "Sagdullaev Yunus": "1111",
    "Toxirov Muslimbek": "2222",
    "Ravshanov Oxunjon": "3333",
    "Samadov To'lqin": "4444",
    "Shernazarov Tolib": "5555",
    "Ruziboev Sindor": "6666",
    "Ravshanov Ziyodullo": "7777",
    "Samandar Foto": "8888",
    "Mustafoev Abdullo": "9999",
    "Rajabboev Pulat": "0000",
}


# ============================================================
# BOT
# ============================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ============================================================
# DB
# ============================================================

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,              -- YYYY-MM-DD
    period TEXT NOT NULL,           -- YYYY-MM (period starts on 2nd)
    tg_id INTEGER NOT NULL,
    employee TEXT NOT NULL,
    category TEXT NOT NULL,
    value INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS employee_links (
    tg_id INTEGER PRIMARY KEY,
    employee TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS employee_pins (
    employee TEXT PRIMARY KEY,
    pin TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS monthly_plans (
    period TEXT NOT NULL,
    employee TEXT NOT NULL,
    category TEXT NOT NULL,
    plan_value INTEGER NOT NULL,
    PRIMARY KEY (period, employee, category)
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_period_emp_cat ON reports(period, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_day_emp_cat ON reports(day, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_tgid_created ON reports(tg_id, created_at)")
conn.commit()


def seed_pins():
    for emp, pin in EMPLOYEE_PINS.items():
        cur.execute("INSERT OR REPLACE INTO employee_pins(employee, pin) VALUES (?, ?)", (emp, pin))
    conn.commit()


# ============================================================
# KEYBOARDS
# ============================================================

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CATEGORIES] + [[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )

def after_save_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Yana kategoriya"), KeyboardButton(text="✅ Yakunlash")],
            [KeyboardButton(text="↩️ Undo"), KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )


# ============================================================
# HELPERS
# ============================================================

user_state: dict[int, dict] = {}

def is_private(m: Message) -> bool:
    return m.chat.type == "private"

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def get_linked_employee(tg_id: int):
    cur.execute("SELECT employee FROM employee_links WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    return row[0] if row else None

def get_period_key(d: date | None = None) -> str:
    """
    Period har oy 2-sanadan boshlanadi.
    1-sana -> oldingi oy periodiga kiradi.
    """
    d = d or date.today()
    if d.day >= 2:
        return d.strftime("%Y-%m")
    prev = d.replace(day=1) - timedelta(days=1)
    return prev.strftime("%Y-%m")

def sum_day(day_iso: str, employee: str, category: str) -> int:
    cur.execute("""
        SELECT COALESCE(SUM(value),0) FROM reports
        WHERE day = ? AND employee = ? AND category = ?
    """, (day_iso, employee, category))
    return int(cur.fetchone()[0] or 0)

def sum_day_total(day_iso: str, employee: str) -> int:
    cur.execute("""
        SELECT COALESCE(SUM(value),0) FROM reports
        WHERE day = ? AND employee = ?
    """, (day_iso, employee))
    return int(cur.fetchone()[0] or 0)

def sum_period(period: str, employee: str, category: str) -> int:
    cur.execute("""
        SELECT COALESCE(SUM(value),0) FROM reports
        WHERE period = ? AND employee = ? AND category = ?
    """, (period, employee, category))
    return int(cur.fetchone()[0] or 0)

def sum_period_total(period: str, employee: str) -> int:
    cur.execute("""
        SELECT COALESCE(SUM(value),0) FROM reports
        WHERE period = ? AND employee = ?
    """, (period, employee))
    return int(cur.fetchone()[0] or 0)

def day_has_any(day_iso: str, employee: str, category: str) -> bool:
    cur.execute("""
        SELECT 1 FROM reports
        WHERE day = ? AND employee = ? AND category = ?
        LIMIT 1
    """, (day_iso, employee, category))
    return cur.fetchone() is not None

def get_plan(period: str, employee: str, category: str) -> int | None:
    cur.execute("""
        SELECT plan_value FROM monthly_plans
        WHERE period = ? AND employee = ? AND category = ?
    """, (period, employee, category))
    row = cur.fetchone()
    return int(row[0]) if row else None

def motivational(delta: int) -> str:
    if delta >= 10:
        return "🔥 Zo‘r! Bugun temp juda baland!"
    if delta >= 1:
        return "👏 Juda yaxshi! Kechagidan yuqori!"
    if delta == 0:
        return "💪 Barqaror! Ozgina bosim bersak, yanada zo‘r bo‘ladi!"
    if delta <= -10:
        return "🫶 Hech gap yo‘q. Bugun sal pastroq, ertaga qaytarib olamiz!"
    return "🙂 Bugun sal kamroq. Ruhni tushirmaymiz — tempni yana oshiramiz!"

def box(lines: list[str], title: str | None = None) -> str:
    lines = [("" if x is None else str(x)) for x in lines]
    if title:
        lines = [title, *lines]

    width = max([len(x) for x in lines] + [0])
    top = "┏" + "━" * (width + 2) + "┓"
    mid = ["┃ " + ln.ljust(width) + " ┃" for ln in lines]
    bottom = "┗" + "━" * (width + 2) + "┛"
    return "<pre>" + "\n".join([top, *mid, bottom]) + "</pre>"

async def safe_group_send(html_text: str):
    try:
        await bot.send_message(GROUP_ID, html_text, parse_mode="HTML")
    except Exception as e:
        logging.exception("Groupga yuborishda xatolik: %s", e)


# ============================================================
# LINK / START / CANCEL
# ============================================================

@dp.message(Command("link"))
async def link_employee(message: Message):
    if not is_private(message):
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("✅ Ulanish uchun: <b>/link 1234</b>", parse_mode="HTML")
        return

    pin = parts[1]
    cur.execute("SELECT employee FROM employee_pins WHERE pin = ?", (pin,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ PIN noto‘g‘ri. Adminдан PIN сўранг.")
        return

    employee = row[0]
    cur.execute("INSERT OR REPLACE INTO employee_links(tg_id, employee) VALUES (?, ?)",
                (message.from_user.id, employee))
    conn.commit()

    await message.answer(f"✅ Ulandingiz: <b>{employee}</b>\nEndi /start bosing.", parse_mode="HTML")


@dp.message(Command("start"))
async def start(message: Message):
    if not is_private(message):
        return

    emp = get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer(
            "Siz hali ulanmagansiz.\nAdmin bergan PIN bilan ulang:\n<b>/link 1234</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user_state[message.from_user.id] = {"employee": emp, "session": []}
    await message.answer(
        f"✅ Salom, <b>{emp}</b>!\n📌 Ish turini tanlang:",
        parse_mode="HTML",
        reply_markup=categories_kb()
    )


@dp.message(Command("cancel"))
async def cancel_cmd(message: Message):
    if not is_private(message):
        return
    user_state.pop(message.from_user.id, None)
    await message.answer("Bekor qilindi. /start", reply_markup=ReplyKeyboardRemove())


@dp.message(lambda m: is_private(m) and m.text == "❌ Bekor qilish")
async def cancel_btn(message: Message):
    user_state.pop(message.from_user.id, None)
    await message.answer("Bekor qilindi. /start", reply_markup=ReplyKeyboardRemove())


# ============================================================
# CATEGORY -> NUMBER (NO GROUP SPAM)
# ============================================================

@dp.message(lambda m: is_private(m) and m.text in CATEGORIES)
async def select_category(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        await message.answer("Avval /start bosing.")
        return
    state["category"] = message.text
    await message.answer("✍️ Raqam kiriting (faqat son):", reply_markup=ReplyKeyboardRemove())


@dp.message(lambda m: is_private(m) and m.text and m.text.isdigit())
async def save_number(message: Message):
    state = user_state.get(message.from_user.id)
    if not state or "employee" not in state or "category" not in state:
        await message.answer("Avval /start bosing.")
        return

    emp = state["employee"]
    cat = state["category"]
    add_val = int(message.text)

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)
    now_iso = datetime.now().isoformat(timespec="seconds")

    cur.execute("""
        INSERT INTO reports(day, period, tg_id, employee, category, value, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (today_iso, period, message.from_user.id, emp, cat, add_val, now_iso))
    conn.commit()

    today_sum = sum_day(today_iso, emp, cat)
    period_sum = sum_period(period, emp, cat)

    # yday message without confusion
    yday_exists = day_has_any(yday_iso, emp, cat)
    if yday_exists:
        yday_sum = sum_day(yday_iso, emp, cat)
        delta = today
