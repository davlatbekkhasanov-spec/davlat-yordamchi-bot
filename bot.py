import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from openai import OpenAI

# ================== SOZLAMALAR ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# XO‘JAYINLAR (ID lar)
OWNERS = {
    1432810519,   # SEN
    2624538       # SENING XO‘JAYINING
}

# ================== TEKSHIRUV ==================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY topilmadi")

# ================== INIT ==================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

# ================== AI FUNKSIYA ==================

async def ask_ai(question: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen omborxona bo‘yicha professional AI yordamchisan. "
                        "Javoblaring aniq, qisqa va amaliy bo‘lsin."
                    )
                },
                {"role": "user", "content": question}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OPENAI ERROR: {e}")
        return "❌ AI bilan bog‘lanishda xatolik bo‘ldi."

# ================== START ==================

@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id in OWNERS:
        await message.answer(
            "👑 Salom xo‘jayin!\n\n"
            "Men omborxona bo‘yicha AI yordamchiman.\n"
            "Savol yoki buyruq yozing."
        )
    else:
        await message.answer(
            "📦 Salom!\n"
            "Savolingiz qabul qilindi.\n"
            "Mas’ul shaxsga yuboriladi."
        )

# ================== ASOSIY MANTIQ ==================

@dp.message(F.text)
async def text_handler(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # ===== XO‘JAYIN YOZSA =====
    if user_id in OWNERS:
        await message.answer("⏳ So‘rov qayta ishlanmoqda...")
        answer = await ask_ai(text)
        await message.answer(answer)
        return

    # ===== ISHCHI YOZSA =====
    await message.answer(
        "📨 So‘rovingiz qabul qilindi.\n"
        "Mas’ul shaxs ko‘rib chiqadi."
    )

    ai_answer = await ask_ai(text)

    for owner_id in OWNERS:
        await bot.send_message(
            owner_id,
            (
                "📥 **Yangi so‘rov (ishchi):**\n\n"
                f"👤 ID: `{user_id}`\n"
                f"❓ Savol: {text}\n\n"
                f"🤖 AI javob:\n{ai_answer}"
            ),
            parse_mode="Markdown"
        )

# ================== RUN ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
