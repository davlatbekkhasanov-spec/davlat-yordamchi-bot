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
# КОНФИГ
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
    "АРМ диспетчер",
    "Исправление пересортицы",
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
    "Yadullaev Umidjon": "8888",
    "Mustafoev Abdullo": "9999",
    "Rajabboev Pulat": "0000",
}


# ============================================================
# БОТ
# ============================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ============================================================
# DB (SQLite hardening)
# ============================================================

conn = sqlite3.connect("data.db", check_same_thread=False, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

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
    day TEXT NOT NULL,
    period TEXT NOT NULL,
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
# КЛАВИАТУРА
# ============================================================

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CATEGORIES] + [[KeyboardButton(text="❌ Бекор қилиш")]],
        resize_keyboard=True
    )

def after_save_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Яна категория"), KeyboardButton(text="✅ Якунлаш")],
            [KeyboardButton(text="↩️ Ундо"), KeyboardButton(text="❌ Бекор қилиш")]
        ],
        resize_keyboard=True
    )

def delete_date_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📌 Бугун"), KeyboardButton(text="📌 Кеча")],
            [KeyboardButton(text="🗓 Бошқа сана"), KeyboardButton(text="❌ Бекор қилиш")]
        ],
        resize_keyboard=True
    )

def employees_kb(with_all: bool = False):
    kb = [[KeyboardButton(text=e)] for e in EMPLOYEES]
    if with_all:
        kb.append([KeyboardButton(text="✅ Ҳамма ходим")])
    kb.append([KeyboardButton(text="❌ Бекор қилиш")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def delete_category_kb():
    kb = [[KeyboardButton(text=c)] for c in CATEGORIES]
    kb.append([KeyboardButton(text="✅ Ҳамма категория")])
    kb.append([KeyboardButton(text="❌ Бекор қилиш")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def confirm_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗑 Ўчиришни тасдиқлайман"), KeyboardButton(text="❌ Бекор қилиш")]
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
    Период ҳар ой 2-санада бошланади.
    1-сана -> олдинги ой периодида.
    """
    d = d or date.today()
    if d.day >= 2:
        return d.strftime("%Y-%m")
    prev = d.replace(day=1) - timedelta(days=1)
    return prev.strftime("%Y-%m")

def motivational(delta: int) -> str:
    if delta >= 10:
        return "🔥 Зўр! Бугун темп жуда баланд!"
    if delta >= 1:
        return "👏 Жуда яхши! Кечагидан юқори!"
    if delta == 0:
        return "💪 Барқарор! Озгина босим берсак, янада зўр бўлади!"
    if delta <= -10:
        return "🫶 Ҳеч гап йўқ. Бугун сал пастроқ, эртага қайтариб оламиз!"
    return "🙂 Бугун сал камроқ. Руҳни туширмаймиз — темпни яна ошириб кетамиз!"

def box(lines: list[str], title: str | None = None) -> str:
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
        logging.exception("Гуруҳга юборишда хатолик: %s", e)


# DB query helpers
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

def parse_iso_date(s: str) -> str | None:
    s = s.strip()
    try:
        # YYYY-MM-DD
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        return None

def fair_grade_from_totals(employee_total: int, totals: list[int]) -> tuple[str, str]:
    """
    Адолатли баҳолаш: жамоа ичидаги кунлик натижаларга нисбатан процентил.
    totals: барча ходимларнинг total’и
    """
    if not totals:
        return ("—", "Ҳали маълумот йўқ.")
    sorted_totals = sorted(totals)
    n = len(sorted_totals)
    if n == 1:
        return ("A", "Яккасиз — яхши темп!")

    # rank (0..n-1)
    rank = 0
    for v in sorted_totals:
        if employee_total >= v:
            rank += 1
    percentile = rank / n  # 0..1

    if employee_total == 0:
        return ("D", "Бугун ҳали старт бўлмади. Бирта иш билан очиб кетамиз 💪")

    if percentile >= 0.90:
        return ("A+", "Лидер! Шу темпни ушлаб турсак, жуда катта натижа бўлади 🔥")
    if percentile >= 0.70:
        return ("A", "Жуда яхши! Барқарорликни сақласак, лидерликка чиқасиз 👏")
    if percentile >= 0.45:
        return ("B", "Нормал темп. Озгина босим — натижа яна юқори бўлади 💪")
    if percentile >= 0.25:
        return ("C", "Ўртача. Ҳозирдан бир-икки йўналишни кучайтирсак, тез ўсиш бўлади 🙂")
    return ("D", "Бугун пастроқ. Руҳни туширмаймиз — эртага қайтарамиз 🫶")


# ============================================================
# /link /start /cancel
# ============================================================

@dp.message(Command("link"))
async def link_employee(message: Message):
    if not is_private(message):
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("✅ Уланиш учун: <b>/link 1234</b>", parse_mode="HTML")
        return

    pin = parts[1]
    row = await db_fetchone("SELECT employee FROM employee_pins WHERE pin = ?", (pin,))
    if not row:
        await message.answer("❌ PIN нотўғри. Админдан PIN сўранг.")
        return

    employee = row["employee"]
    await db_exec(
        "INSERT OR REPLACE INTO employee_links(tg_id, employee) VALUES (?, ?)",
        (message.from_user.id, employee)
    )

    await message.answer(f"✅ Уланди: <b>{html.escape(employee)}</b>\nЭнди /start босинг.", parse_mode="HTML")


@dp.message(Command("start"))
async def start(message: Message):
    if not is_private(message):
        return

    emp = await get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer(
            "Сиз ҳали уланмагансиз.\nАдмин берган PIN билан уланинг:\n<b>/link 1234</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user_state[message.from_user.id] = {"employee": emp, "session": []}
    await message.answer(
        f"✅ Салом, <b>{html.escape(emp)}</b>!\n📌 Категорияни танланг:",
        parse_mode="HTML",
        reply_markup=categories_kb()
    )


@dp.message(Command("cancel"))
async def cancel_cmd(message: Message):
    if not is_private(message):
        return
    user_state.pop(message.from_user.id, None)
    await message.answer("Бекор қилинди. /start", reply_markup=ReplyKeyboardRemove())


@dp.message(lambda m: is_private(m) and m.text == "❌ Бекор қилиш")
async def cancel_btn(message: Message):
    user_state.pop(message.from_user.id, None)
    await message.answer("Бекор қилинди. /start", reply_markup=ReplyKeyboardRemove())


# ============================================================
# Категория -> Сон (ГУРУҲГА СПАМ ЙЎҚ)
# ============================================================

@dp.message(lambda m: is_private(m) and m.text in CATEGORIES)
async def select_category(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        await message.answer("Аввал /start босинг.")
        return
    state["category"] = message.text
    await message.answer("✍️ Рақам киритинг (фақат сон):", reply_markup=ReplyKeyboardRemove())


@dp.message(lambda m: is_private(m) and m.text and m.text.isdigit())
async def save_number(message: Message):
    state = user_state.get(message.from_user.id)
    if not state or "employee" not in state or "category" not in state:
        await message.answer("Аввал /start босинг.")
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

    if await day_has_any(yday_iso, emp, cat):
        yday_sum = await sum_day(yday_iso, emp, cat)
        delta = today_sum - yday_sum
        ytxt = f"Кечага: {delta:+d}"
        mot_delta = delta
    else:
        ytxt = "Кеча: киритилмаган"
        mot_delta = 0

    plan = await get_plan(period, emp, cat)
    if plan and plan > 0:
        pct = int((period_sum / plan) * 100)
        left = max(plan - period_sum, 0)
        plan_txt = f"План: {period_sum}/{plan} ({pct}%) | Қолди: {left}"
    else:
        plan_txt = "План: қўйилмаган"

    state.setdefault("session", []).append({"category": cat, "added": add_val})
    state.pop("category", None)

    await message.answer(
        f"✅ Сақланди.\n"
        f"🧩 {cat}\n"
        f"Бугун жами: <b>{today_sum}</b> ({ytxt})\n"
        f"Период (2-сана): <b>{period_sum}</b>\n"
        f"{plan_txt}\n\n"
        f"{motivational(mot_delta)}\n"
        f"Энди нима қиламиз?",
        parse_mode="HTML",
        reply_markup=after_save_kb()
    )


@dp.message(lambda m: is_private(m) and m.text == "➕ Яна категория")
async def again_category(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        await message.answer("Аввал /start босинг.")
        return
    await message.answer("📌 Категорияни танланг:", reply_markup=categories_kb())


@dp.message(lambda m: is_private(m) and m.text == "✅ Якунлаш")
async def finalize_report(message: Message):
    state = user_state.get(message.from_user.id)
    if not state or not state.get("session"):
        await message.answer("❗ Ҳали ҳеч нарса киритилмаган. /start", reply_markup=ReplyKeyboardRemove())
        return

    emp = state["employee"]
    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    agg: dict[str, int] = {}
    for it in state["session"]:
        agg[it["category"]] = agg.get(it["category"], 0) + int(it["added"])

    best_cat, best_add = max(agg.items(), key=lambda x: x[1])

    # умумий баҳо (фақат иштирок этган категориялар бўйича)
    today_total = 0
    yday_total = 0
    for cat in agg.keys():
        today_total += await sum_day(today_iso, emp, cat)
        if await day_has_any(yday_iso, emp, cat):
            yday_total += await sum_day(yday_iso, emp, cat)

    if yday_total == 0:
        overall_text = "Кеча маълумот йўқ. Бугун яхши старт! 💪"
    else:
        overall_delta = today_total - yday_total
        overall_text = f"Кечага нисбатан: {overall_delta:+d}. {motivational(overall_delta)}"

    lines = [
        f"📅 Сана: {today_iso}",
        f"👤 Ходим: {emp}",
        f"🗓 Период (2-сана): {period}",
        ""
    ]

    for cat in CATEGORIES:
        if cat not in agg:
            continue
        added = agg[cat]
        t_sum = await sum_day(today_iso, emp, cat)
        p_sum = await sum_period(period, emp, cat)

        if await day_has_any(yday_iso, emp, cat):
            y_sum = await sum_day(yday_iso, emp, cat)
            delta = t_sum - y_sum
            ytxt = f"{delta:+d}"
        else:
            ytxt = "йўқ"

        lines.append(f"• {cat}:  +{added}")
        lines.append(f"  Бугун: {t_sum} | Период: {p_sum} | Кеча: {ytxt}")

    lines.append("")
    lines.append(f"⭐ Энг кучли йўналиш: {best_cat} (+{best_add})")
    lines.append(f"🔥 Умумий баҳо: {overall_text}")

    await safe_group_send(box(lines, title="КУНЛИК ҲИСОБОТ (ЯКУН)"))

    await message.answer("✅ Якунланди. /start билан янги ҳисобот бошланг.", reply_markup=ReplyKeyboardRemove())
    user_state.pop(message.from_user.id, None)


@dp.message(lambda m: is_private(m) and m.text == "↩️ Ундо")
async def undo_btn(message: Message):
    await undo_cmd(message)


# ============================================================
# /me (ходим)
# ============================================================

@dp.message(Command("me"))
async def me_cmd(message: Message):
    if not is_private(message):
        return

    emp = await get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Аввал /link билан уланинг.")
        return

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    lines = [
        f"👤 Ходим: {emp}",
        f"📅 Бугун: {today_iso} | Кеча: {yday_iso}",
        f"🗓 Период (2-сана): {period}",
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
            ytxt = f"кечага {d:+d}"
        else:
            ytxt = "кеча йўқ"
        lines.append(f"• {cat}: бугун {t} ({ytxt}) | период {p}")

    await message.answer(box(lines, title="МЕНИНГ СТАТИСТИКАМ"), parse_mode="HTML")


# ============================================================
# /undo (ходим)
# ============================================================

@dp.message(Command("undo"))
async def undo_cmd(message: Message):
    if not is_private(message):
        return

    emp = await get_linked_employee(message.from_user.id)
    if not emp:
        await message.answer("Аввал /link билан уланинг.")
        return

    row = await db_fetchone("""
        SELECT id, day, category, value, created_at
        FROM reports
        WHERE tg_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (message.from_user.id,))
    if not row:
        await message.answer("❗ Бекор қилиш учун ёзув йўқ.")
        return

    rid = row["id"]
    cat = row["category"]
    val = row["value"]
    day_iso = row["day"]
    created_at = row["created_at"]

    await db_exec("DELETE FROM reports WHERE id = ?", (rid,))

    st = user_state.get(message.from_user.id)
    if st and st.get("session"):
        for i in range(len(st["session"]) - 1, -1, -1):
            if st["session"][i].get("category") == cat and int(st["session"][i].get("added", -1)) == int(val):
                st["session"].pop(i)
                break

    await message.answer(
        box([f"Бекор қилинди: {cat}", f"-{val} | {day_iso}", f"Вақт: {created_at}"], title="УНДО"),
        parse_mode="HTML"
    )


# ============================================================
# АДМИН: /status (0 ларсиз, адолатли баҳолаш)
# ============================================================

@dp.message(Command("status"))
async def status_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    today = date.today()
    today_iso = today.isoformat()
    period = get_period_key(today)

    # жамоа totals (bugun) — процентил учун
    team_totals = []
    for emp in EMPLOYEES:
        team_totals.append(await sum_day_total(today_iso, emp))

    blocks = []
    blocks.append(f"📅 Сана: {today_iso}")
    blocks.append(f"🗓 Период (2-сана): {period}")
    blocks.append("")

    # ҳар ходим
    for emp in EMPLOYEES:
        total_today = await sum_day_total(today_iso, emp)
        grade, comment = fair_grade_from_totals(total_today, team_totals)

        # 0 бўлса — умуман чиқармасин десанг, бу ерда continue қиламиз.
        # Сен “0лар кк эмас” дединг — демак total_today==0 бўлса ходимни чиқармаймиз.
        if total_today == 0:
            continue

        # non-zero categories
        lines_emp = []
        for cat in CATEGORIES:
            v = await sum_day(today_iso, emp, cat)
            if v > 0:
                lines_emp.append(f"• {cat}: {v}")

        # strongest cat today
        best_cat = None
        best_val = 0
        for cat in CATEGORIES:
            v = await sum_day(today_iso, emp, cat)
            if v > best_val:
                best_val = v
                best_cat = cat if v > 0 else None

        blocks.append(f"👤 {emp}")
        blocks.append(f"Бугун жами: {total_today} | Баҳо: {grade}")
        if best_cat:
            blocks.append(f"⭐ Кучли йўналиш: {best_cat} ({best_val})")
        blocks.extend(lines_emp)
        blocks.append(f"Изоҳ: {comment}")
        blocks.append("")

    if len(blocks) <= 3:
        blocks.append("Ҳали ҳеч кимдан маълумот киритилмаган.")

    await message.answer(box(blocks, title="АДМИН СТАТУС"), parse_mode="HTML")


# ============================================================
# АДМИН: ХАТО ҲИСОБОТНИ ЎЧИРИШ (ИНТЕРАКТИВ) /delete
# ============================================================

@dp.message(Command("delete"))
async def delete_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    if not is_private(message):
        # админга қулай: личкада ишлатсин
        await message.answer("Бу командани личкада ишлатинг: /delete")
        return

    user_state[message.from_user.id] = {
        "admin_delete": {"step": "date_choice"}
    }
    await message.answer("Қайси санадаги хатони ўчирамиз?", reply_markup=delete_date_kb())


@dp.message(lambda m: is_private(m) and m.text in {"📌 Бугун", "📌 Кеча", "🗓 Бошқа сана"} )
async def delete_date_pick(message: Message):
    st = user_state.get(message.from_user.id, {})
    ad = st.get("admin_delete")
    if not ad or ad.get("step") != "date_choice":
        return
    if not is_admin(message.from_user.id):
        return

    if message.text == "📌 Бугун":
        day_iso = date.today().isoformat()
        ad["day"] = day_iso
        ad["step"] = "employee"
        await message.answer(f"Сана танланди: {day_iso}\nҚайси ходимники?", reply_markup=employees_kb(with_all=True))
    elif message.text == "📌 Кеча":
        day_iso = (date.today() - timedelta(days=1)).isoformat()
        ad["day"] = day_iso
        ad["step"] = "employee"
        await message.answer(f"Сана танланди: {day_iso}\nҚайси ходимники?", reply_markup=employees_kb(with_all=True))
    else:
        ad["step"] = "date_manual"
        await message.answer("Санани ёзинг (YYYY-MM-DD). Масалан: 2026-03-02", reply_markup=ReplyKeyboardRemove())


@dp.message(lambda m: is_private(m) and m.text and parse_iso_date(m.text) is not None)
async def delete_date_manual(message: Message):
    st = user_state.get(message.from_user.id, {})
    ad = st.get("admin_delete")
    if not ad or ad.get("step") != "date_manual":
        return
    if not is_admin(message.from_user.id):
        return

    day_iso = parse_iso_date(message.text)
    ad["day"] = day_iso
    ad["step"] = "employee"
    await message.answer(f"Сана танланди: {day_iso}\nҚайси ходимники?", reply_markup=employees_kb(with_all=True))


@dp.message(lambda m: is_private(m) and (m.text in EMPLOYEES or m.text == "✅ Ҳамма ходим"))
async def delete_employee_pick(message: Message):
    st = user_state.get(message.from_user.id, {})
    ad = st.get("admin_delete")
    if not ad or ad.get("step") != "employee":
        return
    if not is_admin(message.from_user.id):
        return

    ad["employee"] = None if message.text == "✅ Ҳамма ходим" else message.text
    ad["step"] = "category"
    await message.answer("Қайси категория? (ёки 'Ҳамма категория')", reply_markup=delete_category_kb())


@dp.message(lambda m: is_private(m) and (m.text in CATEGORIES or m.text == "✅ Ҳамма категория"))
async def delete_category_pick(message: Message):
    st = user_state.get(message.from_user.id, {})
    ad = st.get("admin_delete")
    if not ad or ad.get("step") != "category":
        return
    if not is_admin(message.from_user.id):
        return

    ad["category"] = None if message.text == "✅ Ҳамма категория" else message.text
    ad["step"] = "confirm"

    day_iso = ad["day"]
    emp = ad["employee"] or "ҲАММА ХОДИМ"
    cat = ad["category"] or "ҲАММА КАТЕГОРИЯ"

    await message.answer(
        box([f"Сана: {day_iso}", f"Ходим: {emp}", f"Категория: {cat}", "", "Шу маълумот ўчирилсинми?"], title="ЎЧИРИШ ТАСДИҒИ"),
        parse_mode="HTML",
        reply_markup=confirm_kb()
    )


@dp.message(lambda m: is_private(m) and m.text == "🗑 Ўчиришни тасдиқлайман")
async def delete_confirm(message: Message):
    st = user_state.get(message.from_user.id, {})
    ad = st.get("admin_delete")
    if not ad or ad.get("step") != "confirm":
        return
    if not is_admin(message.from_user.id):
        return

    day_iso = ad["day"]
    emp = ad["employee"]
    cat = ad["category"]

    # Build delete query
    q = "DELETE FROM reports WHERE day = ?"
    params = [day_iso]

    if emp is not None:
        q += " AND employee = ?"
        params.append(emp)
    if cat is not None:
        q += " AND category = ?"
        params.append(cat)

    # count before delete
    count_q = "SELECT COUNT(*) AS c FROM reports WHERE day = ?"
    count_params = [day_iso]
    if emp is not None:
        count_q += " AND employee = ?"
        count_params.append(emp)
    if cat is not None:
        count_q += " AND category = ?"
        count_params.append(cat)

    row = await db_fetchone(count_q, tuple(count_params))
    before = int(row["c"] or 0)

    await db_exec(q, tuple(params))

    await message.answer(
        box([f"Ўчирилди: {before} та ёзув", f"Сана: {day_iso}", f"Ходим: {emp or 'ҲАММА'}", f"Категория: {cat or 'ҲАММА'}"], title="ТАЙЁР ✅"),
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    user_state.pop(message.from_user.id, None)


# ============================================================
# АДМИН: ТЕЗКОР ЎЧИРИШ /del YYYY-MM-DD | Employee | Category/ALL
# ============================================================

@dp.message(Command("del"))
async def del_quick(message: Message):
    if not is_admin(message.from_user.id):
        return
    if not is_private(message):
        await message.answer("Бу командани личкада ишлатинг: /del YYYY-MM-DD | Employee | Category/ALL")
        return

    txt = message.text.replace("/del", "", 1).strip()
    parts = [p.strip() for p in txt.split("|")] if "|" in txt else []
    if len(parts) < 2:
        await message.answer("Формат:\n/del YYYY-MM-DD | Employee | Category/ALL\nМисол:\n/del 2026-03-02 | Rajabboev Pulat | Пересчет товаров")
        return

    day_iso = parse_iso_date(parts[0])
    if not day_iso:
        await message.answer("❌ Сана нотўғри. YYYY-MM-DD бўлсин.")
        return

    emp = parts[1]
    if emp != "ALL" and emp not in EMPLOYEES:
        await message.answer("❌ Employee нотўғри. Ёки ALL ёзинг.")
        return
    emp_val = None if emp == "ALL" else emp

    cat_val = None
    if len(parts) >= 3:
        cat = parts[2]
        if cat == "ALL":
            cat_val = None
        elif cat not in CATEGORIES:
            await message.answer("❌ Category нотўғри. Ёки ALL ёзинг.")
            return
        else:
            cat_val = cat

    count_q = "SELECT COUNT(*) AS c FROM reports WHERE day = ?"
    count_params = [day_iso]
    if emp_val is not None:
        count_q += " AND employee = ?"
        count_params.append(emp_val)
    if cat_val is not None:
        count_q += " AND category = ?"
        count_params.append(cat_val)

    row = await db_fetchone(count_q, tuple(count_params))
    before = int(row["c"] or 0)

    q = "DELETE FROM reports WHERE day = ?"
    params = [day_iso]
    if emp_val is not None:
        q += " AND employee = ?"
        params.append(emp_val)
    if cat_val is not None:
        q += " AND category = ?"
        params.append(cat_val)

    await db_exec(q, tuple(params))

    await message.answer(
        box([f"Ўчирилди: {before} та ёзув", f"Сана: {day_iso}", f"Ходим: {emp}", f"Категория: {parts[2] if len(parts)>=3 else 'ALL'}"], title="ТЕЗКОР /del ✅"),
        parse_mode="HTML"
    )


# ============================================================
# АДМИН: /report /top /leaders /stats (old)
# ============================================================

@dp.message(Command("report"))
async def report_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    mode = parts[1].lower() if len(parts) > 1 else "period"

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    lines = []
    if mode == "today":
        lines.append(f"ҲИСОБОТ: БУГУН ({today_iso})")
        for emp in EMPLOYEES:
            total = await sum_day_total(today_iso, emp)
            if total:
                lines.append(f"{emp}: {total}")
    elif mode == "yesterday":
        lines.append(f"ҲИСОБОТ: КЕЧА ({yday_iso})")
        for emp in EMPLOYEES:
            total = await sum_day_total(yday_iso, emp)
            if total:
                lines.append(f"{emp}: {total}")
    else:
        lines.append(f"ҲИСОБОТ: ПЕРИОД (2-сана) [{period}]")
        for emp in EMPLOYEES:
            total = await sum_period_total(period, emp)
            if total:
                lines.append(f"{emp}: {total}")

    if len(lines) == 1:
        lines.append("Ҳали маълумот йўқ.")

    await message.answer(box(lines, title="АДМИН /report"), parse_mode="HTML")


@dp.message(Command("top"))
async def top_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    mode = parts[1].lower() if len(parts) > 1 else "period"

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    totals = []
    if mode == "today":
        key = f"БУГУН {today_iso}"
        for emp in EMPLOYEES:
            totals.append((emp, await sum_day_total(today_iso, emp)))
    elif mode == "yesterday":
        key = f"КЕЧА {yday_iso}"
        for emp in EMPLOYEES:
            totals.append((emp, await sum_day_total(yday_iso, emp)))
    else:
        key = f"ПЕРИОД {period}"
        for emp in EMPLOYEES:
            totals.append((emp, await sum_period_total(period, emp)))

    totals = sorted(totals, key=lambda x: x[1], reverse=True)
    top5 = totals[:5]
    bottom5 = list(reversed(totals[-5:]))

    lines = [f"РЕЙТИНГ ({key})", ""]
    lines.append("🏆 ТОП 5:")
    for i, (emp, v) in enumerate(top5, 1):
        lines.append(f"{i}) {emp}: {v}")

    lines.append("")
    lines.append("🙂 ҚЎЛЛАБ-ҚУВВАТЛАШ (Bottom 5):")
    for i, (emp, v) in enumerate(bottom5, 1):
        lines.append(f"{i}) {emp}: {v}")

    lines.append("")
    lines.append("Изоҳ: паст натижа — ёмон дегани эмас. Мақсад: барқарор ўсиш 🤝")

    await message.answer(box(lines, title="АДМИН /top"), parse_mode="HTML")


@dp.message(Command("leaders"))
async def leaders_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    mode = parts[1].lower() if len(parts) > 1 else "period"

    today = date.today()
    today_iso = today.isoformat()
    period = get_period_key(today)

    lines = []
    if mode == "today":
        lines.append(f"ЛИДЕРЛАР: БУГУН ({today_iso})")
        for cat in CATEGORIES:
            best_emp, best_val = "—", 0
            for emp in EMPLOYEES:
                v = await sum_day(today_iso, emp, cat)
                if v > best_val:
                    best_val, best_emp = v, emp
            lines.append(f"{cat}: {best_emp} ({best_val})" if best_val > 0 else f"{cat}: —")
    else:
        lines.append(f"ЛИДЕРЛАР: ПЕРИОД (2-сана) [{period}]")
        for cat in CATEGORIES:
            best_emp, best_val = "—", 0
            for emp in EMPLOYEES:
                v = await sum_period(period, emp, cat)
                if v > best_val:
                    best_val, best_emp = v, emp
            lines.append(f"{cat}: {best_emp} ({best_val})" if best_val > 0 else f"{cat}: —")

    await message.answer(box(lines, title="АДМИН /leaders"), parse_mode="HTML")


@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    today = date.today()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)

    totals = [(emp, await sum_period_total(period, emp)) for emp in EMPLOYEES]
    totals_sorted = sorted(totals, key=lambda x: x[1], reverse=True)

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
        f"Период (2-сана): {period}",
        f"Бугун: {today_iso} | Кеча: {yday_iso}",
        ""
    ]
    lines.append("📌 Период бўйича умумий (Top 10):")
    for i, (emp, v) in enumerate(totals_sorted[:10], 1):
        lines.append(f"{i}) {emp}: {v}")

    lines.append("")
    lines.append("⭐ Ким қаерда кучли (период):")
    lines.extend(strong_lines if strong_lines else ["Ҳали маълумот йўқ."])

    await message.answer(box(lines, title="АДМИН /stats"), parse_mode="HTML")


# ============================================================
# АДМИН: RESET + PLAN
# ============================================================

@dp.message(Command("reset_today"))
async def reset_today(message: Message):
    if not is_admin(message.from_user.id):
        return
    today_iso = date.today().isoformat()
    await db_exec("DELETE FROM reports WHERE day = ?", (today_iso,))
    await message.answer(box([f"Бугун: {today_iso}", "Маълумотлар 0 қилинди ✅"], title="RESET TODAY"), parse_mode="HTML")

@dp.message(Command("reset_yesterday"))
async def reset_yesterday(message: Message):
    if not is_admin(message.from_user.id):
        return
    yday_iso = (date.today() - timedelta(days=1)).isoformat()
    await db_exec("DELETE FROM reports WHERE day = ?", (yday_iso,))
    await message.answer(box([f"Кеча: {yday_iso}", "Маълумотлар 0 қилинди ✅"], title="RESET YESTERDAY"), parse_mode="HTML")

@dp.message(Command("reset_period"))
async def reset_period(message: Message):
    if not is_admin(message.from_user.id):
        return
    period = get_period_key(date.today())
    await db_exec("DELETE FROM reports WHERE period = ?", (period,))
    await message.answer(box([f"Период: {period}", "Маълумотлар 0 қилинди ✅"], title="RESET PERIOD"), parse_mode="HTML")

@dp.message(Command("reset_all"))
async def reset_all(message: Message):
    if not is_admin(message.from_user.id):
        return
    await db_exec("DELETE FROM reports")
    await message.answer(box(["Ҳамма маълумотлар ўчди ✅"], title="RESET ALL"), parse_mode="HTML")


@dp.message(Command("setplan"))
async def setplan_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    txt = message.text.replace("/setplan", "", 1).strip()
    parts = [p.strip() for p in txt.split("|")] if "|" in txt else []
    if len(parts) != 3:
        await message.answer(
            "Формат:\n<b>/setplan Employee | Category | Plan</b>\n"
            "Мисол:\n<b>/setplan Ravshanov Oxunjon | Фото ТМЦ | 120</b>",
            parse_mode="HTML"
        )
        return

    emp, cat, plan_str = parts
    if emp not in EMPLOYEES:
        await message.answer("❌ Employee нотўғри (рўйхатдагина бўлсин).")
        return
    if cat not in CATEGORIES:
        await message.answer("❌ Category нотўғри (рўйхатдагина бўлсин).")
        return
    if not plan_str.isdigit():
        await message.answer("❌ План фақат сон бўлсин.")
        return

    plan_val = int(plan_str)
    period = get_period_key(date.today())

    await db_exec("""
        INSERT OR REPLACE INTO monthly_plans(period, employee, category, plan_value)
        VALUES (?,?,?,?)
    """, (period, emp, cat, plan_val))

    await message.answer(
        box([f"Период: {period}", f"{emp}", f"{cat}", f"План = {plan_val}"], title="PLAN SET"),
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
