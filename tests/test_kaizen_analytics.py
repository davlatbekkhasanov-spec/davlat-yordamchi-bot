"""Kaizen analytics — muda va PDCA."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kaizen_analytics import _parse_dam_sec, build_kaizen_report


def test_parse_dam_hms():
    assert _parse_dam_sec("Reys 5, ish 3:29, dam 14:22") == 14 * 60 + 22
    assert _parse_dam_sec("dam 0:00") == 0


def test_kaizen_report_empty_matrix():
    class FakeConn:
        def execute(self, *a, **k):
            class R:
                def fetchall(self):
                    return []

                def fetchone(self):
                    return None

            return R()

    matrix = [
        {
            "employee": "Test User",
            "total": 0,
            "cat_total": 0,
            "bot_total": 0,
            "rank": 1,
            "roles": {k: {"points": 0, "active": False, "summary": ""} for k in ("omborga", "ombor", "yuk", "sklad", "ishxona")},
        }
    ]
    for k in matrix[0]["roles"]:
        matrix[0]["roles"][k]["summary"] = ""

    rep = build_kaizen_report(
        conn=FakeConn(),
        day="2026-06-10",
        matrix=matrix,
        employees=["Test User"],
        sum_day_total=lambda *a, **k: 0,
        hub_merged=lambda *a, **k: {},
        employee_tg_map=lambda c: {},
    )
    assert "pdca" in rep
    assert rep["stats"]["team_total"] == 0
    assert any(m["type"] == "bo_sh" for m in rep["muda"])


if __name__ == "__main__":
    test_parse_dam_hms()
    test_kaizen_report_empty_matrix()
    print("PASS test_kaizen_analytics")
