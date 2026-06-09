"""HTML hisobot — korporativ A4."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cross_bot_hub import BOT_LABELS
from daily_report_card import DailyReportCardData
from points_breakdown import build_daily_breakdown_lines

ASSETS = Path(__file__).resolve().parent / "assets" / "report"

BOT_TITLES = {
    "omborga": "ОМБОРГА КИРИТИШ",
    "ombor": "ОМБОР ХИЗМАТ",
    "yuk": "ЮК ЖАРАЁНИ",
    "sklad": "СКЛАД НАЗОРАТ",
    "ishxona": "ИШХОНА НАЗОРАТ",
}

BOT_ICONS = {
    "omborga": "🚛",
    "ombor": "📦",
    "yuk": "🛒",
    "sklad": "📋",
    "ishxona": "🔧",
}

EMPTY_BOT = "—"

METRIC_LABELS = {
    "holat": "Ҳолат",
    "reys": "Рейс",
    "ish vaqti": "Иш вақти",
    "jami vaqt": "Жами вақт",
    "dam": "Дам",
    "son": "Сония",
    "ma'lumot": "Маълумот",
    "shikoyat": "Шикоят",
    "info": "Маълумот",
}


def _metric_label(key: str) -> str:
    return METRIC_LABELS.get(key.lower(), key)


def _metric_value_ok(value: str) -> bool:
    v = (value or "").strip()
    if not v or v in ("—", "-", "–"):
        return False
    low = v.lower()
    if "event yo'q" in low or "faoliyat yo'q" in low:
        return False
    return True


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ASSETS)),
        autoescape=select_autoescape(["html"]),
    )


def _css_text() -> str:
    return (ASSETS / "report.css").read_text(encoding="utf-8")


def _logo_b64() -> str:
    svg = (ASSETS / "kanstik-logo.svg").read_bytes()
    return base64.b64encode(svg).decode("ascii")


def _image_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"GIF":
        return "image/gif"
    return "image/jpeg"


def _format_omborga_body(summary: str) -> tuple[str, bool]:
    from daily_report_card import _fmt_work_duration, _parse_omborga_time

    if not summary or not summary.strip():
        return EMPTY_BOT, True
    sl = summary.lower()
    reys = re.search(r"reys\s*(\d+)", sl)
    yuk = re.search(r"yuk\s*(\d+)", sl)
    ish = re.search(r"ish\s+([\d:]+)", sl)
    dam = re.search(r"dam\s+([\d:]+)", sl)
    bits = []
    if reys:
        bits.append(f"Рейс: {reys.group(1)}")
    if yuk:
        bits.append(f"Юк: {yuk.group(1)} м")
    if ish:
        bits.append(f"Иш: {_fmt_work_duration(_parse_omborga_time(ish.group(1)))}")
    if dam:
        bits.append(f"Дам: {_fmt_work_duration(_parse_omborga_time(dam.group(1)))}")
    if bits:
        return " · ".join(bits), False
    return summary.strip(), False


def _format_bot_body(summary: str, metrics: list[tuple[str, str]]) -> tuple[str, bool]:
    if summary and summary.strip() and "event yo'q" not in summary.lower():
        return summary.strip(), False
    if metrics:
        parts = [f"{_metric_label(k)}: {v}" for k, v in metrics if _metric_value_ok(v)]
        if parts:
            return ", ".join(parts), False
    return EMPTY_BOT, True


def _report_density(row_count: int) -> str:
    if row_count <= 6:
        return "normal"
    if row_count <= 10:
        return "compact"
    return "dense"


def build_report_html(data: DailyReportCardData, avatar: bytes | None = None) -> str:
    avatar_b64 = base64.b64encode(avatar).decode("ascii") if avatar else None
    avatar_mime = _image_mime(avatar) if avatar else "image/jpeg"

    bots = []
    for bot in data.bots:
        title = BOT_TITLES.get(bot.key, BOT_LABELS.get(bot.key, bot.label).upper())
        if bot.key == "omborga":
            body, empty = _format_omborga_body(bot.summary)
        else:
            body, empty = _format_bot_body(bot.summary, bot.metrics)
        bots.append(
            {
                "title": title,
                "icon": BOT_ICONS.get(bot.key, "📌"),
                "body": body,
                "empty": empty,
                "score": bot.score,
                "score_text": (
                    f"+{bot.score}" if bot.score > 0 else (str(bot.score) if bot.score else "")
                ),
            }
        )

    breakdown_lines = build_daily_breakdown_lines(data)

    row_count = len(data.categories)
    density = _report_density(row_count)

    ctx = {
        "css": _css_text(),
        "density": density,
        "row_count": row_count,
        "day_iso": data.day_iso,
        "employee": data.employee,
        "period": data.period,
        "categories": data.categories,
        "best_cat": data.best_cat,
        "best_add": data.best_add,
        "overall_text": data.overall_text,
        "summary_text": data.summary_text,
        "recommendation_text": data.recommendation_text,
        "work_ish_time": data.work_ish_time or "—",
        "work_dam_time": data.work_dam_time or "—",
        "footer_date": data.footer_date,
        "grand_total": data.grand_total,
        "cat_total": data.cat_total,
        "bot_total": data.bot_total,
        "total_work": data.total_work,
        "bots": bots,
        "breakdown_lines": breakdown_lines,
        "avatar_b64": avatar_b64,
        "avatar_mime": avatar_mime,
        "logo_b64": _logo_b64(),
    }

    return _env().get_template("report.html").render(**ctx)
