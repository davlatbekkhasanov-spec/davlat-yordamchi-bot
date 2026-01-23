import os
import asyncio
from collections import defaultdict, deque
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from openai import AsyncOpenAI

# ================== ENV ==================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("BOT_TOKEN yoki OPENAI_API_KEY yo‘q")

# ================== ROLES ==================
OWNERS = {1432810519, 2624538}

def is_owner(uid: int) -> bool:
    return uid in OWNERS

def role_name(uid: int) -> str:
    return "XO‘JAYIN" if is_owner(uid) else "ISHCHI"

# ================== STORAGE ==================
CHAT_MEMORY = defaultdict(lambda: deque(maxlen=15))

WAREHOUSE = {
    "kirim": 0,
    "chiqim": 0
}

LOGS = []

def log_event(user, text, category):
    LOGS.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user": user,
        "category": category,
        "text": text
    })

# ================== AI ==================
ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
SEN — KORPORATIV OMBORXONA AI YORDAMCHISAN.

QOIDALAR:
- XO‘JAYIN → strategik, batafsil, tahlilli
- ISHCHI → qisqa, buyruq ohangida
- Ombor: kirim, chiqim, qoldiq, kamomad
- Keraksiz gap yozma
- Faqat O‘ZBEK TILIDA
"""

async def ask_ai(chat_id: int, uid: int, text: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(CHAT_MEMORY[chat_id])
    messages.append({
        "role": "user",
        "content": f"ROL: {role_name(uid)}\n{text}"
    })

    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.25
        )
        answer = r.choices[0].message.content.strip()

        CHAT_MEMORY[chat_id].append({"role": "user", "content": text})
        CHAT_MEMORY[chat_id].append({"role": "assistant", "content": answer})

        return answer
    except Exception:
        return "❌ AI vaqtincha javob bera olmadi"

# ================== BOT ==================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ================== START ==================
@dp.message(CommandStart())
async def start(msg: Message):
    if is_owner(msg.from_user.id):
        await msg.answer("👑 Xo‘jayin, ombor AI tayyor.")
    else:
        await msg.answer("📦 Ombor yordamchisi. Buyruq yozing.")

# ================== COMMANDS ==================
@dp.message(F.text.startswith("/kirim"))
async def kirim(msg: Message):
    try:
        qty = int(msg.text.split()[-1])
        WAREHOUSE["kirim"] += qty
        log_event(msg.from_user.full_name, msg.text, "KIRIM")
        await msg.answer(f"✅ Kirim qabul qilindi: {qty}")
    except:
        await msg.answer("❌ To‘g‘ri format: /kirim 10")

@dp.message(F.text.startswith("/chiqim"))
async def chiqim(msg: Message):
    try:
        qty = int(msg.text.split()[-1])
        WAREHOUSE["chiqim"] += qty
        log_event(msg.from_user.full_name, msg.text, "CHIQIM")
        await msg.answer(f"📤 Chiqim yozildi: {qty}")
    except:
        await msg.answer("❌ To‘g‘ri format: /chiqim 5")

@dp.message(F.text.startswith("/qoldiq"))
async def qoldiq(msg: Message):
    q = WAREHOUSE["kirim"] - WAREHOUSE["chiqim"]
    await msg.answer(f"📊 Joriy qoldiq: {q}")

@dp.message(F.text.startswith("/hisobot"))
async def hisobot(msg: Message):
    if not is_owner(msg.from_user.id):
        await msg.answer("❌ Bu buyruq faqat xo‘jayinga")
        return

    if not LOGS:
        await msg.answer("📭 Hozircha hisobot yo‘q")
        return

    text = "\n".join(
        f"{l['time']} | {l['user']} | {l['category']} | {l['text']}"
        for l in LOGS[-20:]
    )
    await msg.answer(text)

# ================== TEXT HANDLER ==================
@dp.message(F.text)
async def text_handler(msg: Message):
    if msg.chat.type in ["group", "supergroup"]:
        if not msg.reply_to_message and "bot" not in msg.text.lower():
            return

    answer = await ask_ai(
        chat_id=msg.chat.id,
        uid=msg.from_user.id,
        text=msg.text
    )
    await msg.answer(answer)

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
