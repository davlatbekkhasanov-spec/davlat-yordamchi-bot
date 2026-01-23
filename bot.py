import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from openai import AsyncOpenAI
import asyncio

# ================== CONFIG ==================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = """
Sen Davlat Yordamchi botsan.
Sen omborxona va logistika bo‘yicha ENG YETUK mutaxassissan.

Qoidalar:
- Faqat o‘zbek tilida javob ber
- Juda aniq, ishchan va professional bo‘l
- Ishchilar, haydovchilar, ombor mudirlari bilan gaplashayotgandek yoz
- Keraksiz gap yozma
- Agar muammo bo‘lsa — bosqichma-bosqich yechim ber
- 24/7 xo‘jayin o‘rniga javob ber

Agar savol noaniq bo‘lsa — aniqlashtiruvchi savol ber.
"""

# ================== INIT ==================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ================== AI FUNCTION ==================

async def ask_ai(user_text: str) -> str:
    response = await ai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

# ================== COMMANDS ==================

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "👋 Salom!\n\n"
        "🤖 Men <b>Davlat Yordamchi</b> botman.\n"
        "📦 Omborxona va logistika bo‘yicha yordam beraman.\n\n"
        "Savolingni yoz — javob beraman."
    )

@dp.message(Command("stop"))
async def stop_cmd(message: Message):
    await message.answer("⛔ Bot vaqtincha to‘xtadi.\n/start bilan yana ishga tushirasan.")

# ================== MAIN HANDLER ==================

@dp.message()
async def ai_reply(message: Message):
    if not message.text:
        return

    text = message.text.strip()
    bot_username = (await bot.me()).username

    # Guruh va superguruh logikasi
    if message.chat.type in ("group", "supergroup"):
        # Agar mention bo‘lmasa va /buyruq bo‘lmasa — jim turadi
        if f"@{bot_username}" not in text and not text.startswith("/"):
            return

        # mentionni olib tashlash
        text = text.replace(f"@{bot_username}", "").strip()

    try:
        answer = await ask_ai(text)
        await message.reply(answer)
    except Exception as e:
        logging.error(e)
        await message.reply("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko‘ring.")

# ================== RUN ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
