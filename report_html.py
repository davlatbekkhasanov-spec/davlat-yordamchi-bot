"""HTML hisobot (referens dizayn)."""

from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cross_bot_hub import BOT_LABELS
from daily_report_card import DailyReportCardData

ASSETS = Path(__file__).resolve().parent / "assets" / "report"

METRIC_LABELS = {
    "reys": "Reys",
    "ish vaqti": "Ish",
    "ish": "Ish",
    "dam": "Dam",
    "jami vaqt": "Jami vaqt",
    "son": "Son",
    "holat": "Holat",
    "ma'lumot": "Ma'lumot",
    "shikoyat": "Shikoyat",
    "info": "Info",
}

BOT_TITLES = {
    "omborga": "Омборга киритиш",
    "ombor": "Омбор хизмат",
    "yuk": "Юк жараёни",
    "sklad": "Склад nazorat",
    "ishxona": "Ишxona nazorat",
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


def build_report_html(data: DailyReportCardData, avatar: bytes | None = None) -> str:
    avatar_b64 = base64.b64encode(avatar).decode("ascii") if avatar else None
    avatar_mime = _image_mime(avatar) if avatar else "image/jpeg"

    bots = []
    for bot in data.bots:
        title = BOT_TITLES.get(bot.key, BOT_LABELS.get(bot.key, bot.label))
        metrics = [(METRIC_LABELS.get(k, k), v) for k, v in bot.metrics]
        bots.append({"title": title, "metrics": metrics, "score": bot.score})

    leaders = []
    for lead in data.leaders:
        leaders.append(
            {
                "rank": lead.rank,
                "name": lead.name,
                "score": lead.score,
                "work_time": lead.work_time or "00:00",
                "pct": lead.pct,
                "is_self": lead.name == data.employee,
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
        "cat_total": data.cat_total,
        "bot_total": data.bot_total,
        "grand_total": data.grand_total,
        "total_work": data.total_work,
        "period_sum": data.period_sum,
        "rank": data.rank,
        "rank_total": data.rank_total,
        "bots": bots,
        "leaders": leaders,
        "work_log": data.work_log,
        "avatar_b64": avatar_b64,
        "avatar_mime": avatar_mime,
    }

    return _env().get_template("report.html").render(**ctx)
