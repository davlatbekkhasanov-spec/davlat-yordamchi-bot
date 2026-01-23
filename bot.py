import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
import os

TOKEN = os.getenv("BOT_TOKEN")

# XO‘JAYINLAR
OWNERS = {
    1432810519,  # SEN
    2624538      # XO‘JAYINING
}

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_role(user_id: int) -> str:
    if user_id in OWNERS:
        return "owner"
    return "worker"


@dp.message(CommandStart())
async def start_handler(message: Message):
    role = get_role(message.from_user.id)

    if role == "owner":
        await message.answer(
            "👑 Salom xo‘jayin!\n\n"
            "Men omborxona bo‘yicha AI yordamchiman.\n"
            "Buyruq bering."
        )
    else:
        await message.answer(
            "📦 Salom!\n"
            "Men omborxona bo‘yicha yordamchi botman.\n"
            "Savolingizni yozing."
        )


@dp.message(Command("id"))
async def id_handler(message: Message):
    await message.answer(
        f"🆔 Sizning ID: `{message.from_user.id}`",
        parse_mode="Markdown"
    )


@dp.message(F.text)
async def text_handler(message: Message):
    role = get_role(message.from_user.id)

    if role == "owner":
        await message.answer(
            f"👑 Xo‘jayin so‘rovi qabul qilindi:\n\n"
            f"📝 {message.text}"
        )
    else:
        await message.answer(
            "📦 So‘rovingiz qabul qilindi.\n"
            "Mas’ul shaxs javob beradi."
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
