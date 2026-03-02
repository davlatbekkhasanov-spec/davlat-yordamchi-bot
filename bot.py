import os
import asyncio
import logging
import sqlite3
from datetime import datetime, date, timedelta
import html

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


# ============================================================
# КОНФИГ
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
# БОТ
# ============================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ============================================================
# DB (SQLite hardening)
# ============================================================

conn = sqlite3.connect("data.db", check_same_thread=False, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")
conn.commit()

db_lock = asyncio.Lock()

async def db_exec(query: str, params: tuple = ()):
    async with db_lock:
        cur.execute(query, params)
        conn.commit()

async def db_fetchone(query: str, params: tuple = ()):
    async with db_lock:
        cur.execute(query, params)
        return cur.fetchone()

async def db_fetchall(query: str, params: tuple = ()):
    async with db_lock:
        cur.execute(query, params)
        return cur.fetchall()


# Tables
cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    period TEXT NOT NULL,
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


async def seed_pins():
    for emp, pin in EMPLOYEE_PINS.items():
        await db_exec(
            "INSERT OR REPLACE INTO employee_pins(employee, pin) VALUES (?, ?)",
            (emp, pin)
        )


# ============================================================
# КЛАВИАТУРА
# ============================================================

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CATEGORIES] + [[KeyboardButton(text="❌ Бекор қилиш")]],
        resize_keyboard=True
    )

def after_save_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Яна категория"), KeyboardButton(text="✅ Якунлаш")],
            [KeyboardButton(text="↩️ Ундо"), KeyboardButton(text="❌ Бекор қилиш")]
