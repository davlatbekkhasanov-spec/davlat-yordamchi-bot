import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

# ================== DATA ==================
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

FIELDS = [
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

REPORTS = {}  # date -> employee -> field -> value
MESSAGE_ID = None

# ================== FSM ==================
class InputState(StatesGroup):
    waiting_number = State()

# ================== KEYBOARD ==================
def build_keyboard(date: str):
    rows = []
    for emp in EMPLOYEES:
        for field in FIELDS:
            value = REPORTS[date][emp].get(field)
            text = f"{field} ({value})" if value is not None else f"{field} ( )"
            cb = f"set|{emp}|{field}"
            rows.append([InlineKeyboardButton(text=text, callback_data=cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ================== TEXT ==================
def build_text(date: str):
    lines = [f"📋 <b>KUNLIK HISOBOT — {date}</b>\n"]
    for emp in EMPLOYEES:
        lines.append(f"<b>{emp}</b>")
        for field in FIELDS:
            v = REPORTS[date][emp].get(field)
            lines.append(f"{field}: {v if v is not None else ''}")
        lines.append("")
    return "\n".join(lines)

# ================== BOT ==================
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=TZ)

# ================== HANDLERS ==================
@dp.message(F.text == "/start")
async def start(msg: Message):
    await msg.answer(
        "✅ Bot ishlayapti.\n"
        "/test_report — test shablon\n"
        "Hisobotlar har kuni 19:30 da yuboriladi."
    )

@dp.message(F.text == "/test_report")
async def test_report(msg: Message):
    await send_report(test=True)

@dp.callback_query(F.data.startswith("set|"))
async def select_field(call: CallbackQuery, state: FSMContext):
    _, emp, field = call.data.split("|", 2)
    await state.update_data(emp=emp, field=field)
    await state.set_state(InputState.waiting_number)
    await call.message.answer(
        f"✍️ <b>{emp}</b>\n<b>{field}</b> uchun raqam kiriting:"
    )
    await call.answer()

@dp.message(InputState.waiting_number)
async def input_number(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ Faqat raqam kiriting")
        return

    data = await state.get_data()
    emp = data["emp"]
    field = data["field"]
    date = datetime.now(TZ).strftime("%Y-%m-%d")

    REPORTS[date][emp][field] = int(msg.text)

    await bot.edit_message_text(
        chat_id=GROUP_ID,
        message_id=MESSAGE_ID,
        text=build_text(date),
        reply_markup=build_keyboard(date),
    )

    await state.clear()
    await msg.answer("✅ Saqlandi")

# ================== REPORT ==================
async def send_report(test=False):
    global MESSAGE_ID

    date = datetime.now(TZ).strftime("%Y-%m-%d")
    REPORTS[date] = {e: {} for e in EMPLOYEES}

    msg = await bot.send_message(
        chat_id=GROUP_ID,
        text=build_text(date),
        reply_markup=build_keyboard(date),
    )
    MESSAGE_ID = msg.message_id

# ================== SCHEDULE ==================
scheduler.add_job(send_report, "cron", hour=19, minute=30)

# ================== MAIN ==================
async def main():
    logging.basicConfig(level=logging.INFO)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
