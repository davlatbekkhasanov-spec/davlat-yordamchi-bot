import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Salom! 👋\n\n"
        "Men **Davlat Yordamchi Botman 🤖**\n\n"
        "📦 Omborxona\n"
        "📊 Buxgalteriya\n"
        "🧾 Hisobotlar\n"
        "📈 Analitika\n"
        "👨‍💼 Operator yordami\n\n"
        "Bo‘yicha **professional yordam beraman**.\n\n"
        "Savolingni yoz 👇"
    )


@dp.message()
async def any_message(message: Message):
    text = message.text.lower()

    if "ombor" in text:
        await message.answer(
            "📦 **Omborxona bo‘yicha yordam:**\n"
            "• Kirim-chiqim\n"
            "• Qoldiq nazorati\n"
            "• Inventarizatsiya\n"
            "• FIFO / LIFO\n"
            "• Ombor xatolari\n\n"
            "Aniq savolingni yoz."
        )

    elif "buxgalter" in text or "hisob" in text:
        await message.answer(
            "📊 **Buxgalteriya bo‘yicha yordam:**\n"
            "• Debet / Kredit\n"
            "• Ombor + buxgalteriya bog‘lanishi\n"
            "• Hisobotlar\n"
            "• Qoldiq farqlari\n\n"
            "Qanday masala bor?"
        )

    else:
        await message.answer(
            "Tushundim ✅\n"
            "Savolingni biroz aniqroq yozsang, professional javob beraman."
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
