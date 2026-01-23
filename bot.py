import os
import logging
import openai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.enums import ChatType
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
import asyncio

# =====================
# ENV
# =====================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# =====================
# ROLES
# =====================
BOSS_IDS = {
    1432810519,  # sen
    2624538      # sendan katta xo‘jayin
}

# =====================
# LOGGING
# =====================
logging.basicConfig(level=logging.INFO)

# =====================
# BOT
# =====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================
# HELPERS
# =====================
def get_role(user_id: int) -> str:
    if user_id in BOSS_IDS:
        return "boss"
    return "worker"


async def ask_ai(question: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen omborxona bo‘yicha professional AI yordamchisan. "
                        "Qisqa, aniq va tushunarli javob ber. "
                        "Keraksiz gap yozma."
                    )
                },
                {"role": "user", "content": question}
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(e)
        return "❌ AI bilan bog‘lanishda xatolik bo‘ldi."

# =====================
# START
# =====================
@dp.message(CommandStart())
async def start(message: types.Message):
    role = get_role(message.from_user.id)

    if role == "boss":
        await message.answer(
            "👑 Salom xo‘jayin!\n"
            "Men omborxona bo‘yicha AI yordamchiman.\n"
            "Buyruq yoki savolingizni yozing."
        )
    else:
        await message.answer(
            "📦 Salom!\n"
            "Men omborxona bo‘yicha yordamchi botman.\n"
            "Savolingizni yozing."
        )

# =====================
# MAIN HANDLER
# =====================
@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return

    role = get_role(message.from_user.id)

    # Boss bo‘lsa — to‘g‘ridan-to‘g‘ri AI javob beradi
    if role == "boss":
        await message.answer("⏳ So‘rov qayta ishlanmoqda...")
        answer = await ask_ai(message.text)
        await message.answer(answer)
        return

    # Worker bo‘lsa
    await message.answer(
        "📨 So‘rovingiz qabul qilindi.\n"
        "Mas’ul shaxs javob beradi."
    )

    # Worker savoli AI ga yuboriladi
    answer = await ask_ai(message.text)

    # Javob XO‘JAYINLARGA yuboriladi
    for boss_id in BOSS_IDS:
        try:
            await bot.send_message(
                boss_id,
                f"👷‍♂️ Ishchi savoli:\n"
                f"{hbold(message.from_user.full_name)}\n\n"
                f"❓ {message.text}\n\n"
                f"🤖 AI javobi:\n{answer}"
            )
        except:
            pass

# =====================
# RUN
# =====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
