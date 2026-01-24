import asyncio
import logging
from datetime import datetime, time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== SOZLAMALAR ==================
API_TOKEN = "BOT_TOKENINGNI_BU_YERGA_QOY"
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
    "Sherazarov Tolib",
    "Ruziboev Sindor",
    "Ruziboev Sardor",
    "Samandar Foto",
    "Mustafayev Abdullo",
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

DATA = {}  # {date: {employee: {task: number}}}
USER_STATE = {}  # user_id -> (employee, task, date)

# ================== INIT ==================
logging.basicConfig(level=logging.INFO)
bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ================== KLAVIATURALAR ==================
def employees_keyboard(date_key: str, test=False):
    kb = InlineKeyboardBuilder()
    for emp in EMPLOYEES:
        kb.button(
            text=emp,
            callback_data=f"emp|{emp}|{date_key}|{int(test)}"
        )
    kb.adjust(1)
    return kb.as_markup()


def tasks_keyboard(emp: str, date_key: str):
    kb = InlineKeyboardBuilder()
    for task in TASKS:
        kb.button(
            text=f"{task}",
            callback_data=f"task|{emp}|{task}|{date_key}"
        )
    kb.adjust(2)
    return kb.as_markup()

# ================== HISOBOT TEXT ==================
def build_report(date_key: str, title: str):
    text = f"📊 <b>{title} — {date_key}</b>\n\n"
    day_data = DATA.get(date_key, {})
    for emp in EMPLOYEES:
        text += f"<b>{emp}</b>\n"
        emp_data = day_data.get(emp, {})
        for task in TASKS:
            val = emp_data.get(task)
            text += f"{task}: ({val if val is not None else ''})\n"
        text += "\n"
    return text

# ================== HISOBOT YUBORISH ==================
async def send_report(test=False):
    date_key = datetime.now().strftime("%Y-%m-%d")
    title = "TEST HISOBOT" if test else "KUNLIK HISOBOT"

    await bot.send_message(
        GROUP_ID,
        build_report(date_key, title),
        reply_markup=employees_keyboard(date_key, test)
    )

# ================== SCHEDULER ==================
scheduler.add_job(send_report, "cron", hour=19, minute=30, args=[False])
scheduler.add_job(send_report, "cron", hour=7, minute=0, args=[False])

# ================== BUYRUQLAR ==================
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    await msg.answer("✅ Bot ishlayapti.")

@dp.message(Command("test1"))
async def test1(msg: Message):
    await send_report(test=True)

@dp.message(Command("test2"))
async def test2(msg: Message):
    await send_report(test=True)

# ================== CALLBACKLAR ==================
@dp.callback_query(F.data.startswith("emp|"))
async def emp_clicked(cb):
    _, emp, date_key, test = cb.data.split("|")
    await cb.message.answer(
        f"<b>{emp}</b> uchun ishni tanlang:",
        reply_markup=tasks_keyboard(emp, date_key)
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("task|"))
async def task_clicked(cb):
    _, emp, task, date_key = cb.data.split("|")
    USER_STATE[cb.from_user.id] = (emp, task, date_key)
    await bot.send_message(
        cb.from_user.id,
        f"<b>{emp}</b>\n<b>{task}</b>\n\nSonini kiriting:"
    )
    await cb.answer("✍️ Shaxsiy chatga yozing")

# ================== RAQAM QABUL ==================
@dp.message(F.text.regexp(r"^\d+$"))
async def save_number(msg: Message):
    uid = msg.from_user.id
    if uid not in USER_STATE:
        return

    emp, task, date_key = USER_STATE.pop(uid)
    DATA.setdefault(date_key, {}).setdefault(emp, {})[task] = int(msg.text)
    await msg.answer("✅ Saqlandi")

# ================== MAIN ==================
async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
