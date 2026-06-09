"""Hub merge — ombor #47+#51+#55 nolga tushmasligi."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cross_bot_hub import _merge_hub_summary  # noqa: E402
from daily_report_card import score_bot_summary  # noqa: E402


def test_ombor_two_orders_not_zero():
    a = "#47 🙋 Xizmat so'rovi: bajarildi, 50 daqiqa 26 soniya"
    b = "#51 🙋 Xizmat so'rovi: bajarildi, 53 daqiqa 36 soniya"
    merged = _merge_hub_summary("ombor", a, b)
    assert "0 soniya" not in merged, merged
    pts, sec = score_bot_summary("ombor", merged)
    assert sec > 6000, (sec, merged)
    assert pts > 100, (pts, merged)


def test_ombor_three_orders_sindor_day():
    a = "#47 🙋 Xizmat so'rovi: bajarildi, 50 daqiqa 26 soniya"
    b = _merge_hub_summary(
        "ombor",
        a,
        "#51 🙋 Xizmat so'rovi: bajarildi, 53 daqiqa 36 soniya",
    )
    merged = _merge_hub_summary(
        "ombor",
        b,
        "#55 📦 Tovar buyurtma: bajarildi, 10 daqiqa 50 soniya",
    )
    pts, sec = score_bot_summary("ombor", merged)
    assert sec >= 6800, (sec, merged)
    assert pts >= 110, (pts, merged)


def test_ombor_cumulative_replaces_not_adds():
    old = "Ombor (bugun jami): 2 ta, ish vaqti 3000 soniya"
    new = "Ombor (bugun jami): 3 ta, ish vaqti 6892 soniya"
    merged = _merge_hub_summary("ombor", old, new)
    assert merged == new
    pts, sec = score_bot_summary("ombor", merged)
    assert sec == 6892
    assert pts == 115  # ceil(6892/60)


def test_ombor_cumulative_after_legacy_per_order():
    legacy = _merge_hub_summary(
        "ombor",
        "#47 🙋 Xizmat so'rovi: bajarildi, 50 daqiqa 26 soniya",
        "#51 🙋 Xizmat so'rovi: bajarildi, 53 daqiqa 36 soniya",
    )
    fixed = "Ombor (bugun jami): 3 ta, ish vaqti 6892 soniya"
    merged = _merge_hub_summary("ombor", legacy, fixed)
    assert merged == fixed


def test_ombor_zero_cumulative_does_not_wipe():
    good = "Ombor (jami): 2 ta, ish vaqti 6242 soniya"
    bad = "Ombor (jami): 0 ta, ish vaqti 0 soniya"
    assert _merge_hub_summary("ombor", good, bad) == good
    chain = "#47 🙋 Xizmat so'rovi: bajarildi, 50 daqiqa 26 soniya"
    chain = _merge_hub_summary(
        "ombor",
        chain,
        "#51 🙋 Xizmat so'rovi: bajarildi, 53 daqiqa 36 soniya",
    )
    chain = _merge_hub_summary("ombor", chain, bad)
    pts, sec = score_bot_summary("ombor", chain)
    assert sec > 6000, (sec, chain)


def test_omborga_sessions_sum():
    s1 = "Reys 5, yuk 190m, ish 3:29, dam 1:10"
    s2 = "Reys 10, yuk 364m, ish 22:36, dam 3:58"
    merged = _merge_hub_summary("omborga", s1, s2)
    assert "Reys 15" in merged, merged
    pts, _ = score_bot_summary("omborga", merged)
    assert pts > score_bot_summary("omborga", s2)[0]


def test_omborga_seed_not_doubled_with_trips():
    from cross_bot_hub import _best_omborga_daily, _replay_merged_by_bot
    from daily_report_card import score_bot_summary

    summaries = [
        "Reys 21, ish 55:36, dam 0:00",
        "Reys 2, yuk 138m, ish 7:06, dam 3:14",
        "Reys 6, yuk 222m, ish 12:56, dam 7:53",
    ]
    merged = _best_omborga_daily(summaries)
    pts, _ = score_bot_summary("omborga", merged)
    assert "Reys 21" in merged, merged
    assert pts < 120, (pts, merged)
    rows = [{"bot_key": "omborga", "summary": s} for s in summaries]
    assert _replay_merged_by_bot(rows)["omborga"] == merged


def test_fetch_replay_not_latest_zero():
    from cross_bot_hub import _replay_merged_by_bot

    rows = [
        {"bot_key": "ombor", "summary": "#47 bajarildi, 50 daqiqa 26 soniya"},
        {"bot_key": "ombor", "summary": "Ombor (jami): 0 ta, ish vaqti 0 soniya"},
        {"bot_key": "ombor", "summary": "#51 bajarildi, 53 daqiqa 36 soniya"},
    ]
    out = _replay_merged_by_bot(rows)
    pts, sec = score_bot_summary("ombor", out["ombor"])
    assert sec > 6000, (sec, out["ombor"])
    assert "0 soniya" not in out["ombor"]


if __name__ == "__main__":
    test_fetch_replay_not_latest_zero()
    test_ombor_two_orders_not_zero()
    test_ombor_three_orders_sindor_day()
    test_ombor_cumulative_replaces_not_adds()
    test_ombor_cumulative_after_legacy_per_order()
    test_omborga_sessions_sum()
    print("PASS test_hub_merge")
