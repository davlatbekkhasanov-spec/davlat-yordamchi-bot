"""Kelishilgan ball qoidalari."""

from __future__ import annotations

import math
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from daily_report_card import score_bot_summary, _ceil_minutes


def test_ceil_minutes():
    assert _ceil_minutes(0) == 0
    assert _ceil_minutes(1) == 1
    assert _ceil_minutes(60) == 1
    assert _ceil_minutes(61) == 2
    assert _ceil_minutes(24 * 60 + 42) == 25


def test_omborga():
    pts, sec = score_bot_summary("omborga", "Reys 9, ish 24:42, dam 14:22")
    assert pts == 9 * 2 + 25 // 2  # 18 + 12 = 30
    assert sec == 24 * 60 + 42
    assert score_bot_summary("omborga", "Reys 0, ish 0:00, dam 5:00") == (0, 0)


def test_ombor():
    assert score_bot_summary("ombor", "Ombor (jami): 1 ta, ish vaqti 1377 soniya") == (23, 1377)
    assert score_bot_summary("ombor", "ish vaqti 0 soniya") == (0, 0)


def test_yuk():
    assert score_bot_summary("yuk", "Yuk (jami): ish vaqti 6840 soniya") == (57, 6840)
    assert score_bot_summary("yuk", "Yuk (bugun jami): ish vaqti 48:30") == (24, 48 * 60 + 30)
    assert score_bot_summary("yuk", "Yuk (bugun jami): ish vaqti 0:00") == (0, 0)


def test_sklad():
    assert score_bot_summary("sklad", "Sklad (forward jami): sanaldi 5") == (10, 0)


def test_ishxona():
    assert score_bot_summary("ishxona", "Ishxona: ochiq=2, yopilgan=0, rad=0") == (-80, 0)
    assert score_bot_summary("ishxona", "Ishxona: ochiq=0, yopilgan=1, rad=0") == (0, 0)
    assert score_bot_summary("ishxona", "admin_card\n\n✅ Бартараф этилди") == (0, 0)
    assert score_bot_summary("ishxona", "Shikoyat (Tolib): test") == (-40, 0)


def test_ombor_17h_capped():
    from daily_report_card import _MAX_DAILY_WORK_SEC

    pts, sec = score_bot_summary(
        "ombor", "#55 bajarildi, 17 soat 3 daqiqa 49 soniya"
    )
    assert sec <= _MAX_DAILY_WORK_SEC
    assert pts <= 720


def test_mesta():
    # 10 poz norma 30 daq; 27 daqda bajarildi → 3 daq tejash = 1 ball
    assert score_bot_summary("mesta", "Mesta: poz 10, ish 27:00, dam 0:00, tejash 3:00, bekor 0:00") == (1, 27 * 60)
    # Normada — ball yo'q
    assert score_bot_summary("mesta", "Mesta: poz 10, ish 30:00, dam 0:00, tejash 0:00, bekor 0:00") == (0, 30 * 60)
    # 6 daq tejash = 2 ball
    assert score_bot_summary("mesta", "Mesta: poz 10, ish 24:00, dam 0:00, tejash 6:00, bekor 0:00") == (2, 24 * 60)
    # Ortda qolsa — ball yo'q
    assert score_bot_summary("mesta", "Mesta: poz 10, ish 35:00, dam 0:00, tejash 0:00, bekor 5:00") == (0, 35 * 60)
    assert score_bot_summary("mesta", "Mesta: poz 0, ish 0:00, dam 0:00, bekor 0:00") == (0, 0)
    # ≥1 soat tejash — H:MM:SS
    assert score_bot_summary(
        "mesta", "Mesta: poz 33, ish 13:30, dam 0:00, tejash 1:25:30, bekor 0:00, kaizen 28"
    ) == (28, 13 * 60 + 30)
    # kaizen maydoni ustuvor
    assert score_bot_summary(
        "mesta", "Mesta: poz 13, ish 7:49, dam 0:00, tejash 0:00, bekor 0:00, kaizen 10"
    ) == (10, 7 * 60 + 49)


def test_omborga_982_ignored():
    pts, sec = score_bot_summary("omborga", "Reys 18, yuk 522m, ish 982:00, dam 6:12")
    assert pts == 36
    assert sec == 0


if __name__ == "__main__":
    test_ceil_minutes()
    test_omborga()
    test_ombor()
    test_yuk()
    test_sklad()
    test_ishxona()
    test_ombor_17h_capped()
    test_mesta()
    test_omborga_982_ignored()
    print("PASS test_score_rules")
