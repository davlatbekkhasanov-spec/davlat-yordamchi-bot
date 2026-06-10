"""Deploydan keyin bo'sh DB ni kod ichidagi baseline dan tiklash."""

from __future__ import annotations

import logging
import os
import sqlite3

log = logging.getLogger(__name__)

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "data", "baseline_history.json")
MIN_REPORTS_FOR_OK = 100
MIN_HUB_FOR_OK = 60
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


def _init_db_schema(db_path: str) -> None:
    """Yangi DB fayl — jadvallar bo'lmasa yaratish."""
    import sqlite3

    from cross_bot_hub import init_schema as init_hub_schema

    init_hub_schema()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                period TEXT NOT NULL,
                tg_id INTEGER NOT NULL,
                employee TEXT NOT NULL,
                category TEXT NOT NULL,
                value INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS employee_links (
                tg_id INTEGER PRIMARY KEY,
                employee TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS employee_pins (
                employee TEXT PRIMARY KEY,
                pin TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS monthly_plans (
                period TEXT NOT NULL,
                employee TEXT NOT NULL,
                category TEXT NOT NULL,
                plan_value INTEGER NOT NULL,
                PRIMARY KEY (period, employee, category)
            );
            CREATE TABLE IF NOT EXISTS ranking_broadcasts (
                day TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_baseline_restored(db_path: str) -> dict:
    """DB kam bo'lsa baseline dan tiklash — mavjud yozuvlarni o'chirmaydi."""
    if not os.path.isfile(BASELINE_PATH):
        return {"ok": False, "reason": "baseline yo'q"}

    _init_db_schema(db_path)
    before_r = _report_count(db_path)
    before_h = _hub_count(db_path)
    if not _needs_restore(db_path):
        return {"ok": True, "skipped": True, "reports": before_r, "hub": before_h}

    from db_backup import restore_all_from_json

    wipe = before_r == 0 and before_h == 0
    res = restore_all_from_json(db_path, BASELINE_PATH, replace=wipe)
    after_r = _report_count(db_path)
    after_h = _hub_count(db_path)
    log.warning(
        "Baseline %s: hisobot %s→%s, hub %s→%s",
        "to'liq" if wipe else "merge",
        before_r,
        after_r,
        before_h,
        after_h,
    )
    return {
        "ok": True,
        "restored": True,
        "merged": not wipe,
        "before": before_r,
        "after": after_r,
        "hub_before": before_h,
        "hub_after": after_h,
        "detail": res,
    }
