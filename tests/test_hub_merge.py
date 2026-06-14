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


def test_omborga_live_high_reys_not_daily_total():
    """Jonli Reys 18/22 — sessiyalar yig'indisi, bitta qator emas."""
    from cross_bot_hub import _best_omborga_daily, _omborga_looks_daily_total
    from daily_report_card import score_bot_summary

    live18 = "Reys 18, yuk 270m, ish 6:02, dam 0:33"
    live22 = "Reys 22, yuk 330m, ish 8:52, dam 0:31"
    assert not _omborga_looks_daily_total(live18)
    assert not _omborga_looks_daily_total(live22)
    rows = [
        "Reys 1, yuk 37m, ish 2:08, dam 0:48",
        "Reys 12, yuk 324m, ish 11:00, dam 0:42",
        "Reys 4, yuk 108m, ish 3:23, dam 0:13",
        live18,
        live22,
        "Reys 7, yuk 105m, ish 2:45, dam 0:14",
    ]
    merged = _best_omborga_daily(rows)
    pts, sec = score_bot_summary("omborga", merged)
    assert "Reys 22" not in merged or "Reys 3" in merged or pts > 50, (pts, sec, merged)
    assert pts > 50, (pts, sec, merged)
    assert sec > 2000, (pts, sec, merged)


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


def test_yuk_zero_does_not_wipe():
    good = "Yuk (forward jami): ish vaqti 3457 soniya"
    bad = "Yuk (bugun jami): ish vaqti 0:00"
    assert _merge_hub_summary("yuk", good, bad) == good
    merged = _merge_hub_summary("yuk", bad, good)
    assert "3457" in merged, merged


def test_mesta_multiple_sessions_sum_kaizen():
    """Bir kunda 5 ta mesta yakuni — botdagi kabi ball yig'indisi."""
    from cross_bot_hub import _merge_mesta_daily, _replay_merged_by_bot
    from daily_report_card import score_bot_summary

    sessions = [
        "Mesta: poz 13, ish 7:49, dam 0:00, tejash 31:11, bekor 0:00, kaizen 10",
        "Mesta: poz 15, ish 9:33, dam 0:00, tejash 35:27, bekor 0:00, kaizen 11",
        "Mesta: poz 33, ish 13:30, dam 0:00, tejash 1:25:30, bekor 0:00, kaizen 28",
        "Mesta: poz 11, ish 5:16, dam 0:00, tejash 27:44, bekor 0:00, kaizen 9",
        "Mesta: poz 18, ish 7:34, dam 0:00, tejash 46:26, bekor 0:00, kaizen 15",
    ]
    per = [score_bot_summary("mesta", s)[0] for s in sessions]
    assert per == [10, 11, 28, 9, 15]
    assert sum(per) == 73

    merged = _merge_mesta_daily(sessions)
    assert "poz 90" in merged
    assert "kaizen 73" in merged
    assert score_bot_summary("mesta", merged)[0] == 73

    rows = [{"bot_key": "mesta", "summary": s} for s in sessions]
    replay = _replay_merged_by_bot(rows)["mesta"]
    assert score_bot_summary("mesta", replay)[0] == 73


    a = "Yuk (bugun jami): ish vaqti 1200 soniya"
    b = "Yuk (bugun jami): ish vaqti 2400 soniya"
    merged = _merge_hub_summary("yuk", a, b)
    assert "2400" in merged, merged
    assert "3600" not in merged, merged


def test_yuk_per_session_max_not_sum():
    """Eski format (jami yo'q) — qo'shilmasin, eng kattasi."""
    from cross_bot_hub import _best_yuk_daily, _replay_merged_by_bot

    rows = [{"bot_key": "yuk", "summary": f"Yuk #{i}: ish vaqti 4500 soniya"} for i in range(1, 4)]
    merged = _replay_merged_by_bot(rows)["yuk"]
    assert "4500" in merged, merged
    assert "13500" not in merged, merged
    assert _best_yuk_daily([r["summary"] for r in rows]) == merged


def test_yuk_live_inflation_abdullo_case():
    """Jonli pushlar 13500 soniya — rasmiy yakun yo'q, 0 bo'lishi kerak."""
    from cross_bot_hub import _best_yuk_daily, _replay_merged_by_bot

    rows = [
        {"bot_key": "yuk", "summary": f"Yuk (bugun jami): ish vaqti {i * 450} soniya"}
        for i in range(1, 31)
    ]
    merged = _replay_merged_by_bot(rows)["yuk"]
    assert "0 soniya" in merged, merged
    assert "13500" not in merged, merged


def test_yuk_single_3h_without_yakun_zeroed():
    from cross_bot_hub import _best_yuk_daily

    s = "Yuk (jami): ish vaqti 13500 soniya"
    out = _best_yuk_daily([s])
    assert "0 soniya" in out, out


def test_yuk_official_yakun_wins():
    from cross_bot_hub import _best_yuk_daily

    legacy = [f"Yuk (bugun jami): ish vaqti {i * 450} soniya" for i in range(1, 20)]
    official = "Yuk (yakun): ish vaqti 1847 soniya"
    out = _best_yuk_daily(legacy + [official])
    assert "1847" in out, out
    assert "13500" not in out, out


def test_yuk_mm_ss_parsed():
    from cross_bot_hub import _parse_yuk_ish_sec

    assert _parse_yuk_ish_sec("yuk (bugun jami): ish vaqti 48:30") == 48 * 60 + 30
    assert _parse_yuk_ish_sec("yuk (bugun jami): ish vaqti 0:45") == 45


def test_ombor_replay_ignores_zero_spam():
    from cross_bot_hub import _replay_merged_by_bot

    rows = [
        {"bot_key": "ombor", "summary": "#2 bajarildi, 7 daqiqa 3 soniya"},
        {"bot_key": "ombor", "summary": "Ombor (jami): 0 ta, ish vaqti 0 soniya"},
        {"bot_key": "ombor", "summary": "Ombor (jami): 0 ta, ish vaqti 0 soniya"},
    ]
    out = _replay_merged_by_bot(rows)["ombor"]
    pts, sec = score_bot_summary("ombor", out)
    assert sec > 400, (sec, out)
    assert "0 soniya" not in out or sec > 0


def test_sklad_sanaldi_summed():
    from cross_bot_hub import _replay_merged_by_bot

    rows = [
        {"bot_key": "sklad", "summary": "Papka A: sanaldi 1, joy 1, xato 0, kun 1/28"},
        {"bot_key": "sklad", "summary": "Papka B: sanaldi 1, joy 1, xato 0, kun 2/28"},
        {"bot_key": "sklad", "summary": "Papka C: sanaldi 1, joy 1, xato 0, kun 3/28"},
    ]
    out = _replay_merged_by_bot(rows)["sklad"]
    pts, _ = score_bot_summary("sklad", out)
    assert pts == 6, (pts, out)
    assert "sanaldi 3" in out.lower(), out


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
    test_ombor_replay_ignores_zero_spam()
    test_sklad_sanaldi_summed()
    print("PASS test_hub_merge")
