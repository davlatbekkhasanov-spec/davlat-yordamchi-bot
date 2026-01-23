import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
import os

TOKEN = os.getenv("BOT_TOKEN")

OWNERS = {
    1432810519,
    2624538
}

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()


def is_owner(user_id: int) -> bool:
    return user_id in OWNERS


@dp.message(CommandStart())
async def start_handler(message: Message):
    if is_owner(message.from_user.id):
        await message.answer(
            "👑 Salom xo‘jayin.\n\n"
            "Men omborxona bo‘yicha AI yordamchiman.\n"
            "Savol yoki buyruq yozing."
        )
    else:
        await message.answer(
            "📦 Salom!\n"
            "Men omborxona bo‘yicha yordamchi botman.\n"
            "Savolingizni yozing."
        )


@dp.message(Command("id"))
async def id_handler(message: Message):
    await message.answer(f"🆔 ID: `{message.from_user.id}`", parse_mode="Markdown")


@dp.message(F.text)
async def ai_answer(message: Message):
    text = message.text.lower()

    # Hozircha oddiy mantiq (keyin OpenAI ulanadi)
    if "inventarizatsiya" in text:
        answer = (
            "📦 Inventarizatsiya — bu ombordagi mavjud "
            "mahsulotlarni sanab, hujjatlar bilan solishtirish jarayoni.\n\n"
            "U yo‘qotishlar, kamomad yoki ortiqchani aniqlash uchun qilinadi."
        )
    else:
        answer = (
            "📘 Savolingiz qabul qilindi.\n"
            "Bu savol bo‘yicha aniqroq yozsangiz, batafsil tushuntiraman."
        )

    if is_owner(message.from_user.id):
        await message.answer(f"👑 Xo‘jayin uchun javob:\n\n{answer}")
    else:
        await message.answer(answer)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
