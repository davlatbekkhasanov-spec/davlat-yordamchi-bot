"""HTML hisobot — korporativ A4."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cross_bot_hub import BOT_LABELS
from daily_report_card import DailyReportCardData, HUB_CATEGORY_BOT_KEYS
from points_breakdown import build_daily_breakdown_lines
from report_format import fmt_debt_min, fmt_points
from time_display import fmt_duration, parse_duration_text

ASSETS = Path(__file__).resolve().parent / "assets" / "report"

BOT_TITLES = {
    "omborga": "ОМБОРГА КИРИТИШ",
    "ombor": "ОМБОР ХИЗМАТ",
    "yuk": "ЮК ЖАРАЁНИ",
    "sklad": "СКЛАД НАЗОРАТ",
    "mesta": "МЕСТА ХР",
    "inventarizatsiya": "ПЕРЕСЧЕТ ТОВАРОВ",
    "navbatchi": "НАВБАТЧИЛИК",
    "ishxona": "ИШХОНА НАЗОРАТ",
    "faceid": "FACE ID DAVOMAT",
}

BOT_ICONS = {
    "omborga": "🚛",
    "ombor": "📦",
    "yuk": "🛒",
    "sklad": "📋",
    "ishxona": "🔧",
    "faceid": "🆔",
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


def _format_hub_time_body(summary: str, *, count_label: str | None = None) -> tuple[str, bool]:
    if not summary or not summary.strip():
        return EMPTY_BOT, True
    sl = summary.lower()
    if "event yo'q" in sl or "faoliyat yo'q" in sl:
        return EMPTY_BOT, True
    sec = parse_duration_text(summary)
    bits: list[str] = []
    if count_label:
        cnt = re.search(r"(\d+)\s*ta", sl)
        if cnt:
            bits.append(f"{cnt.group(1)} {count_label}")
    if sec > 0:
        bits.append(f"Иш: {fmt_duration(sec)}")
    if bits:
        return " · ".join(bits), False
    return summary.strip(), False


def _format_faceid_body(summary: str, metrics: list[tuple[str, str]]) -> tuple[str, bool]:
    if not summary or not summary.strip():
        return EMPTY_BOT, True
    sl = summary.lower()
    keldi = re.search(r"keldi\s*[=:]?\s*([\d:]+)", sl)
    ketdi = re.search(r"ketdi\s*[=:]?\s*([\d:]+)", sl)
    ish_daq = re.search(r"ish_daq\s*[=:]?\s*(\d+)", sl)
    bits: list[str] = []
    if keldi:
        bits.append(f"Келди: {keldi.group(1)}")
    if ketdi and ketdi.group(1) not in ("—", "-"):
        bits.append(f"Кетди: {ketdi.group(1)}")
    if ish_daq:
        bits.append(f"Иш: {ish_daq.group(1)} daq")
    if bits:
        return " · ".join(bits), False
    if metrics:
        parts = [f"{_metric_label(k)}: {v}" for k, v in metrics if _metric_value_ok(v)]
        if parts:
            return ", ".join(parts), False
    return summary.strip(), False


def _format_bot_body(
    summary: str, metrics: list[tuple[str, str]], *, bot_key: str = ""
) -> tuple[str, bool]:
    if bot_key == "faceid":
        body, empty = _format_faceid_body(summary, metrics)
        if not empty:
            return body, False
    if bot_key == "yuk":
        body, empty = _format_hub_time_body(summary)
        if not empty:
            return body, False
    if bot_key == "ombor":
        body, empty = _format_hub_time_body(summary, count_label="та")
        if not empty:
            return body, False
    if summary and summary.strip() and "event yo'q" not in summary.lower():
        sl = summary.lower()
        if "ish vaqti" in sl and re.search(r"\d+\s*soniya", sl):
            body, empty = _format_hub_time_body(summary)
            if not empty:
                return body, False
        return summary.strip(), False
    if metrics:
        parts = [f"{_metric_label(k)}: {v}" for k, v in metrics if _metric_value_ok(v)]
        if parts:
            return ", ".join(parts), False
    return EMPTY_BOT, True


def _report_density(row_count: int, breakdown_count: int = 0) -> str:
    if breakdown_count > 7 or row_count > 10:
        return "dense"
    if breakdown_count > 4 or row_count > 6:
        return "compact"
    return "normal"


def build_report_html(data: DailyReportCardData, avatar: bytes | None = None) -> str:
    avatar_b64 = base64.b64encode(avatar).decode("ascii") if avatar else None
    avatar_mime = _image_mime(avatar) if avatar else "image/jpeg"

    bots = []
    for bot in data.bots:
        title = BOT_TITLES.get(bot.key, BOT_LABELS.get(bot.key, bot.label).upper())
        if bot.key == "omborga":
            body, empty = _format_omborga_body(bot.summary)
        else:
            body, empty = _format_bot_body(bot.summary, bot.metrics, bot_key=bot.key)
        hub_only = bot.key in HUB_CATEGORY_BOT_KEYS
        card_score = 0 if hub_only else bot.score
        score_text = ""
        if not hub_only and card_score:
            score_text = fmt_points(card_score)["text"]
        bots.append(
            {
                "title": title,
                "icon": BOT_ICONS.get(bot.key, "📌"),
                "body": body,
                "empty": empty,
                "score": card_score,
                "score_fmt": fmt_points(card_score),
                "score_text": score_text,
            }
        )

    breakdown_lines = build_daily_breakdown_lines(data)
    for row in breakdown_lines:
        pts = fmt_points(int(row.get("points_raw", 0)))
        row["points"] = pts["text"]
        row["points_cls"] = pts["cls"]

    row_count = len(data.categories)
    compare_count = len(data.compare_rows or [])
    density = _report_density(row_count, len(breakdown_lines) + compare_count)

    face = data.face
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
        "weak_cat": data.weak_cat,
        "weak_add": data.weak_add,
        "compare_rows": data.compare_rows,
        "rank": data.rank,
        "rank_total": data.rank_total,
        "face": face,
        "face_keldi": face.keldi if face.has_frame else "—",
        "face_ketdi": face.ketdi if face.has_frame else "—",
        "face_active_work": face.active_work if face.active_min > 0 else data.total_work,
        "face_qarz_today": fmt_debt_min(face.qarz_today_min),
        "face_qarz_yesterday": fmt_debt_min(face.qarz_yesterday_min),
        "face_qarz_month": fmt_debt_min(face.qarz_month_min),
        "face_ball": fmt_points(face.ball),
        "work_ish_time": data.work_ish_time or "—",
        "work_dam_time": data.work_dam_time or "—",
        "footer_date": data.footer_date,
        "grand_total": fmt_points(data.grand_total),
        "cat_total": fmt_points(data.cat_total),
        "bot_total": fmt_points(data.bot_total),
        "total_work": data.total_work,
        "period_sum": data.period_sum,
        "overall_text": data.overall_text,
        "summary_text": data.summary_text,
        "recommendation_text": data.recommendation_text,
        "bots": bots,
        "breakdown_lines": breakdown_lines,
        "avatar_b64": avatar_b64,
        "avatar_mime": avatar_mime,
        "logo_b64": _logo_b64(),
    }

    return _env().get_template("report.html").render(**ctx)
