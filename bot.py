import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== SOZLAMALAR ==================

API_TOKEN = "BOT_TOKENNI_BU_YERGA_QO'Y"
GROUP_ID = -1001234567890  # guruh ID

ADMIN_IDS = {
    5732350707,
    2624538,
    6991673998,
    1432810519,
}

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To‘lqum",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ruziboev Sardor",
    "Samandar Foto",
    "Mustafoev Abdullo",
    "Rajabboev Pulat",
]

TASKS = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Счет ТСД",
    "Фасовка",
    "Услуга",
    "Доставка",
    "Переоценка",
    "Акт пересортица",
    "Пересчет товаров",
]

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# vaqtinchalik saqlash
REPORT_DATA = {}
WAITING_INPUT = {}

# ================== YORDAMCHI FUNKSIYALAR ==================

def today_key():
    return datetime.now().strftime("%Y-%m-%d")


def build_report(date_key, title="KUNLIK HISOBOT"):
    text = f"📊 <b>{title} — {date_key}</b>\n\n"
    data = REPORT_DATA.get(date_key, {})

    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for t in TASKS:
            val = data.get(emp, {}).get(t)
            text += f"{t}: ({val if val is not None else ''})\n"
        text += "\n"

    return text


def employees_keyboard(date_key, test=False):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for emp in EMPLOYEES:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=emp,
                callback_data=f"emp|{date_key}|{emp}|{'test' if test else 'real'}"
            )
        ])
    return kb


def tasks_keyboard(date_key, emp, mode):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for t in TASKS:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=t,
                callback_data=f"task|{date_key}|{emp}|{t}|{mode}"
            )
        ])
    return kb


# ================== START ==================

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer("✅ Bot ishlayapti.")


# ================== TEST BUYRUQLAR ==================

@dp.message(Command("test1"))
async def test1(msg: Message):
    date_key = today_key()
    await bot.send_message(
        GROUP_ID,
        build_report(date_key, "TEST HISOBOT"),
        reply_markup=employees_keyboard(date_key, test=True)
    )


@dp.message(Command("test2"))
async def test2(msg: Message):
    date_key = today_key()
    await bot.send_message(
        GROUP_ID,
        build_report(date_key, "TEST HISOBOT"),
        reply_markup=employees_keyboard(date_key, test=True)
    )


# ================== REAL HISOBOT ==================

async def send_real_report():
    date_key = today_key()
    await bot.send_message(
        GROUP_ID,
        build_report(date_key),
        reply_markup=employees_keyboard(date_key)
    )


# ================== CALLBACKLAR ==================

@dp.callback_query(F.data.startswith("emp|"))
async def choose_employee(call: CallbackQuery):
    _, date_key, emp, mode = call.data.split("|")
    await call.message.answer(
        f"<b>{emp}</b>\nIshni tanlang:",
        reply_markup=tasks_keyboard(date_key, emp, mode)
    )
    await call.answer()


@dp.callback_query(F.data.startswith("task|"))
async def choose_task(call: CallbackQuery):
    _, date_key, emp, task, mode = call.data.split("|")

    WAITING_INPUT[call.from_user.id] = {
        "date": date_key,
        "emp": emp,
        "task": task,
    }

    await call.message.answer(
        f"<b>{emp}</b>\n<b>{task}</b>\n\nRaqam kiriting:",
    )
    await call.answer()


# ================== RAQAM QABUL QILISH ==================

@dp.message()
async def get_number(msg: Message):
    if msg.from_user.id not in WAITING_INPUT:
        return

    if not msg.text.isdigit():
        await msg.answer("❗️Faqat raqam kiriting")
        return

    info = WAITING_INPUT.pop(msg.from_user.id)
    date_key = info["date"]
    emp = info["emp"]
    task = info["task"]

    REPORT_DATA.setdefault(date_key, {}).setdefault(emp, {})[task] = int(msg.text)

    await msg.answer("✅ Saqlandi")


# ================== SCHEDULER ==================

scheduler.add_job(send_real_report, "cron", hour=7, minute=0)
scheduler.add_job(send_real_report, "cron", hour=19, minute=30)

# ================== MAIN ==================

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
