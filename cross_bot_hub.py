"""Boshqa botlardan kelgan kunlik xulosalar — davlat-yordamchi yakunida qo'shiladi."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

DB_PATH = os.getenv("DB_PATH", "/data/data.db").strip() or "/data/data.db"
HUB_SECRET = os.getenv("YORDAMCHI_HUB_SECRET", "").strip()
MAX_SUMMARY_LEN = 420
MAX_APPENDIX_CHARS = 1050

BOT_LABELS = {
    "omborga": "Omborga kiritish",
    "ombor": "Ombor xizmat",
    "yuk": "Yuk jarayoni",
    "sklad": "Sklad nazorat",
    "ishxona": "Ishxona nazorat",
}

_BOT_KEY_ALIASES = {
    "omborga": {"omborga", "omborga_kiritish", "omborgakiritish", "kirim", "prihod"},
    "ombor": {"ombor", "omborxizmat", "ombor_xizmat"},
    "yuk": {"yuk", "yukjarayoni", "yuk_jarayoni"},
    "sklad": {"sklad", "skladnazorat", "sklad_nazorat"},
    "ishxona": {"ishxona", "ishxonanazorat", "ishxona_nazorat"},
}

_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

_legacy_db = "data.db"
if DB_PATH != _legacy_db and not os.path.exists(DB_PATH) and os.path.exists(_legacy_db):
    try:
        shutil.copy2(_legacy_db, DB_PATH)
        log.warning("Legacy DB migrated to %s", DB_PATH)
    except Exception as e:
        log.warning("Legacy DB migration failed: %s", e)

_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
_conn.row_factory = sqlite3.Row
_lock = asyncio.Lock()


def init_schema() -> None:
    cur = _conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_bot_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            tg_id INTEGER NOT NULL,
            bot_key TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cross_bot_day_tg ON cross_bot_events(day, tg_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cross_bot_bot_day ON cross_bot_events(bot_key, day, tg_id)"
    )
    _conn.commit()


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_bot_key(raw: str) -> str:
    key = "".join(ch for ch in str(raw or "").strip().lower() if ch.isalnum() or ch == "_")
    if not key:
        return ""
    for canonical, aliases in _BOT_KEY_ALIASES.items():
        if key == canonical:
            return canonical
        if key in aliases:
            return canonical
    return key[:32]


async def record_event(
    *,
    tg_id: int,
    day: str,
    bot_key: str,
    summary: str,
) -> None:
    text = " ".join(str(summary or "").split())
    if not text:
        return
    text = text[:MAX_SUMMARY_LEN]
    key = normalize_bot_key(bot_key)
    if not key:
        return
    day_s = str(day or "").strip()[:10]
    if len(day_s) != 10:
        day_s = datetime.now(TZ).date().isoformat()

    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            """
            INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (day_s, int(tg_id), key, text, _now_iso()),
        )
        _conn.commit()


async def fetch_merged_latest_by_bot(tg_ids: set[int] | list[int], day: str) -> dict[str, str]:
    """Bir nechta tg_id uchun har bot_key bo'yicha eng so'nggi xulosa."""
    ids = sorted({int(x) for x in tg_ids if x})
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            f"""
            SELECT bot_key, summary, id FROM cross_bot_events
            WHERE day = ? AND tg_id IN ({placeholders})
            ORDER BY id DESC
            """,
            (day, *ids),
        )
        rows = cur.fetchall()
    out: dict[str, str] = {}
    for row in rows:
        k = row["bot_key"]
        if k not in out:
            out[k] = row["summary"]
    return out


async def fetch_latest_by_bot(tg_id: int, day: str) -> dict[str, str]:
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            """
            SELECT bot_key, summary, id FROM cross_bot_events
            WHERE day = ? AND tg_id = ?
            ORDER BY id DESC
            """,
            (day, int(tg_id)),
        )
        rows = cur.fetchall()

    out: dict[str, str] = {}
    for row in rows:
        k = row["bot_key"]
        if k not in out:
            out[k] = row["summary"]
    return out


async def build_appendix_lines_async(tg_id: int | set[int], day_iso: str) -> list[str]:
    tg_ids = {int(tg_id)} if isinstance(tg_id, int) else {int(x) for x in tg_id if x}
    events = await fetch_merged_latest_by_bot(tg_ids, day_iso)
    if not events:
        return []

    order = ("omborga", "ombor", "yuk", "sklad", "ishxona")
    lines = ["", "── Boshqa botlar (bugun) ──"]
    used = 0
    for key in order:
        if key not in events:
            continue
        label = BOT_LABELS.get(key, key)
        chunk = f"• {label}: {events[key]}"
        if used + len(chunk) + 1 > MAX_APPENDIX_CHARS:
            lines.append("• … (qisqartirildi)")
            break
        lines.append(chunk)
        used += len(chunk) + 1
    for key, summary in events.items():
        if key in order:
            continue
        label = BOT_LABELS.get(key, key)
        chunk = f"• {label}: {summary}"
        if used + len(chunk) + 1 > MAX_APPENDIX_CHARS:
            break
        lines.append(chunk)
        used += len(chunk) + 1
    return lines


def hub_secret_ok(provided: str) -> bool:
    if not HUB_SECRET:
        return False
    return str(provided or "").strip() == HUB_SECRET


async def count_employee_links() -> int:
    async with _lock:
        cur = _conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM employee_links")
        row = cur.fetchone()
    return int(row["c"]) if row else 0


async def hub_events_for_day(day: str, *, limit: int = 80) -> list[dict]:
    """Admin diagnostika: bugungi barcha hub eventlar (yangidan eskiga)."""
    lim = max(1, min(int(limit), 500))
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            """
            SELECT tg_id, bot_key, summary, created_at
            FROM cross_bot_events
            WHERE day = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (day, lim),
        )
        rows = cur.fetchall()
    return [
        {
            "tg_id": int(r["tg_id"]),
            "bot_key": r["bot_key"],
            "summary": r["summary"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def hub_stats_today(day: str) -> dict[str, tuple[int, str | None]]:
    """bot_key → (event_soni, oxirgi vaqt)."""
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            """
            SELECT bot_key, COUNT(*) AS cnt, MAX(created_at) AS last_at
            FROM cross_bot_events
            WHERE day = ?
            GROUP BY bot_key
            """,
            (day,),
        )
        rows = cur.fetchall()
    out: dict[str, tuple[int, str | None]] = {}
    for row in rows:
        out[row["bot_key"]] = (int(row["cnt"]), row["last_at"])
    return out
