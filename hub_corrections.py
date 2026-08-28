"""Noto'g'ri hub yozuvlarini o'chirish (ishga tushganda)."""

from __future__ import annotations

import logging
from datetime import datetime

log = logging.getLogger(__name__)

from hub_sanity import GLOBAL_BLOCK_FRAGMENTS

# (day, tg_id, bot_key, summary_ichida qidiruv) — aniq yozuvlar
HUB_PURGE_RULES: tuple[tuple[str, int, str, str], ...] = (
    ("2026-06-07", 8440127425, "ombor", "17 soat"),
    ("2026-06-09", 5465963344, "omborga", "982:00"),
    ("2026-06-09", 5465963344, "omborga", "ish 982"),
    # 12.06 Toxirov — eski hub format (1:25 → 85 son sifatida o'qilgan) noto'g'ri ball
    ("2026-06-12", 5732350707, "mesta", "poz"),
)

# Purge dan keyin bo'sh qolgan slotlarga to'g'ri yozuv (day, tg_id, bot_key, summary)
HUB_RESTORE_ROWS: tuple[tuple[str, int, str, str], ...] = (
    ("2026-06-09", 5465963344, "omborga", "Reys 18, yuk 522m, dam 6:12"),
    (
        "2026-06-12",
        5732350707,
        "mesta",
        "Mesta: poz 90, ish 43:42, dam 0:00, tejash 3:46:18, bekor 0:00, kaizen 73",
    ),
)


async def apply_hub_purges() -> int:
    from cross_bot_hub import _conn, _lock, init_schema

    init_schema()
    total = 0
    async with _lock:
        cur = _conn.cursor()
        for day, tg_id, bot_key, needle in HUB_PURGE_RULES:
            cur.execute(
                """
                DELETE FROM cross_bot_events
                WHERE day = ? AND tg_id = ? AND bot_key = ? AND summary LIKE ?
                """,
                (day, int(tg_id), bot_key, f"%{needle}%"),
            )
            n = cur.rowcount
            if n:
                log.warning(
                    "Hub purge: %s tg=%s %s — %s ta o'chirildi", day, tg_id, bot_key, n
                )
            total += n
        for needle in GLOBAL_BLOCK_FRAGMENTS:
            cur.execute(
                "DELETE FROM cross_bot_events WHERE summary LIKE ?",
                (f"%{needle}%",),
            )
            n = cur.rowcount
            if n:
                log.warning("Hub global purge %r — %s ta", needle, n)
            total += n
        _conn.commit()
    return total


_PENALTY_BOT_KEYS = ("faceid", "navbatchi", "ishxona")


def _purge_marker_path(data_dir: str, name: str) -> str:
    import os

    return os.path.join(data_dir, name)


def _purge_marker_done(data_dir: str, name: str, today: str) -> bool:
    import os

    marker = _purge_marker_path(data_dir, name)
    if not os.path.isfile(marker):
        return False
    try:
        with open(marker, encoding="utf-8") as fh:
            stored = fh.read().strip()
    except OSError:
        return False
    return stored >= today


def _write_purge_marker(data_dir: str, name: str, today: str) -> None:
    with open(_purge_marker_path(data_dir, name), "w", encoding="utf-8") as fh:
        fh.write(today)


async def apply_faceid_history_reset(db_path: str) -> int:
    """Face ID: bugundan oldingi hub yozuvlarini o'chirish."""
    import os
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from cross_bot_hub import _conn, _lock, init_schema

    init_schema()
    data_dir = os.path.dirname(db_path) or "/data"
    today = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d")
    if _purge_marker_done(data_dir, ".faceid_purge_before_today", today):
        return 0

    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            """
            DELETE FROM cross_bot_events
            WHERE bot_key = 'faceid' AND day < ?
            """,
            (today,),
        )
        removed = cur.rowcount
        _conn.commit()
    _write_purge_marker(data_dir, ".faceid_purge_before_today", today)
    if removed:
        log.warning(
            "Face ID tarix tozalandi: %s ta yozuv o'chirildi (bugun=%s)",
            removed,
            today,
        )
    return removed


async def apply_ranking_minus_reset_before_today(db_path: str) -> dict[str, int]:
    """Reyting minuslari: bugundan oldin faceid/navbatchi/ishxona + jarima."""
    import os
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from cross_bot_hub import _conn, _lock, init_schema
    from ranking_adjustments import init_schema as init_adj_schema

    init_schema()
    init_adj_schema(_conn)
    data_dir = os.path.dirname(db_path) or "/data"
    today = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d")
    if _purge_marker_done(data_dir, ".ranking_minus_reset", today):
        return {"skipped": 1}

    keys = ", ".join("?" for _ in _PENALTY_BOT_KEYS)
    out = {"hub_events": 0, "penalties": 0}
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            f"""
            DELETE FROM cross_bot_events
            WHERE bot_key IN ({keys}) AND day < ?
            """,
            (*_PENALTY_BOT_KEYS, today),
        )
        out["hub_events"] = cur.rowcount
        cur.execute(
            """
            DELETE FROM ranking_adjustments
            WHERE kind = 'penalty' AND day < ?
            """,
            (today,),
        )
        out["penalties"] = cur.rowcount
        _conn.commit()
    _write_purge_marker(data_dir, ".ranking_minus_reset", today)
    if out["hub_events"] or out["penalties"]:
        log.warning(
            "Reyting minus tozalandi: hub=%s jarima=%s (bugun=%s)",
            out["hub_events"],
            out["penalties"],
            today,
        )
    return out


async def apply_hub_restores() -> int:
    """Noto'g'ri yozuv o'chirilgach yoki faqat bloklangan qolganda — to'g'ri xulosa."""
    from cross_bot_hub import _conn, _lock, fetch_merged_latest_by_bot, init_schema, normalize_bot_key
    from hub_sanity import hub_summary_blocked

    init_schema()
    total = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for day, tg_id, bot_key, summary in HUB_RESTORE_ROWS:
        key = normalize_bot_key(bot_key)
        merged = await fetch_merged_latest_by_bot({int(tg_id)}, day)
        current = merged.get(key, "")
        if current and not hub_summary_blocked(current, bot_key=key):
            continue
        async with _lock:
            cur = _conn.cursor()
            cur.execute(
                "DELETE FROM cross_bot_events WHERE day = ? AND tg_id = ? AND bot_key = ?",
                (day, int(tg_id), key),
            )
            cur.execute(
                """
                INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (day, int(tg_id), key, summary[:420], now),
            )
            _conn.commit()
        log.warning(
            "Hub restore: %s tg=%s %s — %r",
            day,
            tg_id,
            key,
            summary[:80],
        )
        total += 1
    return total
