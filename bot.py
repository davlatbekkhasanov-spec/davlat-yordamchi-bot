import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ================== SOZLAMALAR ==================

API_TOKEN = "BOT_TOKENNI_BU_YERGA_QO‘Y"
GROUP_ID = -1001877019294

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
    "Samadov To‘lqin",
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

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# ================== XOTIRA ==================
# reports[date][employee][task] = number
reports = {}
# callback_data -> (date, employee, task, message_id)
callback_map = {}

# ================== FSM ==================

class InputNumber(StatesGroup):
    waiting_number = State()

# ================== YORDAMCHI ==================

def today():
    return datetime.now().strftime("%Y-%m-%d")

def build_keyboard(date, employee, message_id):
    buttons = []
    for task in TASKS[:3]:  # xavfsizlik uchun 3 tadan
        value = reports.get(date, {}).get(employee, {}).get(task)
        text = f"{task} ({value if value is not None else ''})"
        cb = f"{date}|{employee}|{task}|{message_id}"
        callback_map[cb] = (date, employee, task, message_id)
        buttons.append([InlineKeyboardButton(text=text, callback_data=cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def send_daily_report():
    date = today()
    reports.setdefault(date, {})

    for employee in EMPLOYEES:
        reports[date].setdefault(employee, {})
        text = f"📋 <b>KUNLIK HISOBOT — {date}</b>\n\n👤 <b>{employee}</b>"
        msg = await bot.send_message(GROUP_ID, text)
        kb = build_keyboard(date, employee, msg.message_id)
        await bot.edit_message_text(
            chat_id=GROUP_ID,
            message_id=msg.message_id,
            text=text,
            reply_markup=kb
        )

# ================== HANDLERLAR ==================

@dp.message(Command("start"))
async def start_cmd(msg: Message):
    await msg.answer(
        "✅ Bot ishlayapti.\n"
        "/test_report — test hisobot"
    )

@dp.message(Command("test_report"))
async def test_report(msg: Message):
    if msg.chat.id != GROUP_ID:
        await msg.answer("❌ Bu buyruq faqat guruhda.")
        return
    await send_daily_report()

@dp.callback_query()
async def callback_handler(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer("⛔ Sizda ruxsat yo‘q", show_alert=True)
        return

    if call.data not in callback_map:
        await call.answer()
        return

    date, employee, task, message_id = callback_map[call.data]

    await state.update_data(
        date=date,
        employee=employee,
        task=task,
        message_id=message_id,
        group_id=call.message.chat.id
    )

    await call.message.answer(
        f"<b>{employee}</b>\n<b>{task}</b> sonini kiriting:"
    )
    await state.set_state(InputNumber.waiting_number)
    await call.answer()

@dp.message(InputNumber.waiting_number)
async def save_number(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ Faqat raqam kiriting")
        return

    data = await state.get_data()
    number = int(msg.text)

    date = data["date"]
    employee = data["employee"]
    task = data["task"]
    message_id = data["message_id"]
    group_id = data["group_id"]

    reports.setdefault(date, {}).setdefault(employee, {})[task] = number

    kb = build_keyboard(date, employee, message_id)
    text = f"📋 <b>KUNLIK HISOBOT — {date}</b>\n\n👤 <b>{employee}</b>"

    await bot.edit_message_text(
        chat_id=group_id,
        message_id=message_id,
        text=text,
        reply_markup=kb
    )

    await msg.answer("✅ Saqlandi")
    await state.clear()

# ================== SCHEDULER ==================

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_report, CronTrigger(hour=19, minute=30))
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
