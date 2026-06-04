"""Bonus / jarima — premium HTML→PNG kartochka."""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import date
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFont

from daily_report_card import FONT_DIR, GOLD, GREEN, WHITE, _load_fonts, _truncate
from report_html import _image_mime, _logo_b64

log = logging.getLogger(__name__)

ASSETS = Path(__file__).resolve().parent / "assets" / "report"
CARD_W, CARD_H = 1080, 1350


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ASSETS)),
        autoescape=select_autoescape(["html"]),
    )


_UZ_MONTHS = (
    "",
    "январ",
    "феврал",
    "март",
    "апрел",
    "май",
    "июн",
    "июл",
    "август",
    "сентябр",
    "октябр",
    "ноябр",
    "декабр",
)

_UZ_WEEKDAYS = (
    "душанба",
    "сешанба",
    "чорашанба",
    "пайшанба",
    "жума",
    "шанба",
    "якшанба",
)


def format_day_display(day_iso: str) -> tuple[str, str]:
    """(katta sana, hafta kuni) — masalan 04.06.2026, чорашанба."""
    d = date.fromisoformat(day_iso)
    main = f"{d.day:02d}.{_UZ_MONTHS[d.month]}.{d.year}"
    wd = _UZ_WEEKDAYS[d.weekday()]
    return main, wd


def _initials(employee: str) -> str:
    parts = (employee or "").strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return "?"


def build_adj_card_html(
    *,
    kind: str,
    employee: str,
    points: int,
    period: str,
    day_iso: str,
    avatar: bytes | None = None,
) -> str:
    is_bonus = kind == "bonus"
    sign = "+" if is_bonus else "−"
    avatar_b64 = base64.b64encode(avatar).decode("ascii") if avatar else ""
    avatar_mime = _image_mime(avatar) if avatar else ""
    day_main, day_weekday = format_day_display(day_iso)
    if is_bonus:
        extra_line = f"Қўшимча бонус: {sign}{points} очко (рейтинг)"
        extra_class = "extra-bonus"
    else:
        extra_line = f"Жарима: {sign}{points} очко (рейтинг)"
        extra_class = "extra-penalty"

    ctx = {
        "css": (ASSETS / "adj_card.css").read_text(encoding="utf-8"),
        "kind_class": "bonus" if is_bonus else "penalty",
        "is_bonus": is_bonus,
        "logo_b64": _logo_b64(),
        "ribbon_title": "ТАНТАНАВИЙ БОНУС" if is_bonus else "ЖАРИМА ОЧКО",
        "ribbon_sub": "Рейтинг жадвалида кўтарилди" if is_bonus else "Рейтингдан айирилди",
        "employee": employee,
        "initials": _initials(employee),
        "avatar_b64": avatar_b64,
        "avatar_mime": avatar_mime,
        "score_display": f"{sign}{points}",
        "score_label": "БОНУС ОЧКО" if is_bonus else "ЖАРИМА",
        "day_main": day_main,
        "day_weekday": day_weekday,
        "extra_line": extra_line,
        "extra_class": extra_class,
        "footer_quote": (
            "Жамоа фахрланади! Чемпионлик йўли — очиқ!"
            if is_bonus
            else "Диққат: қайта такрорланмасин — жамоа сиздан яхшироқни кутмоқда."
        ),
        "stars_line": "★ ★ ★ ★ ★" if is_bonus else "⚠ ⚠ ⚠",
    }
    return _env().get_template("adj_card.html").render(**ctx)


async def _html_to_card_png(html: str) -> bytes:
    from report_png import _ensure_playwright, html_to_png

    if not await _ensure_playwright():
        raise RuntimeError("playwright yo'q")
    return await html_to_png(
        html,
        width=CARD_W,
        height=CARD_H,
        min_height=CARD_H,
        page_selector=".page",
    )


def _render_pil_fallback(
    *,
    kind: str,
    employee: str,
    points: int,
    period: str,
    day_iso: str,
    avatar: bytes | None,
) -> bytes:
    """Playwright bo'lmasa — soddaroq PIL."""
    is_bonus = kind == "bonus"
    W, H = CARD_W, CARD_H
    img = Image.new("RGB", (W, H), (8, 14, 32) if is_bonus else (24, 8, 12))
    draw = ImageDraw.Draw(img)
    f_title, _, _, f_bold, f_body, _ = _load_fonts()
    draw.rounded_rectangle((24, 24, W - 24, H - 24), radius=24, outline=GOLD if is_bonus else (200, 70, 80), width=4)
    draw.text((W // 2 - 120, 80), "BONUS" if is_bonus else "JARIMA", fill=WHITE, font=f_title)
    initials = _initials(employee)
    cx, cy, sz = W // 2, 320, 200
    draw.ellipse((cx - sz // 2, cy - sz // 2, cx + sz // 2, cy + sz // 2), fill=(20, 80, 100) if is_bonus else (80, 30, 40))
    if avatar:
        try:
            av = Image.open(BytesIO(avatar)).convert("RGB").resize((sz, sz))
            mask = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, sz, sz), fill=255)
            img.paste(av, (cx - sz // 2, cy - sz // 2), mask)
        except Exception:
            draw.text((cx - 40, cy - 30), initials, fill=WHITE, font=f_title)
    else:
        draw.text((cx - 40, cy - 30), initials, fill=WHITE, font=f_title)
    tw = draw.textlength(employee, font=f_bold)
    draw.text(((W - tw) / 2, 460), employee, fill=WHITE, font=f_bold)
    sign = "+" if is_bonus else "-"
    sc = f"{sign}{points}"
    draw.text(((W - 80) / 2, 520), sc, fill=GREEN if is_bonus else (255, 100, 110), font=f_title)
    day_main, day_wd = format_day_display(day_iso)
    draw.text((80, 660), "BUGUN", fill=WHITE, font=f_body)
    draw.text((80, 690), day_main, fill=WHITE, font=f_bold)
    draw.text((80, 720), day_wd, fill=WHITE, font=f_body)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def render_adj_card_png(
    *,
    kind: str,
    employee: str,
    points: int,
    period: str,
    day_iso: str,
    avatar: bytes | None = None,
) -> bytes:
    html = build_adj_card_html(
        kind=kind,
        employee=employee,
        points=points,
        period=period,
        day_iso=day_iso,
        avatar=avatar,
    )
    try:
        return await _html_to_card_png(html)
    except Exception as e:
        log.warning("Adj card HTML→PNG, PIL fallback: %s", e)
        return await asyncio.to_thread(
            _render_pil_fallback,
            kind=kind,
            employee=employee,
            points=points,
            period=period,
            day_iso=day_iso,
            avatar=avatar,
        )
