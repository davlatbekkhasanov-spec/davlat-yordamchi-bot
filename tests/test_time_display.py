"""Vaqt formatlash — yagona logika."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from time_display import fmt_duration, parse_colon_token, parse_duration_text  # noqa: E402


def test_under_hour_mm_ss():
    assert fmt_duration(2849) == "47:29"
    assert fmt_duration(90) == "01:30"


def test_over_hour_hms():
    assert fmt_duration(3600) == "1:00:00"
    assert fmt_duration(4529) == "1:15:29"
    assert fmt_duration(3332) == "55:32"


def test_parse_colon_mm_ss():
    assert parse_colon_token("47:29") == 47 * 60 + 29
    assert parse_colon_token("75:00") == 75 * 60
    assert parse_colon_token("1:15:29") == 3600 + 15 * 60 + 29


def test_no_47_as_hours():
    """47:29 hech qachon 47 soat bo'lmasin."""
    assert parse_duration_text("47:29") == 47 * 60 + 29
    assert parse_duration_text("ish 1:15:29") == 3600 + 15 * 60 + 29


def test_omborga_merge_format():
    from cross_bot_hub import _format_omborga_summary

    s = _format_omborga_summary(79, 3332, 0)
    assert "55:32" in s
    s2 = _format_omborga_summary(22, 4529, 1890)
    assert "1:15:29" in s2
    assert "31:30" in s2  # dam 1890s


if __name__ == "__main__":
    test_under_hour_mm_ss()
    test_over_hour_hms()
    test_parse_colon_mm_ss()
    test_no_47_as_hours()
    test_omborga_merge_format()
    print("PASS test_time_display")
