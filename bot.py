import os
import asyncio
import logging
import sqlite3
import shutil
from datetime import datetime, date, timedelta
from io import BytesIO
import html
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from cross_bot_hub import (
    BOT_LABELS,
    build_appendix_lines_async,
    fetch_latest_by_bot,
    fetch_merged_latest_by_bot,
    hub_events_for_day,
    init_schema as init_cross_bot_schema,
    record_event,
)
from daily_report_card import BOT_ORDER, _fmt_clock, build_card_data, build_demo_card_data, score_bot_summary
from report_png import render_demo_preview_png, render_ranking_png, render_report_png
from employee_photos import (
    init_schema as init_photo_schema,
    load_photo_for_employee,
    save_employee_photo,
)
from employee_tg_map import TG_EMPLOYEE, resolve_owner_tg_id, resolve_tg_id, tg_ids_for_employee
from hub_ingest import start_ingest_server
from admin_status import (
    BTN_ADMIN_PHOTO,
    BTN_ADMIN_STATUS,
    BTN_PREVIEW_REPORT,
    BTN_RANKING,
    admin_status_kb,
    handle_admin_status,
)
from employee_photo_admin import (
    admin_photo_state,
    handle_photo_cancel,
    handle_photo_employee_pick,
    handle_photo_upload,
    start_photo_upload,
)
from ranking_broadcast import (
    build_team_rankings,
    format_ranking_lines,
    init_schema as init_ranking_schema,
    mark_ranking_sent,
    ranking_already_sent,
    ranking_employees,
)
from db_backup import (
    export_payload,
    payload_to_hub_csv,
    payload_to_json_bytes,
    payload_to_reports_csv,
    payload_to_summary_csv,
    write_backup_files,
)
from metrics_import import (
    insert_import_rows,
    parse_import_csv_bytes,
    parse_import_text,
)


# ============================================================
# КОНФИГ
# ============================================================

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is empty. Set Railway variable BOT_TOKEN.")

GROUP_ID = int(os.getenv("GROUP_ID", "-1001877019294"))
INGEST_CHAT_ID = int(os.getenv("YORDAMCHI_INGEST_CHAT_ID", "0") or "0")
TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

def _parse_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "").strip()
    out = {5732350707, 2624538, 6991673998, 1432810519}
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


ADMINS = _parse_admin_ids()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


REPORT_TO_GROUP = _env_bool("REPORT_TO_GROUP", True)
REPORT_ADMIN_DM_ID = int(os.getenv("REPORT_ADMIN_DM_ID", "1432810519") or "1432810519")

# Kunlik reyting (alohida xabar, 00:01) — productionda default yoqilgan
RANKING_BROADCAST_ENABLED = _env_bool("RANKING_BROADCAST_ENABLED", True)
RANKING_BROADCAST_HOUR = int(os.getenv("RANKING_BROADCAST_HOUR", "0") or "0")
RANKING_BROADCAST_MINUTE = int(os.getenv("RANKING_BROADCAST_MINUTE", "1") or "1")
RANKING_TO_GROUP = _env_bool("RANKING_TO_GROUP", False)
_RANKING_CHAT_RAW = os.getenv("RANKING_CHAT_ID", "").strip()


def ranking_chat_id() -> int:
    if _RANKING_CHAT_RAW:
        return int(_RANKING_CHAT_RAW)
    if RANKING_TO_GROUP:
        return GROUP_ID
    return REPORT_ADMIN_DM_ID


def today_local() -> date:
    return datetime.now(TZ).date()

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

DB_PATH = os.getenv("DB_PATH", "/data/data.db").strip() or "/data/data.db"
_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

_legacy_db = "data.db"
if DB_PATH != _legacy_db and not os.path.exists(DB_PATH) and os.path.exists(_legacy_db):
    try:
        shutil.copy2(_legacy_db, DB_PATH)
        logging.warning("Legacy DB migrated to %s", DB_PATH)
    except Exception as e:
        logging.warning("Legacy DB migration failed: %s", e)

conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
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
init_photo_schema(conn)
init_ranking_schema(conn)
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

