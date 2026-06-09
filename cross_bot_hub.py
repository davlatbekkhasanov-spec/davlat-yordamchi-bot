"""Boshqa botlardan kelgan kunlik xulosalar — davlat-yordamchi yakunida qo'shiladi."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

from persist_data import bootstrap_persistence, resolve_db_path

DB_PATH = resolve_db_path(default_filename="data.db")
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

_PERSIST = bootstrap_persistence(DB_PATH, legacy_names=("data.db",))
DB_PATH = _PERSIST["db_path"]

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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_seed_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL DEFAULT 0,
            applied_at TEXT
        )
        """
    )
    _conn.commit()


def _parse_duration_seconds(sl: str) -> int:
    """'50 daqiqa 26 soniya', '1 soat 30 daqiqa', '5907 soniya'."""
    sm = re.search(r"ish\s+vaqti\s+(\d+)\s*soniya", sl)
    if sm:
        return int(sm.group(1))
    total = 0
    h = re.search(r"(\d+)\s*soat", sl)
    daq = re.search(r"(\d+)\s*daqiqa", sl)
    son = re.search(r"(\d+)\s*soniya", sl)
    if h:
        total += int(h.group(1)) * 3600
    if daq:
        total += int(daq.group(1)) * 60
    if son:
        total += int(son.group(1))
    return total


def _parse_omborga_ish_sec(sl: str) -> int:
    """Omborga: ish 3:29 = daqiqa:soniya."""
    ish_m = re.search(r"ish\s+([\d:]+)", sl)
    if not ish_m:
        return 0
    token = ish_m.group(1).strip()
    m = re.match(r"^(\d+):(\d{2})$", token)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return _parse_duration_seconds(f"ish vaqti {token}")


def _is_ombor_cumulative(summary: str) -> bool:
    sl = (summary or "").lower()
    return "jami" in sl and "ish vaqti" in sl and "soniya" in sl


def _parse_count_sec(summary: str, bot_key: str) -> tuple[int, int]:
    """ombor/yuk — jami yoki bitta ariza (#47 bajarildi, ...) formatidan."""
    sl = (summary or "").lower()
    cnt = 0
    sec = 0
    if bot_key == "ombor":
        if _is_ombor_cumulative(summary):
            cm = re.search(r"(\d+)\s*ta", sl)
            if cm:
                cnt = int(cm.group(1))
            sec = _parse_duration_seconds(sl)
            return cnt, sec
        if "#" in summary and "bajarildi" in sl:
            return 1, _parse_duration_seconds(sl)
        return 0, 0
    cm = re.search(r"(\d+)\s*ta", sl)
    if cm:
        cnt = int(cm.group(1))
    sm = re.search(r"ish\s+vaqti\s+(\d+)\s*soniya", sl)
    if sm:
        sec = int(sm.group(1))
    elif bot_key == "yuk":
        sm = re.search(r"ish\s+vaqti\s+(\d+)", sl)
        if sm:
            sec = int(sm.group(1))
    return cnt, sec


def _parse_omborga_totals(summary: str) -> tuple[int, int]:
    sl = (summary or "").lower()
    reys_m = re.search(r"reys\s*(\d+)", sl)
    reys = int(reys_m.group(1)) if reys_m else 0
    return reys, _parse_omborga_ish_sec(sl)


def _merge_hub_summary(bot_key: str, old: str, new: str) -> str:
    """Bir xil kun+xodim+bot uchun yangi hisobotni eskisiga qo'shish."""
    key = normalize_bot_key(bot_key)
    if not old:
        return new
    if key == "ombor":
        if _is_ombor_cumulative(new):
            nc, ns = _parse_count_sec(new, key)
            if ns > 0 or nc > 0:
                return new
            oc, os_ = _parse_count_sec(old, key)
            if os_ > 0 or oc > 0:
                return old
            return new
        oc, os_ = _parse_count_sec(old, key)
        nc, ns = _parse_count_sec(new, key)
        total_c = oc + nc
        total_s = os_ + ns
        if total_s <= 0 and total_c <= 0:
            return old if (os_ > 0 or oc > 0) else new
        return f"Ombor (jami): {total_c} ta, ish vaqti {total_s} soniya"
    if key == "yuk":
        oc, os_ = _parse_count_sec(old, key)
        nc, ns = _parse_count_sec(new, key)
        total_s = os_ + ns
        return f"Yuk (jami): ish vaqti {total_s} soniya"
    if key == "omborga":
        or_, oi = _parse_omborga_totals(old)
        nr, ni = _parse_omborga_totals(new)
        total_reys = or_ + nr
        total_ish = oi + ni
        ish_t = f"{total_ish // 60}:{total_ish % 60:02d}"
        return f"Reys {total_reys}, ish {ish_t}, dam 0:00"
    return new


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
        existing = _latest_by_bot_sync(int(tg_id), day_s)
        if key in existing:
            text = _merge_hub_summary(key, existing[key], text)
        cur = _conn.cursor()
        cur.execute(
            """
            INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (day_s, int(tg_id), key, text, _now_iso()),
        )
        _conn.commit()


async def ensure_hub_seed() -> int:
    """Kod ichidagi boshlang'ich yozuvlar — faqat bo'sh slotlarga, bir marta."""
    from hub_seed import HUB_SEED_ROWS, HUB_SEED_VERSION

    init_schema()
    async with _lock:
        cur = _conn.cursor()
        row = cur.execute("SELECT version FROM hub_seed_meta WHERE id = 1").fetchone()
        applied_ver = int(row["version"]) if row else 0

    added = 0
    for day, tg_id, bot_key, summary in HUB_SEED_ROWS:
        key = normalize_bot_key(bot_key)
        existing = await fetch_latest_by_bot(int(tg_id), day)
        if key in existing:
            continue
        await record_event(tg_id=int(tg_id), day=day, bot_key=bot_key, summary=summary)
        added += 1

    if added or applied_ver < HUB_SEED_VERSION:
        async with _lock:
            cur = _conn.cursor()
            cur.execute(
                """
                INSERT INTO hub_seed_meta(id, version, applied_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    version = excluded.version,
                    applied_at = excluded.applied_at
                """,
                (HUB_SEED_VERSION, _now_iso()),
            )
            _conn.commit()

    if added:
        log.info("Hub seed: %s yozuv (v%s)", added, HUB_SEED_VERSION)
    return added


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


def _latest_by_bot_sync(tg_id: int, day: str) -> dict[str, str]:
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


async def fetch_latest_by_bot(tg_id: int, day: str) -> dict[str, str]:
    async with _lock:
        return _latest_by_bot_sync(tg_id, day)


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
