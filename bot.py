import os
import asyncio
import logging
import sqlite3
from datetime import datetime, date, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


# ================== SOZLAMALAR ==================

TOKEN = os.getenv("8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI")
if not TOKEN:
    raise RuntimeError("8231063055:AAE6uspIbD0xVC8Q8PL6aBUEZMUAeL1X2QI")

GROUP_ID = int(os.getenv("GROUP_ID", "-1001877019294"))

ADMINS = {5732350707, 2624538, 6991673998, 1432810519}

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To'lqin",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ravshanov Ziyodullo",
    "Yadullaev Umidjon",
    "Mustafoev Abdullo",
    "Rajabboev Pulat"
]

CATEGORIES = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Счет ТСД",
    "Фасовка",
    "Исправление пересортицы",
    "АРМ диспетчер",
    "Переоценка",
    "Пересчет товаров",
    "Места хр"
]

# PINлар (ходимларга берилади). Ҳохласанг кейин алмаштириб чиқасан.
EMPLOYEE_PINS = {
    "Sagdullaev Yunus": "1111",
    "Toxirov Muslimbek": "2222",
    "Ravshanov Oxunjon": "3333",
    "Samadov To'lqin": "4444",
    "Shernazarov Tolib": "5555",
    "Ruziboev Sindor": "6666",
    "Ravshanov Ziyodullo": "7777",
    "Yadullaev Umidjon": "8888",
    "Mustafoev Abdullo": "9999",
    "Rajabboev Pulat": "0000",
}

logging.basicConfig(level=logging.INFO)

