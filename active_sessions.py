"""Jonli ish sessiyalari — hub-connected botlar."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import cross_bot_hub as hub
from employee_tg_map import TG_EMPLOYEE

log = logging.getLogger(__name__)
TZ = ZoneInfo(__import__("os").getenv("TZ", "Asia/Tashkent"))

ACTIVITY_LABELS = {
    "mesta": "Mesta",
    "prihod": "Prihod",
    "invent": "Inventarizatsiya",
    "yuk": "Юк ташиш",
    "omborga": "Reyslar",
    "sklad": "Sklad nazorat",
    "ombor": "Ombor xizmat",
    "ishxona": "Ishxona",
    "navbatchi": "Navbatchi",
}

SECTION_ORDER = ("mesta", "prihod", "invent", "yuk", "omborga", "sklad", "ombor", "ishxona", "navbatchi")

_STALE_HOURS = 10


def init_active_sessions_schema() -> None:
    cur = hub._conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS active_sessions (
            session_key TEXT PRIMARY KEY,
            bot_key TEXT NOT NULL,
            tg_id INTEGER NOT NULL,
            user_name TEXT NOT NULL DEFAULT '',
            activity_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_active_sessions_type ON active_sessions(activity_type)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_active_sessions_updated ON active_sessions(updated_at)"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    hub._conn.commit()


def get_hub_meta(key: str) -> str:
    init_active_sessions_schema()
    cur = hub._conn.cursor()
    row = cur.execute("SELECT value FROM hub_meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else ""


def set_hub_meta(key: str, value: str) -> None:
    init_active_sessions_schema()
    cur = hub._conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO hub_meta(key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    hub._conn.commit()


def _now_iso() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def _resolve_activity_type(bot_key: str, summary: str = "", activity_type: str = "") -> str:
    raw = (activity_type or "").strip().lower()
    if raw:
        if raw in ("inventarizatsiya", "inv"):
            return "invent"
        if raw in ("reys", "reyslar"):
            return "omborga"
        return raw[:32]
    key = hub.normalize_bot_key(bot_key)
    sl = (summary or "").strip().lower()
    if key == "inventarizatsiya":
        if sl.startswith("приход:") or sl.startswith("prihod:"):
            return "prihod"
        return "invent"
    if key == "omborga":
        return "omborga"
    return key or "other"


def _session_key(bot_key: str, tg_id: int, activity_type: str) -> str:
    key = hub.normalize_bot_key(bot_key)
    act = _resolve_activity_type(key, activity_type=activity_type)
    return f"{act}:{int(tg_id)}"


def _resolve_user_name(tg_id: int, user_name: str) -> str:
    name = " ".join(str(user_name or "").split()).strip()
    if name:
        return name[:80]
    return TG_EMPLOYEE.get(int(tg_id), f"ID {tg_id}")


def _parse_metadata(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return {}


def _metadata_from_summary(summary: str) -> dict:
    sl = (summary or "").lower()
    meta: dict = {}
    poz_m = re.search(r"poz\s*(\d+)", sl)
    if poz_m:
        meta["poz"] = int(poz_m.group(1))
    reys_m = re.search(r"reys\s*(\d+)", sl)
    if reys_m:
        meta["trip_count"] = int(reys_m.group(1))
    folder_m = re.search(r"(?:papka|папка|folder)\s+([^,]+)", sl, re.I)
    if folder_m:
        meta["folder"] = folder_m.group(1).strip()[:60]
    yuk_m = re.search(r"yuk\s+(\d+)", sl)
    if yuk_m:
        meta["yuk_m"] = int(yuk_m.group(1))
    if "dam" in sl or "pauza" in sl or "paused" in sl:
        meta["paused_hint"] = True
    return meta


def _elapsed_sec(started_at: str, now: datetime | None = None) -> int:
    now = now or datetime.now(TZ)
    try:
        start = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
        return max(0, int((now - start).total_seconds()))
    except (TypeError, ValueError):
        return 0


def _row_to_dict(row: sqlite3.Row) -> dict:
    meta = _parse_metadata(row["metadata_json"])
    started = str(row["started_at"])
    return {
        "session_key": row["session_key"],
        "bot_key": row["bot_key"],
        "activity_type": row["activity_type"],
        "activity_label": ACTIVITY_LABELS.get(row["activity_type"], row["activity_type"]),
        "tg_id": int(row["tg_id"]),
        "user_name": row["user_name"],
        "status": row["status"],
        "started_at": started,
        "updated_at": row["updated_at"],
        "elapsed_sec": _elapsed_sec(started),
        "metadata": meta,
    }


def _purge_stale_sync() -> int:
    cur = hub._conn.cursor()
    cur.execute(
        """
        DELETE FROM active_sessions
        WHERE datetime(updated_at) < datetime('now', ?)
        """,
        (f"-{_STALE_HOURS} hours",),
    )
    n = cur.rowcount
    if n:
        hub._conn.commit()
    return n


async def upsert_active_session(
    *,
    tg_id: int,
    bot_key: str,
    user_name: str = "",
    activity_type: str = "",
    status: str = "active",
    metadata: dict | None = None,
    summary: str = "",
) -> None:
    key = hub.normalize_bot_key(bot_key)
    if not key or not tg_id:
        return
    act = _resolve_activity_type(key, summary, activity_type)
    sk = _session_key(key, tg_id, act)
    name = _resolve_user_name(tg_id, user_name)
    st = (status or "active").strip().lower()
    if st not in ("active", "paused"):
        st = "paused" if st in ("pause", "dam", "pauza") else "active"
    meta = dict(metadata or {})
    if summary and not meta:
        meta.update(_metadata_from_summary(summary))
    now = _now_iso()
    meta_json = json.dumps(meta, ensure_ascii=False)[:2000]

    async with hub._lock:
        cur = hub._conn.cursor()
        row = cur.execute(
            "SELECT started_at FROM active_sessions WHERE session_key = ?",
            (sk,),
        ).fetchone()
        started = row["started_at"] if row else now
        cur.execute(
            """
            INSERT INTO active_sessions(
                session_key, bot_key, tg_id, user_name, activity_type,
                status, started_at, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                bot_key = excluded.bot_key,
                user_name = excluded.user_name,
                activity_type = excluded.activity_type,
                status = excluded.status,
                updated_at = excluded.updated_at,
                metadata_json = excluded.metadata_json
            """,
            (sk, key, int(tg_id), name, act, st, started, now, meta_json),
        )
        hub._conn.commit()
    log.debug("Active session upsert: %s %s %s", sk, name, st)


async def end_active_session(
    *,
    tg_id: int,
    bot_key: str,
    activity_type: str = "",
) -> bool:
    key = hub.normalize_bot_key(bot_key)
    if not key or not tg_id:
        return False
    act = _resolve_activity_type(key, activity_type=activity_type)
    sk = _session_key(key, tg_id, act)
    async with hub._lock:
        cur = hub._conn.cursor()
        cur.execute("DELETE FROM active_sessions WHERE session_key = ?", (sk,))
        deleted = cur.rowcount > 0
        if activity_type == "" and not deleted:
            cur.execute(
                "DELETE FROM active_sessions WHERE bot_key = ? AND tg_id = ?",
                (key, int(tg_id)),
            )
            deleted = cur.rowcount > 0
        hub._conn.commit()
    if deleted:
        log.debug("Active session ended: %s", sk)
    return deleted


async def list_active_sessions() -> dict:
    async with hub._lock:
        _purge_stale_sync()
        cur = hub._conn.cursor()
        cur.execute(
            """
            SELECT * FROM active_sessions
            ORDER BY activity_type ASC, started_at ASC
            """
        )
        rows = cur.fetchall()
    sessions = [_row_to_dict(r) for r in rows]
    sections: dict[str, list] = {k: [] for k in SECTION_ORDER}
    for s in sessions:
        act = s["activity_type"]
        sections.setdefault(act, []).append(s)
    ordered_sections = {k: sections.get(k, []) for k in SECTION_ORDER if sections.get(k)}
    for k, v in sections.items():
        if k not in ordered_sections and v:
            ordered_sections[k] = v
    return {
        "ok": True,
        "updated_at": _now_iso(),
        "total_active": len(sessions),
        "sessions": sessions,
        "sections": ordered_sections,
        "labels": ACTIVITY_LABELS,
    }


async def process_session_ingest(data: dict) -> bool:
    """Ingest payload dan sessiya boshqaruvi. True = sessiya eventi qayta ishlandi."""
    event_type = str(data.get("event_type") or data.get("session_event") or "").strip().lower()
    if not event_type:
        summary = str(data.get("summary") or data.get("text") or "")
        sl = summary.lower()
        if summary.startswith("[SESSION:"):
            m = re.match(r"\[SESSION:(START|UPDATE|END)\]", summary, re.I)
            if m:
                event_type = f"session_{m.group(1).lower()}"
        elif "jonli sessiya tugadi" in sl or "session_end" in sl:
            event_type = "session_end"
        elif "jonli sessiya" in sl or "[live]" in sl:
            event_type = "session_update" if "yangilash" in sl or "update" in sl else "session_start"

    if not event_type:
        return False

    try:
        tg_id = int(data.get("tg_id") or data.get("telegram_id") or data.get("user_id") or 0)
    except (TypeError, ValueError):
        return False
    bot_key = str(data.get("bot_key") or data.get("bot") or data.get("source") or "").strip()
    if not tg_id or not bot_key:
        return False

    user_name = str(data.get("user_name") or data.get("employee") or data.get("name") or "")
    activity_type = str(data.get("activity_type") or data.get("activity") or "")
    status = str(data.get("status") or "active")
    metadata = _parse_metadata(data.get("metadata"))
    summary = str(data.get("summary") or data.get("text") or "")

    if event_type in ("session_end", "end", "finish", "stop"):
        await end_active_session(tg_id=tg_id, bot_key=bot_key, activity_type=activity_type)
        return True

    if event_type in ("session_start", "start", "session_update", "update", "ping", "resume"):
        if event_type in ("session_start", "start"):
            status = status or "active"
        await upsert_active_session(
            tg_id=tg_id,
            bot_key=bot_key,
            user_name=user_name,
            activity_type=activity_type,
            status=status,
            metadata=metadata,
            summary=summary,
        )
        return True

    return False
