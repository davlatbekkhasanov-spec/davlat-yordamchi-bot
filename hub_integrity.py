"""Hub ma'lumotlari — analytics oldidan avtomatik tekshiruv va tuzatish."""

from __future__ import annotations

import logging

from cross_bot_hub import CANONICAL_UPSERT_KEYS, DB_PATH, init_schema
from hub_repair import repair_hub_db

log = logging.getLogger(__name__)


def ensure_hub_repaired_for_day(db_path: str | None = None, *, day: str) -> int:
    """
    Berilgan kun uchun hub yozuvlarini kanonik qilib qayta yozadi.
    Analytics har safar ochilishidan oldin chaqiriladi — kesh yo'q, doim yangi hisob.
    """
    day_s = (day or "").strip()[:10]
    if not day_s:
        return 0
    path = (db_path or DB_PATH).strip() or DB_PATH
    init_schema()
    fixes = repair_hub_db(path, day=day_s, apply=True)
    if fixes:
        log.info("Hub integrity %s: %s ta guruh tuzatildi", day_s, len(fixes))
    return len(fixes)
