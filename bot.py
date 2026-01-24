import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ================= DATA =================
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
    "Фото тмц",
    "Уборка",
]

# reports[employee][field] = value
reports = {}

# vaqtinchalik kim nimani kiritayapti
waiting_input = {}

# ================= HELPERS =================
def build_keyboard(emp):
    buttons = []
    for f in FIELDS:
        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ {f}",
                callback_data=f"edit|{emp}|{f}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_text():
    text = "📋 <b>KUNLIK HISOBOT</b>\n\n"
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        for f in FIELDS:
            val = reports.get(emp, {}).get(f, "—")
            text += f"{f}: ( {val} )\n"
        text += "\n"
    return text

# ================= COMMANDS =================
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "✅ Bot ishlayapti\n"
        "/test_report — test shablon"
    )

@dp.message(Command("test_report"))
async def test_report(message: Message):
    msg = await bot.send_message(
        GROUP_ID,
        build_text(),
        reply_markup=build_keyboard(EMPLOYEES[0])
    )
    # bitta xabarni hamma uchun ishlatamiz
    dp["report_message_id"] = msg.message_id

# ================= CALLBACK =================
@dp.callback_query(F.data.startswith("edit|"))
async def edit_field(call: CallbackQuery):
    _, emp, field = call.data.split("|")

    waiting_input[call.from_user.id] = (emp, field)

    await call.message.answer(
        f"✍️ <b>{emp}</b>\n{field} uchun raqam kiriting:"
    )
    await call.answer()

# ================= NUMBER INPUT =================
@dp.message(F.text.regexp(r"^\d+$"))
async def save_number(message: Message):
    uid = message.from_user.id
    if uid not in waiting_input:
        return

    emp, field = waiting_input.pop(uid)

    reports.setdefault(emp, {})[field] = message.text

    await bot.edit_message_text(
        chat_id=GROUP_ID,
        message_id=dp["report_message_id"],
        text=build_text(),
        reply_markup=build_keyboard(emp)
    )

    await message.answer("✅ Saqlandi")

# ================= SCHEDULER =================
async def send_daily():
    msg = await bot.send_message(
        GROUP_ID,
        build_text(),
        reply_markup=build_keyboard(EMPLOYEES[0])
    )
    dp["report_message_id"] = msg.message_id

async def main():
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(send_daily, "cron", hour=19, minute=30)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
