"""Har bir ochko qanday hisoblanganini ko'rsatadigan alohida xabar (ping jadval)."""

from __future__ import annotations

import html
import re
from datetime import date

from cross_bot_hub import BOT_LABELS, fetch_merged_latest_by_bot
from daily_report_card import (
    BOT_ORDER,
    DailyReportCardData,
    HUB_CATEGORY_BOT_KEYS,
    INV_NORM_MIN,
    MESTA_NORM_MIN,
    _ceil_minutes,
    _inventarizatsiya_scoring,
    _mesta_scoring,
    _parse_omborga_time,
    _parse_ombor_duration,
    _parse_hms,
    score_bot_summary,
)
from time_display import fmt_duration_scoring
from employee_tg_map import employee_name_variants, tg_ids_for_employee
from ranking_broadcast import period_days_through

RULES_FOOTER = (
    "📐 <b>Ҳисоблаш қоидалари:</b>\n"
    "Ёрдамчи — 1 бирлик = 1 очко\n"
    "Омборга — рейс×2 + иш вақти÷2\n"
    "Омбор — иш вақти×1 · Юк — иш вақти÷2\n"
    "Склад — саналди×2 · Mesta — poz alohida, faqat tejash bonusi (kaizen) ochko\n"
    "Inventarizatsiya — poz alohida, faqat tejash bonusi (kaizen) ochko\n"
    "Ишхона — очиқ шикоят −40"
)

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

_BOT_COLS = (
    ("omborga", "Ombg"),
    ("ombor", "Omb"),
    ("yuk", "Yuk"),
    ("sklad", "Skl"),
    ("mesta", "Mes"),
    ("inventarizatsiya", "Inv"),
    ("ishxona", "Ish"),
    ("faceid", "FI"),
)

BOT_SOURCE_CYRL = {
    "omborga": "Омборга киритиш",
    "ombor": "Омбор хизмат",
    "yuk": "Юк жараёни",
    "sklad": "Склад назорат",
    "mesta": "Mesta",
    "inventarizatsiya": "Inventarizatsiya",
    "ishxona": "Ишхона шикоят",
    "faceid": "Face ID davomat",
}

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
        ish_lbl = fmt_duration_scoring(ish)
        if half:
            return pts, f"{reys}×2 + {ish_lbl}÷2 = {pts}"
        return pts, f"{reys}×2 = {pts}"
    if key == "ombor":
        sec = _parse_ombor_duration(sl) or sec or _parse_hms(s)
        return pts, f"{fmt_duration_scoring(sec)}×1"
    if key == "yuk":
        sec = _parse_hms(s)
        if not sec:
            sm = re.search(r"ish\s+vaqti\s+(\d+)", sl)
            if sm:
                sec = int(sm.group(1))
        half = _ceil_minutes(sec) // 2 if sec else 0
        return pts, f"{fmt_duration_scoring(sec)}÷2 = {half}"
    if key == "sklad":
        sm = re.search(r"sanaldi\s*(\d+)", sl)
        n = int(sm.group(1)) if sm else 0
        return pts, f"{n}×2"
    if key == "mesta":
        poz, work_sec, saved_sec, _ = _mesta_scoring(s)
        if not poz:
            return 0, "—"
        saved_min = saved_sec // 60
        if re.search(r"kaizen\s+(\d+)", sl):
            return pts, f"{poz} poz · kaizen bonus +{pts}"
        return pts, f"{poz} poz · tejash {saved_min}÷{MESTA_NORM_MIN}={pts}"
    if key == "inventarizatsiya":
        poz, work_sec, saved_sec, _ = _inventarizatsiya_scoring(s)
        if not poz:
            return 0, "—"
        saved_min = saved_sec // 60
        if re.search(r"kaizen\s+(\d+)", sl):
            return pts, f"{poz} poz · kaizen bonus +{pts}"
        return pts, f"{poz} poz · tejash {saved_min}÷{INV_NORM_MIN}={pts}"
    if key == "ishxona":
        om = re.search(r"ochiq\s*=\s*(\d+)", sl)
        if om:
            n = int(om.group(1))
            return pts, f"ochiq {n}×(−40)" if n else (0, "0")
        if "shikoyat" in sl:
            return pts, "−40"
        return pts, "0"
    if key == "faceid":
        ball_m = re.search(r"ball\s*[=:]?\s*([+-]?\d+)", sl)
        if ball_m:
            return pts, f"ball={ball_m.group(1)}"
        return pts, "—"
    return pts, "—"


