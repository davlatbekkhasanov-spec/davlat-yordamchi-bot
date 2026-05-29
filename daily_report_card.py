"""Kunlik yakuniy hisobot — premium PNG dashboard."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cross_bot_hub import BOT_LABELS, fetch_latest_by_bot

SCALE = 2
W = 740 * SCALE
M = 22 * SCALE
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

BOT_ORDER = ("omborga", "ombor", "yuk", "sklad", "ishxona")
BOT_BADGE = {
    "omborga": ("OM", (0, 180, 220)),
    "ombor": ("OX", (255, 140, 60)),
    "yuk": ("YJ", (120, 200, 90)),
    "sklad": ("SN", (170, 120, 255)),
    "ishxona": ("IN", (255, 90, 120)),
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
    line1: str
    line2: str


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
    cat_total: int = 0
    bot_total: int = 0
    grand_total: int = 0
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
    s = SCALE
    if not reg or not bold:
        d = ImageFont.load_default()
        return d, d, d, d, d
    return (
        ImageFont.truetype(str(bold), 34 * s),
        ImageFont.truetype(str(bold), 22 * s),
        ImageFont.truetype(str(bold), 18 * s),
        ImageFont.truetype(str(reg), 16 * s),
        ImageFont.truetype(str(reg), 13 * s),
    )


def _truncate(text: str, n: int = 38) -> str:
    t = str(text or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _parse_hms(text: str) -> int:
    text = (text or "").lower()
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3) or 0)
    m = re.search(r"(\d+)\s*soniya", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*daqiqa", text)
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
    s = summary or ""
    sl = s.lower()
    if key == "omborga":
        reys = int(re.search(r"reys\s*(\d+)", sl).group(1)) if re.search(r"reys\s*(\d+)", sl) else 0
        ish = _parse_hms(s)
        if "ish" in sl:
            m = re.search(r"ish\s+([\d:]+)", sl)
            if m:
                ish = _parse_hms(m.group(1))
        mins = max(1, ish // 60) if ish else 0
        dam_m = re.search(r"dam\s+([\d:]+)", sl)
        total_sec = ish + (_parse_hms(dam_m.group(1)) if dam_m else 0)
        return reys * 3 + mins // 2, total_sec
    if key == "ombor":
        sec = _parse_hms(s)
        if not sec and re.search(r"(\d+)\s*son", sl):
            sec = int(re.search(r"(\d+)\s*son", sl).group(1))
        return max(0, sec // 2 + 1), sec
    if key == "yuk":
        sec = _parse_hms(s)
        return max(0, sec // 130 + 1), sec
    if key == "sklad":
        n = int(re.search(r"sanaldi\s*(\d+)", sl).group(1)) if re.search(r"sanaldi\s*(\d+)", sl) else 0
        return n * 5, 0
    return 0, 0


def _bot_lines(key: str, summary: str, work_sec: int) -> tuple[str, str]:
    s = summary or ""
    sl = s.lower()
    if not s:
        return "event yo'q", ""
    if key == "omborga":
        reys = re.search(r"reys\s*(\d+)", sl)
        r = reys.group(1) if reys else "0"
        ish_m = re.search(r"ish\s+([\d:]+)", sl)
        dam_m = re.search(r"dam\s+([\d:]+)", sl)
        ish = ish_m.group(1) if ish_m else _fmt_short(work_sec)
        jami = work_sec
        if dam_m:
            jami = _parse_hms(ish_m.group(1) if ish_m else "0") + _parse_hms(dam_m.group(1))
        return f"reys {r}  ·  ish vaqti {ish}", f"jami vaqt {_fmt_short(jami)}"
    if key == "ombor":
        return f"ish vaqti {_fmt_short(work_sec)}", f"son {work_sec // 1 if work_sec else 0}"
    if key == "yuk":
        return f"ish vaqti {_fmt_short(work_sec)}", ""
    if key == "sklad":
        return _truncate(s, 44), ""
    if key == "ishxona":
        return _truncate(s, 44), ""
    return _truncate(s, 44), ""


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
    cat_total = 0
    for cat in categories:
        if cat not in session_agg:
            continue
        added = int(session_agg[cat])
        cat_total += added
        today = await sum_day(day_iso, employee, cat)
        per = await sum_period(period, employee, cat)
        plan = await get_plan(period, employee, cat)
        norm = int(plan) if plan else today
        period_sum += per
        data.categories.append(
            CategoryRow(name=cat, added=added, today=today, period=per, norm=norm)
        )

    data.cat_total = cat_total
    data.period_sum = period_sum

    events = await fetch_latest_by_bot(tg_id, day_iso) if tg_id else {}
    total_work_sec = 0
    for key in BOT_ORDER:
        summary = events.get(key, "")
        score, wsec = score_bot_summary(key, summary)
        total_work_sec += wsec if wsec else 0
        l1, l2 = _bot_lines(key, summary, wsec)
        data.bots.append(
            BotRow(
                key=key,
                label=BOT_LABELS.get(key, key).upper(),
                summary=summary,
                score=score,
                line1=l1,
                line2=l2,
            )
        )
        if summary and wsec:
            data.work_log.append((BOT_LABELS.get(key, key), _fmt_short(wsec)))
        data.bot_total += score

    data.total_work = _fmt_hms(total_work_sec)
    data.grand_total = cat_total + data.bot_total

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
    active = len([s for s in scores if s[1] > 0])
    for i, (name, pts, wsec) in enumerate(scores[:9], 1):
        pct = int(100 * pts / max_sc) if max_sc else 0
        data.leaders.append(
            LeaderRow(rank=i, name=name, score=pts, work_time=_fmt_short(wsec), pct=pct)
        )
        if name == employee:
            data.rank = i
    data.rank_total = active or len(scores)
    return data


def _rounded_panel(draw, box, fill, outline=None, radius=14, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _progress_bar(draw, x, y, w, h, pct, fill, track):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=track)
    fw = max(4, int(w * max(0, min(100, pct)) / 100))
    draw.rounded_rectangle((x, y, x + fw, y + h), radius=h // 2, fill=fill)


def _badge(draw, x, y, size, abbr, color, font):
    draw.ellipse((x, y, x + size, y + size), fill=color)
    tw = draw.textlength(abbr, font=font)
    draw.text((x + (size - tw) / 2, y + size * 0.22), abbr, fill=(255, 255, 255), font=font)


def render_daily_report_png(data: DailyReportCardData, avatar: bytes | None = None) -> bytes:
    f_huge, f_title, f_head, f_body, f_small = _load_fonts()
    s = SCALE

    row_h = 28 * s
    cat_rows = max(len(data.categories), 1)
    top_h = 56 * s + cat_rows * row_h + 56 * s
    bot_h = 56 * s + len(BOT_ORDER) * (72 * s) + 48 * s
    bottom_h = 56 * s + max(len(data.leaders), 4) * 34 * s + 40 * s
    header_h = 96 * s
    H = M * 2 + header_h + top_h + bot_h + bottom_h + 24 * s

    bg = (8, 14, 36)
    panel = (14, 24, 52)
    panel2 = (18, 32, 62)
    teal = (0, 168, 188)
    teal2 = (0, 130, 155)
    accent = (70, 230, 200)
    gold = (255, 205, 80)
    white = (248, 250, 255)
    muted = (130, 148, 178)
    green = (60, 235, 150)
    orange = (255, 165, 70)
    track = (32, 48, 78)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    _rounded_panel(draw, (M, M, W - M, H - M), bg, outline=teal, radius=18 * s, width=3)

    # ── Header ──
    hy = M + header_h
    _rounded_panel(draw, (M + 6 * s, M + 6 * s, W - M - 6 * s, hy), teal, radius=14 * s)
    draw.text((M + 24 * s, M + 18 * s), "КУНЛИК ҲИСОБОТ (ЯКУН)", fill=white, font=f_huge)
    draw.text((M + 24 * s, M + 58 * s), f"📅  {data.day_iso}     👤  {data.employee}", fill=white, font=f_body)
    draw.text((M + 24 * s, M + 78 * s), f"🗓  Период (2-сана): {data.period}", fill=(220, 240, 255), font=f_small)

    av_size = 72 * s
    if avatar:
        try:
            av = Image.open(BytesIO(avatar)).convert("RGB").resize((av_size, av_size))
            mask = Image.new("L", (av_size, av_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
            img.paste(av, (W - M - av_size - 16 * s, M + 14 * s), mask)
            draw.ellipse(
                (W - M - av_size - 18 * s, M + 12 * s, W - M - 14 * s, M + av_size + 16 * s),
                outline=gold,
                width=3 * s,
            )
        except Exception:
            pass

    y = hy + 16 * s
    inner_w = W - 2 * M - 24 * s
    lx = M + 12 * s

    # ── Top 3 columns ──
    col3_w = 200 * s
    col2_w = 210 * s
    col1_w = inner_w - col2_w - col3_w - 24 * s
    col2_x = lx + col1_w + 12 * s
    col3_x = col2_x + col2_w + 12 * s

    _rounded_panel(draw, (lx, y, lx + col1_w, y + top_h), panel, outline=(40, 70, 110), radius=12 * s)
    draw.text((lx + 16 * s, y + 14 * s), "📊  ФАОЛИЯТ ВА КЎРСАТКИЧЛАР", fill=accent, font=f_head)

    ty = y + 48 * s
    headers = ("ФАОЛИЯТ", "ОЧКО", "БУГУН", "ПЕРИОД", "НОРМА")
    hx = [lx + 14 * s, lx + col1_w - 220 * s, lx + col1_w - 165 * s, lx + col1_w - 110 * s, lx + col1_w - 58 * s]
    for i, h in enumerate(headers):
        draw.text((hx[i], ty), h, fill=muted, font=f_small)
    ty += 22 * s
    draw.line((lx + 12 * s, ty, lx + col1_w - 12 * s, ty), fill=track, width=2)
    ty += 10 * s

    for row in data.categories:
        draw.text((hx[0], ty), _truncate(row.name, 24), fill=white, font=f_small)
        draw.text((hx[1], ty), f"+{row.added}", fill=green, font=f_body)
        draw.text((hx[2], ty), str(row.today), fill=white, font=f_small)
        draw.text((hx[3], ty), str(row.period), fill=white, font=f_small)
        draw.text((hx[4], ty), str(row.norm), fill=muted, font=f_small)
        ty += row_h

    ty += 6 * s
    draw.text((lx + 14 * s, ty), f"⭐  Энг кuchli: {data.best_cat} (+{data.best_add})", fill=gold, font=f_small)
    ty += 22 * s
    draw.text((lx + 14 * s, ty), f"🔥  {_truncate(data.overall_text, 52)}", fill=orange, font=f_small)

    _rounded_panel(draw, (col2_x, y, col2_x + col2_w, y + top_h), panel, outline=(40, 70, 110), radius=12 * s)
    draw.text((col2_x + 14 * s, y + 14 * s), "📋  ОЧКО ҲИСОБЛАШ ТИЗИМИ", fill=accent, font=f_head)
    rules = [
        "• To'liq va sifatli ish — +5",
        "• TSD faol — +6",
        "• Xato/kamchilik — minus",
        "• Boshqa botlar — vaqt/reys",
    ]
    ry = y + 52 * s
    for rule in rules:
        draw.text((col2_x + 14 * s, ry), rule, fill=muted, font=f_body)
        ry += 30 * s
    ry += 12 * s
    draw.text((col2_x + 14 * s, ry), f"Yordamchi: +{data.cat_total}", fill=green, font=f_head)
    ry += 28 * s
    draw.text((col2_x + 14 * s, ry), f"Boshqa botlar: +{data.bot_total}", fill=green, font=f_head)

    _rounded_panel(draw, (col3_x, y, col3_x + col3_w, y + top_h), panel2, outline=accent, radius=12 * s, width=2)
    draw.text((col3_x + 16 * s, y + 16 * s), "ЖАМИ ОЧКО", fill=muted, font=f_body)
    gt = f"+{data.grand_total}"
    draw.text((col3_x + 16 * s, y + 44 * s), gt, fill=green, font=f_huge)
    draw.text((col3_x + 16 * s, y + 96 * s), "БУГУН", fill=accent, font=f_title)
    draw.text((col3_x + 16 * s, y + 128 * s), f"📅  Период: {data.period_sum}", fill=white, font=f_small)
    draw.text((col3_x + 16 * s, y + 152 * s), f"⏱  Ish vaqti: {data.total_work}", fill=white, font=f_small)
    draw.text((col3_x + 16 * s, y + 176 * s), "⏸  Kechikish: yo'q", fill=muted, font=f_small)
    if data.rank:
        draw.text((col3_x + 16 * s, y + 204 * s), f"🏆  Bugungi o'rin: {data.rank}-", fill=gold, font=f_body)
        draw.text((col3_x + 16 * s, y + 228 * s), f"    ({data.rank_total} xodim)", fill=gold, font=f_small)

    y += top_h + 16 * s

    # ── Boshqa botlar ──
    _rounded_panel(draw, (lx, y, W - M - 12 * s, y + bot_h), panel, outline=(40, 70, 110), radius=12 * s)
    draw.text((lx + 16 * s, y + 14 * s), "🤖  БОШҚА БОТЛАР (БУГУН)", fill=accent, font=f_head)
    by = y + 52 * s
    for bot in data.bots:
        card_y1, card_y2 = by, by + 64 * s
        _rounded_panel(draw, (lx + 12 * s, card_y1, W - M - 24 * s, card_y2), panel2, outline=(35, 55, 90), radius=10 * s)
        abbr, color = BOT_BADGE.get(bot.key, ("??", teal))
        _badge(draw, lx + 24 * s, card_y1 + 12 * s, 40 * s, abbr, color, f_head)
        tx = lx + 76 * s
        draw.text((tx, card_y1 + 8 * s), bot.label, fill=accent, font=f_body)
        draw.text((tx, card_y1 + 28 * s), bot.line1, fill=white, font=f_small)
        if bot.line2:
            draw.text((tx, card_y1 + 44 * s), bot.line2, fill=muted, font=f_small)
        sc = f"+{bot.score}" if bot.score else "+0"
        sc_col = green if bot.score else muted
        sw = draw.textlength(sc, font=f_title)
        draw.text((W - M - 36 * s - sw, card_y1 + 20 * s), sc, fill=sc_col, font=f_title)
        by += 72 * s

    draw.text((lx + 16 * s, by + 4 * s), f"📌  JAMI BOSHQ BOTLARDAN: +{data.bot_total}", fill=gold, font=f_head)
    y += bot_h + 16 * s

    # ── Bottom: reyting + ishlar ──
    half = (inner_w - 12 * s) // 2
    rx = lx + half + 12 * s
    _rounded_panel(draw, (lx, y, lx + half, y + bottom_h), panel, outline=(40, 70, 110), radius=12 * s)
    _rounded_panel(draw, (rx, y, W - M - 12 * s, y + bottom_h), panel, outline=(40, 70, 110), radius=12 * s)

    draw.text((lx + 16 * s, y + 14 * s), "📈  КУНЛИК ФОЙДАЛИЛИК РЕЙТИНГИ", fill=accent, font=f_head)
    draw.text((rx + 16 * s, y + 14 * s), "✅  БАЖАРИЛГАН ИШЛАР (БУГУН)", fill=accent, font=f_head)

    ly = y + 50 * s
    bar_w = half - 120 * s
    for lead in data.leaders:
        medal = "🥇" if lead.rank == 1 else "🥈" if lead.rank == 2 else "🥉" if lead.rank == 3 else f"{lead.rank}."
        nc = gold if lead.name == data.employee else white
        draw.text((lx + 14 * s, ly), f"{medal} {_truncate(lead.name, 16)}", fill=nc, font=f_small)
        draw.text((lx + half - 58 * s, ly), f"+{lead.score}", fill=green, font=f_small)
        draw.text((lx + half - 28 * s, ly), f"{lead.pct}%", fill=orange if lead.pct >= 70 else muted, font=f_small)
        _progress_bar(draw, lx + 14 * s, ly + 18 * s, bar_w, 8 * s, lead.pct, teal, track)
        ly += 34 * s

    wy = y + 50 * s
    if data.work_log:
        for label, wt in data.work_log[:8]:
            draw.text((rx + 16 * s, wy), f"•  {label}", fill=white, font=f_body)
            draw.text((rx + 220 * s, wy), wt, fill=accent, font=f_body)
            wy += 32 * s
    else:
        draw.text((rx + 16 * s, wy), "Boshqa botlardan ish yo'q", fill=muted, font=f_body)
        wy += 28 * s
        for row in data.categories[:5]:
            draw.text((rx + 16 * s, wy), f"•  {row.name}: +{row.added}", fill=white, font=f_small)
            wy += 26 * s

    buf = BytesIO()
    img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()
