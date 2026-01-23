import os
import logging
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

from openai import OpenAI

# ================== LOG ==================
logging.basicConfig(level=logging.INFO)

# ================== ENV ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN topilmadi")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY topilmadi")

# ================== OPENAI ==================
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Sen omborxona bo‘yicha eng yetuk mutaxassissan.
24/7 javob berasan.
Javoblaring aniq, tushunarli va o‘zbek tilida bo‘lsin.
"""

async def ask_ai(text: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

# ================== TELEGRAM ==================
bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# ================== START ==================
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Salom!\n\n"
        "📦 Men omborxona bo‘yicha AI yordamchi botman.\n"
        "Savolingni yoz — javob beraman."
    )

# ================== AI REPLY (PRIVATE + GROUP) ==================
@dp.message()
async def ai_reply(message: types.Message):
    if not message.text:
        return

    # BOT O‘ZIGA JAVOB BERMASIN
    if message.from_user.is_bot:
        return

    try:
        answer = await ask_ai(message.text)
        await message.reply(answer)
    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Xatolik yuz berdi, keyinroq urinib ko‘ring.")

# ================== MAIN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
