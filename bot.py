import asyncio
import logging
from datetime import datetime, date
from collections import defaultdict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

# =======================
# 🔧 SOZLAMALAR
# =======================

API_TOKEN = "BOT_TOKEN"
GROUP_ID = -1001877019294
OWNER_ID = 1432810519

TEST_MODE = True  # 🔴 avval TEST, keyin False qilamiz

# =======================
# 👥 XODIMLAR
# =======================

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

FIELDS = [
    "Приход",
    "Перемещение",
    "Фото тмц",
    "Уборка",
    "Фасовка",
    "Доставка",
]

# =======================
# 📦 MA’LUMOTLAR
# =======================

user_states = {}
daily_reports = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
total_reports = defaultdict(lambda: defaultdict(int))

# =======================
# 🚀 BOT
# =======================

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# =======================
# ▶️ START
# =======================

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("✅ Ombor AI bot ishga tushdi.")

# =======================
# 🧾 SHABLON
# =======================

async def send_daily_template():
    chat_id = OWNER_ID if TEST_MODE else GROUP_ID

    for emp in EMPLOYEES:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f,
                    callback_data=f"{emp}|{f}"
                )
            ] for f in FIELDS
        ])

        await bot.send_message(
            chat_id,
            f"📋 <b>HISOBOT</b>\n👤 <b>{emp}</b>\nBo‘limni tanlang:",
            reply_markup=kb
        )

# =======================
# 🔘 TUGMA
# =======================

@dp.callback_query()
async def button_handler(call: types.CallbackQuery):
    emp, field = call.data.split("|")
    user_states[call.from_user.id] = (emp, field)
    await call.message.answer(
        f"✏️ <b>{emp}</b>\n<b>{field}</b> uchun raqam kiriting:"
    )
    await call.answer()

# =======================
# 🔢 RAQAM
# =======================

@dp.message(lambda m: m.text and m.text.isdigit())
async def number_handler(msg: types.Message):
    uid = msg.from_user.id
    if uid not in user_states:
        return

    emp, field = user_states.pop(uid)
    today = date.today().isoformat()
    value = int(msg.text)

    daily_reports[today][emp][field] += value
    total_reports[emp][field] += value

    await msg.answer(
        f"✅ Saqlandi:\n<b>{emp}</b>\n{field} ( {value} )"
    )

# =======================
# 📊 NATIJA
# =======================

async def publish_results():
    chat_id = OWNER_ID if TEST_MODE else GROUP_ID
    today = date.today().isoformat()

    text = f"📊 <b>HISOBOT ({today})</b>\n\n"

    for emp in EMPLOYEES:
        text += f"👤 <b>{emp}</b>\n"
        for f in FIELDS:
            d = daily_reports[today][emp].get(f, 0)
            t = total_reports[emp].get(f, 0)
            text += f"• {f}: {d} | Jami: {t}\n"
        text += "\n"

    await bot.send_message(chat_id, text)

# =======================
# ⏰ SCHEDULER (UTC)
# =======================

async def scheduler():
    while True:
        now = datetime.utcnow()

        # 19:30 UZ → 14:30 UTC
        if now.hour == 14 and now.minute == 30:
            await send_daily_template()
            await asyncio.sleep(60)

        # 07:00 UZ → 02:00 UTC
        if now.hour == 2 and now.minute == 0:
            await publish_results()
            await asyncio.sleep(60)

        await asyncio.sleep(20)

# =======================
# ▶️ RUN
# =======================

async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