# ================== BOT ==================

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== DATABASE ==================

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,              -- real day: YYYY-MM-DD
    period TEXT NOT NULL,           -- period key: YYYY-MM (period starts on 2nd)
    tg_id INTEGER NOT NULL,
    employee TEXT NOT NULL,
    category TEXT NOT NULL,
    value INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS employee_links (
    tg_id INTEGER PRIMARY KEY,
    employee TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS employee_pins (
    employee TEXT PRIMARY KEY,
    pin TEXT NOT NULL
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_period_emp_cat ON reports(period, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_day_emp_cat ON reports(day, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_tgid_created ON reports(tg_id, created_at)")
conn.commit()


def seed_pins():
    for emp, pin in EMPLOYEE_PINS.items():
        cur.execute("INSERT OR REPLACE INTO employee_pins(employee, pin) VALUES (?, ?)", (emp, pin))
    conn.commit()


# ================== KLAVIATURA ==================

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CATEGORIES] + [[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )


# ================== HELPERS ==================

user_state = {}

def is_private(m: Message) -> bool:
    return m.chat.type == "private"

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def get_linked_employee(tg_id: int):
    cur.execute("SELECT employee FROM employee_links WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    return row[0] if row else None

def get_period_key(d: date | None = None) -> str:
    """
    Period starts every month on day 2.
    - If day >= 2 -> current month is the period key (YYYY-MM)
    - If day == 1 -> belongs to previous month's period
    """
    d = d or date.today()
    if d.day >= 2:
        return d.strftime("%Y-%m")
    prev = d.replace(day=1) - timedelta(days=1)
    return prev.strftime("%Y-%m")

def sum_day(day_iso: str, employee: str, category: str) -> int:
    cur.execute("""
        SELECT COALESCE(SUM(value),0) FROM reports
        WHERE day = ? AND employee = ? AND category = ?
    """, (day_iso, employee, category))
    return int(cur.fetchone()[0] or 0)

def sum_period(period: str, employee: str, category: str) -> int:
    cur.execute("""
        SELECT COALESCE(SUM(value),0) FROM reports
        WHERE period = ? AND employee = ? AND category = ?
    """, (period, employee, category))
    return int(cur.fetchone()[0] or 0)

def sum_period_employee_total(period: str, employee: str) -> int:
    cur.execute("""
        SELECT COALESCE(SUM(value),0) FROM reports
        WHERE period = ? AND employee = ?
    """, (period, employee))
    return int(cur.fetchone()[0] or 0)

def motivational(delta: int) -> str:
    if delta >= 10:
        return "🔥 Зўр! Бугунги темп жуда баланд — давом!"
    if delta >= 1:
        return "👏 Яхши! Кечагидан юқори — супер!"
    if delta == 0:
        return "💪 Барқарор! Озгина қўшимча босим берсак, янада яхши бўлади."
    if delta <= -10:
        return "🫶 Ҳеч гап йўқ. Бугун сал пастроқ — эртага албатта кўтарамиз!"
    return "🙂 Бугун сал камроқ. Руҳни туширмаймиз — темпни қайта ошириб кетамиз!"

async def safe_group_send(text: str):
    try:
        await bot.send_message(GROUP_ID, text, parse_mode="HTML")
    except Exception as e:
        logging.exception("Groupga yuborishda xatolik: %s", e)


# ================== LINK / START ==================

@dp.message(Command("link"))
async def link_employee(message: Message):
    if not is_private(message):
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("✅ Уланиш учун: <b>/link 1234</b>", parse_mode="HTML")
        return

    pin = parts[1]
    cur.execute("SELECT employee FROM employee_pins WHERE pin = ?", (pin,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ PIN нотўғри. Adminдан PIN сўранг.")
        return

    employee = row[0]
    cur.execute("INSERT OR REPLACE INTO employee_links(tg_id, employee) VALUES (?, ?)",
                (message.from_user.id, employee))
    conn.commit()

    await message.answer(f"✅ Уландингиз: <b>{employee}</b>\nЭнди /start босинг.", parse_mode="HTML")


@dp.message(Command("start"))
async def start(message: Message):
    if not is_private(message):
        return

    emp = get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer(
            "Сиз ҳали уланмагансиз.\n"
            "Admin берган PIN билан уланинг:\n"
            "<b>/link 1234</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user_state[message.from_user.id] = {"employee": emp}
    await message.answer(
        f"✅ Салом, <b>{emp}</b>!\n📌 Иш турини танланг:",
        parse_mode="HTML",
        reply_markup=categories_kb()
    )


@dp.message(Command("cancel"))
async def cancel_cmd(message: Message):
    if not is_private(message):
        return
    user_state.pop(message.from_user.id, None)
    await message.answer("Bekor qilindi. /start", reply_markup=ReplyKeyboardRemove())


@dp.message(lambda m: is_private(m) and m.text == "❌ Bekor qilish")
async def cancel_btn(message: Message):
    user_state.pop(message.from_user.id, None)
    await message.answer("Bekor qilindi. /start", reply_markup=ReplyKeyboardRemove())


# ================== CATEGORY -> NUMBER ==================

@dp.message(lambda m: is_private(m) and m.text in CATEGORIES)
async def select_category(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        await message.answer("Avval /start bosing.")
        return

    state["category"] = message.text
    await message.answer("✍️ Raqam kiriting (faqat son):", reply_markup=ReplyKeyboardRemove())


@dp.message(lambda m: is_private(m) and m.text and m.text.isdigit())
async def save_number(message: Message):
    state = user_state.get(message.from_user.id)
    if not state or "employee" not in state or "category" not in state:
        await message.answer("Avval /start bosing.")
        return

    emp = state["employee"]
    cat = state["category"]
    add_val = int(message.text)

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    now_iso = datetime.now().isoformat(timespec="seconds")

    cur.execute("""
        INSERT INTO reports(day, period, tg_id, employee, category, value, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (today_iso, period, message.from_user.id, emp, cat, add_val, now_iso))
    conn.commit()

    today_sum = sum_day(today_iso, emp, cat)
    yday_sum = sum_day(yday_iso, emp, cat)
    delta = today_sum - yday_sum

    period_sum = sum_period(period, emp, cat)

    # Hodimga javob
    await message.answer(
        f"✅ Saqlandi.\n"
        f"👤 {emp}\n"
        f"🧩 {cat}\n"
        f"📌 Бугунги жами: <b>{today_sum}</b> (кечага: {delta:+d})\n"
        f"📆 Ойлик (2-сана период): <b>{period_sum}</b>\n\n"
        f"/start билан давом этинг.",
        parse_mode="HTML"
    )

    # Guruhga LIVE хабар
    text = (
        f"✅ <b>{emp}</b> киритди\n"
        f"🧩 Категория: <b>{cat}</b>\n"
        f"➕ Қўшилди: <b>+{add_val}</b>\n"
        f"📌 Бугунги жами: <b>{today_sum}</b> (кечага {delta:+d})\n"
        f"📆 Ойлик (2-сана период): <b>{period_sum}</b>\n"
        f"{motivational(delta)}"
    )
    await safe_group_send(text)

    user_state.pop(message.from_user.id, None)


# ================== /me (ходим учун) ==================

@dp.message(Command("me"))
async def me_cmd(message: Message):
    if not is_private(message):
        return

    emp = get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Аввал /link билан уланинг.")
        return

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    lines = [
        f"👤 <b>{emp}</b>",
        f"📆 Период (2-сана): <b>{period}</b>",
        f"🗓 Бугун: <b>{today_iso}</b> | Кеча: <b>{yday_iso}</b>",
        ""
    ]

    for cat in CATEGORIES:
        t = sum_day(today_iso, emp, cat)
        y = sum_day(yday_iso, emp, cat)
        d = t - y
        p = sum_period(period, emp, cat)
        lines.append(f"• <b>{cat}</b>: бугун {t} (кечага {d:+d}) | период {p}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ================== /undo (ходим учун) ==================

@dp.message(Command("undo"))
async def undo_cmd(message: Message):
    if not is_private(message):
        return

    emp = get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Аввал /link билан уланинг.")
        return

    cur.execute("""
        SELECT id, day, period, category, value, created_at
        FROM reports
        WHERE tg_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (message.from_user.id,))
    row = cur.fetchone()
    if not row:
        await message.answer("❗ Бекор қилиш учун ёзув йўқ.")
        return

    rid, day_iso, period, cat, val, created_at = row
    cur.execute("DELETE FROM reports WHERE id = ?", (rid,))
    conn.commit()

    await message.answer(f"✅ Бекор қилинди: <b>{cat}</b> (-{val}) [{day_iso}]", parse_mode="HTML")

    await safe_group_send(
        f"↩️ <b>{emp}</b> охирги киритганини бекор қилди\n"
        f"🧩 Категория: <b>{cat}</b>\n"
        f"➖ Айирилди: <b>-{val}</b>\n"
        f"🗓 {day_iso} | 📆 период {period}\n"
        f"🕒 {created_at}"
    )


# ================== ADMIN RESET COMMANDS ==================
# (sen aytgan: bugun/kecha/0ga tushirish va umumiy)

@dp.message(Command("reset_today"))
async def reset_today(message: Message):
    if not is_admin(message.from_user.id):
        return
    today_iso = date.today().isoformat()
    cur.execute("DELETE FROM reports WHERE day = ?", (today_iso,))
    conn.commit()
    await message.answer(f"✅ Bugungi ma’lumotlar 0 qilindi: {today_iso}")

@dp.message(Command("reset_yesterday"))
async def reset_yesterday(message: Message):
    if not is_admin(message.from_user.id):
        return
    yday_iso = (date.today() - timedelta(days=1)).isoformat()
    cur.execute("DELETE FROM reports WHERE day = ?", (yday_iso,))
    conn.commit()
    await message.answer(f"✅ Kechagi ma’lumotlar 0 qilindi: {yday_iso}")

@dp.message(Command("reset_period"))
async def reset_period(message: Message):
    if not is_admin(message.from_user.id):
        return
    period = get_period_key(date.today())
    cur.execute("DELETE FROM reports WHERE period = ?", (period,))
    conn.commit()
    await message.answer(f"✅ Hozirgi period 0 qilindi (2-sanadan): {period}")

@dp.message(Command("reset_all"))
async def reset_all(message: Message):
    if not is_admin(message.from_user.id):
        return
    cur.execute("DELETE FROM reports")
    conn.commit()
    await message.answer("✅ Barcha ma’lumotlar 0 qilindi (hammasi o'chdi).")


# ================== ADMIN STATS ==================
# Сен команд берганда: ким фаол/ким қолоқ, категория лидерлари

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    period = get_period_key(date.today())

    # 1) Umumiy faoliyat (period bo'yicha)
    totals = []
    for emp in EMPLOYEES:
        totals.append((emp, sum_period_employee_total(period, emp)))
    totals_sorted = sorted(totals, key=lambda x: x[1], reverse=True)

    # 2) Category leaders (period bo'yicha)
    cat_leaders = []
    for cat in CATEGORIES:
        best_emp = None
        best_val = -1
        for emp in EMPLOYEES:
            v = sum_period(period, emp, cat)
            if v > best_val:
                best_val = v
                best_emp = emp
        if best_val > 0:
            cat_leaders.append((cat, best_emp, best_val))
        else:
            cat_leaders.append((cat, "—", 0))

    # 3) Faol / sust (oddiy threshold)
    # Threshold: median ga nisbatan "sust" aniqlaymiz (yomon demaymiz, motivatsiya uslubida)
    vals = [v for _, v in totals_sorted]
    med = sorted(vals)[len(vals)//2] if vals else 0

    top5 = totals_sorted[:5]
    bottom5 = list(reversed(totals_sorted[-5:]))

    text = [f"📊 <b>STATISTIKA</b>\n📆 Период (2-сана): <b>{period}</b>\n"]

    text.append("🏆 <b>Энг фаол (Top 5)</b>")
    for i, (emp, v) in enumerate(top5, 1):
        text.append(f"{i}) {emp}: <b>{v}</b>")

    text.append("\n🙂 <b>Қўллаб-қувватлаш керак (Bottom 5)</b>")
    for i, (emp, v) in enumerate(bottom5, 1):
        text.append(f"{i}) {emp}: <b>{v}</b>")

    text.append("\n🎯 <b>Категория бўйича лидерлар</b>")
    for cat, emp, v in cat_leaders:
        if v > 0:
            text.append(f"• {cat}: <b>{emp}</b> ({v})")
        else:
            text.append(f"• {cat}: —")

    text.append("\n💡 Изоҳ: Паст чиққанлар — 'ёмон' дегани эмас. Шароит/смена/вазият бўлиши мумкин. Асосийси — бирга темпни ошириш. 🤝")

    await message.answer("\n".join(text), parse_mode="HTML")


# ================== MAIN ==================

async def main():
    seed_pins()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
