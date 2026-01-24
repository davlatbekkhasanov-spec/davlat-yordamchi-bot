import os
import asyncio
import json
import pytz
from collections import defaultdict, deque
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv
from openai import AsyncOpenAI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= ENV =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_ID = int(os.getenv("GROUP_ID"))

TZ = pytz.timezone("Asia/Tashkent")

# ================= ROLES =================
OWNERS = {1432810519, 2624538}

def is_owner(uid):
    return uid in OWNERS

def role(uid):
    return "XO‘JAYIN" if is_owner(uid) else "ISHCHI"

# ================= AI SYSTEM (OLD) =================
CHAT_MEMORY = defaultdict(lambda: deque(maxlen=15))
ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
SEN — KORPORATIV OMBOR AI.
XO‘JAYIN — strategik.
ISHCHI — qisqa va aniq.
Faqat o‘zbek tilida.
"""

async def ask_ai(chat_id, uid, text):
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs.extend(CHAT_MEMORY[chat_id])
    msgs.append({"role": "user", "content": f"ROL:{role(uid)}\n{text}"})

    r = await ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=msgs,
        temperature=0.25
    )

    ans = r.choices[0].message.content.strip()
    CHAT_MEMORY[chat_id].append({"role": "user", "content": text})
    CHAT_MEMORY[chat_id].append({"role": "assistant", "content": ans})
    return ans

# ================= BOT =================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ================= DAILY REPORT =================
EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov Toʻlqim",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ruziboev Sardor",
    "Samandar Foto",
    "Mustafoev Abdullo",
    "Rajabboev Pulat",
]

TEMPLATE = """Место хр:
Приход:
Перемещение:
Фото тмц:
Уборка:
Счет ТСД:
Фасовка:
Услуга:
Выгрузка/отгрузка:
Доставка:
Переоценка:
Акт пересортица:
Пересчет товаров:
"""

DATA_FILE = "daily_reports.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================= CORE FUNCTIONS =================
async def send_daily_form():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    data = load_data()

    data[today] = {"message_id": None, "answers": {}}

    text = f"📊 KUNLIK HISOBOT — {today}\n\n"
    for emp in EMPLOYEES:
        text += f"👤 {emp}\n{TEMPLATE}\n"

    msg = await bot.send_message(GROUP_ID, text)
    data[today]["message_id"] = msg.message_id
    save_data(data)

async def publish_results():
    day = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    data = load_data()

    if day not in data:
        return

    answered = data[day]["answers"].keys()

    text = f"📢 HISOBOT NATIJASI — {day}\n\n"
    for emp in EMPLOYEES:
        text += f"{'✅' if emp in answered else '❌'} {emp}\n"

    await bot.send_message(GROUP_ID, text)

# ================= HANDLERS =================
@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer("🤖 Ombor AI ishga tushdi.")

@dp.message(Command("test"))
async def test_mode(msg: Message):
    if not is_owner(msg.from_user.id):
        return
    await send_daily_form()
    await msg.reply("🧪 TEST: Shablon yuborildi.")

@dp.message(F.reply_to_message)
async def collect_answer(msg: Message):
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    data = load_data()

    if today not in data:
        return

    if msg.reply_to_message.message_id != data[today]["message_id"]:
        return

    if not msg.text.replace("\n", "").isdigit():
        await msg.reply("❗ Faqat raqamlar kiriting.")
        return

    data[today]["answers"][msg.from_user.full_name] = msg.text
    save_data(data)
    await msg.reply("✅ Qabul qilindi.")

@dp.message(F.text)
async def ai_handler(msg: Message):
    if msg.chat.type in ["group", "supergroup"]:
        if not msg.reply_to_message and "bot" not in msg.text.lower():
            return
    ans = await ask_ai(msg.chat.id, msg.from_user.id, msg.text)
    await msg.answer(ans)

# ================= MAIN =================
async def main():
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(send_daily_form, "cron", hour=19, minute=30)
    scheduler.add_job(publish_results, "cron", hour=7, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
