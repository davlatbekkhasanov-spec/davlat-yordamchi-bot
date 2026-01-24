import asyncio
import logging
import os
from datetime import datetime

import pytz
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== SOZLAMALAR ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN ENV da yo‘q")

GROUP_ID = -1001877019294  # <-- GURUH ID

ADMINS = {
    5732350707,
    2624538,
    6991673998,
    1432810519,
}

TIMEZONE = pytz.timezone("Asia/Tashkent")

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

# ================== STORAGE ==================
daily_data = {}
user_waiting = {}

# ================== INIT ==================
logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ================== HELPERS ==================
def today_key():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


def init_day(date):
    if date not in daily_data:
        daily_data[date] = {}
        for emp in EMPLOYEES:
            daily_data[date][emp] = {task: None for task in TASKS}


def build_report(date, title):
    init_day(date)
    text = f"📊 <b>{title}</b> — {date}\n\n"

    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for task in TASKS:
            val = daily_data[date][emp][task]
            text += f"{task}: ({val if val is not None else ''})\n"
        text += "\n"

    return text


def build_keyboard(date):
    rows = []
    for emp in EMPLOYEES:
        for task in TASKS:
            rows.append([
                InlineKeyboardButton(
                    text=f"{emp} — {task}",
                    callback_data=f"fill|{date}|{emp}|{task}"
                )
            ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================== COMMANDS ==================
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    await msg.answer("✅ Bot REAL rejimda ishlayapti.")


@dp.message(Command("test"))
async def test_cmd(msg: Message):
    if msg.from_user.id not in ADMINS:
        return

    parts = msg.text.split()
    if len(parts) != 2 or parts[1] not in {"1", "2"}:
        await msg.answer("/test 1 yoki /test 2")
        return

    date = today_key()
    title = "TEST HISOBOT"

    if parts[1] == "1":
        await bot.send_message(GROUP_ID, build_report(date, title))
    else:
        await bot.send_message(
            GROUP_ID,
            build_report(date, title),
            reply_markup=build_keyboard(date)
        )


# ================== CALLBACK ==================
@dp.callback_query(F.data.startswith("fill|"))
async def fill_callback(call: CallbackQuery):
    _, date, emp, task = call.data.split("|")

    user_waiting[call.from_user.id] = (emp, task, date)

    await call.answer()
    await bot.send_message(
        call.from_user.id,
        f"<b>{emp}</b>\n<b>{task}</b> sonini kiriting:"
    )


# ================== PRIVATE CHAT INPUT ==================
@dp.message(F.chat.type == "private")
async def private_input(msg: Message):
    if msg.from_user.id not in user_waiting:
        return

    if not msg.text.isdigit():
        await msg.answer("❌ Faqat raqam kiriting.")
        return

    value = int(msg.text)
    emp, task, date = user_waiting.pop(msg.from_user.id)

    init_day(date)
    daily_data[date][emp][task] = value

    await msg.answer("✅ Saqlandi.")


# ================== REAL HISOBOT ==================
async def send_real_report():
    date = today_key()
    await bot.send_message(
        GROUP_ID,
        build_report(date, "KUNLIK HISOBOT"),
        reply_markup=build_keyboard(date)
    )


# ================== SCHEDULER ==================
async def on_startup():
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(send_real_report, "cron", hour=7, minute=0)
    scheduler.add_job(send_real_report, "cron", hour=19, minute=30)
    scheduler.start()
    logging.info("Scheduler started")


# ================== MAIN ==================
async def main():
    await on_startup()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
