import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Render Environment Variables da yo‘q")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Salom!\n\n"
        "Men *Davlat Yordamchi Bot* 🤖\n"
        "📦 Ombor\n"
        "📊 Buxgalteriya\n"
        "🧾 Hisobotlar\n\n"
        "Savolingni yoz.",
        parse_mode="Markdown"
    )

@dp.message()
async def echo_handler(message: Message):
    await message.answer(
        "✅ Savoling qabul qilindi.\n"
        "Aniqroq yozsang, professional yordam beraman."
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
