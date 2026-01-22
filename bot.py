import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from openai import OpenAI

# === ENV ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === BOT & AI ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Salom! 👋\n"
        "Men Davlat Yordamchi botman 🤖\n"
        "Savolingni yoz — javob beraman."
    )


@dp.message()
async def ai_handler(message: Message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen foydali va muloyim yordamchi botsan."},
                {"role": "user", "content": message.text}
            ]
        )

        answer = response.choices[0].message.content
        await message.answer(answer)

    except Exception as e:
        await message.answer("❌ Xatolik yuz berdi. Keyinroq urinib ko‘ring.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
