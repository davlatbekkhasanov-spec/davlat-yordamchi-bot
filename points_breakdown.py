"""Har bir ochko qanday hisoblanganini ko'rsatadigan alohida xabar."""

from __future__ import annotations

import html
import re
from datetime import date

from cross_bot_hub import BOT_LABELS, fetch_merged_latest_by_bot
from daily_report_card import (
    BOT_ORDER,
    DailyReportCardData,
    _ceil_minutes,
    _parse_omborga_time,
    _parse_ombor_duration,
    _parse_hms,
    score_bot_summary,
)
from employee_tg_map import employee_name_variants, tg_ids_for_employee
from ranking_broadcast import period_days_through

RULES_FOOTER = (
    "📐 <b>Qoidalar:</b>\n"
    "• Yordamchi kategoriya: 1 birlik = +1 ochko\n"
    "• Omborga: reys×2 + ⌈ish daqiqa⌉÷2\n"
    "• Ombor: ⌈ish daqiqa⌉×1\n"
    "• Yuk: ⌈ish daqiqa⌉÷2\n"
    "• Sklad: sanaldi×2\n"
    "• Ishxona: ochiq shikoyat −40"
)

_COMPACT_LEGEND = (
    "<i>Manba: Kat=yordamchi · Ombg=omborga · Omb=ombor · Yuk · Skl=sklad · In=ishxona</i>"
)

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

_BOT_SHORT = (
    ("omborga", "Ombg"),
    ("ombor", "Omb"),
    ("yuk", "Yuk"),
    ("sklad", "Skl"),
    ("ishxona", "In"),
)

_TG_MAX = 3900


def explain_bot_formula(key: str, summary: str) -> tuple[int, str]:
    """(ochko, hisoblash matni)."""
    pts, sec = score_bot_summary(key, summary)
    s = (summary or "").strip()
    if not s:
        return 0, "—"
    sl = s.lower()
    if key == "omborga":
        reys_m = re.search(r"reys\s*(\d+)", sl)
        reys = int(reys_m.group(1)) if reys_m else 0
        ish_m = re.search(r"ish\s+([\d:]+)", sl)
        ish = _parse_omborga_time(ish_m.group(1)) if ish_m else sec
        mins = _ceil_minutes(ish)
        half = mins // 2 if mins else 0
        return pts, f"reys {reys}×2 + ⌈{mins} daq⌉÷2 = {reys * 2}+{half}"
    if key == "ombor":
        sec = _parse_ombor_duration(sl) or sec or _parse_hms(s)
        mins = _ceil_minutes(sec)
        return pts, f"⌈{sec} son⌉ → {mins} daq×1"
    if key == "yuk":
        sec = _parse_hms(s)
        if not sec:
            sm = re.search(r"ish\s+vaqti\s+(\d+)", sl)
            if sm:
                sec = int(sm.group(1))
        mins = _ceil_minutes(sec)
        half = mins // 2 if mins else 0
        return pts, f"⌈{mins} daq⌉÷2 = {half}"
    if key == "sklad":
        sm = re.search(r"sanaldi\s*(\d+)", sl)
        n = int(sm.group(1)) if sm else 0
        return pts, f"sanaldi {n}×2"
    if key == "ishxona":
        om = re.search(r"ochiq\s*=\s*(\d+)", sl)
        if om:
            n = int(om.group(1))
            return pts, f"ochiq {n}×(−40)" if n else (0, "ochiq=0")
        if "shikoyat" in sl:
            return pts, "shikoyat −40"
        return pts, "bartaraf/rad"
    return pts, "—"


def _format_sources_line(cat_pts: int, bot_by_key: dict[str, int]) -> str:
    """Mobil uchun qisqa manba qatori."""
    parts: list[str] = []
    if cat_pts:
        parts.append(f"Kat <b>+{cat_pts}</b>")
    for key, short in _BOT_SHORT:
        val = int(bot_by_key.get(key) or 0)
        if not val:
            continue
        sign = f"+{val}" if val > 0 else str(val)
        parts.append(f"{short} <b>{sign}</b>")
    return " · ".join(parts)


