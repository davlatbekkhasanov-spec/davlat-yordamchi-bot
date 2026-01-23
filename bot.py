import os
import asyncio
from collections import defaultdict, deque

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from openai import AsyncOpenAI

# ================== CONFIG ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("BOT_TOKEN yoki OPENAI_API_KEY yo‘q!")

# 👑 XO‘JAYINLAR
OWNERS = {1432810519, 2624538}

# xotira (chat_id → messages)
CHAT_MEMORY = defaultdict(lambda: deque(maxlen=10))

# buyruqlar logi
COMMAND_LOG = defaultdict(list)

# OpenAI client
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Telegram
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== SYSTEM PROMPT ==================
SYSTEM_PROMPT = """
SEN professional OMBORXONA AI yordamchisisan.

QOIDALAR:
- Agar yozgan odam XO‘JAYIN bo‘lsa → to‘liq, strategik, aniq javob ber
- Agar ISHCHI bo‘lsa → qisqa, rasmiy, tartibli javob ber
- Ombor qoidalariga qat’iy amal qil
- Xato, kamomat, inventar masalalarini aniq tushuntir
- Keraksiz gap yo‘q
- O‘zbek tilida javob ber
"""

# ================== HELPERS ==================
def is_owner(user_id: int) -> bool:
    return user_id in OWNERS


async def ask_ai(chat_id: int, user_id: int, text: str) -> str:
    role = "xo‘jayin" if is_owner(user_id) else "ishchi"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(CHAT_MEMORY[chat_id])

    messages.append({
        "role": "user",
        "content": f"Rol: {role}\nSavol: {text}"
    })

    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2
        )

        answer = response.choices[0].message.content

        CHAT_MEMORY[chat_id].append({"role": "user", "content": text})
        CHAT_MEMORY[chat_id].append({"role": "assistant", "content": answer})

        return answer

    except Exception as e:
        return "❌ AI bilan bog‘lanishda xatolik bo‘ldi."


# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message):
    if is_owner(message.from_user.id):
        await message.answer(
            "👑 Salom xo‘jayin!\n\n"
            "Men omborxona bo‘yicha AI yordamchiman.\n"
            "Buyruq yoki savolingizni yozing."
        )
    else:
        await message.answer(
            "📦 Salom!\n"
            "Men omborxona bo‘yicha yordamchi botman.\n"
            "Savolingizni yozing."
        )


# ================== COMMANDS ==================
@dp.message(F.text.startswith("/kamomat"))
async def kamomat(message: Message):
    COMMAND_LOG[message.chat.id].append(
        f"KAMOMAT | {message.from_user.full_name}: {message.text}"
    )

    if not is_owner(message.from_user.id):
        await message.answer("⏳ So‘rov qabul qilindi. Mas’ul shaxs ko‘rib chiqadi.")
    else:
        await message.answer("👑 Kamomat qayd etildi.")


@dp.message(F.text.startswith("/inventar"))
async def inventar(message: Message):
    logs = COMMAND_LOG[message.chat.id][-10:]
    text = "\n".join(logs) if logs else "Hozircha ma’lumot yo‘q."
    await message.answer(f"📋 Oxirgi inventar ma’lumotlari:\n{text}")


# ================== TEXT HANDLER ==================
@dp.message(F.text)
async def handle_text(message: Message):
    await message.answer("⏳ So‘rov qayta ishlanmoqda...")

    answer = await ask_ai(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        text=message.text
    )

    await message.answer(answer)


# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
