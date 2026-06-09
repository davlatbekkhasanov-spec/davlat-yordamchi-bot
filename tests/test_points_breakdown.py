from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from daily_report_card import BotRow, CategoryRow, DailyReportCardData
from points_breakdown import explain_bot_formula, format_daily_breakdown_html


def test_explain_omborga():
    pts, formula = explain_bot_formula(
        "omborga", "Reys 7, yuk 105m, ish 2:45, dam 0:14"
    )
    assert pts == 15  # 7*2 + ceil(165)/2 = 14+1
    assert "reys 7" in formula


def test_format_daily_has_table():
    card = DailyReportCardData(
        day_iso="2026-06-08",
        employee="Test",
        period="2026-06",
        categories=[
            CategoryRow(name="Приход", added=56, today=56, period=100, norm=56),
        ],
        bots=[
            BotRow(
                key="omborga",
                label="Omborga",
                summary="Reys 5, ish 3:29, dam 1:10",
                score=12,
                metrics=[],
            ),
        ],
        cat_total=56,
        bot_total=12,
        grand_total=68,
    )
    html = format_daily_breakdown_html(card)
    assert "Приход" in html
    assert "+56" in html
    assert "JAMI" in html
    assert "+68" in html


if __name__ == "__main__":
    test_explain_omborga()
    test_format_daily_has_table()
    print("PASS test_points_breakdown")
