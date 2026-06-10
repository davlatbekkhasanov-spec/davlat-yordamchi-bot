"""Vaqt ko'rsatish va parse — barcha botlar uchun yagona logika.

Qoida:
  < 1 soat  → MM:SS   (masalan 47:29)
  ≥ 1 soat  → H:MM:SS (masalan 1:15:29, 2:05:00)
Hech qachon 75:00 kabi «daqiqa» ko'rinishida qolmaydi.
"""

from __future__ import annotations

import re

_MAX_REASONABLE_MIN = 720  # 12 soat


def fmt_duration(seconds: int) -> str:
    """Asosiy ko'rinish: MM:SS yoki H:MM:SS."""
    sec = max(0, int(seconds))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def fmt_duration_hms(seconds: int) -> str:
    """Jami ish vaqti (analytics): doim HH:MM:SS."""
    sec = max(0, int(seconds))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_duration_label(seconds: int) -> str:
    """Inson o'qiydigan: 1 soat 15 daqiqa / 47 daqiqa 29 soniya."""
    sec = max(0, int(seconds))
    if not sec:
        return "0 soniya"
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    parts: list[str] = []
    if h:
        parts.append(f"{h} soat")
    if m:
        parts.append(f"{m} daqiqa")
    if s and not h:
        parts.append(f"{s} soniya")
    return " ".join(parts) if parts else "0 soniya"


def fmt_duration_scoring(seconds: int) -> str:
    """Ochko formulasi: soatga o'tganda H:MM, aks holda N daq."""
    sec = max(0, int(seconds))
    h, r = divmod(sec, 3600)
    m, _ = divmod(r, 60)
    if h > 0:
        return f"{h}:{m:02d}" if m else f"{h} soat"
    m_ceil = (sec + 59) // 60
    return f"{m_ceil} daq"


def parse_colon_token(token: str) -> int:
    """
    ish/dam/reys tokenlari: 47:29 = 47daq 29son, 1:15:29 = 1soat 15daq 29son.
  75:00 = 75 daqiqa (MM:SS), 1:15:00 = 1 soat 15 daqiqa.
    """
    t = (token or "").strip()
    if not t:
        return 0
    m3 = re.match(r"^(\d+):(\d{2}):(\d{2})$", t)
    if m3:
        return int(m3.group(1)) * 3600 + int(m3.group(2)) * 60 + int(m3.group(3))
    m2 = re.match(r"^(\d+):(\d{2})$", t)
    if m2:
        left = int(m2.group(1))
        right = int(m2.group(2))
        if left > _MAX_REASONABLE_MIN:
            return 0
        # Botlar: 2 qism = daqiqa:soniya (47:29, 75:00)
        return left * 60 + right
    return 0


def parse_duration_text(text: str) -> int:
    """'1 soat 30 daqiqa', '5907 soniya', 'ish vaqti 1200 soniya'."""
    sl = (text or "").lower()
    m = re.search(r"ish\s+vaqti\s+(\d+)\s*soniya", sl)
    if m:
        return int(m.group(1))
    m = re.search(r"ish\s+vaqti\s+(\d+)\s*soat\s+(\d+)\s*daq", sl)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    m = re.search(r"ish\s+vaqti\s+(\d+):(\d{2}):(\d{2})", sl)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.search(r"ish\s+vaqti\s+(\d+):(\d{2})(?!\d)", sl)
    if m:
        return parse_colon_token(m.group(0).split()[-1])
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
    if total:
        return total
    m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", sl)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.search(r"\b(\d+):(\d{2})\b", sl)
    if m:
        return parse_colon_token(f"{m.group(1)}:{m.group(2)}")
    return 0
