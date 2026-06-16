"""report_format tests."""

from report_format import CategoryRow, fmt_points, parse_faceid_summary, build_compare_rows


def test_fmt_points_negative():
    p = fmt_points(-93)
    assert p["text"] == "−93"
    assert p["cls"] == "pts-neg"


def test_parse_faceid_extended():
    s = "Face ID: ball=-93 kech=0 qarz=93 bonus=0 keldi=08:05 ketdi=12:17 ish_daq=252 qarz_oy_daq=750"
    f = parse_faceid_summary(s)
    assert f.ball == -93
    assert f.qarz_today_min == 93
    assert f.keldi == "08:05"
    assert f.ketdi == "12:17"
    assert f.active_min == 252
    assert f.qarz_month_min == 750


def test_compare_rows():
    cats = [
        CategoryRow("A", 2, 5, 10, 8, "40"),
        CategoryRow("B", 0, 0, 5, 3, "15"),
    ]
    rows = build_compare_rows(cats)
    assert len(rows) == 2
    assert rows[0].delta == -35
