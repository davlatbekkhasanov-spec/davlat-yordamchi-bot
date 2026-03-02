import os
import asyncio
import logging
import sqlite3
from datetime import datetime, date, timedelta
import html

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


# ============================================================
# BOT
# ============================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ============================================================
# DB (SQLite hardening)
# ============================================================

# timeout=30 -> lock kamroq bo'ladi
conn = sqlite3.connect("data.db", check_same_thread=False, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# WAL -> parallel o'qish/yozish ancha yaxshi
cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")
conn.commit()

db_lock = asyncio.Lock()

async def db_exec(query: str, params: tuple = ()):
    async with db_lock:
        cur.execute(query, params)
        conn.commit()

async def db_fetchone(query: str, params: tuple = ()):
    async with db_lock:
        cur.execute(query, params)
        return cur.fetchone()

async def db_fetchall(query: str, params: tuple = ()):
    async with db_lock:
        cur.execute(query, params)
        return cur.fetchall()


# Tables
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
    period TEXT NOT NULL,
    employee TEXT NOT NULL,
    category TEXT NOT NULL,
    plan_value INTEGER NOT NULL,
    PRIMARY KEY (period, employee, category)
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_period_emp_cat ON reports(period, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_day_emp_cat ON reports(day, employee, category)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_tgid_created ON reports(tg_id, created_at)")
conn.commit()


async def seed_pins():
    for emp, pin in EMPLOYEE_PINS.items():
        await db_exec(
            "INSERT OR REPLACE INTO employee_pins(employee, pin) VALUES (?, ?)",
            (emp, pin)
        )


# ============================================================
# KEYBOARDS
# ============================================================

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CATEGORIES] + [[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )

def after_save_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Yana kategoriya"), KeyboardButton(text="✅ Yakunlash")],
            [KeyboardButton(text="↩️ Undo"), KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )


# ============================================================
# HELPERS
# ============================================================

user_state: dict[int, dict] = {}

def is_private(m: Message) -> bool:
    return m.chat.type == "private"

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

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

def motivational(delta: int) -> str:
    # doim motivatsiya
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
    # HTML safe
    lines = [html.escape("" if x is None else str(x)) for x in lines]
    if title:
        lines = [html.escape(title), *lines]

    width = max([len(x) for x in lines] + [0])
    top = "┏" + "━" * (width + 2) + "┓"
    mid = ["┃ " + ln.ljust(width) + " ┃" for ln in lines]
    bottom = "┗" + "━" * (width + 2) + "┛"
    return "<pre>" + "\n".join([top, *mid, bottom]) + "</pre>"

async def safe_group_send(html_text: str):
    try:
        await bot.send_message(GROUP_ID, html_text, parse_mode="HTML")
    except Exception as e:
        logging.exception("Groupga yuborishda xatolik: %s", e)


# DB query helpers (async)
async def get_linked_employee(tg_id: int) -> str | None:
    row = await db_fetchone("SELECT employee FROM employee_links WHERE tg_id = ?", (tg_id,))
    return row["employee"] if row else None

async def sum_day(day_iso: str, employee: str, category: str) -> int:
    row = await db_fetchone("""
        SELECT COALESCE(SUM(value),0) AS s FROM reports
        WHERE day = ? AND employee = ? AND category = ?
    """, (day_iso, employee, category))
    return int(row["s"] or 0)

async def sum_day_total(day_iso: str, employee: str) -> int:
    row = await db_fetchone("""
        SELECT COALESCE(SUM(value),0) AS s FROM reports
        WHERE day = ? AND employee = ?
    """, (day_iso, employee))
    return int(row["s"] or 0)

async def sum_period(period: str, employee: str, category: str) -> int:
    row = await db_fetchone("""
        SELECT COALESCE(SUM(value),0) AS s FROM reports
        WHERE period = ? AND employee = ? AND category = ?
    """, (period, employee, category))
    return int(row["s"] or 0)

async def sum_period_total(period: str, employee: str) -> int:
    row = await db_fetchone("""
        SELECT COALESCE(SUM(value),0) AS s FROM reports
        WHERE period = ? AND employee = ?
    """, (period, employee))
    return int(row["s"] or 0)

async def day_has_any(day_iso: str, employee: str, category: str) -> bool:
    row = await db_fetchone("""
        SELECT 1 AS ok FROM reports
        WHERE day = ? AND employee = ? AND category = ?
        LIMIT 1
    """, (day_iso, employee, category))
    return row is not None

async def get_plan(period: str, employee: str, category: str) -> int | None:
    row = await db_fetchone("""
        SELECT plan_value FROM monthly_plans
        WHERE period = ? AND employee = ? AND category = ?
    """, (period, employee, category))
    return int(row["plan_value"]) if row else None


# ============================================================
# LINK / START / CANCEL
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
    row = await db_fetchone("SELECT employee FROM employee_pins WHERE pin = ?", (pin,))
    if not row:
        await message.answer("❌ PIN noto‘g‘ri. Adminдан PIN сўранг.")
        return

    employee = row["employee"]
    await db_exec(
        "INSERT OR REPLACE INTO employee_links(tg_id, employee) VALUES (?, ?)",
        (message.from_user.id, employee)
    )

    await message.answer(f"✅ Ulandingiz: <b>{html.escape(employee)}</b>\nEndi /start bosing.", parse_mode="HTML")


@dp.message(Command("start"))
async def start(message: Message):
    if not is_private(message):
        return

    emp = await get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer(
            "Siz hali ulanmagansiz.\nAdmin bergan PIN bilan ulang:\n<b>/link 1234</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user_state[message.from_user.id] = {"employee": emp, "session": []}
    await message.answer(
        f"✅ Salom, <b>{html.escape(emp)}</b>!\n📌 Ish turini tanlang:",
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
# CATEGORY -> NUMBER (NO GROUP SPAM)
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

    await db_exec("""
        INSERT INTO reports(day, period, tg_id, employee, category, value, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (today_iso, period, message.from_user.id, emp, cat, add_val, now_iso))

    today_sum = await sum_day(today_iso, emp, cat)
    period_sum = await sum_period(period, emp, cat)

    # "kecha yo'q" bo'lsa +252 deb chalg'itmaymiz
    if await day_has_any(yday_iso, emp, cat):
        yday_sum = await sum_day(yday_iso, emp, cat)
        delta = today_sum - yday_sum
        ytxt = f"Kechaga: {delta:+d}"
        mot_delta = delta
    else:
        ytxt = "Kecha: kiritilmagan"
        mot_delta = 0

    plan = await get_plan(period, emp, cat)
    if plan and plan > 0:
        pct = int((period_sum / plan) * 100)
        left = max(plan - period_sum, 0)
        plan_txt = f"Plan: {period_sum}/{plan} ({pct}%) | Qoldi: {left}"
    else:
        plan_txt = "Plan: qo‘yilmagan"

    # session ichiga yig'amiz (yakunlashda guruhga bitta ketadi)
    state.setdefault("session", []).append({
        "category": cat,
        "added": add_val,
    })
    state.pop("category", None)

    await message.answer(
        f"✅ Saqlandi.\n"
        f"🧩 {cat}\n"
        f"Bugun jami: <b>{today_sum}</b> ({ytxt})\n"
        f"Period (2-sanadan): <b>{period_sum}</b>\n"
        f"{plan_txt}\n\n"
        f"{motivational(mot_delta)}\n"
        f"Endi nima qilamiz?",
        parse_mode="HTML",
        reply_markup=after_save_kb()
    )


@dp.message(lambda m: is_private(m) and m.text == "➕ Yana kategoriya")
async def again_category(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        await message.answer("Avval /start bosing.")
        return
    await message.answer("📌 Ish turini tanlang:", reply_markup=categories_kb())


@dp.message(lambda m: is_private(m) and m.text == "✅ Yakunlash")
async def finalize_report(message: Message):
    state = user_state.get(message.from_user.id)
    if not state or not state.get("session"):
        await message.answer("❗ Hali hech narsa kiritilmadi. /start", reply_markup=ReplyKeyboardRemove())
        return

    emp = state["employee"]
    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    # session agregatsiya: har kategoriya bo'yicha + nechta
    agg: dict[str, int] = {}
    for it in state["session"]:
        agg[it["category"]] = agg.get(it["category"], 0) + int(it["added"])

    lines = [
        f"Sana: {today_iso}",
        f"Xodim: {emp}",
        f"Period: {period}",
        ""
    ]

    total_added = 0
    # faqat sessiondagi kategoriya chiqadi
    for cat, added in agg.items():
        total_added += added

        t_sum = await sum_day(today_iso, emp, cat)
        p_sum = await sum_period(period, emp, cat)

        if await day_has_any(yday_iso, emp, cat):
            y_sum = await sum_day(yday_iso, emp, cat)
            delta = t_sum - y_sum
            ytxt = f"kechaga {delta:+d}"
            mot_delta = delta
        else:
            ytxt = "kecha yo‘q"
            mot_delta = 0

        lines.append(f"{cat}: +{added} | bugun {t_sum} ({ytxt}) | period {p_sum} | {motivational(mot_delta)}")

    lines.append("")
    lines.append(f"Session jami qo‘shildi: {total_added}")
    lines.append("Rahmat! Barakalla! 💪🙂")

    await safe_group_send(box(lines, title="KUNLIK HISOBOT (YAKUN)"))

    await message.answer("✅ Yakunlandi. /start bilan yangi hisobot boshlang.", reply_markup=ReplyKeyboardRemove())
    user_state.pop(message.from_user.id, None)


@dp.message(lambda m: is_private(m) and m.text == "↩️ Undo")
async def undo_btn(message: Message):
    await undo_cmd(message)


# ============================================================
# /me (employee)
# ============================================================

@dp.message(Command("me"))
async def me_cmd(message: Message):
    if not is_private(message):
        return

    emp = await get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Avval /link bilan ulang.")
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
        t = await sum_day(today_iso, emp, cat)
        p = await sum_period(period, emp, cat)
        if t == 0 and p == 0:
            continue
        if await day_has_any(yday_iso, emp, cat):
            y = await sum_day(yday_iso, emp, cat)
            d = t - y
            ytxt = f"kechaga {d:+d}"
        else:
            ytxt = "kecha yo‘q"
        lines.append(f"- {cat}: bugun {t} ({ytxt}) | period {p}")

    await message.answer(box(lines, title="MENING STATISTIKAM"), parse_mode="HTML")


# ============================================================
# /undo (employee)
# ============================================================

@dp.message(Command("undo"))
async def undo_cmd(message: Message):
    if not is_private(message):
        return

    emp = await get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Avval /link bilan ulang.")
        return

    row = await db_fetchone("""
        SELECT id, day, period, category, value, created_at
        FROM reports
        WHERE tg_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (message.from_user.id,))
    if not row:
        await message.answer("❗ Bekor qilish uchun yozuv yo‘q.")
        return

    rid = row["id"]
    cat = row["category"]
    val = row["value"]
    day_iso = row["day"]
    created_at = row["created_at"]

    await db_exec("DELETE FROM reports WHERE id = ?", (rid,))

    # sessiondan ham olib tashlash (agar session bor bo'lsa)
    st = user_state.get(message.from_user.id)
    if st and st.get("session"):
        # oxirgi mos category/value ni chiqarishga urinib ko'ramiz
        # (session "added" bo'yicha aniq topa olmasa ham, muammo emas)
        for i in range(len(st["session"]) - 1, -1, -1):
            if st["session"][i].get("category") == cat and int(st["session"][i].get("added", -1)) == int(val):
                st["session"].pop(i)
                break

    await message.answer(box(
        [f"Bekor qilindi: {cat}", f"-{val} | {day_iso}", f"Time: {created_at}"],
        title="UNDO"
    ), parse_mode="HTML")


# ============================================================
# ADMIN: REPORT / TOP / LEADERS / STATS
# ============================================================

@dp.message(Command("report"))
async def report_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    # /report today | yesterday | period
    parts = message.text.strip().split()
    mode = parts[1].lower() if len(parts) > 1 else "period"

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    lines = []
    if mode == "today":
        lines.append(f"REPORT: BUGUN ({today_iso})")
        for emp in EMPLOYEES:
            total = await sum_day_total(today_iso, emp)
            if total:
                lines.append(f"{emp}: {total}")
    elif mode == "yesterday":
        lines.append(f"REPORT: KECHA ({yday_iso})")
        for emp in EMPLOYEES:
            total = await sum_day_total(yday_iso, emp)
            if total:
                lines.append(f"{emp}: {total}")
    else:
        lines.append(f"REPORT: PERIOD (2-sanadan) [{period}]")
        for emp in EMPLOYEES:
            total = await sum_period_total(period, emp)
            if total:
                lines.append(f"{emp}: {total}")

    if len(lines) == 1:
        lines.append("Hali ma’lumot yo‘q.")

    await message.answer(box(lines, title="HISOBOT"), parse_mode="HTML")


@dp.message(Command("top"))
async def top_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    # /top today | yesterday | period
    parts = message.text.strip().split()
    mode = parts[1].lower() if len(parts) > 1 else "period"

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    totals = []
    if mode == "today":
        key = f"BUGUN {today_iso}"
        for emp in EMPLOYEES:
            totals.append((emp, await sum_day_total(today_iso, emp)))
    elif mode == "yesterday":
        key = f"KECHA {yday_iso}"
        for emp in EMPLOYEES:
            totals.append((emp, await sum_day_total(yday_iso, emp)))
    else:
        key = f"PERIOD {period}"
        for emp in EMPLOYEES:
            totals.append((emp, await sum_period_total(period, emp)))

    totals = sorted(totals, key=lambda x: x[1], reverse=True)
    top5 = totals[:5]
    bottom5 = list(reversed(totals[-5:]))

    lines = [f"TOP/BOTTOM ({key})", ""]
    lines.append("🏆 TOP 5:")
    for i, (emp, v) in enumerate(top5, 1):
        lines.append(f"{i}) {emp}: {v}")

    lines.append("")
    lines.append("🙂 QO‘LLAB-QUVVATLASH (Bottom 5):")
    for i, (emp, v) in enumerate(bottom5, 1):
        lines.append(f"{i}) {emp}: {v}")

    lines.append("")
    lines.append("Izoh: past natija yomon emas. Maqsad — barqaror o‘sish 🤝")

    await message.answer(box(lines, title="RANKING"), parse_mode="HTML")


@dp.message(Command("leaders"))
async def leaders_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    # /leaders today | period
    parts = message.text.strip().split()
    mode = parts[1].lower() if len(parts) > 1 else "period"

    today = date.today()
    today_iso = today.isoformat()
    period = get_period_key(today)

    lines = []
    if mode == "today":
        lines.append(f"LEADERS: BUGUN ({today_iso})")
        for cat in CATEGORIES:
            best_emp, best_val = "—", 0
            for emp in EMPLOYEES:
                v = await sum_day(today_iso, emp, cat)
                if v > best_val:
                    best_val, best_emp = v, emp
            lines.append(f"{cat}: {best_emp} ({best_val})" if best_val > 0 else f"{cat}: —")
    else:
        lines.append(f"LEADERS: PERIOD (2-sanadan) [{period}]")
        for cat in CATEGORIES:
            best_emp, best_val = "—", 0
            for emp in EMPLOYEES:
                v = await sum_period(period, emp, cat)
                if v > best_val:
                    best_val, best_emp = v, emp
            lines.append(f"{cat}: {best_emp} ({best_val})" if best_val > 0 else f"{cat}: —")

    await message.answer(box(lines, title="KATEGORIYA LIDERLARI"), parse_mode="HTML")


@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    # period ranking
    totals = [(emp, await sum_period_total(period, emp)) for emp in EMPLOYEES]
    totals_sorted = sorted(totals, key=lambda x: x[1], reverse=True)

    # strong category per employee (period)
    strong_lines = []
    for emp in EMPLOYEES:
        best_cat, best_val = None, 0
        for cat in CATEGORIES:
            v = await sum_period(period, emp, cat)
            if v > best_val:
                best_val, best_cat = v, cat
        if best_val > 0:
            strong_lines.append(f"{emp}: {best_cat} ({best_val})")

    lines = [
        f"Period (2-sanadan): {period}",
        f"Bugun: {today_iso} | Kecha: {yday_iso}",
        ""
    ]
    lines.append("📌 Period bo‘yicha umumiy (Top 10):")
    for i, (emp, v) in enumerate(totals_sorted[:10], 1):
        lines.append(f"{i}) {emp}: {v}")

    lines.append("")
    lines.append("⭐ Kim qaysi sohada kuchli (period):")
    if strong_lines:
        lines.extend(strong_lines)
    else:
        lines.append("Hali ma’lumot yo‘q.")

    lines.append("")
    lines.append("💡 Motivatsiya: hamma bir xil sharoitda emas. Maqsad — barqaror o‘sish. 🤝")

    await message.answer(box(lines, title="ADMIN DASHBOARD"), parse_mode="HTML")


# ============================================================
# ADMIN: RESETs (0 ga tushirish)
# ============================================================

@dp.message(Command("reset_today"))
async def reset_today(message: Message):
    if not is_admin(message.from_user.id):
        return
    today_iso = date.today().isoformat()
    await db_exec("DELETE FROM reports WHERE day = ?", (today_iso,))
    await message.answer(box([f"Bugun: {today_iso}", "Ma'lumotlar 0 qilindi ✅"], title="RESET TODAY"), parse_mode="HTML")

@dp.message(Command("reset_yesterday"))
async def reset_yesterday(message: Message):
    if not is_admin(message.from_user.id):
        return
    yday_iso = (date.today() - timedelta(days=1)).isoformat()
    await db_exec("DELETE FROM reports WHERE day = ?", (yday_iso,))
    await message.answer(box([f"Kecha: {yday_iso}", "Ma'lumotlar 0 qilindi ✅"], title="RESET YESTERDAY"), parse_mode="HTML")

@dp.message(Command("reset_period"))
async def reset_period(message: Message):
    if not is_admin(message.from_user.id):
        return
    period = get_period_key(date.today())
    await db_exec("DELETE FROM reports WHERE period = ?", (period,))
    await message.answer(box([f"Period: {period}", "Ma'lumotlar 0 qilindi ✅"], title="RESET PERIOD"), parse_mode="HTML")

@dp.message(Command("reset_all"))
async def reset_all(message: Message):
    if not is_admin(message.from_user.id):
        return
    await db_exec("DELETE FROM reports", ())
    await message.answer(box(["Hamma ma'lumotlar o'chdi ✅"], title="RESET ALL"), parse_mode="HTML")


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
            "Format:\n<b>/setplan Employee | Category | Plan</b>\n"
            "Misol:\n<b>/setplan Ravshanov Oxunjon | Фото ТМЦ | 120</b>",
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

    await db_exec("""
        INSERT OR REPLACE INTO monthly_plans(period, employee, category, plan_value)
        VALUES (?,?,?,?)
    """, (period, emp, cat, plan_val))

    await message.answer(
        box([f"Period: {period}", f"{emp}", f"{cat}", f"Plan = {plan_val}"], title="PLAN SET"),
        parse_mode="HTML"
    )


# ============================================================
# MAIN
# ============================================================

async def main():
    await seed_pins()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
