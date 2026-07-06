"""Hub (mesta / inventarizatsiya) → yordamchi reports jadvali."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta

from cross_bot_hub import DB_PATH, fetch_merged_latest_by_bot
from daily_report_card import (
    HUB_ONLY_CATEGORIES,
    hub_category_points,
)
from employee_registry import TG_EMPLOYEE, canonical_employee_name
from metrics_import import period_key_for_day, resolve_employee_name

log = logging.getLogger(__name__)

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To'lqin",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ravshanov Ziyodullo",
    "Ergashev Ozodbek",
    "Mustafoev Abdullo",
    "Tuvalov Farrux",
]


def employee_for_tg(tg_id: int) -> str | None:
    raw = TG_EMPLOYEE.get(int(tg_id))
    if not raw:
        return None
    return resolve_employee_name(canonical_employee_name(raw), EMPLOYEES) or resolve_employee_name(raw, EMPLOYEES)


async def hub_category_points_for_tg(tg_id: int, day_iso: str) -> dict[str, int]:
    events = await fetch_merged_latest_by_bot({int(tg_id)}, day_iso)
    return hub_category_points(events)


def _sync_reports_sync(
    conn: sqlite3.Connection,
    *,
    tg_id: int,
    day_iso: str,
    employee: str,
    points: dict[str, int],
) -> None:
    period = period_key_for_day(day_iso)
    now_iso = datetime.now().isoformat(timespec="seconds")
    cur = conn.cursor()
    for cat, pts in points.items():
        if cat not in HUB_ONLY_CATEGORIES:
            continue
        cur.execute(
            """
            DELETE FROM reports
            WHERE day = ? AND employee = ? AND category = ?
            """,
            (day_iso, employee, cat),
        )
        if pts <= 0:
            continue
        cur.execute(
            """
            INSERT INTO reports(day, period, tg_id, employee, category, value, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (day_iso, period, int(tg_id), employee, cat, int(pts), now_iso),
        )
    conn.commit()


async def sync_hub_categories_for_tg(tg_id: int, day_iso: str) -> dict[str, int]:
    """Hub dan kategoriya ballarini reports ga yozadi."""
    employee = employee_for_tg(tg_id)
    if not employee:
        return {}
    events = await fetch_merged_latest_by_bot({int(tg_id)}, day_iso)
    points = hub_category_points(events)
    # Bo'sh bo'lsa ham eski yozuvlarni tozalash
    full_pts = {cat: points.get(cat, 0) for cat in HUB_ONLY_CATEGORIES}
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    try:
        _sync_reports_sync(conn, tg_id=tg_id, day_iso=day_iso, employee=employee, points=full_pts)
    finally:
        conn.close()
    if points:
        log.info("Hub→reports %s %s: %s", day_iso, employee, points)
    return points


async def enrich_session_agg_from_hub(
    employee: str,
    day_iso: str,
    agg: dict[str, int],
    *,
    employee_tg_map: dict[str, int],
) -> dict[str, int]:
    """Hisobot uchun hub kategoriyalarini qo'shadi (reports bilan bir xil)."""
    from employee_tg_map import tg_ids_for_employee

    tg_set = tg_ids_for_employee(employee, employee_tg_map=employee_tg_map)
    if not tg_set:
        return agg
    events = await fetch_merged_latest_by_bot(tg_set, day_iso)
    hub_pts = hub_category_points(events)
    out = dict(agg)
    for cat, pts in hub_pts.items():
        if pts <= 0:
            continue
        out[cat] = pts
    return out


async def replay_hub_categories_for_day(day_iso: str) -> int:
    """Kun bo'yicha barcha hub xodimlarini reports ga qayta yozish."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT tg_id FROM cross_bot_events
            WHERE day = ? AND bot_key IN ('mesta', 'inventarizatsiya', 'prihod')
            """,
            (day_iso,),
        )
        tg_ids = [int(r["tg_id"]) for r in cur.fetchall()]
    finally:
        conn.close()
    n = 0
    for tg_id in tg_ids:
        if await sync_hub_categories_for_tg(tg_id, day_iso):
            n += 1
    return n


def hub_category_days_in_db() -> list[str]:
    """Mesta/inventarizatsiya bo'lgan kunlar."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT day FROM cross_bot_events
            WHERE bot_key IN ('mesta', 'inventarizatsiya', 'prihod')
            ORDER BY day
            """
        )
        return [str(r[0]) for r in cur.fetchall() if r and r[0]]
    finally:
        conn.close()


async def replay_hub_categories_all_days() -> tuple[int, int]:
    """Barcha kunlar va xodimlar — Места хр / Пересчет / Приход reports ni qayta yozish."""
    days = hub_category_days_in_db()
    total = 0
    for day in days:
        total += await replay_hub_categories_for_day(day)
    return len(days), total
