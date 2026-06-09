"""Deploydan keyin bo'sh DB ni kod ichidagi baseline dan tiklash."""

from __future__ import annotations

import logging
import os
import sqlite3

log = logging.getLogger(__name__)

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "data", "baseline_history.json")
MIN_REPORTS_FOR_OK = 80
MIN_HUB_FOR_OK = 40
MIN_DB_BYTES_FOR_OK = 48 * 1024


def _report_count(db_path: str) -> int:
    if not os.path.isfile(db_path):
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM reports").fetchone()
        return int(row[0] or 0)
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _hub_count(db_path: str) -> int:
    if not os.path.isfile(db_path):
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM cross_bot_events").fetchone()
        return int(row[0] or 0)
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _needs_restore(db_path: str) -> bool:
    n = _report_count(db_path)
    h = _hub_count(db_path)
    if n >= MIN_REPORTS_FOR_OK and h >= MIN_HUB_FOR_OK:
        return False
    if os.path.isfile(db_path):
        if os.path.getsize(db_path) < MIN_DB_BYTES_FOR_OK and n < MIN_REPORTS_FOR_OK:
            return True
    return n < MIN_REPORTS_FOR_OK or h < MIN_HUB_FOR_OK


def ensure_baseline_restored(db_path: str) -> dict:
    """DB juda bo'sh bo'lsa baseline_history.json dan to'liq tiklash."""
    if not os.path.isfile(BASELINE_PATH):
        return {"ok": False, "reason": "baseline yo'q"}
    n = _report_count(db_path)
    if not _needs_restore(db_path):
        return {"ok": True, "skipped": True, "reports": n, "hub": _hub_count(db_path)}

    from db_backup import restore_all_from_json

    res = restore_all_from_json(db_path, BASELINE_PATH, replace=True)
    after = _report_count(db_path)
    log.warning(
        "Baseline tiklandi: %s -> %s hisobot (hub: %s)",
        n,
        after,
        (res.get("hub") or {}).get("inserted"),
    )
    return {"ok": True, "restored": True, "before": n, "after": after, "detail": res}
