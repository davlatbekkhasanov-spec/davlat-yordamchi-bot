"""Period jamoa reytingi — korporativ PNG HTML."""

from __future__ import annotations

from datetime import date

from daily_report_card import LeaderRow, _fmt_footer_date
from report_html import _css_text, _env, _logo_b64

_MEDALS = {1: "1", 2: "2", 3: "3"}
_TIERS = {1: "green-1", 2: "green-2", 3: "green-3"}


def build_ranking_html(
    period: str,
    ref_date: date,
    leaders: list[LeaderRow],
    active: int,
) -> str:
    rows = []
    for row in leaders:
        rows.append(
            {
                "rank": row.rank,
                "medal": _MEDALS.get(row.rank, str(row.rank)),
                "tier": _TIERS.get(row.rank, "default"),
                "name": row.name,
                "score": row.score,
                "work_time": row.work_time or "00:00",
                "pct": row.pct,
                "zero": row.score <= 0,
            }
        )

    top = leaders[0] if leaders else None
    top_score = top.score if top else 0
    top_name = top.name if top and top.score > 0 else "—"
    total_score = sum(r.score for r in leaders)

    ctx = {
        "css": _css_text(),
        "logo_b64": _logo_b64(),
        "period": period,
        "ref_date": ref_date.isoformat(),
        "ref_date_fmt": _fmt_footer_date(ref_date.isoformat()),
        "team_size": len(leaders),
        "active": active,
        "top_score": top_score,
        "top_name": top_name,
        "total_score": total_score,
        "leaders": rows,
    }
    return _env().get_template("ranking.html").render(**ctx)
