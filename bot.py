import os
import asyncio
import logging
import sqlite3
from datetime import datetime, date, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


# ============================================================
# CONFIG
# ============================================================

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
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
    "Samandar Foto",
    "Mustafoev Abdullo",
    "Rajabboev Pulat"
]

CATEGORIES = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Счет ТСД",
    "Фасовка",
    "Услуга",
    "Доставка",
    "Переоценка",
    "Пересчет товаров",
    "Места хр"
]

# PINлар (ходимларга берилади)
EMPLOYEE_PINS = {
    "Sagdullaev Yunus": "1111",
    "Toxirov Muslimbek": "2222",
    "Ravshanov Oxunjon": "3333",
    "Samadov To'lqin": "4444",
    "Shernazarov Tolib": "5555",
    "Ruziboev Sindor": "6666",
    "Ravshanov Ziyodullo": "7777",
    "Samandar Foto": "8888",
    "Mustafoev Abdullo": "9999",
    "Rajabboev Pulat": "0000",
}

# Optional: stock file path (agar kerak bo'lsa)
STOCK_FILE = os.getenv("STOCK_FILE", "")  # masalan: "stock.csv"


# ============================================================
# BOT
# ============================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ============================================================
# DB
# ============================================================

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,              -- YYYY-MM-DD
    period TEXT NOT NULL,           -- YYYY-MM (period starts on 2nd)
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

cur.execute("""
CREATE TABLE IF NOT EXISTS monthly_plans (
    period TEXT NOT NULL,           -- YYYY-MM (2-sanadan boshlanadigan period)
    employee TEXT NOT NULL,
    category TEXT NOT NULL,
    plan_value INTEGER NOT NULL,
    PRIMARY KEY (period, employee, category)
)
""")

