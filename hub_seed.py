"""Boshlang'ich hub ma'lumotlari — bot ishga tushganda avtomatik."""

from __future__ import annotations

HUB_SEED_VERSION = 3

# (day, tg_id, bot_key, summary)
HUB_SEED_ROWS: tuple[tuple[str, int, str, str], ...] = (
    # 2026-06-02
    ("2026-06-02", 6931958983, "ombor", "Ombor (forward jami): 2 ta, ish vaqti 2647 soniya"),
    ("2026-06-02", 5412958249, "yuk", "Yuk (forward jami): ish vaqti 2957 soniya"),
    ("2026-06-02", 8440127425, "ombor", "Ombor (forward jami): 1 ta, ish vaqti 534 soniya"),
    ("2026-06-02", 8547365654, "ombor", "Ombor (forward jami): 2 ta, ish vaqti 3429 soniya"),
    ("2026-06-02", 8547365654, "omborga", "Reys 9, ish 24:42, dam 14:22"),
    ("2026-06-02", 6991673998, "ombor", "Ombor (forward jami): 1 ta, ish vaqti 9 soniya"),
    ("2026-06-02", 5465963344, "yuk", "Yuk (forward jami): ish vaqti 3457 soniya"),
    ("2026-06-02", 5732350707, "ombor", "Ombor (forward jami): 2 ta, ish vaqti 1878 soniya"),
    # 2026-06-03
    ("2026-06-03", 6931958983, "ombor", "Ombor (forward jami): 4 ta, ish vaqti 3632 soniya"),
    ("2026-06-03", 6931958983, "omborga", "Reys 5, ish 8:33, dam 5:37"),
    ("2026-06-03", 5412958249, "ombor", "Ombor (forward jami): 3 ta, ish vaqti 3534 soniya"),
    ("2026-06-03", 8440127425, "ombor", "Ombor (forward jami): 2 ta, ish vaqti 683 soniya"),
    ("2026-06-03", 8440127425, "omborga", "Reys 3, ish 19:46, dam 0:00"),
    ("2026-06-03", 8547365654, "ombor", "Ombor (forward jami): 1 ta, ish vaqti 5907 soniya"),
    # 2026-06-04 — to'liq forward (04.06.2026, oxirgi log bilan)
    ("2026-06-04", 8440127425, "ombor", "Ombor (forward jami): 6 ta, ish vaqti 7342 soniya"),
    ("2026-06-04", 8440127425, "omborga", "Reys 3, ish 0:08:32, dam 0:00:48"),
    ("2026-06-04", 8547365654, "ombor", "Ombor (forward jami): 5 ta, ish vaqti 3861 soniya"),
    ("2026-06-04", 8547365654, "omborga", "Reys 36, ish 4:03:03, dam 2:33:52"),
    ("2026-06-04", 5732350707, "ombor", "Ombor (forward jami): 2 ta, ish vaqti 2852 soniya"),
    ("2026-06-04", 5732350707, "omborga", "Reys 10, ish 2:46:00, dam 1:30:00"),
    ("2026-06-04", 5465963344, "omborga", "Reys 9, ish 3:49:33, dam 0:00"),
    ("2026-06-04", 6001619806, "omborga", "Reys 1, ish 1:26:55, dam 0:00"),
    ("2026-06-04", 6931958983, "ombor", "Ombor (forward jami): 1 ta, ish vaqti 1622 soniya"),
    ("2026-06-04", 5412958249, "ombor", "Ombor (forward jami): 2 ta, ish vaqti 1255 soniya"),
    ("2026-06-04", 5412958249, "omborga", "Reys 18, ish 16:34, dam 0:00"),
)
