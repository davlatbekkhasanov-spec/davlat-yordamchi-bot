import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ================== SOZLAMALAR ==================

API_TOKEN = 8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI

GROUP_ID = -1001877019294

MANAGER_IDS = [
    5732350707,  # 1-rahbar
    5732350707,  # 2-rahbar (bir xil bo‘lsa ham muammo yo‘q)
    5732350707   # 3-rahbar
]

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
    "Пересчет товаров",
]

# ================== LOG ==================

logging.basicConfig(level=logging.INFO)

# ================== BOT ==================

bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

scheduler = AsyncIOScheduler(timezone=timezone("Asia/Tashkent"))

# ================== YORDAMCHI ==================

def build_report(date_str: str) -> str:
    text = f"📋 <b>KUNLIK HISOBOT — {date_str}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for sec in SECTIONS:
            text += f"{sec}: ( )\n"
        text += "\n"
    return text

# ================== BUYRUQLAR ==================

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "✅ Bot ishlayapti.\n"
        "/test_report — test shablon\n"
        "⏰ Hisobotlar har kuni 19:30 da yuboriladi."
    )

@dp.message(Command("test_report"))
async def test_report(message: Message):
    if message.chat.id != GROUP_ID:
        await message.answer("❌ Bu buyruq faqat guruhda ishlaydi.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    await message.answer(build_report(today))

# ================== AVTO HISOBOT ==================

async def send_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    await bot.send_message(
        GROUP_ID,
        build_report(today)
    )

async def send_summary():
    await bot.send_message(
        GROUP_ID,
        "📊 <b>ERTALABGI NATIJALAR</b>\n\n(Hozircha test rejim)"
    )

# ================== ISHGA TUSHIRISH ==================

async def main():
    scheduler.add_job(send_daily_report, "cron", hour=19, minute=30)
    scheduler.add_job(send_summary, "cron", hour=7, minute=0)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
