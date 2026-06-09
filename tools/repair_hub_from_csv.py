#!/usr/bin/env python3
"""
Hub CSV dan ombor/omborga yozuvlarini qayta birlashtirish (0 soniya tuzatish).

Ishlatish:
  python tools/repair_hub_from_csv.py hub_events.csv --apply

--apply bo'lmasa faqat ko'rsatadi.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cross_bot_hub import _merge_hub_summary  # noqa: E402


def rebuild(rows: list[dict]) -> dict[tuple[str, int, str], str]:
    """(day, tg_id, bot_key) -> to'g'ri merged summary."""
    groups: dict[tuple[str, int, str], list[str]] = defaultdict(list)
    for r in rows:
        key = (r["day"], int(r["tg_id"]), r["bot_key"])
        groups[key].append(r["summary"])

    out: dict[tuple[str, int, str], str] = {}
    for key, summaries in groups.items():
        merged = ""
        for s in summaries:
            if not merged:
                merged = s
            else:
                merged = _merge_hub_summary(key[2], merged, s)
        out[key] = merged
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("csv_path")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--day", default="", help="Faqat shu kun (2026-06-08)")
    args = p.parse_args()

    with open(args.csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if args.day:
        rows = [r for r in rows if r["day"] == args.day]

    fixed = rebuild(rows)
    bad = 0
    for (day, tg, bot), summary in sorted(fixed.items()):
        if bot == "ombor" and "0 soniya" in summary and "0 ta" in summary:
            # try find if any raw had data
            raw = [r for r in rows if r["day"] == day and int(r["tg_id"]) == tg and r["bot_key"] == bot]
            if any("bajarildi" in r["summary"] and "0 soniya" not in r["summary"] for r in raw):
                bad += 1
                print(f"FIX {day} tg={tg} {bot}:")
                print(f"  was: {raw[-1]['summary'][:80]}")
                print(f"  now: {summary}")
        elif bot in ("ombor", "omborga"):
            last = [r for r in rows if r["day"] == day and int(r["tg_id"]) == tg and r["bot_key"] == bot][-1]
            if last["summary"] != summary:
                print(f"DIFF {day} tg={tg} {bot}:")
                print(f"  db_last: {last['summary'][:90]}")
                print(f"  rebuilt: {summary[:90]}")

    print(f"\nGroups: {len(fixed)}, need fix hints: {bad}")
    if not args.apply:
        print("Qo'llash uchun: --apply (keyin DB skriptini alohida yozing)")


if __name__ == "__main__":
    main()