def categories_kb(user_id: int | None = None):
    rows = [[KeyboardButton(text=c)] for c in CATEGORIES] + [[KeyboardButton(text="❌ Бекор қилиш")]]
    if user_id and is_admin(user_id):
        rows.append([KeyboardButton(text=BTN_ADMIN_STATUS), KeyboardButton(text=BTN_PREVIEW_REPORT)])
        rows.append([KeyboardButton(text=BTN_ADMIN_PHOTO), KeyboardButton(text=BTN_RANKING)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def after_save_kb(user_id: int | None = None):
    rows = [
        [KeyboardButton(text="➕ Яна категория"), KeyboardButton(text="✅ Якунлаш")],
        [KeyboardButton(text="↩️ Ундо"), KeyboardButton(text="❌ Бекор қилиш")],
        [KeyboardButton(text=BTN_PREVIEW_REPORT)],
    ]
    if user_id and is_admin(user_id):
        rows.append([KeyboardButton(text=BTN_ADMIN_STATUS), KeyboardButton(text=BTN_ADMIN_PHOTO), KeyboardButton(text=BTN_RANKING)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

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

def report_chat_id(private_fallback: int = 0) -> int:
    if REPORT_TO_GROUP:
        return GROUP_ID
    return REPORT_ADMIN_DM_ID or private_fallback


async def safe_report_send(html_text: str, *, private_fallback: int = 0):
    chat_id = report_chat_id(private_fallback)
    try:
        await bot.send_message(chat_id, html_text, parse_mode="HTML")
    except Exception as e:
        logging.exception("Hisobot xabarini yuborishda xato (chat=%s): %s", chat_id, e)


async def safe_report_send_photo(png: bytes, caption: str = "", *, private_fallback: int = 0):
    chat_id = report_chat_id(private_fallback)
    try:
        await bot.send_photo(
            chat_id,
            BufferedInputFile(png, filename="kunlik_hisobot.png"),
            caption=caption[:1024] if caption else None,
        )
    except Exception as e:
        logging.exception("Hisobot PNG yuborishda xato (chat=%s): %s", chat_id, e)
        raise


async def safe_ranking_send(html_text: str) -> None:
    chat_id = ranking_chat_id()
    try:
        await bot.send_message(chat_id, html_text, parse_mode="HTML")
    except Exception as e:
        logging.exception("Kunlik reyting yuborishda xato (chat=%s): %s", chat_id, e)
        raise


async def safe_ranking_send_png(png: bytes, caption: str = "") -> None:
    chat_id = ranking_chat_id()
    try:
        await bot.send_photo(
            chat_id,
            BufferedInputFile(png, filename="kunlik_reyting.png"),
            caption=caption[:1024] if caption else None,
        )
    except Exception as e:
        logging.exception("Kunlik reyting PNG yuborishda xato (chat=%s): %s", chat_id, e)
        raise


async def broadcast_daily_ranking(day_iso: str | None = None, *, force: bool = False) -> bool:
    """Period bo'yicha yig'ilgan reyting. 00:01 da kechagi kun holati."""
    if day_iso:
        ref = date.fromisoformat(day_iso)
    else:
        ref = today_local() - timedelta(days=1)
    send_key = ref.isoformat()
    if not force and await ranking_already_sent(db_fetchone, send_key):
        logging.info("Period reyting allaqachon yuborilgan: %s", send_key)
        return False

    leaders, active, period = await build_team_rankings(
        ref,
        employees=ranking_employees(EMPLOYEES),
        sum_period_total=sum_period_total,
        get_period_key=get_period_key,
        employee_tg_map=await employee_tg_map(),
    )
    try:
        png = await render_ranking_png(period, ref, leaders, active)
        await safe_ranking_send_png(png)
    except Exception:
        logging.exception("Reyting PNG xato, matn fallback")
        lines = format_ranking_lines(period, ref, leaders, active)
        await safe_ranking_send(box(lines, title="🏆 PERIOD REYTING"))
    await mark_ranking_sent(db_exec, send_key)
    logging.info("Period reyting yuborildi: %s / %s (%s faol)", period, send_key, active)
    return True


async def maybe_catchup_ranking() -> None:
    if not RANKING_BROADCAST_ENABLED:
        return
    now = datetime.now(TZ)
    if now.hour == 0 and now.minute < RANKING_BROADCAST_MINUTE:
        return
    yday = (today_local() - timedelta(days=1)).isoformat()
    if await ranking_already_sent(db_fetchone, yday):
        return
    await broadcast_daily_ranking(yday)


def setup_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone=TZ)

    if RANKING_BROADCAST_ENABLED:
        async def _job():
            try:
                await broadcast_daily_ranking()
            except Exception:
                logging.exception("Rejalashtirilgan kunlik reyting xato")

        scheduler.add_job(
            _job,
            CronTrigger(
                hour=RANKING_BROADCAST_HOUR,
                minute=RANKING_BROADCAST_MINUTE,
                timezone=TZ,
            ),
            id="daily_ranking_broadcast",
            replace_existing=True,
        )
        logging.info(
            "Kunlik reyting rejalashtirildi: %02d:%02d (%s)",
            RANKING_BROADCAST_HOUR,
            RANKING_BROADCAST_MINUTE,
            TZ,
        )

    scheduler.add_job(
        _auto_backup_db,
        CronTrigger(hour=23, minute=50, timezone=TZ),
        id="auto_backup_db",
        replace_existing=True,
    )
    scheduler.start()
    logging.info("Kunlik auto-backup: 23:50 (%s)", TZ)
    return scheduler


async def fetch_user_avatar(user_id: int) -> bytes | None:
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if not photos.photos:
            return None
        file = await bot.get_file(photos.photos[0][-1].file_id)
        if not file.file_path:
            return None
        buf = BytesIO()
        await bot.download_file(file.file_path, buf)
        return buf.getvalue()
    except Exception:
        return None


async def get_employee_photo(user_id: int, employee: str | None = None) -> bytes | None:
    subject_tg_id = resolve_owner_tg_id(employee) if employee else None

    saved = await load_photo_for_employee(
        db_fetchone,
        tg_id=subject_tg_id,
        employee=employee,
    )
    if saved:
        return saved
    if subject_tg_id:
        return await fetch_user_avatar(subject_tg_id)
    if user_id and not employee:
        return await fetch_user_avatar(user_id)
    return None


async def _persist_employee_photo(*, employee: str, data: bytes, tg_id: int | None = None) -> None:
    await save_employee_photo(db_exec, employee=employee, data=data, tg_id=tg_id)


async def employee_tg_map() -> dict[str, int]:
    rows = await db_fetchall("SELECT tg_id, employee FROM employee_links")
    linked = {r["employee"]: int(r["tg_id"]) for r in rows}
    out: dict[str, int] = {}
    for emp in EMPLOYEES:
        tid = resolve_tg_id(emp, linked=linked)
        if tid:
            out[emp] = tid
    return out


async def _session_agg(uid: int, emp: str, state: dict | None) -> dict[str, int]:
    session = (state or {}).get("session") or []
    if session:
        agg: dict[str, int] = {}
        for it in session:
            agg[it["category"]] = agg.get(it["category"], 0) + int(it["added"])
        return agg
    today_iso = today_local().isoformat()
    agg = {}
    for cat in CATEGORIES:
        v = await sum_day(today_iso, emp, cat)
        if v > 0:
            agg[cat] = v
    return agg


async def build_report_png_for_user(uid: int, emp: str, agg: dict[str, int]) -> tuple[bytes, object] | None:
    if not agg:
        return None
    today = today_local()
    today_iso = today.isoformat()
    yday_iso = (today - timedelta(days=1)).isoformat()
    period = get_period_key(today)
    best_cat, best_add = max(agg.items(), key=lambda x: x[1])

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

    avatar = await get_employee_photo(uid, employee=emp)
    etg_map = await employee_tg_map()
    card = await build_card_data(
        employee=emp,
        day_iso=today_iso,
        period=period,
        yday_iso=yday_iso,
        session_agg=agg,
        categories=CATEGORIES,
        best_cat=best_cat,
        best_add=best_add,
        overall_text=overall_text,
        employees=EMPLOYEES,
        sum_day=sum_day,
        sum_period=sum_period,
        get_plan=get_plan,
        sum_day_total=sum_day_total,
        employee_tg_map=etg_map,
        day_has_any=day_has_any,
    )
    png = await render_report_png(card, avatar=avatar)
    return png, card


async def send_report_preview(message: Message, *, demo: bool = False) -> None:
    uid = message.from_user.id if message.from_user else 0
    if demo:
        png = await render_demo_preview_png()
        card = build_demo_card_data()
        note = "📎 Namuna (demo). Haqiqiy hisobot — kategoriya kiritib 👁 bosing."
    else:
        state = user_state.get(uid, {})
        emp = state.get("employee") or await get_linked_employee(uid)
        if not emp:
            await message.answer("Avval /link va /start bosing.")
            return
        agg = await _session_agg(uid, emp, state)
        built = await build_report_png_for_user(uid, emp, agg)
        if not built:
            png = await render_demo_preview_png()
            card = build_demo_card_data()
            note = "⚠️ Hali ma'lumot yo'q — namuna ko'rinishi. Kategoriya qo'shing yoki /preview_demo"
        else:
            png, card = built
            note = f"👁 Preview · {emp} · +{card.grand_total} ochko (guruhga hali yuborilmadi)"
    await message.answer_photo(
        BufferedInputFile(png, filename="preview.png"),
        caption=note,
    )
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if domain:
        url = domain if domain.startswith("http") else f"https://{domain}"
        await message.answer(f"🌐 Brauzerda namuna: {url}/preview")


# DB query helpers
async def get_linked_employee(tg_id: int) -> str | None:
    row = await db_fetchone("SELECT employee FROM employee_links WHERE tg_id = ?", (tg_id,))
    return row["employee"] if row else None


async def keyboard_for_user(uid: int) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """Har javobdan keyin tugmalar yo'qolmasligi uchun."""
    if await get_linked_employee(uid):
        return categories_kb(uid)
    if is_admin(uid):
        return admin_status_kb()
    return ReplyKeyboardRemove()

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

    uid = message.from_user.id
    emp = await get_linked_employee(uid)
    if not emp:
        if is_admin(uid):
            await message.answer(
                "Сиз админсиз. PIN bilan ham ulanishingiz mumkin: <b>/link 1234</b>\n\n"
                "Tizim holatini ko'rish uchun tugmani bosing 👇",
                parse_mode="HTML",
                reply_markup=admin_status_kb(),
            )
        else:
            await message.answer(
                "Сиз ҳали уланмагансиз.\nАдмин берган PIN билан уланинг:\n<b>/link 1234</b>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
        return

    user_state[message.from_user.id] = {"employee": emp, "session": []}
    await message.answer(
        f"✅ Салом, <b>{html.escape(emp)}</b>!\n📌 Категорияни танланг:",
        parse_mode="HTML",
        reply_markup=categories_kb(message.from_user.id)
    )


@dp.message(Command("cancel"))
async def cancel_cmd(message: Message):
    if not is_private(message):
        return
    user_state.pop(message.from_user.id, None)
    await message.answer("Бекор қилинди. /start", reply_markup=ReplyKeyboardRemove())


# ============================================================
# Admin: xodim rasmi (boshqa handlerlar oldin)
# ============================================================

@dp.message(lambda m: is_private(m) and m.text == BTN_ADMIN_PHOTO and is_admin(m.from_user.id))
async def admin_photo_start(message: Message):
    await start_photo_upload(message, EMPLOYEES)


@dp.message(
    lambda m: is_private(m)
    and is_admin(m.from_user.id)
    and m.from_user
    and m.from_user.id in admin_photo_state
)
async def admin_photo_flow(message: Message):
    uid = message.from_user.id if message.from_user else 0
    st = admin_photo_state.get(uid, {})

    if await handle_photo_cancel(message, admin_status_kb):
        return
    if st.get("step") == "employee" and message.photo:
        await message.answer(
            "Avval ro'yxatdan xodimni tanlang.\n"
            "Ism bosilgach «Endi rasm yuboring» degan xabar chiqishi kerak."
        )
        return
    if message.photo and await handle_photo_upload(
        message,
        bot,
        save_photo=_persist_employee_photo,
        admin_status_kb=admin_status_kb,
    ):
        return
    if st.get("step") == "upload" and message.text:
        await message.answer("📷 Endi rasm yuboring (foto file).")
        return
    if message.text:
        await handle_photo_employee_pick(
            message,
            employees=EMPLOYEES,
            employee_tg_map=await employee_tg_map(),
            admin_status_kb=admin_status_kb,
        )


@dp.message(
    lambda m: is_private(m)
    and m.text == "❌ Бекор қилиш"
    and not (m.from_user and m.from_user.id in admin_photo_state)
)
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
        reply_markup=after_save_kb(message.from_user.id)
    )


@dp.message(lambda m: is_private(m) and m.text == "➕ Яна категория")
async def again_category(message: Message):
    state = user_state.get(message.from_user.id)
    if not state:
        await message.answer("Аввал /start босинг.")
        return
    await message.answer(
        "📌 Категорияни танланг:",
        reply_markup=categories_kb(message.from_user.id),
    )


@dp.message(lambda m: is_private(m) and m.text == "✅ Якунлаш")
async def finalize_report(message: Message):
    state = user_state.get(message.from_user.id)
    if not state or not state.get("session"):
        await message.answer("❗ Ҳали ҳеч нарса киритилмаган. /start", reply_markup=ReplyKeyboardRemove())
        return

    emp = state["employee"]
    today = today_local()
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

    tg_id = message.from_user.id if message.from_user else 0

    sent_card = False
    if tg_id:
        try:
            built = await build_report_png_for_user(tg_id, emp, agg)
            if built:
                png, card = built
                await safe_report_send_photo(
                    png,
                    private_fallback=tg_id,
                )
                sent_card = True
        except Exception as e:
            logging.exception("PNG hisobot xato, matn fallback: %s", e)

    if not sent_card:
        lines = [
            f"📅 Сана: {today_iso}",
            f"👤 Ходим: {emp}",
            f"🗓 Период (2-сана): {period}",
            "",
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
        tg_set = tg_ids_for_employee(emp, employee_tg_map=await employee_tg_map())
        if tg_set:
            lines.extend(await build_appendix_lines_async(tg_set, today_iso))
        await safe_report_send(box(lines, title="КУНЛИК ҲИСОБОТ (ЯКУН)"), private_fallback=tg_id)

    if REPORT_TO_GROUP:
        done_note = "✅ Якунланди. Hisobot guruhga yuborildi. /start bilan yangi hisobot."
    else:
        done_note = (
            f"✅ Якунlandi. Hisobot admin lichkasiga yuborildi "
            f"(ID {REPORT_ADMIN_DM_ID})."
        )
    await message.answer(done_note, reply_markup=ReplyKeyboardRemove())
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


@dp.message(
    lambda m: is_private(m)
    and (m.text in EMPLOYEES or m.text == "✅ Ҳамма ходим")
    and not (m.from_user and m.from_user.id in admin_photo_state)
)
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


@dp.message(Command("ranking"))
async def ranking_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = (message.text or "").strip().split()
    force = "--force" in parts or "-f" in parts
    mode = next((p for p in parts[1:] if not p.startswith("-")), "yesterday").lower()

    if mode in ("today", "bugun"):
        day_iso = today_local().isoformat()
    elif mode in ("yesterday", "kecha"):
        day_iso = (today_local() - timedelta(days=1)).isoformat()
    else:
        day_iso = mode

    try:
        date.fromisoformat(day_iso)
    except ValueError:
        await message.answer(
            "Формат:\n/ranking yesterday\n/ranking today\n/ranking 2026-05-29\n/ranking yesterday --force"
        )
        return

    try:
        sent = await broadcast_daily_ranking(day_iso, force=force)
    except Exception as e:
        logging.exception("Admin ranking xato")
        await message.answer(f"❌ Xato: {html.escape(str(e))}", parse_mode="HTML")
        return

    if sent:
        await message.answer(f"✅ Reyting yuborildi: {day_iso} → chat {ranking_chat_id()}")
    else:
        await message.answer(f"ℹ️ {day_iso} uchun reyting allaqachon yuborilgan (--force bilan qayta yuboring).")


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

@dp.message(Command("import", "importpaste"))
async def import_metrics_cmd(message: Message):
    """Admin: guruh ko'rsatkichlarini DB ga kiritish (period oxirigacha saqlanadi)."""
    if not is_private(message) or not is_admin(message.from_user.id):
        return
    uid = message.from_user.id if message.from_user else 0
    cmd = (message.text or "").split()[0].lower()
    body = (message.text or "").strip()
    if cmd.startswith("/import"):
        body = body.split(maxsplit=1)[1] if " " in body else ""

    if not body.strip():
        await message.answer(
            "📥 <b>Import</b> — guruh ko'rsatkichlari\n\n"
            "Har qator (bir format):\n"
            "<code>2026-06-03|Mustafoev Abdullo|Приход|12</code>\n"
            "<code>03.06.2026  Ruziboev Sindor  Перемещение  +10</code>\n\n"
            "Yoki CSV fayl yuboring (.csv).\n"
            "Yoki matnni shu yerga yuboring: <code>/importpaste</code> + matn.",
            parse_mode="HTML",
            reply_markup=await keyboard_for_user(uid),
        )
        return

    rows, errs = parse_import_text(
        body,
        employees=EMPLOYEES,
        categories=CATEGORIES,
        default_day=today_local().isoformat(),
    )
    if not rows:
        await message.answer(
            "❌ Import bo'lmadi.\n" + "\n".join(errs[:15]),
            parse_mode="HTML",
        )
        return
    n = await insert_import_rows(db_exec, rows, tg_id=uid)
    summary = f"✅ {n} ta yozuv kiritildi."
    if errs:
        summary += f"\n⚠️ {len(errs)} xato:\n" + "\n".join(errs[:10])
    await message.answer(summary, reply_markup=await keyboard_for_user(uid))


@dp.message(lambda m: is_private(m) and m.document and is_admin(m.from_user.id))
async def import_metrics_file(message: Message):
    doc = message.document
    if not doc or not (doc.file_name or "").lower().endswith(".csv"):
        return
    uid = message.from_user.id if message.from_user else 0
    try:
        f = await bot.get_file(doc.file_id)
        buf = BytesIO()
        await bot.download_file(f.file_path, buf)
        rows, errs = parse_import_csv_bytes(
            buf.getvalue(),
            employees=EMPLOYEES,
            categories=CATEGORIES,
            default_day=today_local().isoformat(),
        )
        if not rows:
            await message.answer("❌ CSV import xato.\n" + "\n".join(errs[:12]))
            return
        n = await insert_import_rows(db_exec, rows, tg_id=uid)
        msg = f"✅ CSV: {n} ta yozuv kiritildi."
        if errs:
            msg += f"\n⚠️ {len(errs)} xato."
        await message.answer(msg, reply_markup=await keyboard_for_user(uid))
    except Exception as e:
        logging.exception("import csv")
        await message.answer(f"❌ CSV xato: {html.escape(str(e))}", parse_mode="HTML")


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
# Admin: tizim holati
# ============================================================

@dp.message(Command("status_system", "tizim"))
async def admin_status_cmd(message: Message):
    if not is_private(message):
        return
    if not is_admin(message.from_user.id):
        await message.answer(
            f"Faqat admin.\nSizning ID: <code>{message.from_user.id}</code>\n"
            "Railway da ADMIN_IDS ga qo'shing.",
            parse_mode="HTML",
        )
        return
    uid = message.from_user.id if message.from_user else 0
    await handle_admin_status(message, bot, reply_markup=await keyboard_for_user(uid))


@dp.message(lambda m: is_private(m) and m.text == BTN_ADMIN_STATUS)
async def admin_status_btn(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            f"Faqat admin.\nSizning ID: <code>{message.from_user.id}</code>",
            parse_mode="HTML",
        )
        return
    uid = message.from_user.id if message.from_user else 0
    await handle_admin_status(message, bot, reply_markup=await keyboard_for_user(uid))


@dp.message(Command("botdebug"))
async def botdebug_cmd(message: Message):
    """Admin debug: har bir xodim bo‘yicha qaysi botlar qancha vaqt/ochko berayotganini ko‘rsatadi."""
    if not is_private(message):
        return
    if not is_admin(message.from_user.id):
        await message.answer(
            f"Faqat admin.\nSizning ID: <code>{message.from_user.id}</code>",
            parse_mode="HTML",
        )
        return

    args = (message.text or "").strip().split()[1:]
    mode = "period"  # period | today | yesterday
    period = None
    target_emp: str | None = None

    ref = today_local()
    day_iso: str | None = None

    for a in args:
        aa = (a or "").strip()
        al = aa.lower()
        if al in {"today", "bugun"}:
            mode = "today"
            day_iso = ref.isoformat()
        elif al in {"yesterday", "kecha"}:
            mode = "yesterday"
            day_iso = (ref - timedelta(days=1)).isoformat()
        elif al in {"period"}:
            mode = "period"
        elif len(aa) == 7 and aa[4] == "-" and aa[:4].isdigit() and aa[5:].isdigit():
            mode = "period"
            period = aa
        elif aa in EMPLOYEES:
            target_emp = aa

    if mode == "period":
        if not period:
            period = get_period_key(ref)
        y, m = map(int, period.split("-"))
        d0 = date(y, m, 2)
        days = []
        d = d0
        while d <= ref:
            days.append(d.isoformat())
            d += timedelta(days=1)
        title = f"BOT DEBUG (Pериод {period})"
    else:
        assert day_iso
        days = [day_iso]
        title = f"BOT DEBUG ({mode.upper()}: {day_iso})"

    etg_map = await employee_tg_map()
    emps = ranking_employees(EMPLOYEES)
    if target_emp:
        emps = [target_emp] if target_emp in emps else []

    if not emps:
        await message.answer("Xodim topilmadi (reyting ro‘yxatida emas).")
        return

    lines: list[str] = [
        title,
        f"Ref: {ref.isoformat()} · Kunlar: {len(days)}",
        "",
    ]

    for emp in emps:
        tg_set = tg_ids_for_employee(emp, employee_tg_map=etg_map)
        tg_label = ", ".join(str(t) for t in sorted(tg_set)) if tg_set else "—"

        if mode == "period":
            cat_total = await sum_period_total(period, emp)
        else:
            cat_total = await sum_day_total(day_iso, emp)

        bot_events_count = {k: 0 for k in BOT_ORDER}
        bot_points_by_key = {k: 0 for k in BOT_ORDER}
        work_sec_by_key = {k: 0 for k in BOT_ORDER}

        bot_pts_total = 0
        bot_work_sec_total = 0
        last_day_by_key: dict[str, str | None] = {k: None for k in BOT_ORDER}

        if tg_set:
            for day in days:
                ev = await fetch_merged_latest_by_bot(tg_set, day)
                for key in BOT_ORDER:
                    if key in ev:
                        bot_events_count[key] += 1
                        sc, ws = score_bot_summary(key, ev[key])
                        bot_points_by_key[key] += sc
                        work_sec_by_key[key] += ws
                        bot_pts_total += sc
                        bot_work_sec_total += ws
                        last_day_by_key[key] = day

        lines.append(f"👤 {emp} · tg_id: {tg_label}")
        lines.append(f"  Категория: +{cat_total} | Bot: +{bot_pts_total} | ⏱ { _fmt_clock(bot_work_sec_total)}")
        for key in BOT_ORDER:
            label = BOT_LABELS.get(key, key)
            cnt = bot_events_count[key]
            if cnt == 0:
                lines.append(f"  • {label}: event yo'q")
            else:
                lines.append(
                    f"  • {label}: {cnt}×, +{bot_points_by_key[key]} очко, ⏱ { _fmt_clock(work_sec_by_key[key])}"
                    f" (oxirgi: {last_day_by_key[key]})"
                )
        lines.append("")

    uid = message.from_user.id if message.from_user else 0
    await message.answer(
        box(lines, title="BOT DEBUG"),
        parse_mode="HTML",
        reply_markup=await keyboard_for_user(uid),
    )


def _tg_to_employee_name(tg_id: int, etg_map: dict[str, int]) -> str:
    for emp, tid in etg_map.items():
        if int(tid) == int(tg_id):
            return emp
    if tg_id in TG_EMPLOYEE:
        return TG_EMPLOYEE[tg_id]
    return "?"


@dp.message(Command("backup"))
async def backup_cmd(message: Message):
    """Admin: barcha hisobotlar va hub eventlar zaxirasi (Telegram fayl)."""
    if not is_private(message):
        return
    if not is_admin(message.from_user.id):
        await message.answer(
            f"Faqat admin.\nSizning ID: <code>{message.from_user.id}</code>",
            parse_mode="HTML",
        )
        return

    await message.answer("⏳ Zaxira tayyorlanmoqda…")
    try:
        payload = export_payload(DB_PATH)
        counts = payload.get("counts", {})
        stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
        files = [
            (f"backup_{stamp}.json", payload_to_json_bytes(payload)),
            (f"reports_{stamp}.csv", payload_to_reports_csv(payload)),
            (f"summary_{stamp}.csv", payload_to_summary_csv(payload)),
            (f"hub_events_{stamp}.csv", payload_to_hub_csv(payload)),
        ]
        for name, data in files:
            await message.answer_document(
                BufferedInputFile(data, filename=name),
                caption=name,
            )
        lines = [
            "✅ Zaxira tayyor",
            f"DB: <code>{html.escape(DB_PATH)}</code>",
            "",
            "Jadval yozuvlari:",
        ]
        for t, c in counts.items():
            lines.append(f"  • {t}: {c}")
        lines.append("")
        lines.append("Deploydan oldin shu fayllarni saqlang.")
        lines.append("Tiklash: tools/restore_backup.py yoki menga CSV/JSON yuboring.")
        uid = message.from_user.id if message.from_user else 0
        await message.answer(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=await keyboard_for_user(uid),
        )
    except Exception as e:
        logging.exception("backup_cmd")
        uid = message.from_user.id if message.from_user else 0
        await message.answer(
            f"❌ Zaxira xato: {html.escape(str(e))}",
            parse_mode="HTML",
            reply_markup=await keyboard_for_user(uid),
        )


@dp.message(Command("hubtoday"))
async def hubtoday_cmd(message: Message):
    """Admin: bugungi hub eventlar va tg_id → xodim."""
    if not is_private(message):
        return
    if not is_admin(message.from_user.id):
        await message.answer(
            f"Faqat admin.\nSizning ID: <code>{message.from_user.id}</code>",
            parse_mode="HTML",
        )
        return

    args = (message.text or "").strip().split()[1:]
    day = today_local().isoformat()
    for a in args:
        if len(a) == 10 and a[4] == "-" and a[7] == "-":
            day = a
            break

    etg_map = await employee_tg_map()
    events = await hub_events_for_day(day, limit=60)
    lines: list[str] = [
        f"HUB BUGUN · {day}",
        f"Jami yozuv: {len(events)} (oxirgi 60)",
        "",
    ]
    if not events:
        lines.append("Event yo'q — ish botlarda YORDAMCHI_HUB_URL+SECRET tekshiring.")
    else:
        for ev in events:
            tid = ev["tg_id"]
            emp = _tg_to_employee_name(tid, etg_map)
            label = BOT_LABELS.get(ev["bot_key"], ev["bot_key"])
            summ = (ev["summary"] or "")[:72]
            lines.append(
                f"• {label} · tg {tid} ({emp})\n  {summ} · {ev['created_at']}"
            )

    lines.append("")
    lines.append("Xodim → tg_id (reyting):")
    for emp in ranking_employees(EMPLOYEES):
        tgs = tg_ids_for_employee(emp, employee_tg_map=etg_map)
        lines.append(f"  {emp}: {', '.join(str(t) for t in sorted(tgs)) or '—'}")

    uid = message.from_user.id if message.from_user else 0
    await message.answer(
        box(lines, title="HUB TODAY"),
        parse_mode="HTML",
        reply_markup=await keyboard_for_user(uid),
    )


@dp.message(lambda m: is_private(m) and m.text == BTN_RANKING)
async def ranking_btn(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            f"Faqat admin.\nSizning ID: <code>{message.from_user.id}</code>",
            parse_mode="HTML",
        )
        return
    day_iso = today_local().isoformat()
    try:
        await broadcast_daily_ranking(day_iso, force=True)
        period = get_period_key(today_local())
        uid = message.from_user.id if message.from_user else 0
        await message.answer(
            f"✅ Period reyting yuborildi: {period} · {day_iso}",
            reply_markup=await keyboard_for_user(uid),
        )
    except Exception as e:
        logging.exception("Reyting tugmasi xato")
        uid = message.from_user.id if message.from_user else 0
        await message.answer(
            f"❌ Xato: {html.escape(str(e))}",
            parse_mode="HTML",
            reply_markup=await keyboard_for_user(uid),
        )


@dp.message(Command("preview"))
async def preview_cmd(message: Message):
    if not is_private(message):
        return
    await send_report_preview(message, demo=False)


@dp.message(Command("preview_demo"))
async def preview_demo_cmd(message: Message):
    if not is_private(message):
        return
    await send_report_preview(message, demo=True)


@dp.message(lambda m: is_private(m) and m.text == BTN_PREVIEW_REPORT)
async def preview_btn(message: Message):
    await send_report_preview(message, demo=False)


# ============================================================
# Hub: Telegram ingest (Worker rejimida HTTP o'rniga)
# ============================================================

@dp.message(
    lambda m: INGEST_CHAT_ID
    and m.chat
    and m.chat.id == INGEST_CHAT_ID
    and (m.text or "").startswith("HUB|")
)
async def hub_telegram_ingest(message: Message):
    try:
        parts = (message.text or "").strip().split("|", 4)
        if len(parts) < 5 or parts[0] != "HUB":
            return
        day_s, tg_s, bot_key, summary = parts[1], parts[2], parts[3], parts[4]
        await record_event(
            tg_id=int(tg_s),
            day=day_s,
            bot_key=bot_key,
            summary=summary,
        )
        logging.info("Hub telegram ingest ok: tg=%s bot=%s", tg_s, bot_key)
        try:
            await message.delete()
        except Exception:
            pass
    except Exception as e:
        logging.warning("Hub telegram ingest xato: %s", e)


# ============================================================
# MAIN
# ============================================================

async def _auto_backup_db() -> None:
    try:
        out = os.path.join(os.path.dirname(DB_PATH) or ".", "backups")
        write_backup_files(DB_PATH, out)
        logging.info("Auto backup yozildi: %s", out)
    except Exception:
        logging.exception("Auto backup xato")


async def main():
    init_cross_bot_schema()
    await seed_pins()
    for tg_id, emp_name in TG_EMPLOYEE.items():
        await db_exec(
            "INSERT OR IGNORE INTO employee_links(tg_id, employee) VALUES (?, ?)",
            (int(tg_id), emp_name),
        )
    hub_runner = await start_ingest_server()
    scheduler = setup_scheduler()
    try:
        await maybe_catchup_ranking()
    except Exception:
        logging.exception("Kunlik reyting catch-up xato")
    try:
        await dp.start_polling(bot)
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        if hub_runner:
            await hub_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
