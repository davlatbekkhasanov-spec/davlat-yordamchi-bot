"""Boshqa botlardan kelgan kunlik xulosalar — davlat-yordamchi yakunida qo'shiladi."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

DB_PATH = os.getenv("DB_PATH", "data.db").strip() or "data.db"
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
    key = str(bot_key or "").strip().lower()[:32]
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


async def build_appendix_lines_async(tg_id: int, day_iso: str) -> list[str]:
    events = await fetch_latest_by_bot(tg_id, day_iso)
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
