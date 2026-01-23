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


@dp.message()
async def ai_reply(message: types.Message):
    if message.text is None:
        return

    # Guruhda botga yozilganda yoki mention bo‘lsa javob beradi
    if message.chat.type in ["group", "supergroup"]:
        if not message.text.startswith("/") and bot.username not in message.text:
            return

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ]
        )
        await message.reply(response.choices[0].message.content)
    except:
        pass
