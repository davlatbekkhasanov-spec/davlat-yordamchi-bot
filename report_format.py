"""Hisobot formatlash — ochko, Face ID doira, taqqoslash."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CategoryRow:
    name: str
    added: int
    today: int
    period: int
    norm: int
    yesterday: str = "йўқ"


@dataclass
class CompareRow:
    name: str
    yesterday: int
    today: int
    delta: int

    @property
    def delta_class(self) -> str:
        if self.delta > 0:
            return "delta-up"
        if self.delta < 0:
            return "delta-down"
        return "delta-flat"

    @property
    def delta_text(self) -> str:
        if self.delta > 0:
            return f"↑{self.delta}"
        if self.delta < 0:
            return f"↓{abs(self.delta)}"
        return "—"


@dataclass
class FaceIdFrame:
    keldi: str = "—"
    ketdi: str = "—"
    active_work: str = "00:00:00"
    active_min: int = 0
    ball: int = 0
    kech_pt: int = 0
    qarz_today_min: int = 0
    qarz_yesterday_min: int = 0
    qarz_month_min: int = 0
    bonus_pt: int = 0

    @property
    def has_frame(self) -> bool:
        return self.keldi != "—" or self.active_min > 0 or self.ball != 0


def fmt_points(n: int) -> dict[str, str]:
    """Jadval/KPI uchun: musbat yashil, manfiy qizil (− belgisi)."""
    v = int(n or 0)
    if v > 0:
        return {"text": f"+{v}", "cls": "pts-pos"}
    if v < 0:
        return {"text": f"−{abs(v)}", "cls": "pts-neg"}
    return {"text": "0", "cls": "pts-zero"}


def fmt_debt_min(minutes: int) -> dict[str, str]:
    """Ish beruvchi qarzi — daqiqa, vahimli qizil."""
    m = max(0, int(minutes or 0))
    if not m:
        return {"text": "0", "cls": "debt-zero"}
    h, r = divmod(m, 60)
    if h:
        text = f"{h}:{r:02d}"
    else:
        text = f"{m} daq"
    return {"text": text, "cls": "debt-warn"}


def _yesterday_int(text: str) -> int | None:
    t = (text or "").strip().lower()
    if not t or t in ("йўқ", "yo'q", "—", "-", "–", "нет"):
        return None
    try:
        return int(t)
    except ValueError:
        return None


def parse_faceid_summary(summary: str) -> FaceIdFrame:
    s = (summary or "").strip()
    if not s:
        return FaceIdFrame()
    sl = s.lower()
    frame = FaceIdFrame()

    ball_m = re.search(r"ball\s*[=:]?\s*([+-]?\d+)", sl)
    if ball_m:
        frame.ball = int(ball_m.group(1))

    kech_m = re.search(r"kech\s*[=:]?\s*(\d+)", sl)
    if kech_m:
        frame.kech_pt = int(kech_m.group(1))

    qarz_m = re.search(r"qarz\s*[=:]?\s*(\d+)", sl)
    if qarz_m:
        frame.qarz_today_min = int(qarz_m.group(1))

    bonus_m = re.search(r"bonus\s*[=:]?\s*(\d+)", sl)
    if bonus_m:
        frame.bonus_pt = int(bonus_m.group(1))

    keldi_m = re.search(r"keldi\s*[=:]?\s*([\d:]+)", sl)
    if keldi_m:
        frame.keldi = keldi_m.group(1)

    ketdi_m = re.search(r"ketdi\s*[=:]?\s*([\d:]+)", sl)
    if ketdi_m and ketdi_m.group(1) not in ("—", "-"):
        frame.ketdi = ketdi_m.group(1)

    ish_daq_m = re.search(r"ish_daq\s*[=:]?\s*(\d+)", sl)
    if ish_daq_m:
        frame.active_min = int(ish_daq_m.group(1))
        frame.active_work = _fmt_hms(frame.active_min * 60)
    elif frame.keldi != "—" and frame.ketdi != "—":
        frame.active_min = _clock_diff_min(frame.keldi, frame.ketdi)
        if frame.active_min > 0:
            frame.active_work = _fmt_hms(frame.active_min * 60)

    oy_m = re.search(r"qarz_oy_daq\s*[=:]?\s*(\d+)", sl)
    if oy_m:
        frame.qarz_month_min = int(oy_m.group(1))

    return frame


def _fmt_hms(seconds: int) -> str:
    from time_display import fmt_duration_hms

    return fmt_duration_hms(seconds)


def _clock_diff_min(start: str, end: str) -> int:
    try:
        sh, sm = [int(x) for x in start.split(":")[:2]]
        eh, em = [int(x) for x in end.split(":")[:2]]
        return max(0, (eh * 60 + em) - (sh * 60 + sm))
    except (ValueError, IndexError):
        return 0


def build_compare_rows(categories: list[CategoryRow]) -> list[CompareRow]:
    rows: list[CompareRow] = []
    for cat in categories:
        y = _yesterday_int(cat.yesterday)
        if y is None:
            continue
        delta = int(cat.today) - y
        if delta == 0 and cat.added <= 0:
            continue
        rows.append(
            CompareRow(name=cat.name, yesterday=y, today=int(cat.today), delta=delta)
        )
    return rows


def pick_weakest_category(categories: list[CategoryRow]) -> tuple[str, int]:
    if not categories:
        return "", 0
    weak = min(categories, key=lambda c: (c.added, c.today))
    return weak.name, weak.added
