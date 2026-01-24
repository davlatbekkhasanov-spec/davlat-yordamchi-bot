import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date
from collections import defaultdict

# =======================
# 🔧 SOZLAMALAR
# =======================

API_TOKEN = "BOT_TOKENINGNI_BU_YERGA_QOʻY"
GROUP_ID = -1001877019294
OWNER_ID = 1432810519

TEST_MODE = False  # ❗️SINOV UCHUN True QILIB TURASAN

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

# daily_reports[date][employee][field]
# total_reports[employee][field]

# =======================
# 🚀 BOT
# =======================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# =======================
# ▶️ START
# =======================

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("✅ Ombor AI bot ishga tushdi.")

# =======================
# 🧾 SHABLON YUBORISH
# =======================

async def send_daily_template():
    chat_id = OWNER_ID if TEST_MODE else GROUP_ID

    for emp in EMPLOYEES:
        kb = InlineKeyboardMarkup(row_width=2)
        for f in FIELDS:
            kb.add(
                InlineKeyboardButton(
                    text=f,
                    callback_data=f"{emp}|{f}"
                )
            )

        await bot.send_message(
            chat_id,
            f"📋 HISOBOT\n👤 {emp}\nBo‘limni tanlang:",
            reply_markup=kb
        )

# =======================
# 🔘 TUGMA BOSILDI
# =======================

@dp.callback_query_handler()
async def button_handler(call: types.CallbackQuery):
    emp, field = call.data.split("|")
    user_states[call.from_user.id] = (emp, field)
    await call.message.answer(f"✏️ {emp}\n{field} uchun raqam kiriting:")
    await call.answer()

# =======================
# 🔢 RAQAM QABUL
# =======================

@dp.message_handler(lambda m: m.text.isdigit())
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
        f"✅ Saqlandi:\n{emp}\n{field} ( {value} )"
    )

# =======================
# 📊 NATIJA E’LON QILISH
# =======================

async def publish_results():
    chat_id = OWNER_ID if TEST_MODE else GROUP_ID
    yesterday = date.today().isoformat()

    text = f"📊 HISOBOT ({yesterday})\n\n"

    for emp in EMPLOYEES:
        text += f"👤 {emp}\n"
        for f in FIELDS:
            day_val = daily_reports[yesterday][emp].get(f, 0)
            total_val = total_reports[emp].get(f, 0)
            text += f"• {f}: {day_val} | Jami: {total_val}\n"
        text += "\n"

    await bot.send_message(chat_id, text)

# =======================
# ⏰ VAQT SCHEDULER
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

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)
