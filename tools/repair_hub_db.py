#!/usr/bin/env python3
"""
cross_bot_events ni qayta birlashtirish — 0 soniya / noto'g'ri merge tuzatish.

  python tools/repair_hub_db.py
  python tools/repair_hub_db.py --day 2026-06-08 --apply
  python tools/repair_hub_db.py --apply --db /data/data.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cross_bot_hub import DB_PATH, _merge_hub_summary, init_schema  # noqa: E402

LOST_PATH = Path(__file__).with_name("hub_lost_events.json")


def _load_lost() -> list[dict]:
    if not LOST_PATH.is_file():
        return []
    with open(LOST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _replay(bot_key: str, summaries: list[str]) -> str:
    merged = ""
    for s in summaries:
        if not merged:
            merged = s
        else:
            merged = _merge_hub_summary(bot_key, merged, s)
    return merged


def _lost_for_group(lost_rows: list[dict], day: str, tg_id: int, bot_key: str, max_id: int) -> list[str]:
    out: list[str] = []
    for row in lost_rows:
        if row.get("day") != day or int(row.get("tg_id", 0)) != tg_id or row.get("bot_key") != bot_key:
            continue
        after = int(row.get("after_id") or 0)
        if after and after > max_id:
            continue
        summary = str(row.get("summary") or "").strip()
        if summary:
            out.append(summary)
    return out


def repair_db(
    db_path: str,
    *,
    day: str = "",
    apply: bool = False,
    lost_rows: list[dict] | None = None,
) -> list[dict]:
    lost_rows = lost_rows if lost_rows is not None else _load_lost()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_schema()

    q = "SELECT id, day, tg_id, bot_key, summary FROM cross_bot_events"
    params: list = []
    if day:
        q += " WHERE day = ?"
        params.append(day)
    q += " ORDER BY id ASC"
    rows = conn.execute(q, params).fetchall()

    groups: dict[tuple[str, int, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        key = (row["day"], int(row["tg_id"]), row["bot_key"])
        groups[key].append(row)

    fixes: list[dict] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for (d, tg, bot), evs in sorted(groups.items()):
        summaries = [r["summary"] for r in evs]
        max_id = max(int(r["id"]) for r in evs)
        for extra in _lost_for_group(lost_rows, d, tg, bot, max_id):
            if not any(extra in s or s in extra for s in summaries):
                summaries.append(extra)
        rebuilt = _replay(bot, summaries)
        latest = evs[-1]["summary"]
        if rebuilt == latest:
            continue
        fixes.append(
            {
                "day": d,
                "tg_id": tg,
                "bot_key": bot,
                "was": latest,
                "now": rebuilt,
                "last_id": int(evs[-1]["id"]),
            }
        )
        print(f"FIX {d} tg={tg} {bot}:")
        print(f"  was: {latest[:100]}")
        print(f"  now: {rebuilt[:100]}")
        if apply and rebuilt:
            conn.execute(
                """
                INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (d, tg, bot, rebuilt[:420], now),
            )

    if apply and fixes:
        conn.commit()
    conn.close()
    print(f"\nGroups checked: {len(groups)}, fixes: {len(fixes)}, applied: {apply}")
    return fixes


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--day", default="")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    repair_db(args.db, day=args.day, apply=args.apply)


if __name__ == "__main__":
    main()
