import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

# ENV yuklash
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Salom!\n\n"
        "Men **Davlat Professional Yordamchi Botman** 🤖\n\n"
        "Quyidagi yo‘nalishlarda yordam beraman:\n\n"
        "📦 Omborxona hisobi\n"
        "📊 Buxgalteriya\n"
        "🧾 Hisobotlar\n"
        "🚚 Logistika\n"
        "☎️ Operator savollari\n\n"
        "Savolingni aniq yoz — professional javob beraman."
    )

# Oddiy savollar
@dp.message()
async def any_question(message: Message):
    text = message.text.lower()

    if "qoldiq" in text or "ombor" in text:
        await message.answer("📦 Ombordagi qoldiq bo‘yicha aniq nom va sana yozing.")
    elif "hisobot" in text:
        await message.answer("🧾 Qaysi hisobot kerak? Kunlik, oylik yoki yillik?")
    elif "kirim" in text or "chiqim" in text:
        await message.answer("📊 Kirim/chiqim summasi va sanani ko‘rsating.")
    else:
        await message.answer(
            "❓ Savolingiz qabul qilindi.\n"
            "Iltimos, mahsulot nomi, sana yoki summani aniqlab yozing."
        )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
