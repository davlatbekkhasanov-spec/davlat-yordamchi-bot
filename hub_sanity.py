"""Hub yozuvlari — noto'g'ri vaqt / format himoyasi."""

from __future__ import annotations

import re

# Har qanday xodim/kun — DB ga kirmasligi kerak bo'lgan fragmentlar
GLOBAL_BLOCK_FRAGMENTS: tuple[str, ...] = (
    "982:00",
    "ish 982",
    "17 soat 3 daqiqa 49",
    "17 soat 3 daqiqa",
)

_MAX_SINGLE_OMBOR_SEC = 4 * 3600


def _parse_work_seconds(sl: str) -> int:
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


def hub_summary_blocked(summary: str, *, bot_key: str = "") -> bool:
    """True — yozuvni saqlamaslik / ochkoga olmaslik."""
    s = (summary or "").strip()
    if not s:
        return True
    sl = s.lower()
    for frag in GLOBAL_BLOCK_FRAGMENTS:
        if frag in sl:
            return True
    key = (bot_key or "").lower()
    if key == "omborga":
        m = re.search(r"ish\s+([\d:]+)", sl)
        if m:
            token = m.group(1)
            mm = re.match(r"^(\d+):(\d{2})$", token)
            if mm and int(mm.group(1)) > 600:
                return True
    if key == "ombor" and "#" in s and "bajarildi" in sl:
        if _parse_work_seconds(sl) > _MAX_SINGLE_OMBOR_SEC:
            return True
    return False
