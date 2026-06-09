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
)

# Purge dan keyin bo'sh qolgan slotlarga to'g'ri yozuv (day, tg_id, bot_key, summary)
HUB_RESTORE_ROWS: tuple[tuple[str, int, str, str], ...] = (
    ("2026-06-09", 5465963344, "omborga", "Reys 18, yuk 522m, dam 6:12"),
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
