import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== CONFIG ==================
API_TOKEN = "8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI"
GROUP_ID = -1001877019294   # guruh ID

ADMINS = {
    5732350707,
    2624538,
    6991673998,
    1432810519
}

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

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Rajabboev Pulat",
    "Ravshanov Oxunjon"
]

# ================== INIT ==================
logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

group_message_id = None
report_data = {}

# ================== FSM ==================
class InputState(StatesGroup):
    waiting_number = State()

# ================== HELPERS ==================
def build_report(title: str):
    text = f"📊 <b>{title}</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for task in TASKS:
            value = report_data.get(emp, {}).get(task)
            text += f"{task}: ({value if value is not None else ''})\n"
        text += "\n"
    return text

def employee_keyboard(emp: str):
    buttons = [
        [InlineKeyboardButton(text=task, callback_data=f"task:{emp}:{task}")]
        for task in TASKS
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ================== COMMANDS ==================
@dp.message(F.text == "/start")
async def start(m: Message):
    await m.answer("✅ Bot ishlayapti.")

@dp.message(F.text == "/test1")
async def test1(m: Message):
    await send_report(test=True)

@dp.message(F.text == "/test2")
async def test2(m: Message):
    await send_summary(test=True)

# ================== REPORT ==================
async def send_report(test=False):
    global group_message_id
    title = "TEST HISOBOT" if test else "KUNLIK HISOBOT"
    text = build_report(f"{title} — {datetime.now().date()}")

    if group_message_id:
        await bot.edit_message_text(
            chat_id=GROUP_ID,
            message_id=group_message_id,
            text=text
        )
    else:
        msg = await bot.send_message(GROUP_ID, text)
        group_message_id = msg.message_id

async def send_summary(test=False):
    title = "TEST SUMMARY" if test else "ERTALABGI HISOBOT"
    text = build_report(f"{title} — {datetime.now().date()}")
    await bot.send_message(GROUP_ID, text)

# ================== CALLBACK ==================
@dp.callback_query(F.data.startswith("task:"))
async def choose_task(c: CallbackQuery, state: FSMContext):
    _, emp, task = c.data.split(":")
    await state.update_data(emp=emp, task=task)
    await c.message.answer(f"{emp}\n<b>{task}</b sonini kiriting:")
    await state.set_state(InputState.waiting_number)
    await c.answer()

@dp.message(InputState.waiting_number)
async def save_number(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("❌ Faqat raqam kiriting")
        return

    data = await state.get_data()
    emp = data["emp"]
    task = data["task"]

    report_data.setdefault(emp, {})[task] = int(m.text)

    await send_report()
    await m.answer("✅ Saqlandi", reply_markup=employee_keyboard(emp))
    await state.clear()

# ================== SCHEDULER ==================
scheduler.add_job(send_report, "cron", hour=19, minute=30)
scheduler.add_job(send_summary, "cron", hour=7, minute=0)

# ================== MAIN ==================
async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
