"""Ishga tushganda: tiklash, hub tuzatish, admin xabari."""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any

from persist_data import has_railway_volume, persistence_status_line

log = logging.getLogger(__name__)


def collect_db_stats(db_path: str) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "db_path": db_path,
        "size_kb": 0,
        "reports": 0,
        "hub_events": 0,
        "links": 0,
        "volume": has_railway_volume(),
        "mount": os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "") or "—",
    }
    if not os.path.isfile(db_path):
        return stats
    stats["size_kb"] = os.path.getsize(db_path) // 1024
    try:
        conn = sqlite3.connect(db_path)
        stats["reports"] = int(conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] or 0)
        stats["hub_events"] = int(
            conn.execute("SELECT COUNT(*) FROM cross_bot_events").fetchone()[0] or 0
        )
        stats["links"] = int(
            conn.execute("SELECT COUNT(*) FROM employee_links").fetchone()[0] or 0
        )
        conn.close()
    except sqlite3.Error as exc:
        stats["error"] = str(exc)
    return stats


def format_startup_admin_message(stats: dict, maintenance: dict) -> str:
    vol = "✅" if stats.get("volume") else "❌"
    lines = [
        "🚀 <b>Bot ishga tushdi</b>",
        "",
        f"💾 {html_esc(persistence_status_line(stats.get('db_path', '')))}",
        f"📊 Hisobotlar: <b>{stats.get('reports', 0)}</b>",
        f"🔗 Hub yozuvlar: <b>{stats.get('hub_events', 0)}</b>",
        f"👥 Ulangan xodimlar: <b>{stats.get('links', 0)}</b>",
        f"📦 Volume: {vol} ({html_esc(str(stats.get('mount', '—')))})",
    ]

    br = maintenance.get("baseline") or {}
    if br.get("restored"):
        lines.append(
            f"♻️ Baseline tiklandi: {br.get('before', 0)} → {br.get('after', 0)} hisobot"
        )
    hp = maintenance.get("hub_purge") or 0
    if hp:
        lines.append(f"🧹 Hub purge: {hp} ta noto'g'ri yozuv o'chirildi")
    hres = maintenance.get("hub_restore") or 0
    if hres:
        lines.append(f"♻️ Hub restore: {hres} ta yozuv tiklandi")
    hr = maintenance.get("hub_repair") or 0
    if hr:
        lines.append(f"🔧 Hub repair: {hr} ta guruh tuzatildi")

    reports = int(stats.get("reports") or 0)
    if stats.get("volume") and reports < 80:
        lines.extend(
            [
                "",
                "⚠️ <b>DB hali kam</b> — backup JSON yuboring yoki /repairhub",
            ]
        )
    elif stats.get("volume") and reports >= 80:
        lines.extend(
            [
                "",
                "✅ Ma'lumotlar joyida. Deploydan keyin saqlanadi.",
            ]
        )
    elif not stats.get("volume"):
        lines.extend(
            [
                "",
                "⚠️ Volume yo'q — /data mount qiling!",
            ]
        )

    lines.append("")
    lines.append(
        "📐 Kunlik ochko jadvali asosiy hisobot PNG ichida (bitta xabar)."
    )
    return "\n".join(lines)


def html_esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def run_startup_maintenance(db_path: str) -> dict[str, Any]:
    """Baseline, purge, hub repair — ketma-ket."""
    from baseline_restore import ensure_baseline_restored
    from hub_corrections import apply_hub_purges, apply_hub_restores
    from hub_repair import repair_hub_db

    out: dict[str, Any] = {}
    out["baseline"] = ensure_baseline_restored(db_path)
    try:
        out["hub_purge"] = await apply_hub_purges()
    except Exception:
        log.exception("hub purge")
        out["hub_purge"] = 0
    try:
        out["hub_restore"] = await apply_hub_restores()
    except Exception:
        log.exception("hub restore")
        out["hub_restore"] = 0
    try:
        fixes = repair_hub_db(db_path, apply=True)
        out["hub_repair"] = len(fixes)
    except Exception:
        log.exception("hub repair")
        out["hub_repair"] = 0
    out["stats"] = collect_db_stats(db_path)
    return out
