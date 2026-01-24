import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# =======================
# 🔧 SOZLAMALAR
# =======================

API_TOKEN = "BOT_TOKENINGNI_BU_YERGA_QOʻY"

GROUP_ID = -1001877019294   # asosiy guruh
OWNER_ID = 1432810519       # sen

TEST_MODE = True            # ❗️TEST REJIM

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
    "Уборка",
    "Фасовка",
    "Доставка"
]

# =======================
# 📦 XOTIRA (oddiy)
# =======================

user_states = {}   # kim nima kiritmoqda
reports = {}       # natijalar

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
    await msg.answer(
        "👑 Salom xo‘jayin!\n"
        "🧪 Bot TEST rejimida.\n\n"
        "Sinash uchun 👉 /test_report"
    )


# =======================
# 🧪 TEST REPORT
# =======================

@dp.message_handler(commands=["test_report"])
async def test_report(msg: types.Message):
    if TEST_MODE and msg.from_user.id != OWNER_ID:
        return

    for emp in EMPLOYEES:
        kb = InlineKeyboardMarkup(row_width=2)
        for f in FIELDS:
            kb.add(
                InlineKeyboardButton(
                    text=f,
                    callback_data=f"{emp}|{f}"
                )
            )

        await msg.answer(f"👤 {emp}\nBo‘limni tanlang:", reply_markup=kb)


# =======================
# 🔘 TUGMA BOSILDI
# =======================

@dp.callback_query_handler()
async def handle_button(call: types.CallbackQuery):
    emp, field = call.data.split("|")

    user_states[call.from_user.id] = (emp, field)

    await call.message.answer(
        f"✏️ {emp}\n"
        f"{field} uchun raqam kiriting:"
    )
    await call.answer()


# =======================
# 🔢 RAQAM KIRITISH
# =======================

@dp.message_handler(lambda m: m.text.isdigit())
async def handle_number(msg: types.Message):
    uid = msg.from_user.id
    if uid not in user_states:
        return

    emp, field = user_states.pop(uid)

    reports.setdefault(emp, {})
    reports[emp][field] = msg.text

    await msg.answer(
        f"✅ Saqlandi:\n"
        f"{emp}\n"
        f"{field} ( {msg.text} )"
    )


# =======================
# 🧾 NATIJANI KO‘RISH
# =======================

@dp.message_handler(commands=["result"])
async def show_result(msg: types.Message):
    text = "📊 HISOBOT:\n\n"
    for emp, data in reports.items():
        text += f"👤 {emp}\n"
        for f, v in data.items():
            text += f"• {f} ( {v} )\n"
        text += "\n"

    await msg.answer(text or "Hali ma’lumot yo‘q.")


# =======================
# ▶️ RUN
# =======================

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
