"""Hub DB ni qayta birlashtirish (startup va /repairhub)."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from cross_bot_hub import _best_omborga_daily, _best_yuk_daily, _merge_hub_summary, init_schema

LOST_PATH = Path(__file__).resolve().parent / "tools" / "hub_lost_events.json"


def _load_lost() -> list[dict]:
    if not LOST_PATH.is_file():
        return []
    with open(LOST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _replay(bot_key: str, summaries: list[str]) -> str:
    if bot_key == "omborga":
        return _best_omborga_daily(summaries)
    if bot_key == "yuk":
        return _best_yuk_daily(summaries)
    merged = ""
    for s in summaries:
        if not merged:
            merged = s
        else:
            merged = _merge_hub_summary(bot_key, merged, s)
    return merged


def _lost_for_group(
    lost_rows: list[dict], day: str, tg_id: int, bot_key: str, max_id: int
) -> list[str]:
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


def repair_hub_db(db_path: str, *, day: str = "", apply: bool = False) -> list[dict]:
    lost_rows = _load_lost()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_schema()

    q = "SELECT id, day, tg_id, bot_key, summary FROM cross_bot_events"
    params: list = []
    if day:
        q += " WHERE day = ?"
        params.append(day)
    rows = conn.execute(q + " ORDER BY id ASC", params).fetchall()

    groups: dict[tuple[str, int, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        groups[(row["day"], int(row["tg_id"]), row["bot_key"])].append(row)

    fixes: list[dict] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for (d, tg, bot), evs in groups.items():
        summaries = [r["summary"] for r in evs]
        max_id = max(int(r["id"]) for r in evs)
        for extra in _lost_for_group(lost_rows, d, tg, bot, max_id):
            if not any(extra in s or s in extra for s in summaries):
                summaries.append(extra)
        rebuilt = _replay(bot, summaries)
        if not rebuilt and bot == "yuk":
            rebuilt = "Yuk (jami): ish vaqti 0 soniya"
        latest = evs[-1]["summary"]
        needs_collapse = bot == "yuk" and len(evs) > 1
        if not rebuilt or (rebuilt == latest and not needs_collapse):
            continue
        fixes.append({"day": d, "tg_id": tg, "bot_key": bot, "was": latest, "now": rebuilt})
        if apply:
            conn.execute(
                "DELETE FROM cross_bot_events WHERE day = ? AND tg_id = ? AND bot_key = ?",
                (d, tg, bot),
            )
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
    return fixes
