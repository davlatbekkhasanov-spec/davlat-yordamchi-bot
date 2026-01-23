import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ChatType
from openai import AsyncOpenAI

# ================== ENV ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_USERNAME = os.getenv("BOT_USERNAME")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN topilmadi")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY topilmadi")

# ================== OPENAI ==================
ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Sen omborxona bo‘yicha ENG YETUK mutaxassissan.
24/7 ishlaysan.
Xodimlarga aniq, qisqa, amaliy javob berasan.
Buyruq ohangida emas, professional tarzda gapirasan.
"""

async def ask_ai(text: str) -> str:
    response = await ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

# ================== TELEGRAM ==================
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Salom!\n\n"
        "📦 Men omborxona bo‘yicha yordamchi botman.\n"
        "Savolingni yoz — javob beraman."
    )

@dp.message()
async def ai_reply(message: types.Message):
    if not message.text:
        return

    text = message.text

    # ================== GURUH LOGIKASI ==================
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        mentioned = f"@{BOT_USERNAME}" in text
        replied = message.reply_to_message and message.reply_to_message.from_user.id == bot.id

        if not mentioned and not replied and not text.startswith("/"):
            return

        text = text.replace(f"@{BOT_USERNAME}", "").strip()

    try:
        answer = await ask_ai(text)
        await message.reply(answer)
    except Exception as e:
        await message.reply("❌ Xatolik yuz berdi, keyinroq urinib ko‘ring.")

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
