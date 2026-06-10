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
_MAX_OMBOR_DAILY_SEC = 12 * 3600
_MAX_YUK_DAILY_SEC = 6 * 3600
_MAX_OMBORGA_ISH_SEC = 12 * 3600


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
    if key == "ombor" and "jami" in sl and "ish vaqti" in sl:
        if _parse_work_seconds(sl) > _MAX_OMBOR_DAILY_SEC:
            return True
    if key == "omborga":
        from cross_bot_hub import _parse_omborga_totals

        _, ish = _parse_omborga_totals(s)
        if ish > _MAX_OMBORGA_ISH_SEC:
            return True
    if key == "yuk":
        if "jonli" in sl:
            return True
        from cross_bot_hub import _parse_yuk_ish_sec

        sec = _parse_yuk_ish_sec(sl)
        if sec > _MAX_YUK_DAILY_SEC:
            return True
        if sec >= 10800 and "yakun" not in sl and "forward jami" not in sl:
            return True
    return False