def _short_name(full: str, width: int = 13) -> str:
    parts = (full or "").split()
    if len(parts) >= 2 and len(parts[0]) + len(parts[-1]) + 2 <= width:
        short = f"{parts[0]} {parts[-1][0]}."
    else:
        short = full
    if len(short) > width:
        return short[: width - 1] + "…"
    return short.ljust(width)


def _n(val: int, w: int) -> str:
    """Jadval raqami — 0 bo'lsa chiziqcha."""
    v = int(val or 0)
    if not v:
        return "—".rjust(w)
    s = str(v)
    if len(s) > w:
        return s[-w:].rjust(w)
    return s.rjust(w)


def _pre_table(lines: list[str]) -> str:
    return "<pre>" + "\n".join(html.escape(ln) for ln in lines) + "</pre>"


def _period_table_lines(
    rows: list[tuple[str, int, dict[str, int], int]],
) -> list[str]:
    """Period jamoa jadvali — bir qator = bir xodim."""
    hdr = (
        f"{'#':>2} {'Xodim':13} "
        f"{'Kat':>4} {'Ombg':>4} {'Omb':>4} {'Yuk':>3} {'Skl':>3} {'Mes':>3} {'In':>3} "
        f"{'Σ':>5}"
    )
    sep = "─" * len(hdr)
    out = [hdr, sep]
    for rank, (emp, cat_pts, bot_by_key, total) in enumerate(rows, 1):
        tag = _MEDALS.get(rank, "")
        name = _short_name(emp, 12 if tag else 13)
        if tag:
            name = f"{tag}{name[1:]}" if len(name) > 1 else tag
            name = name[:13].ljust(13)
        out.append(
            f"{rank:>2} {name} "
            f"{_n(cat_pts, 4)} {_n(bot_by_key.get('omborga', 0), 4)} "
            f"{_n(bot_by_key.get('ombor', 0), 4)} {_n(bot_by_key.get('yuk', 0), 3)} "
            f"{_n(bot_by_key.get('sklad', 0), 3)} {_n(bot_by_key.get('mesta', 0), 3)} "
            f"{_n(bot_by_key.get('ishxona', 0), 3)} "
            f"{_n(total, 5)}"
        )
    return out


def format_daily_breakdown_html(card: DailyReportCardData) -> str:
    """Bitta xodim kunlik ochko — jadval ping."""
    lines = [
        "📊 <b>OCHKO JADVALI</b>",
        f"👤 {html.escape(card.employee)} · {card.day_iso}",
        "",
    ]
    tbl = [
        f"{'Manba':<14} {'Hisoblash':<16} {'Ochko':>5}",
        "─" * 38,
    ]
    n = 0
    for row in card.categories:
        if row.added <= 0:
            continue
        n += 1
        tbl.append(
            f"{row.name[:14]:<14} {str(row.today) + ' ta (1:1)':<16} {('+' + str(row.added)):>5}"
        )
    for bot in card.bots:
        if bot.key in HUB_CATEGORY_BOT_KEYS:
            continue
        if bot.score == 0 and not (bot.summary or "").strip():
            continue
        n += 1
        _, formula = explain_bot_formula(bot.key, bot.summary)
        label = BOT_LABELS.get(bot.key, bot.key)[:14]
        sign = f"+{bot.score}" if bot.score >= 0 else str(bot.score)
        tbl.append(f"{label:<14} {formula[:16]:<16} {sign:>5}")
    if not n:
        lines.append("<i>Bugun ochko yo'q</i>")
    else:
        tbl.append("─" * 38)
        tbl.append(
            f"{'JAMI':<14} {'yord+' + str(card.cat_total) + ' bot+' + str(card.bot_total):<16} "
            f"{'+' + str(card.grand_total):>5}"
        )
        lines.append(_pre_table(tbl))
    lines.extend(["", RULES_FOOTER])
    return "\n".join(lines)


