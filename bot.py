import os
import asyncio
import io
from datetime import datetime
from collections import defaultdict, deque

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from openai import AsyncOpenAI

import pandas as pd

# ================= ENV =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("❌ BOT_TOKEN yoki OPENAI_API_KEY yo‘q")

# ================= ROLES =================
OWNERS = {1432810519, 2624538}  # xo‘jayinlar

# ================= MEMORY =================
CHAT_MEMORY = defaultdict(lambda: deque(maxlen=12))
EVENT_LOG = defaultdict(list)

# ================= CLIENTS =================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ================= SYSTEM PROMPT =================
SYSTEM_PROMPT = """
SEN OMBORXONA BO‘YICHA PROFESSIONAL AI YORDAMCHISAN.

QOIDALAR:
- XO‘JAYIN → to‘liq, strategik, aniq
- ISHCHI → qisqa, rasmiy, buyruqqa mos
- Kamomat, inventar, kirim-chiqimni aniq tushuntir
- Ombor intizomiga amal qil
- Keraksiz gap yozma
- O‘zbek tilida javob ber
"""

# ================= HELPERS =================
def is_owner(user_id: int) -> bool:
    return user_id in OWNERS


async def ask_ai(chat_id: int, user_id: int, text: str) -> str:
    role = "XO‘JAYIN" if is_owner(user_id) else "ISHCHI"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(CHAT_MEMORY[chat_id])
    messages.append({
        "role": "user",
        "content": f"ROL: {role}\nSAVOL: {text}"
    })

    try:
        resp = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2
        )

        answer = resp.choices[0].message.content.strip()

        CHAT_MEMORY[chat_id].append({"role": "user", "content": text})
        CHAT_MEMORY[chat_id].append({"role": "assistant", "content": answer})

        return answer

    except Exception:
        return "❌ AI bilan bog‘lanishda xatolik bo‘ldi."


def log_event(chat_id, user, text, category):
    EVENT_LOG[chat_id].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user": user,
        "category": category,
        "text": text
    })


# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    if is_owner(message.from_user.id):
        await message.answer(
            "👑 Salom xo‘jayin!\n\n"
            "Men omborxona bo‘yicha 24/7 AI yordamchiman.\n"
            "Buyruq yoki savol bering."
        )
    else:
        await message.answer(
            "📦 Salom!\n"
            "Omborxona yordamchi botiga xush kelibsiz.\n"
            "Savolingizni yozing."
        )


# ================= COMMANDS =================
@dp.message(F.text.startswith("/kamomat"))
async def kamomat(message: Message):
    log_event(
        message.chat.id,
        message.from_user.full_name,
        message.text,
        "KAMOMAT"
    )

    if is_owner(message.from_user.id):
        await message.answer("👑 Kamomat xo‘jayin tomonidan qayd etildi.")
    else:
        await message.answer("⏳ Kamomat qabul qilindi. Mas’ul shaxs ko‘rib chiqadi.")


@dp.message(F.text.startswith("/inventar"))
async def inventar(message: Message):
    log_event(
        message.chat.id,
        message.from_user.full_name,
        message.text,
        "INVENTAR"
    )

    await message.answer("📋 Inventar so‘rovi qabul qilindi.")


@dp.message(F.text.startswith("/hisobot"))
async def report(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Hisobot faqat xo‘jayinlar uchun.")
        return

    data = EVENT_LOG[message.chat.id]
    if not data:
        await message.answer("📭 Hozircha ma’lumot yo‘q.")
        return

    df = pd.DataFrame(data)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)

    file = BufferedInputFile(
        buffer.read(),
        filename="ombor_hisobot.xlsx"
    )

    await message.answer_document(file)


# ================= TEXT =================
@dp.message(F.text)
async def text_handler(message: Message):
    await message.answer("⏳ So‘rov qayta ishlanmoqda...")

    answer = await ask_ai(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        text=message.text
    )

    await message.answer(answer)


# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
