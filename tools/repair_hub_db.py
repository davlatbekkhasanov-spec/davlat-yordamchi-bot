#!/usr/bin/env python3
"""
cross_bot_events ni qayta birlashtirish — 0 soniya / noto'g'ri merge tuzatish.

  python tools/repair_hub_db.py
  python tools/repair_hub_db.py --day 2026-06-08 --apply
  python tools/repair_hub_db.py --apply --db /data/data.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cross_bot_hub import DB_PATH  # noqa: E402
from hub_repair import repair_hub_db  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--day", default="")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    fixes = repair_hub_db(args.db, day=args.day, apply=args.apply)
    for fx in fixes:
        print(f"FIX {fx['day']} tg={fx['tg_id']} {fx['bot_key']}:")
        print(f"  was: {str(fx['was'])[:100]}")
        print(f"  now: {str(fx['now'])[:100]}")
    print(f"\nfixes: {len(fixes)}, applied: {args.apply}")


if __name__ == "__main__":
    main()
