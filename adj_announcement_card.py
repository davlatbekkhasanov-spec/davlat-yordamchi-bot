"""Bonus / jarima — vizual PNG kartochka (kunlik hisobot uslubida)."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from pathlib import Path

from daily_report_card import (
    ACCENT,
    BG,
    FONT_DIR,
    GOLD,
    GREEN,
    MUTED,
    ORANGE,
    PANEL,
    TEAL,
    TEAL_D,
    WHITE,
    _load_fonts,
    _panel,
    _truncate,
)

W, H = 920, 1180
M = 28

PENALTY_BG = (18, 10, 22)
PENALTY_HDR = (160, 35, 48)
PENALTY_ACCENT = (255, 90, 100)
RED_SCORE = (255, 70, 85)


def _paste_avatar(img: Image.Image, draw: ImageDraw.ImageDraw, avatar: bytes | None, cx: int, cy: int, size: int):
    if not avatar:
        draw.ellipse(
            (cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2),
            fill=PANEL,
            outline=MUTED,
            width=4,
        )
        draw.text((cx - 18, cy - 22), "👤", fill=WHITE)
        return
    try:
        av = Image.open(BytesIO(avatar)).convert("RGB").resize((size, size))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        x0, y0 = cx - size // 2, cy - size // 2
        img.paste(av, (x0, y0), mask)
        draw.ellipse((x0 - 4, y0 - 4, x0 + size + 4, y0 + size + 4), outline=GOLD, width=5)
    except Exception:
        pass


def render_adj_card_png(
    *,
    kind: str,
    employee: str,
    points: int,
    period: str,
    day_iso: str,
    avatar: bytes | None = None,
) -> bytes:
    is_bonus = kind == "bonus"
    fonts = _load_fonts()
    f_title, f_score, f_head, f_bold, f_body, f_small = fonts

    bg = BG if is_bonus else PENALTY_BG
    hdr_top = TEAL if is_bonus else PENALTY_HDR
    hdr_bot = TEAL_D if is_bonus else (100, 22, 32)
    accent = ACCENT if is_bonus else PENALTY_ACCENT
    score_color = GREEN if is_bonus else RED_SCORE
    border = GOLD if is_bonus else PENALTY_ACCENT

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    _panel(draw, (M, M, W - M, H - M), fill=bg, outline=border, radius=22, width=4)

    hdr_h = M + 120
    draw.rounded_rectangle((M + 8, M + 8, W - M - 8, hdr_h), radius=16, fill=hdr_bot)
    draw.rounded_rectangle((M + 8, M + 8, W - M - 8, hdr_h - 32), radius=16, fill=hdr_top)

    if is_bonus:
        title = "ТАНТАНАВИЙ БОНУС"
        sub = "Рейтинг жадвалида КЎТАРИЛДИ"
        motiv = "Жамоа горди! Чемпионлик йўли — очиқ!"
    else:
        title = "ЖАРИМА ОЧКО"
        sub = "Рейтингдан АЙИРИЛДИ"
        motiv = "Диққат: қайта такрорланмасин"

    draw.text((M + 32, M + 22), title, fill=WHITE, font=f_head)
    draw.text((M + 32, M + 52), sub, fill=accent, font=f_bold)

    av_cx, av_cy = W // 2, M + 280
    av_size = 220
    _paste_avatar(img, draw, avatar, av_cx, av_cy, av_size)

    name_y = av_cy + av_size // 2 + 36
    name = _truncate(employee, 28)
    tw = draw.textlength(name, font=f_title)
    draw.text(((W - tw) / 2, name_y), name, fill=WHITE, font=f_title)

    sign = "+" if is_bonus else "−"
    score_txt = f"{sign}{points}"
    f_huge = f_score
    for bold_path in (
        FONT_DIR / "NotoSans-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ):
        if bold_path.is_file():
            try:
                f_huge = ImageFont.truetype(str(bold_path), 96)
            except Exception:
                pass
            break
    sw = draw.textlength(score_txt, font=f_huge)
    score_y = name_y + 56
    draw.text(((W - sw) / 2, score_y), score_txt, fill=score_color, font=f_huge)

    lbl = "БОНУС ОЧКО" if is_bonus else "ЖАРИМА ОЧКО"
    lw = draw.textlength(lbl, font=f_bold)
    draw.text(((W - lw) / 2, score_y + 88), lbl, fill=accent, font=f_bold)

    mid_y = score_y + 150
    _panel(draw, (M + 40, mid_y, W - M - 40, mid_y + 120), fill=PANEL, outline=(45, 65, 95), radius=14)
    draw.text((M + 56, mid_y + 18), f"📈  Период: {period}", fill=WHITE, font=f_body)
    draw.text((M + 56, mid_y + 48), f"📅  Сана: {day_iso}", fill=WHITE, font=f_body)
    draw.text((M + 56, mid_y + 78), "Kanstik Samarqand", fill=MUTED, font=f_small)

    foot_y = H - M - 100
    draw.text((M + 40, foot_y), _truncate(motiv, 42), fill=ORANGE if is_bonus else PENALTY_ACCENT, font=f_body)
    stars = "* * * * *" if is_bonus else "! ! ! ! !"
    draw.text((M + 40, foot_y + 32), stars, fill=GOLD if is_bonus else RED_SCORE, font=f_head)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
