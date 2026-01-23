import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Sen professional omborxona va logistika bo‘yicha eng yetuk mutaxassissan.
Sen xo‘jayinning o‘rniga 24/7 javob berasan.
Ishchilarga qat’iy, aniq, qisqa va tushunarli javob berasan.
O‘zbek tilida gaplashasan.
Keraksiz gap yozmaysan.
Telegram guruhlarda ham ishlaysan.
"""

async def ask_ai(user_text: str) -> str:
    response = await ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content


@dp.message(F.text)
async def handle_message(message: Message):
    try:
        reply = await ask_ai(message.text)
        await message.answer(reply)
    except Exception as e:
        await message.answer("Xatolik yuz berdi. Keyinroq urinib ko‘ring.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
