import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

# ================== SOZLAMALAR ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. Render Environment Variables tekshir.")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== START ==================
@dp.message(CommandStart())
async def start_handler(message: Message):
    text = (
        "👋 *Salom!*\n\n"
        "Men — *Davlat Yordamchi Bot* 🤖\n\n"
        "📦 Omborxona ishlari\n"
        "📊 Buxgalteriya\n"
        "🧾 Hisobotlar\n"
        "📈 Tahlil va maslahat\n\n"
        "Savolingni yoz — men professional yordam beraman."
    )
    await message.answer(text, parse_mode="Markdown")

# ================== UMUMIY JAVOB ==================
@dp.message()
async def universal_handler(message: Message):
    question = message.text.lower()

    if "ombor" in question:
        await message.answer(
            "📦 *Omborxona bo‘yicha yordam:*\n"
            "- Qabul\n"
            "- Chiqim\n"
            "- Qoldiq nazorati\n"
            "- Inventarizatsiya\n\n"
            "Aniq savol bering."
        )

    elif "hisobot" in question or "buxgalter" in question:
        await message.answer(
            "📊 *Buxgalteriya / Hisobotlar:*\n"
            "- Kirim-chiqim\n"
            "- Oylik hisob\n"
            "- Qoldiq hisobot\n\n"
            "Qaysi hisobot kerak?"
        )

    else:
        await message.answer(
            "❓ Savolingizni biroz aniqroq yozing.\n"
            "Men ombor, buxgalteriya va hisobot bo‘yicha yordam beraman."
        )

# ================== ISHGA TUSHIRISH ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