async def gather_period_breakdown_rows(
    ref_date: date,
    period: str,
    *,
    employees: list[str],
    sum_period_total,
    employee_tg_map: dict[str, int],
) -> list[tuple[str, int, dict[str, int], int]]:
    """Period bo'yicha jamoa ochko qatorlari."""
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
    return rows


def build_daily_breakdown_lines(card: DailyReportCardData) -> list[dict[str, str]]:
    """Kunlik hisobot ichidagi «Манба ва ҳисоблаш» qatorlari (kirill)."""
    lines: list[dict[str, str]] = []
    mesta_bot = next((b for b in card.bots if b.key == "mesta"), None)
    inv_bot = next((b for b in card.bots if b.key == "inventarizatsiya"), None)
    for row in card.categories:
        if row.added <= 0:
            continue
        if row.name == "Места хр" and mesta_bot:
            _, formula = explain_bot_formula("mesta", mesta_bot.summary)
        elif row.name == "Пересчет товаров" and inv_bot:
            _, formula = explain_bot_formula("inventarizatsiya", inv_bot.summary)
        else:
            formula = f"{row.today} бирлик (1:1)"
        lines.append(
            {
                "source": row.name,
                "formula": formula,
                "points": f"+{row.added}",
                "points_raw": row.added,
            }
        )
    for bot in card.bots:
        if bot.key in HUB_CATEGORY_BOT_KEYS:
            continue
        if bot.score == 0 and not (bot.summary or "").strip():
            continue
        _, formula = explain_bot_formula(bot.key, bot.summary)
        label = BOT_SOURCE_CYRL.get(bot.key, BOT_LABELS.get(bot.key, bot.key))
        sign = f"+{bot.score}" if bot.score >= 0 else str(bot.score)
        lines.append(
            {
                "source": label,
                "formula": formula,
                "points": sign,
                "points_raw": bot.score,
            }
        )
    if card.adj_total:
        sign = f"+{card.adj_total}" if card.adj_total > 0 else str(card.adj_total)
        lines.append(
            {
                "source": "Қўшимча бонус",
                "formula": "админ бонус/жарима",
                "points": sign,
                "points_raw": card.adj_total,
            }
        )
    return lines


async def build_period_breakdown_html(
    ref_date: date,
    period: str,
    *,
    employees: list[str],
    sum_period_total,
    employee_tg_map: dict[str, int],
) -> list[str]:
    """Period reyting — matn fallback (ping)."""
    rows = await gather_period_breakdown_rows(
        ref_date,
        period,
        employees=employees,
        sum_period_total=sum_period_total,
        employee_tg_map=employee_tg_map,
    )

    header = (
        "📊 <b>ОЧКО ЖАДВАЛИ</b>\n"
        f"Период: {period} (2-санадан) · ҳолат: {ref_date.isoformat()}\n"
        "<i>— = 0 очко · Жами = барча устунлар йиғиндиси</i>\n"
    )
    footer = f"\n{RULES_FOOTER}"

    if not rows:
        return [header + "\n<i>Periodda ochko yo'q</i>\n\n" + footer]

    table_lines = _period_table_lines(rows)
    body = header + "\n" + _pre_table(table_lines)

    # Juda uzun bo'lsa — jadvalni bo'laklarga
    if len(body) + len(footer) <= _TG_MAX:
        return [body + footer]

    chunks: list[str] = []
    part_hdr = header + "\n"
    batch: list[str] = []
    for i, ln in enumerate(table_lines):
        if i < 2:
            batch.append(ln)
            continue
        candidate = part_hdr + _pre_table(batch + [ln])
        if len(candidate) + len(footer) > _TG_MAX and len(batch) > 2:
            chunks.append(part_hdr + _pre_table(batch) + footer)
            batch = table_lines[:2] + [ln]
        else:
            batch.append(ln)
    if batch:
        chunks.append(part_hdr + _pre_table(batch) + footer)
    return chunks or [body + footer]


def split_messages(text: str) -> list[str]:
    if len(text) <= _TG_MAX:
        return [text]
    out: list[str] = []
    while text:
        out.append(text[:_TG_MAX])
        text = text[_TG_MAX:]
    return out
