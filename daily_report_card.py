"""Kunlik yakuniy hisobot — PNG dashboard (guruhga)."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from cross_bot_hub import BOT_LABELS, fetch_latest_by_bot

W = 1280
M = 28
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

BOT_ORDER = ("omborga", "ombor", "yuk", "sklad", "ishxona")
BOT_ICONS = {
    "omborga": "🚛",
    "ombor": "🛎",
    "yuk": "📦",
    "sklad": "📁",
    "ishxona": "🏢",
}


@dataclass
class CategoryRow:
    name: str
    added: int
    today: int
    period: int
    norm: int


@dataclass
class BotRow:
    key: str
    label: str
    summary: str
    score: int
    work_display: str


@dataclass
class LeaderRow:
    rank: int
    name: str
    score: int
    work_time: str
    pct: int


@dataclass
class DailyReportCardData:
    day_iso: str
    employee: str
    period: str
    categories: list[CategoryRow] = field(default_factory=list)
    best_cat: str = ""
    best_add: int = 0
    overall_text: str = ""
    bots: list[BotRow] = field(default_factory=list)
    bot_total: int = 0
    total_work: str = "00:00:00"
    period_sum: int = 0
    rank: int = 0
    rank_total: int = 0
    leaders: list[LeaderRow] = field(default_factory=list)
    work_log: list[tuple[str, str]] = field(default_factory=list)


def _load_fonts():
    reg_paths = [
        FONT_DIR / "NotoSans-Regular.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    bold_paths = [
        FONT_DIR / "NotoSans-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ]
    reg = next((p for p in reg_paths if p.is_file()), None)
    bold = next((p for p in bold_paths if p.is_file()), None)
    if not reg or not bold:
        d = ImageFont.load_default()
        return d, d, d, d
    return (
        ImageFont.truetype(str(bold), 28),
        ImageFont.truetype(str(bold), 22),
        ImageFont.truetype(str(reg), 17),
        ImageFont.truetype(str(reg), 14),
    )


def _truncate(text: str, n: int = 42) -> str:
    t = str(text or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _parse_hms(text: str) -> int:
    """Matndan vaqtni soniyaga."""
    text = text.lower()
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        s = int(m.group(3) or 0)
        return h * 3600 + mi * 60 + s
    m = re.search(r"(\d+)\s*soniya", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*daqiqa", text)
    if m:
        return int(m.group(1)) * 60
    m = re.search(r"(\d+)\s*min", text)
    if m:
        return int(m.group(1)) * 60
    return 0


def _fmt_hms(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fmt_short(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def score_bot_summary(key: str, summary: str) -> tuple[int, int]:
    """(ochko, ish_vaqti_soniya)."""
    s = summary or ""
    sl = s.lower()
    if key == "omborga":
        reys = 0
        m = re.search(r"reys\s*(\d+)", sl)
        if m:
            reys = int(m.group(1))
        ish = _parse_hms(s)
        mins = ish // 60
        return reys * 3 + max(0, mins // 2), ish
    if key == "ombor":
        sec = _parse_hms(s)
        if not sec:
            m = re.search(r"(\d+)\s*son", sl)
            if m:
                sec = int(m.group(1))
        return max(0, sec // 3), sec
    if key == "yuk":
        sec = _parse_hms(s)
        return max(0, sec // 120), sec
    if key == "sklad":
        m = re.search(r"sanaldi\s*(\d+)", sl)
        n = int(m.group(1)) if m else 0
        return n * 5, 0
    if key == "ishxona":
        return 0, 0
    return 0, 0


def _bot_work_display(key: str, summary: str, work_sec: int) -> str:
    s = summary or ""
    if key == "omborga":
        reys = re.search(r"reys\s*(\d+)", s.lower())
        r = reys.group(1) if reys else "0"
        return f"Reys {r} · ish {_fmt_short(work_sec)}"
    if key == "ombor":
        return f"Xizmat · {_fmt_short(work_sec)}"
    if key == "yuk":
        return f"Yuk · ish {_fmt_short(work_sec)}"
    if key == "sklad":
        return _truncate(s, 36)
    if key == "ishxona":
        return _truncate(s, 36)
    return _truncate(s, 36)


async def build_card_data(
    *,
    employee: str,
    day_iso: str,
    period: str,
    yday_iso: str,
    session_agg: dict[str, int],
    categories: list[str],
    tg_id: int,
    best_cat: str,
    best_add: int,
    overall_text: str,
    employees: list[str],
    sum_day: Callable[..., Awaitable[int]],
    sum_period: Callable[..., Awaitable[int]],
    get_plan: Callable[..., Awaitable[int | None]],
    sum_day_total: Callable[..., Awaitable[int]],
    employee_tg_map: dict[str, int],
) -> DailyReportCardData:
    data = DailyReportCardData(
        day_iso=day_iso,
        employee=employee,
        period=period,
        best_cat=best_cat,
        best_add=best_add,
        overall_text=overall_text,
    )

    period_sum = 0
    for cat in categories:
        if cat not in session_agg:
            continue
        added = int(session_agg[cat])
        today = await sum_day(day_iso, employee, cat)
        per = await sum_period(period, employee, cat)
        plan = await get_plan(period, employee, cat)
        norm = int(plan) if plan else today
        period_sum += per
        data.categories.append(
            CategoryRow(name=cat, added=added, today=today, period=per, norm=norm)
        )

    events = await fetch_latest_by_bot(tg_id, day_iso) if tg_id else {}
    total_work_sec = 0
    for key in BOT_ORDER:
        summary = events.get(key, "")
        score, wsec = score_bot_summary(key, summary)
        total_work_sec += wsec
        data.bots.append(
            BotRow(
                key=key,
                label=BOT_LABELS.get(key, key),
                summary=summary,
                score=score,
                work_display=_bot_work_display(key, summary, wsec) if summary else "—",
            )
        )
        if summary:
            data.work_log.append((BOT_LABELS.get(key, key), _fmt_short(wsec) if wsec else "—"))
        data.bot_total += score

    data.total_work = _fmt_hms(total_work_sec)
    data.period_sum = period_sum

    # Reyting — bugun jami (kategoriya + bot ochko)
    scores: list[tuple[str, int, int]] = []
    for emp in employees:
        cat_pts = await sum_day_total(day_iso, emp)
        bot_pts = 0
        work_sec = 0
        etg = employee_tg_map.get(emp)
        if etg:
            ev = await fetch_latest_by_bot(etg, day_iso)
            for k in BOT_ORDER:
                if k in ev:
                    sc, ws = score_bot_summary(k, ev[k])
                    bot_pts += sc
                    work_sec += ws
        total = cat_pts + bot_pts
        if total > 0 or emp == employee:
            scores.append((emp, total, work_sec))

    scores.sort(key=lambda x: (-x[1], x[0]))
    max_sc = max((s[1] for s in scores), default=1) or 1
    for i, (name, pts, wsec) in enumerate(scores[:9], 1):
        pct = int(100 * pts / max_sc) if max_sc else 0
        data.leaders.append(
            LeaderRow(rank=i, name=name, score=pts, work_time=_fmt_short(wsec), pct=pct)
        )
        if name == employee:
            data.rank = i
    data.rank_total = len([s for s in scores if s[1] > 0]) or len(scores)

    return data


def _card_height(data: DailyReportCardData) -> int:
    cat_h = max(4, len(data.categories)) * 34 + 120
    bot_h = len(BOT_ORDER) * 52 + 80
    lead_h = max(5, len(data.leaders)) * 30 + 100
    return 200 + cat_h + bot_h + lead_h + 80


def render_daily_report_png(data: DailyReportCardData, avatar: bytes | None = None) -> bytes:
    f_title, f_head, f_main, f_small = _load_fonts()
    H = _card_height(data)
    bg = (10, 18, 42)
    panel = (16, 28, 58)
    header = (0, 160, 185)
    accent = (0, 220, 190)
    gold = (255, 200, 80)
    white = (245, 248, 255)
    muted = (140, 155, 185)
    green = (80, 230, 150)
    orange = (255, 160, 60)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((M, M, W - M, H - M), radius=16, outline=header, width=2)

    # Header
    hy = M + 72
    draw.rounded_rectangle((M + 4, M + 4, W - M - 4, hy), radius=12, fill=header)
    draw.text((M + 20, M + 14), "КУНЛИК ҲИСОБОТ (ЯКУН)", fill=white, font=f_title)
    draw.text((M + 20, M + 46), f"📅 {data.day_iso}   👤 {data.employee}", fill=white, font=f_small)
    draw.text((M + 20, M + 64), f"🗓 Период: {data.period}", fill=(220, 240, 255), font=f_small)

    if avatar:
        try:
            av = Image.open(BytesIO(avatar)).convert("RGB")
            av = av.resize((56, 56))
            mask = Image.new("L", (56, 56), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 56, 56), fill=255)
            img.paste(av, (W - M - 70, M + 8), mask)
        except Exception:
            pass

    y = hy + 16

    # Left: categories
    lx, rx = M + 12, W // 2 + 20
    draw.text((lx, y), "📊 ФАОЛИЯТ ВА КЪРСАТКИЧЛАР", fill=accent, font=f_head)
    y += 32
    cols = ("ФАОЛИЯТ", "ОЧКО", "БУГУН", "ПЕРИОД", "НОРМА")
    cx = [lx, lx + 280, lx + 340, lx + 400, lx + 470]
    for i, c in enumerate(cols):
        draw.text((cx[i], y), c, fill=muted, font=f_small)
    y += 22
    draw.line((lx, y, rx - 20, y), fill=(40, 60, 100), width=1)
    y += 8

    for row in data.categories:
        draw.text((cx[0], y), _truncate(row.name, 22), fill=white, font=f_small)
        draw.text((cx[1], y), f"+{row.added}", fill=green, font=f_small)
        draw.text((cx[2], y), str(row.today), fill=white, font=f_small)
        draw.text((cx[3], y), str(row.period), fill=white, font=f_small)
        draw.text((cx[4], y), str(row.norm), fill=muted, font=f_small)
        y += 28

    y += 8
    draw.text((lx, y), f"⭐ {data.best_cat} (+{data.best_add})", fill=gold, font=f_small)
    y += 20
    draw.text((lx, y), f"🔥 { _truncate(data.overall_text, 55)}", fill=orange, font=f_small)

    # Right top: score box
    sx = W - M - 200
    sy = hy + 16
    draw.rounded_rectangle((sx, sy, W - M - 12, sy + 130), radius=10, fill=panel, outline=accent, width=1)
    draw.text((sx + 12, sy + 8), "ЖАМИ ОЧКО", fill=muted, font=f_small)
    draw.text((sx + 12, sy + 28), f"+{data.bot_total}", fill=green, font=f_title)
    draw.text((sx + 12, sy + 68), "БУГУН", fill=accent, font=f_head)
    draw.text((sx + 12, sy + 96), f"⏱ {data.total_work}", fill=white, font=f_small)
    if data.rank:
        draw.text((sx + 100, sy + 96), f"🏆 {data.rank}/{data.rank_total}", fill=gold, font=f_small)

    # Middle: scoring info
    mx = lx + 320
    my = hy + 16
    draw.rounded_rectangle((mx, my, sx - 16, my + 130), radius=10, fill=panel, outline=(50, 80, 120), width=1)
    draw.text((mx + 10, my + 8), "ОЧКО ҲИСОБЛАШ", fill=accent, font=f_small)
    rules = [
        "• To'liq va sifatli ish — +5",
        "• TSD faol — +6",
        "• Xato/kamchilik — minus",
        "• Boshqa botlar — vaqt/reys",
    ]
    for i, r in enumerate(rules):
        draw.text((mx + 10, my + 28 + i * 22), r, fill=muted, font=f_small)

    # Other bots
    y = max(y + 40, hy + 170)
    draw.text((lx, y), "🤖 БОШҚА БОТЛАР (БУГУН)", fill=accent, font=f_head)
    y += 34
    for bot in data.bots:
        draw.rounded_rectangle((lx, y, W - M - 12, y + 44), radius=8, fill=panel, outline=(35, 55, 90), width=1)
        icon = BOT_ICONS.get(bot.key, "•")
        draw.text((lx + 12, y + 12), icon, fill=white, font=f_main)
        draw.text((lx + 44, y + 6), bot.label.upper(), fill=accent, font=f_small)
        draw.text((lx + 44, y + 24), bot.work_display if bot.summary else "event yo'q", fill=muted, font=f_small)
        sc = f"+{bot.score}" if bot.score else "+0"
        draw.text((W - M - 60, y + 14), sc, fill=green if bot.score else muted, font=f_head)
        y += 50

    draw.text((lx, y), f"📌 JAMI BOSHQ BOTLARDAN: +{data.bot_total}", fill=gold, font=f_head)
    y += 36

    # Bottom: leaderboard + work log
    half = (W - 2 * M - 24) // 2
    draw.text((lx, y), "📈 КУНЛИК РЕЙТИНГ", fill=accent, font=f_head)
    draw.text((lx + half + 24, y), "✅ БАЖАРИЛГАН ИШЛАР", fill=accent, font=f_head)
    y += 28
    ly = y
    for lead in data.leaders:
        medal = "🥇" if lead.rank == 1 else "🥈" if lead.rank == 2 else "🥉" if lead.rank == 3 else f"{lead.rank}."
        name_col = gold if lead.name == data.employee else white
        draw.text((lx, ly), f"{medal} {_truncate(lead.name, 18)}", fill=name_col, font=f_small)
        draw.text((lx + 200, ly), f"+{lead.score}", fill=green, font=f_small)
        draw.text((lx + 250, ly), lead.work_time, fill=muted, font=f_small)
        draw.text((lx + 310, ly), f"{lead.pct}%", fill=orange if lead.pct >= 80 else muted, font=f_small)
        ly += 26

    wy = y
    for label, wt in data.work_log[:6]:
        draw.text((lx + half + 24, wy), f"• {label}: {wt}", fill=white, font=f_small)
        wy += 24

    buf = BytesIO()
    img.save(buf, format="PNG", compress_level=2)
    return buf.getvalue()
