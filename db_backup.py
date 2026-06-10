"""SQLite backup/export/restore — deploy oldin zaxira va qo'lda tiklash."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

TABLES = (
    "reports",
    "cross_bot_events",
    "employee_links",
    "employee_pins",
    "monthly_plans",
    "ranking_broadcasts",
)


def _now_stamp() -> str:
    return datetime.now(TZ).strftime("%Y%m%d_%H%M%S")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    try:
        cur = conn.execute(f"SELECT * FROM {table} ORDER BY rowid")
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def export_payload(db_path: str) -> dict:
    conn = _connect(db_path)
    try:
        payload = {
            "exported_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "db_path": db_path,
            "tables": {},
        }
        for table in TABLES:
            payload["tables"][table] = _rows(conn, table)
        payload["counts"] = {t: len(payload["tables"][t]) for t in TABLES}
        return payload
    finally:
        conn.close()


def payload_to_json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def payload_to_reports_csv(payload: dict) -> bytes:
    rows = payload.get("tables", {}).get("reports", [])
    buf = io.StringIO()
    fields = ["id", "day", "period", "tg_id", "employee", "category", "value", "created_at"]
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8-sig")


def payload_to_summary_csv(payload: dict) -> bytes:
    """Xodim/kun bo'yicha jami — qo'lda kiritish uchun oson."""
    rows = payload.get("tables", {}).get("reports", [])
    agg: dict[tuple[str, str, str], int] = {}
    for r in rows:
        key = (r.get("employee", ""), r.get("day", ""), r.get("category", ""))
        agg[key] = agg.get(key, 0) + int(r.get("value") or 0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["employee", "day", "category", "total_value"])
    for (emp, day, cat), val in sorted(agg.items()):
        w.writerow([emp, day, cat, val])
    return buf.getvalue().encode("utf-8-sig")


def payload_to_hub_csv(payload: dict) -> bytes:
    rows = payload.get("tables", {}).get("cross_bot_events", [])
    buf = io.StringIO()
    fields = ["id", "day", "tg_id", "bot_key", "summary", "created_at"]
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8-sig")


def copy_db_file(db_path: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"data_{_now_stamp()}.db")
    shutil.copy2(db_path, dst)
    return dst


def write_backup_files(db_path: str, out_dir: str) -> dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    stamp = _now_stamp()
    payload = export_payload(db_path)
    files: dict[str, str] = {}

    json_path = os.path.join(out_dir, f"backup_{stamp}.json")
    with open(json_path, "wb") as f:
        f.write(payload_to_json_bytes(payload))
    files["json"] = json_path

    reports_csv = os.path.join(out_dir, f"reports_{stamp}.csv")
    with open(reports_csv, "wb") as f:
        f.write(payload_to_reports_csv(payload))
    files["reports_csv"] = reports_csv

    summary_csv = os.path.join(out_dir, f"summary_{stamp}.csv")
    with open(summary_csv, "wb") as f:
        f.write(payload_to_summary_csv(payload))
    files["summary_csv"] = summary_csv

    hub_csv = os.path.join(out_dir, f"hub_events_{stamp}.csv")
    with open(hub_csv, "wb") as f:
        f.write(payload_to_hub_csv(payload))
    files["hub_csv"] = hub_csv

    if os.path.isfile(db_path):
        db_copy = os.path.join(out_dir, f"data_{stamp}.db")
        shutil.copy2(db_path, db_copy)
        files["db_copy"] = db_copy

    return files


def restore_reports_from_json(db_path: str, backup_json_path: str, *, replace: bool = False) -> dict:
    with open(backup_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    reports = payload.get("tables", {}).get("reports", [])
    if not reports:
        return {"ok": False, "message": "reports bo'sh", "inserted": 0}

    conn = _connect(db_path)
    try:
        if replace:
            conn.execute("DELETE FROM reports")
        inserted = 0
        for r in reports:
            if not replace:
                ex = conn.execute(
                    """
                    SELECT 1 FROM reports
                    WHERE day=? AND employee=? AND category=? AND value=?
                    LIMIT 1
                    """,
                    (r["day"], r["employee"], r["category"], int(r["value"])),
                ).fetchone()
                if ex:
                    continue
            conn.execute(
                """
                INSERT INTO reports(day, period, tg_id, employee, category, value, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["day"],
                    r["period"],
                    int(r["tg_id"]),
                    r["employee"],
                    r["category"],
                    int(r["value"]),
                    r.get("created_at") or datetime.now(TZ).isoformat(timespec="seconds"),
                ),
            )
            inserted += 1
        conn.commit()
        return {"ok": True, "inserted": inserted, "replace": replace}
    finally:
        conn.close()


def restore_links_from_json(db_path: str, backup_json_path: str, *, replace: bool = False) -> dict:
    with open(backup_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    links = payload.get("tables", {}).get("employee_links", [])
    pins = payload.get("tables", {}).get("employee_pins", [])
    conn = _connect(db_path)
    try:
        if replace:
            conn.execute("DELETE FROM employee_links")
            conn.execute("DELETE FROM employee_pins")
        link_n = 0
        for r in links:
            conn.execute(
                "INSERT OR REPLACE INTO employee_links(tg_id, employee) VALUES (?, ?)",
                (int(r["tg_id"]), r["employee"]),
            )
            link_n += 1
        pin_n = 0
        for r in pins:
            conn.execute(
                "INSERT OR REPLACE INTO employee_pins(employee, pin) VALUES (?, ?)",
                (r["employee"], r["pin"]),
            )
            pin_n += 1
        conn.commit()
        return {"ok": True, "links": link_n, "pins": pin_n, "replace": replace}
    finally:
        conn.close()


def restore_all_from_json(db_path: str, backup_json_path: str, *, replace: bool = False) -> dict:
    """JSON zaxiradan mavjud jadvallarni tiklash."""
    out: dict = {"reports": {}, "hub": {}, "links": {}}
    out["reports"] = restore_reports_from_json(db_path, backup_json_path, replace=replace)
    out["hub"] = restore_hub_from_json(db_path, backup_json_path, replace=replace)
    out["links"] = restore_links_from_json(db_path, backup_json_path, replace=replace)
    with open(backup_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    out["counts_source"] = payload.get("counts", {})
    return out


def restore_hub_from_json(db_path: str, backup_json_path: str, *, replace: bool = False) -> dict:
    with open(backup_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    events = payload.get("tables", {}).get("cross_bot_events", [])
    if not events:
        return {"ok": False, "message": "cross_bot_events bo'sh", "inserted": 0}

    conn = _connect(db_path)
    try:
        if replace:
            conn.execute("DELETE FROM cross_bot_events")
        inserted = 0
        for r in events:
            if not replace:
                ex = conn.execute(
                    """
                    SELECT 1 FROM cross_bot_events
                    WHERE day=? AND tg_id=? AND bot_key=? AND summary=?
                    LIMIT 1
                    """,
                    (r["day"], int(r["tg_id"]), r["bot_key"], r["summary"]),
                ).fetchone()
                if ex:
                    continue
            conn.execute(
                """
                INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    r["day"],
                    int(r["tg_id"]),
                    r["bot_key"],
                    r["summary"],
                    r.get("created_at") or datetime.now(TZ).isoformat(timespec="seconds"),
                ),
            )
            inserted += 1
        conn.commit()
        return {"ok": True, "inserted": inserted, "replace": replace}
    finally:
        conn.close()
