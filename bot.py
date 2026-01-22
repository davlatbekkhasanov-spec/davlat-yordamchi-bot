import asyncio
import os
from datetime import date

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from openai import OpenAI


# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# ================= IDS =================
OWNER_ID = 1432810519          # SEN (o‘zing)
BOSS_IDS = []                  # rahbarlar ID sini keyin qo‘shasan
STAFF_IDS = []                 # ishchilar ID sini keyin qo‘shasan


# ================= INIT =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

last_boss_greet_date = None


# ================= START =================
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Salom! 👋\n"
        "Men Davlat Yordamchi botman 🤖\n"
        "Savolingni yoz — javob beraman.\n\n"
        "📦 Omborxona bo‘yicha yordam beraman."
    )


# ================= GPT =================
def ask_gpt(user_text: str, system_role: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_role},
            {"role": "user", "content": user_text}
        ]
    )
    return response.choices[0].message.content


# ================= GROUP HANDLER =================
@dp.message()
async def group_handler(message: Message):
    global last_boss_greet_date

    # faqat guruh
    if message.chat.type not in ["group", "supergroup"]:
        return

    # faqat mention bo‘lsa
    me = await bot.me()
    if not message.text or f"@{me.username}" not in message.text:
        return

    user_id = message.from_user.id
    text = message.text.replace(f"@{me.username}", "").strip()
    if not text:
        return

    today = date.today()
    greeting = ""

    # -------- RAHBAR --------
    if user_id in BOSS_IDS:
        if last_boss_greet_date != today:
            greeting = "Assalomu Aleykum, "
            last_boss_greet_date = today

        system_role = (
            "Sen omborxona bo‘yicha ixtisoslashgan yordamchisan. "
            "Rahbar (shef) bilan muloqot qilayapsan. "
            "Doim hurmat bilan, 'Siz' deb gapir. "
            "Javoblarda 'shef' so‘zini ishlat. "
            "Aniq, qisqa va professional yoz. "
            "Faqat omborxona faoliyati haqida javob ber."
        )

    # -------- ISHCHI --------
    elif user_id in STAFF_IDS:
        system_role = (
            "Sen omborxona rahbarisan. "
            "Ishchilar bilan gapiryapsan. "
            "Aniq, talabchan va tushunarli bo‘l. "
            "Keraksiz gap qilma. "
            "Faqat omborxona ishlariga oid javob ber."
        )

    # -------- BOSHQA --------
    else:
        system_role = (
            "Sen faqat omborxona faoliyati bo‘yicha savollarga javob berasan. "
            "Agar savol mos bo‘lmasa, muloyim rad et."
        )

    reply = ask_gpt(text, system_role)
    await message.reply(greeting + reply)


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
