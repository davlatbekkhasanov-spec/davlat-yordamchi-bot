"""Kunlik yakuniy hisobot — referens dizayn."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cross_bot_hub import BOT_LABELS, fetch_merged_latest_by_bot
from employee_tg_map import tg_ids_for_employee
from report_summary import build_summary_text as _build_summary_text

W, H = 1520, 2280
M = 24
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

BOT_ORDER = ("omborga", "ombor", "yuk", "sklad", "ishxona")
BOT_BADGE = {
    "omborga": ("OM", (0, 175, 210)),
    "ombor": ("OX", (255, 130, 45)),
    "yuk": ("YJ", (95, 195, 85)),
    "sklad": ("SN", (155, 110, 240)),
    "ishxona": ("IN", (240, 85, 110)),
}

# Ranglar (referens)
BG = (7, 12, 32)
PANEL = (12, 22, 48)
PANEL2 = (16, 28, 58)
TEAL = (0, 168, 188)
TEAL_D = (0, 118, 138)
ACCENT = (65, 225, 195)
GOLD = (255, 200, 70)
WHITE = (248, 250, 255)
MUTED = (125, 142, 172)
GREEN = (55, 235, 145)
ORANGE = (255, 160, 55)
TRACK = (28, 42, 68)


@dataclass
class CategoryRow:
    name: str
    added: int
    today: int
    period: int
    norm: int
    yesterday: str = "йўқ"


@dataclass
class BotRow:
    key: str
    label: str
    summary: str
    score: int
    metrics: list[tuple[str, str]]


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
    summary_text: str = ""
    recommendation_text: str = ""
    work_ish_time: str = "00:00"
    work_dam_time: str = "00:00"
    footer_date: str = ""


def _load_fonts():
    reg = next((p for p in [
        FONT_DIR / "NotoSans-Regular.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ] if p.is_file()), None)
    bold = next((p for p in [
        FONT_DIR / "NotoSans-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ] if p.is_file()), None)
    if not reg or not bold:
        d = ImageFont.load_default()
        return d, d, d, d, d, d
    return (
        ImageFont.truetype(str(bold), 36),
        ImageFont.truetype(str(bold), 52),
        ImageFont.truetype(str(bold), 22),
        ImageFont.truetype(str(bold), 18),
        ImageFont.truetype(str(reg), 16),
        ImageFont.truetype(str(reg), 13),
    )


def _truncate(text: str, n: int = 36) -> str:
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


def _parse_ombor_duration(text: str) -> int:
    """'1 soat 38 daqiqa 27 soniya' yoki '5907 soniya'."""
    sl = (text or "").lower()
    m = re.search(r"ish\s+vaqti\s+(\d+)\s*soniya", sl)
    if m:
        return int(m.group(1))
    total = 0
    h = re.search(r"(\d+)\s*soat", sl)
    daq = re.search(r"(\d+)\s*daqiqa", sl)
    son = re.search(r"(\d+)\s*soniya", sl)
    if h:
        total += int(h.group(1)) * 3600
    if daq:
        total += int(daq.group(1)) * 60
    if son:
        total += int(son.group(1))
    return total


def _parse_omborga_time(token: str) -> int:
    """OmborgaKiritishBot fmt_duration_short: daqiqa:soniya (75:39 = 75 daq 39 son)."""
    token = (token or "").strip()
    m = re.match(r"^(\d+):(\d{2})$", token)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return _parse_hms(token)


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


def _fmt_clock(seconds: int) -> str:
    """Reyting va umumiy ish vaqti — soat bo'lsa H:MM:SS, aks holda MM:SS."""
    return _fmt_work_duration(seconds)


