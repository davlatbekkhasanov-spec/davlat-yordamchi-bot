import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ===================== CONFIG =====================
BOT_TOKEN = "BOT_TOKENNI_BU_YERGA_QOY"
GROUP_ID = -1001234567890  # hisobot chiqadigan guruh ID

ADMINS = {
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

# employee -> task -> value
DATA = {}

# user_id -> (employee, task)
WAITING_INPUT = {}

# ===================== INIT =====================
logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ===================== HELPERS =====================
def init_day():
    today = datetime.now().date().isoformat()
    DATA.clear()
    for emp in EMPLOYEES:
        DATA[emp] = {task: None for task in TASKS}
    return today


def build_report(title: str):
    text = f"📊 <b>{title}</b>\n\n"
    for emp, tasks in DATA.items():
        text += f"<b>{emp}</b>\n"
        for task, val in tasks.items():
            value = val if val is not None else ""
            text += f"{task}: ({value})\n"
        text += "\n"
    return text


def employee_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=emp, callback_data=f"emp|{emp}")]
            for emp in EMPLOYEES
        ]
    )


def task_keyboard(emp):
    rows = []
    for task in TASKS:
        value = DATA[emp][task]
        label = f"{task} ({value})" if value is not None else task
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"task|{emp}|{task}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===================== COMMANDS =====================
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    await msg.answer("✅ Bot ishlayapti.")


@dp.message(Command("test1"))
async def test1(msg: Message):
    init_day()
    text = build_report(f"TEST HISOBOT — {datetime.now().date()}")
    await bot.send_message(GROUP_ID, text, reply_markup=employee_keyboard())


@dp.message(Command("test2"))
async def test2(msg: Message):
    init_day()
    text = build_report(f"TEST HISOBOT — {datetime.now().date()}")
    await bot.send_message(GROUP_ID, text, reply_markup=employee_keyboard())


# ===================== CALLBACKS =====================
@dp.callback_query(F.data.startswith("emp|"))
async def choose_employee(call: CallbackQuery):
    _, emp = call.data.split("|", 1)
    await call.message.edit_reply_markup(reply_markup=task_keyboard(emp))
    await call.answer()


@dp.callback_query(F.data.startswith("task|"))
async def choose_task(call: CallbackQuery):
    _, emp, task = call.data.split("|", 2)
    WAITING_INPUT[call.from_user.id] = (emp, task)
    await bot.send_message(
        call.from_user.id,
        f"<b>{emp}</b>\n{task} sonini kiriting:"
    )
    await call.answer()


# ===================== INPUT =====================
@dp.message(F.text.regexp(r"^\d+$"))
async def save_number(msg: Message):
    if msg.from_user.id not in WAITING_INPUT:
        return

    emp, task = WAITING_INPUT.pop(msg.from_user.id)
    DATA[emp][task] = int(msg.text)

    await msg.answer("✅ Saqlandi")

    text = build_report(f"KUNLIK HISOBOT — {datetime.now().date()}")
    await bot.send_message(GROUP_ID, text, reply_markup=employee_keyboard())


# ===================== SCHEDULE =====================
async def send_morning():
    init_day()
    text = build_report(f"KUNLIK HISOBOT — {datetime.now().date()}")
    await bot.send_message(GROUP_ID, text, reply_markup=employee_keyboard())


async def send_evening():
    text = build_report(f"KUNLIK HISOBOT — {datetime.now().date()}")
    await bot.send_message(GROUP_ID, text)


# ===================== MAIN =====================
async def main():
    scheduler.add_job(send_morning, "cron", hour=7, minute=0)
    scheduler.add_job(send_evening, "cron", hour=19, minute=30)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
