import asyncio
import logging
from datetime import datetime, time as dtime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import os
from dotenv import load_dotenv

# ===================== ENV =====================
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

# ===================== LOG =====================
logging.basicConfig(level=logging.INFO)

# ===================== BOT =====================
bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ===================== ADMINS =====================
ADMINS = [
    1432810519,   # sen
    2624538,      # xo‘jayin
    5732350707     # 3-rahbar (keyin o‘zgartirasan)
]

# ===================== DATA =====================
EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To‘lqim",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ruziboev Sardor",
    "Samandar Foto",
    "Mustafoev Abdullo",
    "Rajabboev Pulat"
]

SECTIONS = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Уборка",
    "Счет ТСД",
    "Фасовка",
    "Услуга",
    "Выгрузка/отгрузка",
    "Доставка",
    "Переоценка",
    "Акт пересортица",
    "Пересчет товаров"
]

# ===================== STORAGE =====================
daily_data = {}
waiting_input = {}
report_message_id = None

# ===================== HELPERS =====================
def today_key():
    return datetime.now().strftime("%Y-%m-%d")

def init_day():
    key = today_key()
    if key not in daily_data:
        daily_data[key] = {}
        for emp in EMPLOYEES:
            daily_data[key][emp] = {s: None for s in SECTIONS}

def build_report_text():
    key = today_key()
    text = f"📊 <b>KUNLIK HISOBOT — {key}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for s in SECTIONS:
            val = daily_data[key][emp][s]
            if val is None:
                text += f"{s}: ( )\n"
            else:
                text += f"{s}: ( <b>{val}</b> )\n"
        text += "\n"
    return text

def build_keyboard():
    rows = []
    for emp in EMPLOYEES:
        for s in SECTIONS:
            rows.append([
                InlineKeyboardButton(
                    text=f"{emp} • {s}",
                    callback_data=f"set|{emp}|{s}"
                )
            ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===================== COMMANDS =====================
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    await msg.answer(
        "✅ Bot ishlayapti.\n"
        "/test_report — test shablon\n"
        "⏰ Hisobotlar har kuni 19:30 da yuboriladi."
    )

@dp.message(Command("test_report"))
async def test_report(msg: Message):
    if msg.chat.id != GROUP_ID:
        await msg.answer("Bu buyruq faqat guruhda.")
        return

    init_day()
    global report_message_id
    sent = await bot.send_message(
        GROUP_ID,
        build_report_text(),
        reply_markup=build_keyboard()
    )
    report_message_id = sent.message_id

# ===================== CALLBACK =====================
@dp.callback_query(F.data.startswith("set|"))
async def set_value(cb: CallbackQuery):
    if cb.from_user.id not in ADMINS:
        await cb.answer("⛔ Ruxsat yo‘q", show_alert=True)
        return

    _, emp, section = cb.data.split("|", 2)
    waiting_input[cb.from_user.id] = (emp, section)

    await cb.message.answer(
        f"<b>{emp}</b>\n"
        f"{section} uchun raqam kiriting:"
    )
    await cb.answer()

# ===================== NUMBER INPUT =====================
@dp.message(F.text.regexp(r"^\d+$"))
async def number_input(msg: Message):
    uid = msg.from_user.id
    if uid not in waiting_input:
        return

    emp, section = waiting_input.pop(uid)
    init_day()
    daily_data[today_key()][emp][section] = int(msg.text)

    global report_message_id
    if report_message_id:
        await bot.edit_message_text(
            build_report_text(),
            GROUP_ID,
            report_message_id,
            reply_markup=build_keyboard()
        )

    await msg.answer("✅ Saqlandi.")

# ===================== SCHEDULER =====================
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

async def send_daily_report():
    init_day()
    global report_message_id
    sent = await bot.send_message(
        GROUP_ID,
        build_report_text(),
        reply_markup=build_keyboard()
    )
    report_message_id = sent.message_id

async def send_summary():
    key = today_key()
    if key not in daily_data:
        return

    text = f"📈 <b>NATIJALAR — {key}</b>\n\n"
    for emp in EMPLOYEES:
        total = sum(v for v in daily_data[key][emp].values() if v)
        text += f"{emp}: <b>{total}</b>\n"

    await bot.send_message(GROUP_ID, text)

scheduler.add_job(send_daily_report, CronTrigger(hour=19, minute=30))
scheduler.add_job(send_summary, CronTrigger(hour=7, minute=0))

# ===================== MAIN =====================
async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
