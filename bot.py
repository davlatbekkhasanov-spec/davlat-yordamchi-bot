import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN topilmadi. Railway Variables ni tekshir!")
if not GROUP_ID:
    raise RuntimeError("❌ GROUP_ID topilmadi. Railway Variables ni tekshir!")

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ================== DATA ==================
EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To'lqim",
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

REPORT_DATA = {}

# ================== HELPERS ==================
def report_text():
    text = f"📊 <b>KUNLIK HISOBOT — {datetime.now().date()}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for f in FIELDS:
            val = REPORT_DATA.get(emp, {}).get(f, "")
            text += f"{f}: ( {val} )\n"
        text += "\n"
    return text

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
    await bot.send_message(GROUP_ID, report_text())

# ================== SCHEDULER ==================
async def daily_report():
    while True:
        now = datetime.now()
        target = now.replace(hour=19, minute=30, second=0, microsecond=0)
        if now >= target:
            target = target.replace(day=now.day + 1)

        await asyncio.sleep((target - now).total_seconds())
        await bot.send_message(GROUP_ID, report_text())

# ================== MAIN ==================
async def main():
    asyncio.create_task(daily_report())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
