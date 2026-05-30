"""Kunlik jamoa reytingi — korporativ PNG HTML."""

from __future__ import annotations

from daily_report_card import LeaderRow, _fmt_footer_date
from report_html import _css_text, _env, _logo_b64

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def build_ranking_html(day_iso: str, leaders: list[LeaderRow], active: int) -> str:
    rows = []
    for row in leaders:
        rows.append(
            {
                "rank": row.rank,
                "medal": _MEDALS.get(row.rank, str(row.rank)),
                "name": row.name,
                "score": row.score,
                "work_time": row.work_time or "00:00",
                "pct": row.pct,
            }
        )

    top_score = leaders[0].score if leaders else 0
    top_name = leaders[0].name if leaders else "—"
    total_score = sum(r.score for r in leaders)

    ctx = {
        "css": _css_text(),
        "logo_b64": _logo_b64(),
        "day_iso": day_iso,
        "active": active,
        "top_score": top_score,
        "top_name": top_name,
        "total_score": total_score,
        "leaders": rows,
        "footer_date": _fmt_footer_date(day_iso),
    }
    return _env().get_template("ranking.html").render(**ctx)
