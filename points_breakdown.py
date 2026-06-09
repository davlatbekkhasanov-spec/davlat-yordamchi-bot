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


def format_daily_breakdown_html(card: DailyReportCardData) -> str:
    """Bitta xodim kunlik ochko jadvali."""
    lines = [
        f"📊 <b>Ochko tafsiloti</b>",
        f"👤 {html.escape(card.employee)} · {card.day_iso}",
        "",
        "<pre>",
        f"{'Manba':<22} {'Hisob':<28} Ochko",
        "─" * 58,
    ]
    n = 0
    for row in card.categories:
        if row.added <= 0:
            continue
        n += 1
        manba = _cell(row.name, 22)
        hisob = _cell(f"{row.today} birlik (1:1)", 28)
        lines.append(f"{manba} {hisob} +{row.added}")
    for bot in card.bots:
        if bot.score == 0 and not (bot.summary or "").strip():
            continue
        n += 1
        _, formula = explain_bot_formula(bot.key, bot.summary)
        label = BOT_LABELS.get(bot.key, bot.key)
        manba = _cell(label, 22)
        hisob = _cell(formula, 28)
        sign = f"+{bot.score}" if bot.score >= 0 else str(bot.score)
        lines.append(f"{manba} {hisob} {sign}")
    if not n:
        lines.append("(bugun ochko yo'q)")
    lines.append("─" * 58)
    lines.append(
        f"{'JAMI':<22} {'Yordamchi+' + str(card.cat_total) + ' Bot+' + str(card.bot_total):<28} +{card.grand_total}"
    )
    lines.append("</pre>")
    lines.append("")
    lines.append(RULES_FOOTER)
    return "\n".join(lines)


def _cell(text: str, width: int) -> str:
    t = (text or "")[:width]
    return t.ljust(width)


async def build_period_breakdown_html(
    ref_date: date,
    period: str,
    *,
    employees: list[str],
    sum_period_total,
    employee_tg_map: dict[str, int],
) -> list[str]:
    """Period reyting — har xodim bo'yicha manba jadvali (bir nechta xabar bo'lishi mumkin)."""
    days = period_days_through(period, ref_date)
    header = (
        f"📊 <b>Period ochko tafsiloti</b>\n"
        f"Период: {period} · holat: {ref_date.isoformat()}\n"
        f"<i>Kat=kategoriya · Ombg=omborga · Omb=ombor · Skl=sklad · In=ishxona</i>\n\n"
    )
    body_lines = [
        "<pre>",
        f"{'Xodim':<18} {'Kat':>5} {'Ombg':>5} {'Omb':>5} {'Yuk':>5} {'Skl':>5} {'In':>5} {'Jami':>6}",
        "─" * 58,
    ]

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
        body_lines.append(
            f"{_cell(emp, 18)} {cat_pts:>5} {bot_by_key['omborga']:>5} "
            f"{bot_by_key['ombor']:>5} {bot_by_key['yuk']:>5} "
            f"{bot_by_key['sklad']:>5} {bot_by_key['ishxona']:>5} {total:>6}"
        )

    body_lines.append("</pre>")
    text = header + "\n".join(body_lines) + "\n\n" + RULES_FOOTER
    if len(text) <= _TG_MAX:
        return [text]

    # Juda uzun bo'lsa — xodimlarni bo'lib yuborish
    chunks = []
    part = header + "<pre>\n" + body_lines[1] + "\n" + body_lines[2] + "\n"
    for line in body_lines[3:-1]:
        if len(part) + len(line) > _TG_MAX:
            chunks.append(part + "</pre>\n\n" + RULES_FOOTER)
            part = "<pre>\n" + body_lines[1] + "\n" + body_lines[2] + "\n"
        part += line + "\n"
    if part.strip():
        chunks.append(part + "</pre>\n\n" + RULES_FOOTER)
    return chunks or [text]


def split_messages(text: str) -> list[str]:
    if len(text) <= _TG_MAX:
        return [text]
    out: list[str] = []
    while text:
        out.append(text[:_TG_MAX])
        text = text[_TG_MAX:]
    return out