def format_daily_breakdown_html(card: DailyReportCardData) -> str:
    """Bitta xodim kunlik ochko — reyting uslubida."""
    lines = [
        "📊 <b>OCHKO TAFSILOTI</b>",
        f"👤 {html.escape(card.employee)} · {card.day_iso}",
        "",
    ]
    n = 0
    for row in card.categories:
        if row.added <= 0:
            continue
        n += 1
        lines.append(
            f"• {html.escape(row.name)}: {row.today} birlik → <b>+{row.added}</b>"
        )
    for bot in card.bots:
        if bot.score == 0 and not (bot.summary or "").strip():
            continue
        n += 1
        _, formula = explain_bot_formula(bot.key, bot.summary)
        label = BOT_LABELS.get(bot.key, bot.key)
        sign = f"+{bot.score}" if bot.score >= 0 else str(bot.score)
        lines.append(
            f"• {html.escape(label)}: {html.escape(formula)} → <b>{sign}</b>"
        )
    if not n:
        lines.append("<i>Bugun ochko yo'q</i>")
    lines.extend(
        [
            "",
            f"🏁 <b>JAMI: +{card.grand_total}</b> "
            f"(yordamchi +{card.cat_total} · botlar +{card.bot_total})",
            "",
            RULES_FOOTER,
        ]
    )
    return "\n".join(lines)


async def build_period_breakdown_html(
    ref_date: date,
    period: str,
    *,
    employees: list[str],
    sum_period_total,
    employee_tg_map: dict[str, int],
) -> list[str]:
    """Period reyting — har xodim bo'yicha manba (mobilga qulay ping)."""
    days = period_days_through(period, ref_date)
    rows: list[tuple[str, int, dict[str, int], int]] = []

    for emp in employees:
        cat_pts = 0
        for name in employee_name_variants(emp):
            cat_pts += await sum_period_total(period, name)

        bot_by_key = {k: 0 for k in BOT_ORDER}
        tg_set = tg_ids_for_employee(emp, employee_tg_map=employee_tg_map)
        if tg_set and days:
            for day_iso in days:
                ev = await fetch_merged_latest_by_bot(tg_set, day_iso)
                for key in BOT_ORDER:
                    if key in ev:
                        sc, _ = score_bot_summary(key, ev[key])
                        bot_by_key[key] += sc

        total = cat_pts + sum(bot_by_key.values())
        if total <= 0:
            continue
        rows.append((emp, cat_pts, bot_by_key, total))

    rows.sort(key=lambda x: (-x[3], x[0]))

    header = (
        "📊 <b>OCHKO TAFSILOTI</b>\n"
        f"Период: {period} (2-sana) · holat: {ref_date.isoformat()}\n"
        "<i>Har bir ochko qayerdan yig'ilgani</i>\n"
    )
    footer = f"\n\n{_COMPACT_LEGEND}"

    blocks: list[str] = []
    for rank, (emp, cat_pts, bot_by_key, total) in enumerate(rows, 1):
        medal = _MEDALS.get(rank, f"{rank}.")
        sources = _format_sources_line(cat_pts, bot_by_key)
        block = f"{medal} <b>{html.escape(emp)}</b> — <b>{total}</b> ochko"
        if sources:
            block += f"\n   {sources}"
        blocks.append(block)

    if not blocks:
        return [header + "\n<i>Periodda ochko yo'q</i>" + footer]

    return _chunk_blocks(header, blocks, footer)


def _chunk_blocks(header: str, blocks: list[str], footer: str) -> list[str]:
    """Xodimlarni bir nechta xabarga bo'lish."""
    out: list[str] = []
    current = header
    for block in blocks:
        sep = "\n\n" if current.strip() != header.strip() else ""
        candidate = f"{current}{sep}{block}"
        if len(candidate) + len(footer) > _TG_MAX and current != header:
            out.append(current.rstrip() + footer)
            current = header + block
        else:
            current = candidate
    if current.strip():
        out.append(current.rstrip() + footer)
    return out or [header + footer]


def split_messages(text: str) -> list[str]:
    if len(text) <= _TG_MAX:
        return [text]
    out: list[str] = []
    while text:
        out.append(text[:_TG_MAX])
        text = text[_TG_MAX:]
    return out
