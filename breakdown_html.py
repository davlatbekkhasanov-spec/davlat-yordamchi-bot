"""Ochko jadvali — korporativ PNG HTML."""

from __future__ import annotations

from datetime import date

from daily_report_card import DailyReportCardData, _fmt_footer_date
from report_html import _css_text, _env, _logo_b64

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_TIERS = {1: "green-1", 2: "green-2", 3: "green-3"}


def _cell_cls(val: int) -> str:
    return "col-zero" if not int(val or 0) else "col-val"


def _cell_disp(val: int) -> str:
    v = int(val or 0)
    return "—" if not v else str(v)


def period_rows_for_template(
    rows: list[tuple[str, int, dict[str, int], int]],
) -> list[dict]:
    out: list[dict] = []
    for rank, (emp, cat_pts, bot_by_key, total) in enumerate(rows, 1):
        ombg = int(bot_by_key.get("omborga") or 0)
        omb = int(bot_by_key.get("ombor") or 0)
        yuk = int(bot_by_key.get("yuk") or 0)
        skl = int(bot_by_key.get("sklad") or 0)
        in_pts = int(bot_by_key.get("ishxona") or 0)
        kat = int(cat_pts or 0)
        out.append(
            {
                "rank": rank,
                "medal": _MEDALS.get(rank, str(rank)),
                "tier": _TIERS.get(rank, "default"),
                "name": emp,
                "kat": _cell_disp(kat),
                "ombg": _cell_disp(ombg),
                "omb": _cell_disp(omb),
                "yuk": _cell_disp(yuk),
                "skl": _cell_disp(skl),
                "in_pts": _cell_disp(in_pts),
                "total": f"+{total}",
                "kat_cls": _cell_cls(kat),
                "ombg_cls": _cell_cls(ombg),
                "omb_cls": _cell_cls(omb),
                "yuk_cls": _cell_cls(yuk),
                "skl_cls": _cell_cls(skl),
                "in_cls": _cell_cls(in_pts),
            }
        )
    return out


def build_period_breakdown_png_html(
    period: str,
    ref_date: date,
    rows: list[tuple[str, int, dict[str, int], int]],
) -> str:
    ctx = {
        "css": _css_text(),
        "logo_b64": _logo_b64(),
        "period": period,
        "ref_date": ref_date.isoformat(),
        "ref_date_fmt": _fmt_footer_date(ref_date.isoformat()),
        "team_size": len(rows),
        "rows": period_rows_for_template(rows),
    }
    return _env().get_template("breakdown.html").render(**ctx)


def build_daily_breakdown_png_html(
    card: DailyReportCardData,
    *,
    lines: list[dict[str, str]],
) -> str:
    ctx = {
        "css": _css_text(),
        "logo_b64": _logo_b64(),
        "employee": card.employee,
        "day_iso": card.day_iso,
        "lines": lines,
        "cat_total": card.cat_total,
        "bot_total": card.bot_total,
        "grand_total": card.grand_total,
    }
    return _env().get_template("breakdown_daily.html").render(**ctx)
