import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

logging.basicConfig(level=logging.INFO)

# ================== BOT ==================
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ================== DATA ==================
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
    "Rajabboev Pulat",
]

FIELDS = [
    "Приход",
    "Перемещение",
    "Фото тмц",
    "Уборка",
    "Счет ТСД",
    "Фасовка",
    "Услуга",
    "Выгрузка/отгрузка",
    "Доставка",
    "Переоценка",
    "Акт пересортица",
    "Пересчет товаров",
]

# vaqtincha RAM da (keyin DB qilamiz)
reports = {}

# ================== HELPERS ==================
def build_template():
    text = "📋 <b>KUNLIK HISOBOT</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for f in FIELDS:
            text += f"{f}: ( )\n"
        text += "\n"
    return text

def build_summary():
    text = "📊 <b>NATIJALAR</b>\n\n"
    for emp, data in reports.items():
        text += f"<b>{emp}</b>\n"
        for k, v in data.items():
            text += f"{k}: {v}\n"
        text += "\n"
    return text if reports else "❗️Ma’lumot kiritilmadi"

# ================== COMMANDS ==================
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "✅ Bot ishlayapti.\n"
        "/test_report — test shablon\n"
        "Hisobotlar har kuni 19:30 da yuboriladi."
    )

@dp.message(Command("test_report"))
async def test_report(message: Message):
    await message.answer(build_template())

# ================== SCHEDULER TASKS ==================
async def send_daily_template():
    try:
        await bot.send_message(GROUP_ID, build_template())
    except Exception as e:
        logging.error(f"Template error: {e}")

async def send_daily_summary():
    try:
        await bot.send_message(GROUP_ID, build_summary())
        reports.clear()
    except Exception as e:
        logging.error(f"Summary error: {e}")

# ================== TEXT HANDLER (NUMBER INPUT) ==================
@dp.message(F.text.regexp(r"\d+"))
async def handle_numbers(message: Message):
    name = message.from_user.full_name
    if name not in reports:
        reports[name] = {}

    reports[name]["Kiritilgan"] = reports[name].get("Kiritilgan", 0) + int(message.text)
    await message.reply("✅ Qabul qilindi")

# ================== MAIN ==================
async def main():
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

    scheduler.add_job(send_daily_template, "cron", hour=19, minute=30)
    scheduler.add_job(send_daily_summary, "cron", hour=7, minute=0)

    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
