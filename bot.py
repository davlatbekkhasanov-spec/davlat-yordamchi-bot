import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

TOKEN = "BU_YERGA_BOT_TOKENING"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Salom! 👋\n"
        "Men Davlat Yordamchi botman.\n"
        "Yaqinda yanada aqlli bo‘laman 🤖"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