def _fmt_work_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def score_bot_summary(key: str, summary: str) -> tuple[int, int]:
    s = (summary or "").strip()
    if not s:
        return 0, 0
    sl = s.lower()
    if key == "omborga":
        reys = int(re.search(r"reys\s*(\d+)", sl).group(1)) if re.search(r"reys\s*(\d+)", sl) else 0
        ish_m = re.search(r"ish\s+([\d:]+)", sl)
        dam_m = re.search(r"dam\s+([\d:]+)", sl)
        ish = _parse_omborga_time(ish_m.group(1)) if ish_m else _parse_hms(s)
        dam = _parse_omborga_time(dam_m.group(1)) if dam_m else 0
        total = ish + dam
        if not reys and not total:
            return 0, 0
        mins = max(1, ish // 60) if ish else 0
        return reys * 3 + mins // 2, total
    if key == "ombor":
        sec = _parse_ombor_duration(sl)
        if not sec:
            sec = _parse_hms(s)
        if not sec and re.search(r"(\d+)\s*son", sl):
            sec = int(re.search(r"(\d+)\s*son", sl).group(1))
        if not sec:
            return 0, 0
        return max(1, sec // 2 + 1), sec
    if key == "yuk":
        sec = _parse_hms(s)
        if not sec:
            return 0, 0
        return max(1, sec // 130 + 1), sec
    if key == "sklad":
        n = int(re.search(r"sanaldi\s*(\d+)", sl).group(1)) if re.search(r"sanaldi\s*(\d+)", sl) else 0
        return n * 5, 0
    return 0, 0


def _bot_metrics(key: str, summary: str, work_sec: int) -> list[tuple[str, str]]:
    s = summary or ""
    sl = s.lower()
    if not s:
        return [("holat", "—")]
    if key == "omborga":
        reys = re.search(r"reys\s*(\d+)", sl)
        ish_m = re.search(r"ish\s+([\d:]+)", sl)
        dam_m = re.search(r"dam\s+([\d:]+)", sl)
        r = reys.group(1) if reys else "0"
        ish_sec = _parse_omborga_time(ish_m.group(1)) if ish_m else work_sec
        out = [
            ("reys", r),
            ("ish vaqti", _fmt_work_duration(ish_sec)),
            ("jami vaqt", _fmt_work_duration(work_sec)),
        ]
        if dam_m:
            dam_sec = _parse_omborga_time(dam_m.group(1))
            out.insert(2, ("dam", _fmt_work_duration(dam_sec)))
        return out
    if key == "ombor":
        return [("ish vaqti", _fmt_hms(work_sec)), ("son", str(work_sec))]
    if key == "yuk":
        return [("ish vaqti", _fmt_short(work_sec))]
    if key == "sklad":
        return [("ma'lumot", _truncate(s, 28))]
    if key == "ishxona":
        return [("shikoyat", _truncate(s, 28))]
    return [("info", _truncate(s, 28))]


def _fmt_footer_date(day_iso: str) -> str:
    try:
        y, m, d = day_iso.split("-")
        return f"{d}.{m}.{y}"
    except Exception:
        return day_iso


def _parse_work_rest(events: dict[str, str]) -> tuple[str, str]:
    summary = events.get("omborga", "") or ""
    sl = summary.lower()
    ish_m = re.search(r"ish\s+([\d:]+)", sl)
    dam_m = re.search(r"dam\s+([\d:]+)", sl)
    ish_sec = _parse_omborga_time(ish_m.group(1)) if ish_m else 0
    dam_sec = _parse_omborga_time(dam_m.group(1)) if dam_m else 0
    return _fmt_work_duration(ish_sec), _fmt_work_duration(dam_sec)


async def build_card_data(
    *,
    employee: str,
    day_iso: str,
    period: str,
    yday_iso: str,
    session_agg: dict[str, int],
    categories: list[str],
    best_cat: str,
    best_add: int,
    overall_text: str,
    employees: list[str],
    sum_day: Callable[..., Awaitable[int]],
    sum_period: Callable[..., Awaitable[int]],
    get_plan: Callable[..., Awaitable[int | None]],
    sum_day_total: Callable[..., Awaitable[int]],
    employee_tg_map: dict[str, int],
    day_has_any: Callable[..., Awaitable[bool]] | None = None,
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
        ytxt = "йўқ"
        if day_has_any:
            if await day_has_any(yday_iso, employee, cat):
                ytxt = str(await sum_day(yday_iso, employee, cat))
        else:
            yday = await sum_day(yday_iso, employee, cat)
            if yday:
                ytxt = str(yday)
        data.categories.append(
            CategoryRow(name=cat, added=added, today=today, period=per, norm=norm, yesterday=ytxt)
        )

    data.cat_total = cat_total
    data.period_sum = period_sum
    # Faqat shu xodimga bog'langan tg_id — operator Telegrami boshqa profil uchun emas
    tg_set = tg_ids_for_employee(employee, employee_tg_map=employee_tg_map)
    events = await fetch_merged_latest_by_bot(tg_set, day_iso) if tg_set else {}
    total_work_sec = 0
    for key in BOT_ORDER:
        summary = events.get(key, "")
        score, wsec = score_bot_summary(key, summary)
        total_work_sec += wsec
        data.bots.append(
            BotRow(
                key=key,
                label=BOT_LABELS.get(key, key).upper(),
                summary=summary,
                score=score,
                metrics=_bot_metrics(key, summary, wsec),
            )
        )
        if summary.strip() and wsec:
            data.work_log.append((BOT_LABELS.get(key, key), _fmt_clock(wsec)))
        data.bot_total += score

    data.total_work = _fmt_hms(total_work_sec)
    data.grand_total = cat_total + data.bot_total

    scores: list[tuple[str, int, int]] = []
    for emp in employees:
        cat_pts = await sum_day_total(day_iso, emp)
        bot_pts = 0
        work_sec = 0
        tg_set = tg_ids_for_employee(emp, employee_tg_map=employee_tg_map)
        if tg_set:
            ev = await fetch_merged_latest_by_bot(tg_set, day_iso)
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
        data.leaders.append(LeaderRow(rank=i, name=name, score=pts, work_time=_fmt_clock(wsec), pct=pct))
        if name == employee:
            data.rank = i
    data.rank_total = active or len(scores)
    data.work_ish_time, data.work_dam_time = _parse_work_rest(events)
    data.footer_date = _fmt_footer_date(day_iso)
    data.summary_text, data.recommendation_text = _build_summary_text(data)
    return data


def _panel(draw, box, fill=PANEL, outline=(38, 58, 92), radius=14, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _bar(draw, x, y, w, h, pct, fill=TEAL):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=TRACK)
    fw = max(6, int(w * max(0, min(100, pct)) / 100))
    draw.rounded_rectangle((x, y, x + fw, y + h), radius=h // 2, fill=fill)


def _metric_chip(draw, x, y, w, h, label, value, fonts):
    _, _, _, f_b, f_r, f_s = fonts
    _panel(draw, (x, y, x + w, y + h), fill=PANEL2, outline=(45, 65, 95), radius=8, width=1)
    draw.text((x + 8, y + 6), label, fill=MUTED, font=f_s)
    draw.text((x + 8, y + 22), value, fill=WHITE, font=f_b)


def render_daily_report_png(data: DailyReportCardData, avatar: bytes | None = None) -> bytes:
    fonts = _load_fonts()
    f_title, f_score, f_head, f_bold, f_body, f_small = fonts

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _panel(draw, (M, M, W - M, H - M), fill=BG, outline=TEAL, radius=18, width=3)

    # Header
    hdr_b = M + 108
    draw.rounded_rectangle((M + 6, M + 6, W - M - 6, hdr_b), radius=14, fill=TEAL_D)
    draw.rounded_rectangle((M + 6, M + 6, W - M - 6, hdr_b - 28), radius=14, fill=TEAL)
    draw.text((M + 28, M + 18), "КУНЛИК ҲИСОБОТ (ЯКУН)", fill=WHITE, font=f_title)
    draw.text((M + 28, M + 58), f"📅  {data.day_iso}     👤  {data.employee}", fill=WHITE, font=f_body)
    draw.text((M + 28, M + 80), f"🗓  Период (2-сана): {data.period}", fill=(220, 240, 255), font=f_small)

    if avatar:
        try:
            avs = 80
            av = Image.open(BytesIO(avatar)).convert("RGB").resize((avs, avs))
            mask = Image.new("L", (avs, avs), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, avs, avs), fill=255)
            ax = W - M - avs - 20
            img.paste(av, (ax, M + 14), mask)
            draw.ellipse((ax - 3, M + 11, ax + avs + 3, M + avs + 17), outline=GOLD, width=3)
        except Exception:
            pass

    y = hdr_b + 18
    lx = M + 14
    inner = W - 2 * M - 28

    # Top row heights
    top_h = 300
    c1w = int(inner * 0.46)
    c2w = int(inner * 0.28)
    c3w = inner - c1w - c2w - 24
    c2x = lx + c1w + 12
    c3x = c2x + c2w + 12

    _panel(draw, (lx, y, lx + c1w, y + top_h))
    draw.text((lx + 16, y + 12), "📊  ФАОЛИЯТ ВА КЎРСАТКИЧЛАР", fill=ACCENT, font=f_head)

    ty = y + 46
    cols_x = [lx + 14, lx + c1w - 248, lx + c1w - 188, lx + c1w - 128, lx + c1w - 68]
    for i, h in enumerate(("ФАОЛИЯТ", "ОЧКО", "БУГУН", "ПЕРИОД", "НОРМА")):
        draw.text((cols_x[i], ty), h, fill=MUTED, font=f_small)
    ty += 24
    draw.line((lx + 10, ty, lx + c1w - 10, ty), fill=TRACK, width=2)
    ty += 10

    for row in data.categories[:10]:
        draw.text((cols_x[0], ty), _truncate(row.name, 22), fill=WHITE, font=f_small)
        draw.text((cols_x[1], ty), f"+{row.added}", fill=GREEN, font=f_bold)
        draw.text((cols_x[2], ty), str(row.today), fill=WHITE, font=f_small)
        draw.text((cols_x[3], ty), str(row.period), fill=WHITE, font=f_small)
        draw.text((cols_x[4], ty), str(row.norm), fill=MUTED, font=f_small)
        ty += 26

    draw.text((lx + 14, y + top_h - 52), f"⭐  {data.best_cat} (+{data.best_add})", fill=GOLD, font=f_small)
    draw.text((lx + 14, y + top_h - 28), f"🔥  {_truncate(data.overall_text, 48)}", fill=ORANGE, font=f_small)

    _panel(draw, (c2x, y, c2x + c2w, y + top_h))
    draw.text((c2x + 14, y + 12), "📋  ОЧКО ҲИСОБЛАШ", fill=ACCENT, font=f_head)
    ry = y + 48
    for rule in (
        "• To'liq va sifatli ish — +5",
        "• TSD faol — +6",
        "• Xato/kamchilik — minus",
        "• Boshqa botlar — vaqt/reys",
    ):
        draw.text((c2x + 14, ry), rule, fill=MUTED, font=f_body)
        ry += 28
    ry += 8
    draw.text((c2x + 14, ry), f"Yordamchi: +{data.cat_total}", fill=GREEN, font=f_bold)
    ry += 26
    draw.text((c2x + 14, ry), f"Boshqa botlar: +{data.bot_total}", fill=GREEN, font=f_bold)

    # Score box — referens: katta raqam = bot ochko
    _panel(draw, (c3x, y, c3x + c3w, y + top_h), fill=PANEL2, outline=ACCENT, radius=14, width=2)
    draw.rectangle((c3x + 8, y + 8, c3x + c3w - 8, y + top_h - 8), outline=(0, 90, 105), width=1)
    draw.text((c3x + 18, y + 16), "ЖАМИ ОЧКО", fill=MUTED, font=f_body)
    draw.text((c3x + 18, y + 42), f"+{data.bot_total}", fill=GREEN, font=f_score)
    draw.text((c3x + 18, y + 108), "БУГУН", fill=ACCENT, font=f_head)
    draw.text((c3x + 18, y + 138), f"📅  Период: {data.period_sum}", fill=WHITE, font=f_small)
    draw.text((c3x + 18, y + 160), f"⏱  Ish vaqti: {data.total_work}", fill=WHITE, font=f_small)
    draw.text((c3x + 18, y + 182), "⏸  Kechikish: yo'q", fill=MUTED, font=f_small)
    if data.rank:
        draw.text((c3x + 18, y + 210), f"🏆  {data.rank}-o'rin ({data.rank_total} xodim)", fill=GOLD, font=f_bold)
    draw.text((c3x + 18, y + 238), f"Jami: +{data.grand_total}", fill=MUTED, font=f_small)

    y += top_h + 16

    # Bots section — referens: har bir qator chip ustunlari
    bot_sec_h = 430
    _panel(draw, (lx, y, W - M - 14, y + bot_sec_h))
    draw.text((lx + 16, y + 12), "🤖  БОШҚА БОТЛАР (БУГУН)", fill=ACCENT, font=f_head)

    by = y + 50
    row_h = 68
    for bot in data.bots:
        _panel(draw, (lx + 10, by, W - M - 24, by + row_h), fill=PANEL2, outline=(35, 52, 82), radius=10, width=1)
        abbr, col = BOT_BADGE.get(bot.key, ("??", TEAL))
        draw.ellipse((lx + 22, by + 14, lx + 62, by + 54), fill=col)
        tw = draw.textlength(abbr, font=f_bold)
        draw.text((lx + 42 - tw / 2, by + 22), abbr, fill=WHITE, font=f_bold)
        draw.text((lx + 74, by + 10), bot.label, fill=ACCENT, font=f_bold)

        mx = lx + 290
        chip_w = 130
        gap = 10
        for i, (lbl, val) in enumerate(bot.metrics[:4]):
            _metric_chip(draw, mx + i * (chip_w + gap), by + 10, chip_w, 48, lbl, val, fonts)

        sc = f"+{bot.score}" if bot.score else "+0"
        sw = draw.textlength(sc, font=f_head)
        draw.text((W - M - 40 - sw, by + 22), sc, fill=GREEN if bot.score else MUTED, font=f_head)
        by += row_h + 8

    draw.text((lx + 16, y + bot_sec_h - 32), f"📌  JAMI BOSHQ BOTLARDAN: +{data.bot_total}", fill=GOLD, font=f_head)
    y += bot_sec_h + 14

    # Bottom
    bot_h = H - M - y - 10
    half = (inner - 12) // 2
    rx = lx + half + 12

    _panel(draw, (lx, y, lx + half, y + bot_h))
    _panel(draw, (rx, y, W - M - 14, y + bot_h))
    draw.text((lx + 16, y + 12), "📈  КУНЛИК ФОЙДАЛИЛИК РЕЙТИНГИ", fill=ACCENT, font=f_head)
    draw.text((rx + 16, y + 12), "✅  БАЖАРИЛГАН ИШЛАР (БУГУН)", fill=ACCENT, font=f_head)

    ly = y + 48
    for lead in data.leaders:
        medal = "🥇" if lead.rank == 1 else "🥈" if lead.rank == 2 else "🥉" if lead.rank == 3 else f"{lead.rank}."
        nc = GOLD if lead.name == data.employee else WHITE
        draw.text((lx + 14, ly), f"{medal} {_truncate(lead.name, 18)}", fill=nc, font=f_small)
        draw.text((lx + half - 72, ly), f"+{lead.score}", fill=GREEN, font=f_small)
        draw.text((lx + half - 38, ly), lead.work_time or "00:00", fill=MUTED, font=f_small)
        draw.text((lx + half - 8, ly), f"{lead.pct}%", fill=ORANGE if lead.pct >= 70 else MUTED, font=f_small)
        _bar(draw, lx + 14, ly + 20, half - 100, 10, lead.pct)
        ly += 38

    wy = y + 48
    items = data.work_log or [(r.name, f"+{r.added}") for r in data.categories[:6]]
    for label, wt in items[:8]:
        draw.text((rx + 16, wy), f"•  {label}", fill=WHITE, font=f_body)
        draw.text((rx + 260, wy), wt, fill=ACCENT, font=f_bold)
        wy += 32

    buf = BytesIO()
    img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()


def build_demo_card_data() -> DailyReportCardData:
    y = "йўқ"
    data = DailyReportCardData(
        day_iso="2026-05-29",
        employee="Mustafoev Abdullo",
        period="2026-05",
        best_cat="Счет ТСД",
        best_add=6,
        overall_text="Кеча маълумот йўқ. Бугун яхши старт! 💪",
        categories=[
            CategoryRow("Приход", 5, 5, 5, 5, y),
            CategoryRow("Перемещение", 5, 5, 5, 5, y),
            CategoryRow("Фото ТМЦ", 5, 5, 5, 5, y),
            CategoryRow("Счет ТСД", 6, 6, 6, 6, y),
            CategoryRow("Фасовка", 5, 5, 5, 5, y),
            CategoryRow("АРМ диспетчер", 6, 6, 6, 6, y),
            CategoryRow("Исправление пересортицы", 5, 5, 5, 5, y),
            CategoryRow("Переоценка", 5, 5, 5, 5, y),
            CategoryRow("Пересчет товаров", 5, 5, 5, 5, y),
            CategoryRow("Места хр", 5, 5, 5, 5, y),
        ],
        bots=[
            BotRow("omborga", "OMBORGA", "Reys: 4, yuk 209m, ish 0:27, dam 0:16", 18, []),
            BotRow("ombor", "OMBOR", "#1 🙋 Хизмат сўрови: бajarilди, 54 soniya", 22, []),
            BotRow("yuk", "YUK", "Yuk #1: ish vaqti 0:39", 17, []),
            BotRow("sklad", "SKLAD", "Papka Datery: sanaldi 1, joy 1, xato 0, kun 2/36", 5, []),
            BotRow("ishxona", "ISHXONA", "Shikoyat (Mustafoev Abdullo): Test2", 0, []),
        ],
        cat_total=31,
        bot_total=62,
        grand_total=93,
        total_work="03:27:16",
        period_sum=31,
        rank=1,
        rank_total=9,
        work_ish_time="01:51",
        work_dam_time="00:16",
        footer_date="29.05.2026",
    )
    data.summary_text, data.recommendation_text = _build_summary_text(data)
    return data


def render_demo_preview_png() -> bytes:
    return render_daily_report_png(build_demo_card_data())
