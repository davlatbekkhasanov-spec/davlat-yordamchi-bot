import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== CONFIG ==================
API_TOKEN = "8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI"

ADMINS = {
    5732350707,
    2624538,
    6991673998,
    1432810519
}

GROUP_CHAT_ID = -1001877019294  # 🔴 O'zingning guruh ID ni qo'y

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Rajabboev Pulat",
    "Ravshanov Oxunjon"
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
    "Пересчет товаров"
]

# ================== STORAGE ==================
report_data = {}
report_message_id = None

# ================== FSM ==================
class ReportState(StatesGroup):
    choose_employee = State()
    choose_task = State()
    enter_value = State()

# ================== INIT ==================
logging.basicConfig(level=logging.INFO)
bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# ================== HELPERS ==================
def build_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Hisobot kiritish", callback_data="start_report")],
        [InlineKeyboardButton(text="📊 Bugungi holat", callback_data="view_report")]
    ])

def employee_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=e, callback_data=f"emp:{e}")]
        for e in EMPLOYEES
    ] + [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main")]])

def task_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=f"task:{t}")]
        for t in TASKS
    ] + [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_emp")]])

def build_report_text(title):
    text = f"📊 <b>{title}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for t in TASKS:
            val = report_data.get(emp, {}).get(t, "")
            text += f"{t}: ({val})\n"
        text += "\n"
    return text

async def update_group_report(title):
    global report_message_id
    text = build_report_text(title)

    if report_message_id:
        await bot.edit_message_text(
            chat_id=GROUP_CHAT_ID,
            message_id=report_message_id,
            text=text
        )
    else:
        msg = await bot.send_message(GROUP_CHAT_ID, text)
        report_message_id = msg.message_id

# ================== COMMANDS ==================
@dp.message(F.text == "/start")
async def start_cmd(message: Message):
    await message.answer(
        "✅ Bot ishlayapti.\n\nQuyidan tanlang:",
        reply_markup=build_main_menu()
    )

@dp.message(F.text == "/test1")
async def test1(message: Message):
    await update_group_report("TEST HISOBOT — 07:00")

@dp.message(F.text == "/test2")
async def test2(message: Message):
    await update_group_report("TEST HISOBOT — 19:30")

# ================== CALLBACKS ==================
@dp.callback_query(F.data == "start_report")
async def start_report(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ReportState.choose_employee)
    await cb.message.edit_text(
        "👤 Xodimni tanlang:",
        reply_markup=employee_keyboard()
    )

@dp.callback_query(F.data == "view_report")
async def view_report(cb: CallbackQuery):
    await cb.message.answer(
        build_report_text("BUGUNGI HISOBOT")
    )

@dp.callback_query(F.data.startswith("emp:"))
async def choose_employee(cb: CallbackQuery, state: FSMContext):
    emp = cb.data.split(":", 1)[1]
    await state.update_data(employee=emp)
    await state.set_state(ReportState.choose_task)
    await cb.message.edit_text(
        f"👤 {emp}\n\n📌 Ish turini tanlang:",
        reply_markup=task_keyboard()
    )

@dp.callback_query(F.data.startswith("task:"))
async def choose_task(cb: CallbackQuery, state: FSMContext):
    task = cb.data.split(":", 1)[1]
    await state.update_data(task=task)
    await state.set_state(ReportState.enter_value)
    await cb.message.edit_text(
        f"✏️ <b>{task}</b>\n\nRaqam kiriting:"
    )

@dp.message(ReportState.enter_value)
async def enter_value(message: Message, state: FSMContext):
    data = await state.get_data()
    emp = data["employee"]
    task = data["task"]

    report_data.setdefault(emp, {})[task] = message.text

    await update_group_report(
        f"KUNLIK HISOBOT — {datetime.now().strftime('%Y-%m-%d')}"
    )

    await state.clear()
    await message.answer(
        "✅ Saqlandi.\n\nYana davom etamizmi?",
        reply_markup=build_main_menu()
    )

@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "Asosiy menyu:",
        reply_markup=build_main_menu()
    )

@dp.callback_query(F.data == "back_emp")
async def back_emp(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ReportState.choose_employee)
    await cb.message.edit_text(
        "👤 Xodimni tanlang:",
        reply_markup=employee_keyboard()
    )

# ================== SCHEDULER ==================
scheduler.add_job(
    lambda: asyncio.create_task(
        update_group_report(
            f"KUNLIK HISOBOT — {datetime.now().strftime('%Y-%m-%d')} (07:00)"
        )
    ),
    "cron",
    hour=7,
    minute=0
)

scheduler.add_job(
    lambda: asyncio.create_task(
        update_group_report(
            f"KUNLIK HISOBOT — {datetime.now().strftime('%Y-%m-%d')} (19:30)"
        )
    ),
    "cron",
    hour=19,
    minute=30
)

# ================== START ==================
async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
