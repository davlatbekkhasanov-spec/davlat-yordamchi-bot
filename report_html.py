"""HTML hisobot — korporativ A4."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cross_bot_hub import BOT_LABELS
from daily_report_card import DailyReportCardData

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


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ASSETS)),
        autoescape=select_autoescape(["html"]),
    )


def _css_text() -> str:
    return (ASSETS / "report.css").read_text(encoding="utf-8")


def _image_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"GIF":
        return "image/gif"
    return "image/jpeg"


def _format_bot_body(key: str, summary: str, metrics: list[tuple[str, str]]) -> str:
    if summary and summary.strip():
        return summary.strip()
    if not metrics:
        return "Ma'lumot yo'q"
    parts = []
    for label, value in metrics:
        parts.append(f"{label}: {value}")
    return ", ".join(parts)


def _format_omborga_body(summary: str) -> str:
    if not summary:
        return "Ma'lumot yo'q"
    sl = summary.lower()
    reys = re.search(r"reys\s*(\d+)", sl)
    yuk = re.search(r"yuk\s*(\d+)", sl)
    ish = re.search(r"ish\s+([\d:]+)", sl)
    dam = re.search(r"dam\s+([\d:]+)", sl)
    bits = []
    if reys:
        bits.append(f"Reys: {reys.group(1)}")
    if yuk:
        bits.append(f"yuk {yuk.group(1)}m")
    if ish:
        bits.append(f"ish {ish.group(1)}")
    if dam:
        bits.append(f"dam {dam.group(1)}")
    return ", ".join(bits) if bits else summary


def build_report_html(data: DailyReportCardData, avatar: bytes | None = None) -> str:
    avatar_b64 = base64.b64encode(avatar).decode("ascii") if avatar else None
    avatar_mime = _image_mime(avatar) if avatar else "image/jpeg"

    bots = []
    for bot in data.bots:
        title = BOT_TITLES.get(bot.key, BOT_LABELS.get(bot.key, bot.label).upper())
        if bot.key == "omborga":
            body = _format_omborga_body(bot.summary)
        else:
            body = _format_bot_body(bot.key, bot.summary, bot.metrics)
        bots.append(
            {
                "title": title,
                "icon": BOT_ICONS.get(bot.key, "📌"),
                "body": body,
            }
        )

    ctx = {
        "css": _css_text(),
        "day_iso": data.day_iso,
        "employee": data.employee,
        "period": data.period,
        "categories": data.categories,
        "best_cat": data.best_cat,
        "best_add": data.best_add,
        "overall_text": data.overall_text,
        "summary_text": data.summary_text,
        "recommendation_text": data.recommendation_text,
        "work_ish_time": data.work_ish_time,
        "work_dam_time": data.work_dam_time,
        "footer_date": data.footer_date,
        "bots": bots,
        "avatar_b64": avatar_b64,
        "avatar_mime": avatar_mime,
    }

    return _env().get_template("report.html").render(**ctx)
