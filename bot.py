import asyncio
import logging
from datetime import datetime, time

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "BOT_TOKENINGNI_BU_YERGA_QO‘Y"
GROUP_ID = -1001877019294  # sen bergan group_id

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ===================== MA'LUMOTLAR =====================

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To‘lqim",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ruziboev Sardor",
    "Samandar Foto",
    "Mustafoev Abdullo",
    "Rajabboev Pulat",
]

SECTIONS = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Уборка",
    "Счет ТСД",
    "Фасовка",
    "Услуга",
    "Выгрузка/отгрузка",
    "Доставка",
    "Переоценка",
    "Акт пересортица",
    "Пересчет товаров",
]

# data[date][fio][section] = number
data = {}
last_report_message_id = None
user_state = {}

# ===================== YORDAMCHI =====================

def today():
    return datetime.now().strftime("%Y-%m-%d")


def build_report_text(date):
    text = f"📋 <b>KUNLIK HISOBOT — {date}</b>\n\n"
    for fio in EMPLOYEES:
        text += f"<b>{fio}</b>\n"
        for sec in SECTIONS:
            val = data.get(date, {}).get(fio, {}).get(sec)
            text += f"{sec}: ({'' if val is None else val})\n"
        text += "\n"
    return text


def main_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Hisobot kiritish", callback_data="start_input")]
        ]
    )

# ===================== BUYRUQLAR =====================

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "✅ Bot ishlayapti.\n"
        "/test_report — test hisobot\n"
        "Hisobotlar har kuni 19:30 da yuboriladi."
    )


@dp.message(Command("test_report"))
async def test_report(msg: Message):
    await send_daily_report(test_mode=True)

# ===================== HISOBOT YUBORISH =====================

async def send_daily_report(test_mode=False):
    global last_report_message_id

    date = today()
    if date not in data:
        data[date] = {}

    text = build_report_text(date)

    msg = await bot.send_message(
        GROUP_ID,
        text,
        reply_markup=main_button()
    )
    last_report_message_id = msg.message_id

    if test_mode:
        await bot.send_message(GROUP_ID, "🧪 Test rejimi: hisobot yuborildi.")

# ===================== TUGMALAR =====================

@dp.callback_query(F.data == "start_input")
async def choose_employee(call):
    kb = InlineKeyboardBuilder()
    for fio in EMPLOYEES:
        kb.button(text=fio, callback_data=f"fio:{fio}")
    kb.adjust(1)

    await call.message.answer("👤 Kim uchun hisobot?", reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("fio:"))
async def choose_section(call):
    fio = call.data.split("fio:")[1]
    user_state[call.from_user.id] = {"fio": fio}

    kb = InlineKeyboardBuilder()
    for sec in SECTIONS:
        kb.button(text=sec, callback_data=f"sec:{sec}")
    kb.adjust(2)

    await call.message.answer(f"📌 {fio}\nQaysi bo‘lim?", reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("sec:"))
async def enter_number(call):
    sec = call.data.split("sec:")[1]
    user_state[call.from_user.id]["sec"] = sec

    await call.message.answer("✍️ Raqamni kiriting:")
    await call.answer()


@dp.message()
async def save_number(msg: Message):
    uid = msg.from_user.id
    if uid not in user_state:
        return
    if not msg.text.isdigit():
        await msg.answer("❌ Faqat raqam yozing.")
        return

    fio = user_state[uid]["fio"]
    sec = user_state[uid]["sec"]
    date = today()

    data.setdefault(date, {}).setdefault(fio, {})[sec] = msg.text

    # EDIT ASOSIY HISOBOT
    if last_report_message_id:
        await bot.edit_message_text(
            build_report_text(date),
            chat_id=GROUP_ID,
            message_id=last_report_message_id,
            reply_markup=main_button()
        )

    await msg.answer("✅ Saqlandi.")
    user_state.pop(uid, None)

# ===================== SCHEDULER =====================

async def scheduler():
    while True:
        now = datetime.now().time()

        if now.hour == 19 and now.minute == 30:
            await send_daily_report()
            await asyncio.sleep(60)

        await asyncio.sleep(20)

# ===================== MAIN =====================

async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
