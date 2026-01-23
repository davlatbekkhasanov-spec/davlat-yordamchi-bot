import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi! Render Environment Variables ni tekshir.")

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start_handler(message: types.Message):
        await message.answer(
            "Salom! 👋\n\n"
            "Men Davlat yordamchi botiman.\n"
            "Bot muvaffaqiyatli ishga tushdi ✅"
        )

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