# Optional stock table (agar keyin ishlatsang)
cur.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    code TEXT,
    qty REAL,
    updated_at TEXT
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_period_emp_cat ON reports(period, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_day_emp_cat ON reports(day, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_tgid_created ON reports(tg_id, created_at)")
conn.commit()


# ============================================================
# KEYBOARDS
# ============================================================

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CATEGORIES] + [[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )


# ============================================================
# HELPERS
# ============================================================

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
    Period har oy 2-sanadan boshlanadi.
    1-sana -> oldingi oy periodiga kiradi.
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

def get_plan(period: str, employee: str, category: str) -> int | None:
    cur.execute("""
        SELECT plan_value FROM monthly_plans
        WHERE period = ? AND employee = ? AND category = ?
    """, (period, employee, category))
    row = cur.fetchone()
    return int(row[0]) if row else None

def motivational(delta: int) -> str:
    # Doim motivatsiya, ruhiy ko'tarinki
    if delta >= 10:
        return "🔥 Zo‘r! Bugun temp juda baland!"
    if delta >= 1:
        return "👏 Juda yaxshi! Kechagidan yuqori!"
    if delta == 0:
        return "💪 Barqaror! Ozgina bosim bersak, yanada zo‘r bo‘ladi!"
    if delta <= -10:
        return "🫶 Hech gap yo‘q. Bugun sal pastroq, ertaga qaytarib olamiz!"
    return "🙂 Bugun sal kamroq. Ruhni tushirmaymiz — tempni yana oshiramiz!"

def box(lines: list[str], title: str | None = None) -> str:
    """
    Beautiful box using Unicode lines, wrapped in <pre>.
    Keep lines not too long for Telegram.
    """
    # sanitize (avoid None)
    lines = [("" if x is None else str(x)) for x in lines]
    if title:
        lines = [f"{title}", *lines]

    width = max([len(x) for x in lines] + [0])
    top = "┏" + "━" * (width + 2) + "┓"
    mid = []
    for ln in lines:
        mid.append("┃ " + ln.ljust(width) + " ┃")
    bottom = "┗" + "━" * (width + 2) + "┛"
    return "<pre>" + "\n".join([top, *mid, bottom]) + "</pre>"

async def safe_group_send(html_text: str):
    try:
        await bot.send_message(GROUP_ID, html_text, parse_mode="HTML")
    except Exception as e:
        logging.exception("Groupga yuborishda xatolik: %s", e)


# ============================================================
# OPTIONAL: STOCK LOADER (KeyError 'name' muammosini 100% yopadi)
# ============================================================

def _norm_keys(row: dict) -> dict:
    # row keys: strip, lower, remove BOM
    return {str(k).replace("\ufeff", "").strip().lower(): v for k, v in row.items()}

def load_stock_safely():
    """
    Agar STOCK_FILE berilgan bo'lsa, yiqilmasdan yuklaydi.
    'name' bo'lmasa ham ruscha/ozbekcha ustunlarni topishga harakat qiladi.
    Hech narsa topolmasa - skip qiladi (bot crash bo'lmaydi).
    """
    if not STOCK_FILE:
        return
    try:
        import csv
        # 1C export ko'pincha ; va utf-8-sig bo'ladi
        with open(STOCK_FILE, "r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(2048)
            f.seek(0)
            # delimiter guess (very simple)
            delimiter = ";" if sample.count(";") >= sample.count(",") else ","

            reader = csv.DictReader(f, delimiter=delimiter)
            now = datetime.now().isoformat(timespec="seconds")

            inserted = 0
            for raw in reader:
                r = _norm_keys(raw)

                # possible name keys
                name = (
                    r.get("name")
                    or r.get("наименование")
                    or r.get("номенклатура")
                    or r.get("товар")
                    or r.get("название")
                )
                if not name:
                    continue

                code = r.get("code") or r.get("артикул") or r.get("код") or r.get("sku") or ""
                qty_raw = r.get("qty") or r.get("quantity") or r.get("остаток") or r.get("количество") or "0"
                try:
                    qty = float(str(qty_raw).replace(",", "."))
                except Exception:
                    qty = 0.0

                cur.execute("INSERT INTO stock(name, code, qty, updated_at) VALUES (?,?,?,?)",
                            (str(name).strip(), str(code).strip(), qty, now))
                inserted += 1

            conn.commit()
            logging.info("Stock loaded: %s rows", inserted)

    except FileNotFoundError:
        logging.warning("STOCK_FILE topilmadi: %s (skip)", STOCK_FILE)
    except Exception as e:
        # eng muhimi: crash bo'lmasin
        logging.exception("load_stock_safely error (skip): %s", e)


# ============================================================
# SEED PINS
# ============================================================

def seed_pins():
    for emp, pin in EMPLOYEE_PINS.items():
        cur.execute("INSERT OR REPLACE INTO employee_pins(employee, pin) VALUES (?, ?)", (emp, pin))
    conn.commit()


# ============================================================
# COMMANDS: LINK / START / CANCEL
# ============================================================

@dp.message(Command("link"))
async def link_employee(message: Message):
    if not is_private(message):
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("✅ Ulanish uchun: <b>/link 1234</b>", parse_mode="HTML")
        return

    pin = parts[1]
    cur.execute("SELECT employee FROM employee_pins WHERE pin = ?", (pin,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ PIN noto‘g‘ri. Adminдан PIN сўранг.")
        return

    employee = row[0]
    cur.execute("INSERT OR REPLACE INTO employee_links(tg_id, employee) VALUES (?, ?)",
                (message.from_user.id, employee))
    conn.commit()

    await message.answer(f"✅ Ulandingiz: <b>{employee}</b>\nEndi /start bosing.", parse_mode="HTML")


@dp.message(Command("start"))
async def start(message: Message):
    if not is_private(message):
        return

    emp = get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer(
            "Siz hali ulanmagansiz.\n"
            "Admin bergan PIN bilan ulang:\n"
            "<b>/link 1234</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user_state[message.from_user.id] = {"employee": emp}
    await message.answer(
        f"✅ Salom, <b>{emp}</b>!\n📌 Ish turini tanlang:",
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


# ============================================================
# CATEGORY -> NUMBER
# ============================================================

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

    plan = get_plan(period, emp, cat)
    if plan and plan > 0:
        pct = int((period_sum / plan) * 100)
        left = max(plan - period_sum, 0)
        plan_txt = f"Plan: {period_sum}/{plan} ({pct}%) | Qoldi: {left}"
    else:
        plan_txt = "Plan: qo‘yilmagan"

    # Hodimga javob
    await message.answer(
        f"✅ Saqlandi.\n"
        f"🧩 {cat}\n"
        f"Bugun: <b>{today_sum}</b> (kechaga {delta:+d})\n"
        f"Period (2-sanadan): <b>{period_sum}</b>\n"
        f"{plan_txt}\n\n"
        f"/start bilan davom eting.",
        parse_mode="HTML"
    )

    # Groupga chiroyli ramka
    lines = [
        f"Xodim: {emp}",
        f"Kategoriya: {cat}",
        f"+Qo‘shildi: {add_val}",
        f"Bugun jami: {today_sum} (kechaga {delta:+d})",
        f"Period jami: {period_sum}  [{period}]",
        plan_txt,
        motivational(delta)
    ]
    await safe_group_send(box(lines, title="LIVE HISOBOT"))

    user_state.pop(message.from_user.id, None)


# ============================================================
# /me (xodim)
# ============================================================

@dp.message(Command("me"))
async def me_cmd(message: Message):
    if not is_private(message):
        return

    emp = get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Avval /link bilan ulanинг.")
        return

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    lines = [
        f"Xodim: {emp}",
        f"Bugun: {today_iso} | Kecha: {yday_iso}",
        f"Period (2-sanadan): {period}",
        ""
    ]
    for cat in CATEGORIES:
        t = sum_day(today_iso, emp, cat)
        y = sum_day(yday_iso, emp, cat)
        d = t - y
        p = sum_period(period, emp, cat)
        lines.append(f"- {cat}: bugun {t} (kechaga {d:+d}) | period {p}")

    await message.answer(box(lines, title="MENING STATISTIKAM"), parse_mode="HTML")


# ============================================================
# /undo (xodim)
# ============================================================

@dp.message(Command("undo"))
async def undo_cmd(message: Message):
    if not is_private(message):
        return

    emp = get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Avval /link bilan ulanинг.")
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
        await message.answer("❗ Bekor qilish uchun yozuv yo‘q.")
        return

    rid, day_iso, period, cat, val, created_at = row
    cur.execute("DELETE FROM reports WHERE id = ?", (rid,))
    conn.commit()

    await message.answer(box(
        [f"Bekor qilindi: {cat}", f"-{val}  |  {day_iso}", f"Time: {created_at}"],
        title="UNDO"
    ), parse_mode="HTML")

    await safe_group_send(box(
        [f"Xodim: {emp}", f"Bekor qildi: {cat}", f"-{val}", f"{day_iso} | period {period}", f"{created_at}"],
        title="UNDO (GROUP)"
    ))


# ============================================================
# ADMIN: PLAN
# /setplan Employee | Category | Plan
# ============================================================

@dp.message(Command("setplan"))
async def setplan_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    txt = message.text.replace("/setplan", "", 1).strip()
    parts = [p.strip() for p in txt.split("|")] if "|" in txt else []
    if len(parts) != 3:
        await message.answer(
            "Format:\n"
            "<b>/setplan Employee | Category | Plan</b>\n"
            "Misol:\n"
            "<b>/setplan Ravshanov Oxunjon | Фото ТМЦ | 120</b>",
            parse_mode="HTML"
        )
        return

    emp, cat, plan_str = parts
    if emp not in EMPLOYEES:
        await message.answer("❌ Employee noto‘g‘ri (ro‘yxatdan bo‘lsin).")
        return
    if cat not in CATEGORIES:
        await message.answer("❌ Category noto‘g‘ri (ro‘yxatdan bo‘lsin).")
        return
    if not plan_str.isdigit():
        await message.answer("❌ Plan faqat son bo‘lsin.")
        return

    plan_val = int(plan_str)
    period = get_period_key(date.today())

    cur.execute("""
        INSERT OR REPLACE INTO monthly_plans(period, employee, category, plan_value)
        VALUES (?,?,?,?)
    """, (period, emp, cat, plan_val))
    conn.commit()

    await message.answer(box(
        [f"Period: {period}", f"{emp}", f"{cat}", f"Plan = {plan_val}"],
        title="PLAN SET"
    ), parse_mode="HTML")


# ============================================================
# ADMIN: RESETs (0 ga tushirish)
# ============================================================

@dp.message(Command("reset_today"))
async def reset_today(message: Message):
    if not is_admin(message.from_user.id):
        return
    today_iso = date.today().isoformat()
    cur.execute("DELETE FROM reports WHERE day = ?", (today_iso,))
    conn.commit()
    await message.answer(box([f"Bugun: {today_iso}", "Ma'lumotlar 0 qilindi ✅"], title="RESET TODAY"), parse_mode="HTML")

@dp.message(Command("reset_yesterday"))
async def reset_yesterday(message: Message):
    if not is_admin(message.from_user.id):
        return
    yday_iso = (date.today() - timedelta(days=1)).isoformat()
    cur.execute("DELETE FROM reports WHERE day = ?", (yday_iso,))
    conn.commit()
    await message.answer(box([f"Kecha: {yday_iso}", "Ma'lumotlar 0 qilindi ✅"], title="RESET YESTERDAY"), parse_mode="HTML")

@dp.message(Command("reset_period"))
async def reset_period(message: Message):
    if not is_admin(message.from_user.id):
        return
    period = get_period_key(date.today())
    cur.execute("DELETE FROM reports WHERE period = ?", (period,))
    conn.commit()
    await message.answer(box([f"Period: {period}", "Ma'lumotlar 0 qilindi ✅"], title="RESET PERIOD"), parse_mode="HTML")

@dp.message(Command("reset_all"))
async def reset_all(message: Message):
    if not is_admin(message.from_user.id):
        return
    cur.execute("DELETE FROM reports")
    conn.commit()
    await message.answer(box(["Hamma ma'lumotlar o'chdi ✅"], title="RESET ALL"), parse_mode="HTML")


# ============================================================
# ADMIN: /stats  (faol / sust, kim qaysi sohada kuchli)
# ============================================================

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    period = get_period_key(date.today())

    # Umumiy total bo'yicha ranking
    totals = [(emp, sum_period_employee_total(period, emp)) for emp in EMPLOYEES]
    totals_sorted = sorted(totals, key=lambda x: x[1], reverse=True)

    # Category leaders
    cat_lines = []
    for cat in CATEGORIES:
        best_emp, best_val = None, -1
        for emp in EMPLOYEES:
            v = sum_period(period, emp, cat)
            if v > best_val:
                best_val, best_emp = v, emp
        if best_val <= 0:
            cat_lines.append(f"{cat}: —")
        else:
            cat_lines.append(f"{cat}: {best_emp} ({best_val})")

    top5 = totals_sorted[:5]
    bottom5 = list(reversed(totals_sorted[-5:]))

    lines = [f"Period (2-sanadan): {period}", ""]
    lines.append("TOP 5 (faol):")
    for i, (emp, v) in enumerate(top5, 1):
        lines.append(f"{i}) {emp} = {v}")

    lines.append("")
    lines.append("Bottom 5 (qo'llab-quvvatlash):")
    for i, (emp, v) in enumerate(bottom5, 1):
        lines.append(f"{i}) {emp} = {v}")

    lines.append("")
    lines.append("Kategoriya bo'yicha liderlar:")
    lines.extend([f"- {x}" for x in cat_lines])

    lines.append("")
    lines.append("Izoh: past natija 'yomon' emas. Vaziyat/shift bo'lishi mumkin. Maqsad — birga tempni oshirish 🤝")

    await message.answer(box(lines, title="STATISTIKA"), parse_mode="HTML")


# ============================================================
# MAIN
# ============================================================

async def main():
    seed_pins()
    # optional stock load (crash qilmaydi)
    load_stock_safely()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
