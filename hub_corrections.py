"""Noto'g'ri hub yozuvlarini o'chirish (ishga tushganda)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# (day, tg_id, bot_key, summary_ichida qidiruv)
HUB_PURGE_RULES: tuple[tuple[str, int, str, str], ...] = (
    ("2026-06-07", 8440127425, "ombor", "17 soat"),
    # Tolib: omborga bot 982:00 (982 daq) noto'g'ri format — +527 soxta ochko
    ("2026-06-09", 5465963344, "omborga", "982:00"),
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
        _conn.commit()
    return total
