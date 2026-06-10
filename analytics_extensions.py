"""Kaizen panel — qo'shimcha bo'limlar (taymlayn, heatmap, norma, ...)."""

from __future__ import annotations

import os
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from cross_bot_hub import BOT_LABELS, _parse_yuk_ish_sec, _replay_merged_by_bot
from daily_report_card import BOT_ORDER, score_bot_summary
from employee_tg_map import tg_ids_for_employee
from kaizen_analytics import _parse_dam_sec
from ranking_broadcast import period_days_through

BOT_ICONS = {
    "omborga": "🚛",
    "ombor": "📦",
    "yuk": "🛒",
    "sklad": "📋",
    "ishxona": "🔧",
}

ROLE_DAILY_NORMS: dict[str, int] = {
    "yordamchi": int(os.getenv("NORM_YORDAMCHI", "25")),
    "omborga": int(os.getenv("NORM_OMBORGA", "35")),
    "ombor": int(os.getenv("NORM_OMBOR", "30")),
    "yuk": int(os.getenv("NORM_YUK", "15")),
    "sklad": int(os.getenv("NORM_SKLAD", "12")),
    "ishxona": int(os.getenv("NORM_ISHXONA", "0")),
}

PERIOD_GOAL = int(os.getenv("KAIZEN_PERIOD_GOAL", "3500"))


def _short_name(emp: str) -> str:
    return emp.split()[-1] if emp else emp


def _time_hm(iso: str) -> str:
    s = (iso or "").strip()
    if len(s) >= 16:
        return s[11:16]
    return s[:5] if s else "—"


def build_shift_timeline(
    conn: sqlite3.Connection,
    day: str,
    *,
    employees: list[str],
    employee_tg_map: dict[str, int],
) -> list[dict]:
    """Kun bo'yicha xodim eventlari — vaqt chizig'i."""
    tg_to_emp: dict[int, str] = {}
    for emp in employees:
        for tid in tg_ids_for_employee(emp, employee_tg_map=employee_tg_map):
            tg_to_emp[int(tid)] = emp

    rows = conn.execute(
        """
        SELECT tg_id, bot_key, summary, created_at
        FROM cross_bot_events WHERE day = ?
        ORDER BY created_at ASC, id ASC
        """,
        (day,),
    ).fetchall()

    by_emp: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        emp = tg_to_emp.get(int(r["tg_id"]))
        if not emp:
            continue
        key = str(r["bot_key"] or "")
        summary = str(r["summary"] or "")[:80]
        by_emp[emp].append(
            {
                "time": _time_hm(r["created_at"]),
                "bot": key,
                "icon": BOT_ICONS.get(key, "•"),
                "label": BOT_LABELS.get(key, key),
                "summary": summary,
            }
        )

    out = []
    for emp in employees:
        events = by_emp.get(emp, [])
        if not events:
            continue
        out.append({"employee": emp, "short_name": _short_name(emp), "events": events})
    return out


def build_dam_analysis(matrix: list[dict]) -> list[dict]:
    """Omborga dam va ish nisbati."""
    rows: list[dict] = []
    for row in matrix:
        summary = (row.get("roles", {}).get("omborga", {}) or {}).get("summary", "")
        if not summary:
            continue
        dam = _parse_dam_sec(summary)
        _, ish_sec = score_bot_summary("omborga", summary)
        if dam <= 0 and ish_sec <= 0:
            continue
        total = dam + ish_sec
        pct = int(round(dam * 100 / total)) if total else 0
        from time_display import fmt_duration

        rows.append(
            {
                "employee": row["employee"],
                "short_name": row.get("short_name") or _short_name(row["employee"]),
                "dam_sec": dam,
                "ish_sec": ish_sec,
                "dam_fmt": fmt_duration(dam),
                "ish_fmt": fmt_duration(ish_sec),
                "ratio_pct": pct,
            }
        )
    rows.sort(key=lambda x: (-x["ratio_pct"], x["employee"]))
    return rows


def build_role_heatmap(matrix: list[dict], roles_meta: list[dict]) -> dict:
    """Xodim × rol — ochko intensivligi."""
    keys = [m["key"] for m in roles_meta]
    employees = [r["employee"] for r in matrix]
    cells: list[list[dict]] = []
    max_pts = 1
    for row in matrix:
        row_cells = []
        for k in keys:
            pts = int((row.get("roles", {}).get(k, {}) or {}).get("points") or 0)
            max_pts = max(max_pts, abs(pts))
            row_cells.append({"key": k, "points": pts, "active": pts != 0})
        cells.append(row_cells)
    return {
        "employees": employees,
        "short_names": [r.get("short_name") or _short_name(r["employee"]) for r in matrix],
        "roles": [{"key": m["key"], "short": m["short"], "icon": m["icon"]} for m in roles_meta],
        "cells": cells,
        "max_pts": max_pts,
    }


def build_cat_bot_matrix(matrix: list[dict]) -> list[dict]:
    """Kategoriya + bot ochkolari bir xodimda."""
    out = []
    for row in matrix:
        cats = row.get("categories") or {}
        top_cat = max(cats.items(), key=lambda x: x[1])[0] if cats else "—"
        bots = {k: int((row.get("roles", {}).get(k, {}) or {}).get("points") or 0) for k in BOT_ORDER}
        out.append(
            {
                "employee": row["employee"],
                "short_name": row.get("short_name") or _short_name(row["employee"]),
                "cat_total": row.get("cat_total") or 0,
                "top_category": top_cat,
                "bots": bots,
                "bot_total": row.get("bot_total") or 0,
            }
        )
    return out


def build_integrity_panel(conn: sqlite3.Connection, day: str) -> dict:
    """Hub ishonchlilik — shubhali yozuvlar va statistika."""
    total = int(
        conn.execute("SELECT COUNT(*) FROM cross_bot_events WHERE day=?", (day,)).fetchone()[0]
    )
    by_bot = {
        r["bot_key"]: int(r["c"])
        for r in conn.execute(
            "SELECT bot_key, COUNT(*) AS c FROM cross_bot_events WHERE day=? GROUP BY bot_key",
            (day,),
        )
    }
    flags: list[dict] = []
    rows = conn.execute(
        "SELECT tg_id, bot_key, summary FROM cross_bot_events WHERE day=? ORDER BY id",
        (day,),
    ).fetchall()
    for r in rows:
        s = str(r["summary"] or "")
        sl = s.lower()
        key = str(r["bot_key"] or "")
        reason = ""
        if key == "yuk" and "bugun jami" in sl and "yakun" not in sl:
            sec = _parse_yuk_ish_sec(sl)
            if sec >= 3600:
                reason = f"yuk jonli taymer ({sec}s)"
        if "982:00" in sl or "982" in sl and "ish" in sl:
            reason = "noto'g'ri ish vaqti formati"
        if key == "yuk" and _parse_yuk_ish_sec(sl) >= 10800:
            reason = "yuk 3+ soat (yakun yo'q)"
        if reason:
            flags.append({"tg_id": int(r["tg_id"]), "bot": key, "reason": reason, "summary": s[:70]})

    return {
        "events_total": total,
        "by_bot": by_bot,
        "flags": flags[:30],
        "flags_count": len(flags),
        "status": "ok" if not flags else "warning",
    }


def build_period_summary(
    *,
    period: str,
    ref: date,
    matrix: list[dict],
    period_ranking: list[dict],
    team_total: int,
) -> dict:
    """Hafta/oy xulosasi."""
    days = period_days_through(period, ref)
    leader = period_ranking[0] if period_ranking and period_ranking[0].get("total") else None
    active = sum(1 for r in period_ranking if r.get("total", 0) > 0)

    role_totals: dict[str, int] = defaultdict(int)
    for r in period_ranking:
        role_totals["yordamchi"] += int(r.get("yordamchi") or 0)
        for k in BOT_ORDER:
            role_totals[k] += int((r.get("bots") or {}).get(k) or 0)

    best_role = max(role_totals.items(), key=lambda x: x[1]) if role_totals else ("—", 0)
    weak_role = min(
        ((k, v) for k, v in role_totals.items() if k != "ishxona"),
        key=lambda x: x[1],
        default=("—", 0),
    )

    tips = []
    if leader:
        tips.append(f"Lider: {leader['employee']} (+{leader['total']} period)")
    tips.append(f"Faol kunlar: {len(days)} · faol xodim: {active}")
    if weak_role[1] < best_role[1] // 4 and weak_role[0] != "—":
        tips.append(f"Zaif rol: {weak_role[0]} — resurs qo'shish mumkin")

    return {
        "period": period,
        "days_count": len(days),
        "team_total_period": sum(int(r.get("total") or 0) for r in period_ranking),
        "team_total_day": team_total,
        "leader": leader,
        "active_employees": active,
        "role_totals": dict(role_totals),
        "best_role": {"key": best_role[0], "points": best_role[1]},
        "weak_role": {"key": weak_role[0], "points": weak_role[1]},
        "tips": tips,
    }


def build_session_analysis(
    conn: sqlite3.Connection,
    day: str,
    *,
    employees: list[str],
    employee_tg_map: dict[str, int],
) -> list[dict]:
    """Yuk/omborga sessiyalar — event soni va vaqt."""
    tg_to_emp: dict[int, str] = {}
    for emp in employees:
        for tid in tg_ids_for_employee(emp, employee_tg_map=employee_tg_map):
            tg_to_emp[int(tid)] = emp

    by_emp: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in conn.execute(
        """
        SELECT tg_id, bot_key, summary FROM cross_bot_events
        WHERE day=? AND bot_key IN ('yuk','omborga') ORDER BY id
        """,
        (day,),
    ):
        emp = tg_to_emp.get(int(r["tg_id"]))
        if emp:
            by_emp[emp][str(r["bot_key"])].append(str(r["summary"] or ""))

    out = []
    for emp, bots in by_emp.items():
        item: dict = {"employee": emp, "short_name": _short_name(emp), "yuk": {}, "omborga": {}}
        if bots.get("yuk"):
            merged = _replay_merged_by_bot(
                [{"bot_key": "yuk", "summary": s} for s in bots["yuk"]]
            ).get("yuk", "")
            _, sec = score_bot_summary("yuk", merged)
            yakun = sum(1 for s in bots["yuk"] if "yakun" in s.lower())
            from time_display import fmt_duration

            item["yuk"] = {
                "events": len(bots["yuk"]),
                "yakun_count": yakun,
                "work_sec": sec,
                "work_fmt": fmt_duration(sec),
            }
        if bots.get("omborga"):
            merged = _replay_merged_by_bot(
                [{"bot_key": "omborga", "summary": s} for s in bots["omborga"]]
            ).get("omborga", "")
            pts, sec = score_bot_summary("omborga", merged)
            reys = 0
            m = re.search(r"reys\s*(\d+)", (merged or "").lower())
            if m:
                reys = int(m.group(1))
            item["omborga"] = {
                "events": len(bots["omborga"]),
                "reys": reys,
                "work_sec": sec,
                "points": pts,
            }
        out.append(item)
    return out


def build_norms_vs_fact(matrix: list[dict]) -> list[dict]:
    """Kunlik norma vs fakt."""
    rows = []
    for row in matrix:
        roles = []
        for key, norm in ROLE_DAILY_NORMS.items():
            pts = int((row.get("roles", {}).get(key, {}) or {}).get("points") or 0)
            pct = int(round(pts * 100 / norm)) if norm > 0 else (100 if pts else 0)
            roles.append(
                {
                    "key": key,
                    "norm": norm,
                    "actual": pts,
                    "pct": min(pct, 999),
                    "ok": pts >= norm if norm > 0 else pts >= 0,
                }
            )
        rows.append(
            {
                "employee": row["employee"],
                "short_name": row.get("short_name") or _short_name(row["employee"]),
                "roles": roles,
            }
        )
    return rows


def build_team_goal(period: str, period_ranking: list[dict]) -> dict:
    """Jamoa period maqsadi (OKR)."""
    current = sum(int(r.get("total") or 0) for r in period_ranking)
    goal = PERIOD_GOAL
    pct = int(round(current * 100 / goal)) if goal > 0 else 0
    return {
        "period": period,
        "goal": goal,
        "current": current,
        "pct": min(pct, 100),
        "remaining": max(0, goal - current),
    }


def build_complaints_trend(
    conn: sqlite3.Connection,
    day: str,
    *,
    employees: list[str],
    employee_tg_map: dict[str, int],
) -> dict:
    """Ishxona shikoyatlar."""
    tg_to_emp: dict[int, str] = {}
    for emp in employees:
        for tid in tg_ids_for_employee(emp, employee_tg_map=employee_tg_map):
            tg_to_emp[int(tid)] = emp

    end = date.fromisoformat(day)
    labels, open_pts, counts = [], [], []
    for i in range(6, -1, -1):
        d = (end - timedelta(days=i)).isoformat()
        labels.append(d[5:])
        day_pts = 0
        day_n = 0
        for r in conn.execute(
            "SELECT tg_id, summary FROM cross_bot_events WHERE day=? AND bot_key='ishxona'",
            (d,),
        ):
            sc, _ = score_bot_summary("ishxona", str(r["summary"] or ""))
            if sc:
                day_pts += sc
                day_n += 1
        open_pts.append(day_pts)
        counts.append(day_n)

    by_emp: list[dict] = []
    for r in conn.execute(
        "SELECT tg_id, summary FROM cross_bot_events WHERE day=? AND bot_key='ishxona'",
        (day,),
    ):
        emp = tg_to_emp.get(int(r["tg_id"]), f"tg:{r['tg_id']}")
        sc, _ = score_bot_summary("ishxona", str(r["summary"] or ""))
        if sc:
            by_emp.append({"employee": emp, "points": sc, "summary": str(r["summary"] or "")[:60]})

    return {"labels": labels, "points": open_pts, "counts": counts, "today": by_emp}


def build_sklad_progress(
    conn: sqlite3.Connection,
    day: str,
    *,
    employees: list[str],
    employee_tg_map: dict[str, int],
) -> list[dict]:
    """Sklad papka progress (kun N/M)."""
    tg_to_emp: dict[int, str] = {}
    for emp in employees:
        for tid in tg_ids_for_employee(emp, employee_tg_map=employee_tg_map):
            tg_to_emp[int(tid)] = emp

    prog: dict[str, dict] = {}
    for r in conn.execute(
        "SELECT tg_id, summary FROM cross_bot_events WHERE day=? AND bot_key='sklad'",
        (day,),
    ):
        emp = tg_to_emp.get(int(r["tg_id"]))
        if not emp:
            continue
        s = str(r["summary"] or "")
        m = re.search(r"kun\s*(\d+)\s*/\s*(\d+)", s, re.I)
        san = re.search(r"sanaldi\s*(\d+)", s, re.I)
        if emp not in prog:
            prog[emp] = {"employee": emp, "short_name": _short_name(emp), "sanaldi": 0, "day_n": 0, "day_total": 28}
        if san:
            prog[emp]["sanaldi"] += int(san.group(1))
        if m:
            prog[emp]["day_n"] = max(prog[emp]["day_n"], int(m.group(1)))
            prog[emp]["day_total"] = int(m.group(2))

    out = list(prog.values())
    for p in out:
        p["pct"] = int(round(p["day_n"] * 100 / p["day_total"])) if p["day_total"] else 0
    out.sort(key=lambda x: -x["sanaldi"])
    return out


def build_benchmark(matrix: list[dict]) -> list[dict]:
    """Xodim vs jamoa o'rtachasi (%)."""
    keys = ["yordamchi", *list(BOT_ORDER)]
    sums: dict[str, int] = defaultdict(int)
    n = max(len(matrix), 1)
    for row in matrix:
        sums["yordamchi"] += row.get("cat_total") or 0
        for k in BOT_ORDER:
            sums[k] += int((row.get("roles", {}).get(k, {}) or {}).get("points") or 0)

    avgs = {k: sums[k] / n for k in keys}
    out = []
    for row in matrix:
        comps = []
        for k in keys:
            if k == "yordamchi":
                val = row.get("cat_total") or 0
            else:
                val = int((row.get("roles", {}).get(k, {}) or {}).get("points") or 0)
            avg = avgs.get(k) or 0
            pct = int(round(val * 100 / avg)) if avg > 0 else (100 if val else 0)
            comps.append({"key": k, "value": val, "avg": int(round(avg)), "pct": pct})
        out.append(
            {
                "employee": row["employee"],
                "short_name": row.get("short_name") or _short_name(row["employee"]),
                "total": row.get("total") or 0,
                "vs_team_pct": int(
                    round((row.get("total") or 0) * 100 / (sum(r.get("total") or 0 for r in matrix) / n))
                )
                if matrix
                else 0,
                "roles": comps,
            }
        )
    out.sort(key=lambda x: -x["vs_team_pct"])
    return out


def build_bottleneck(matrix: list[dict]) -> list[dict]:
    """Rol bo'yicha jamoa vaqti/ochko Pareto."""
    keys = ["yordamchi", *list(BOT_ORDER)]
    totals: dict[str, int] = defaultdict(int)
    for row in matrix:
        totals["yordamchi"] += row.get("cat_total") or 0
        for k in BOT_ORDER:
            totals[k] += int((row.get("roles", {}).get(k, {}) or {}).get("points") or 0)
    grand = sum(totals.values()) or 1
    items = sorted(totals.items(), key=lambda x: -x[1])
    cum = 0
    out = []
    labels = {
        "yordamchi": "Ёрдамчи",
        "omborga": "Омборга",
        "ombor": "Омбор",
        "yuk": "Юк",
        "sklad": "Склад",
        "ishxona": "Ишхона",
    }
    for k, v in items:
        if v <= 0 and k == "ishxona":
            continue
        cum += v
        out.append(
            {
                "key": k,
                "label": labels.get(k, k),
                "points": v,
                "share_pct": int(round(v * 100 / grand)),
                "cum_pct": int(round(cum * 100 / grand)),
            }
        )
    return out


def build_alerts(
    conn: sqlite3.Connection,
    day: str,
    matrix: list[dict],
    *,
    employees: list[str],
    employee_tg_map: dict[str, int],
) -> list[dict]:
    """Signal / ogohlantirishlar (panel)."""
    alerts: list[dict] = []
    ref = date.fromisoformat(day)

    for row in matrix:
        emp = row["employee"]
        yuk = (row.get("roles", {}).get("yuk", {}) or {}).get("active")
        if not yuk:
            streak = 0
            for i in range(1, 4):
                d = (ref - timedelta(days=i)).isoformat()
                tg_set = tg_ids_for_employee(emp, employee_tg_map=employee_tg_map)
                if not tg_set:
                    break
                hub = _replay_merged_by_bot(
                    [
                        {"bot_key": r["bot_key"], "summary": r["summary"]}
                        for r in conn.execute(
                            f"""
                            SELECT bot_key, summary FROM cross_bot_events
                            WHERE day=? AND tg_id IN ({",".join("?" * len(tg_set))})
                            """,
                            (d, *sorted(tg_set)),
                        )
                    ]
                )
                _, sec = score_bot_summary("yuk", hub.get("yuk", ""))
                if sec > 0:
                    break
                streak += 1
            if streak >= 3:
                alerts.append(
                    {
                        "severity": "med",
                        "employee": emp,
                        "text": f"Yuk 3+ kun 0 — sessiya yakunlanmagan bo'lishi mumkin",
                    }
                )

        if (row.get("total") or 0) == 0:
            alerts.append({"severity": "low", "employee": emp, "text": "Bugun faoliyat yo'q"})

    flags = build_integrity_panel(conn, day)["flags"]
    if flags:
        alerts.append(
            {
                "severity": "high",
                "employee": "—",
                "text": f"Hub: {len(flags)} ta shubhali yozuv (taymlayn/ishonchlilik)",
            }
        )

    return alerts[:25]


def build_bot_activity_strip(
    conn: sqlite3.Connection,
    day: str,
    *,
    employees: list[str],
    employee_tg_map: dict[str, int],
) -> list[dict]:
    """Har bot — bugungi oxirgi event (live lenta)."""
    tg_to_emp: dict[int, str] = {}
    for emp in employees:
        for tid in tg_ids_for_employee(emp, employee_tg_map=employee_tg_map):
            tg_to_emp[int(tid)] = emp

    by_bot: dict[str, dict] = {}
    for r in conn.execute(
        """
        SELECT bot_key, tg_id, summary, created_at FROM cross_bot_events
        WHERE day=? ORDER BY id DESC
        """,
        (day,),
    ):
        key = str(r["bot_key"] or "")
        if key in by_bot:
            continue
        emp = tg_to_emp.get(int(r["tg_id"]), f"tg:{r['tg_id']}")
        by_bot[key] = {
            "bot": key,
            "icon": BOT_ICONS.get(key, "•"),
            "label": BOT_LABELS.get(key, key),
            "employee": emp.split()[-1] if emp else emp,
            "time": _time_hm(r["created_at"]),
            "summary": str(r["summary"] or "")[:72],
        }
    order = list(BOT_ORDER) + ["yordamchi"]
    return [by_bot[k] for k in order if k in by_bot]


def build_role_work_times(matrix: list[dict]) -> dict:
    """Rol bo'yicha jami ish vaqti (diagramma)."""
    from time_display import fmt_duration

    keys = list(BOT_ORDER)
    secs = []
    labels = []
    for k in keys:
        total = 0
        for row in matrix:
            role = (row.get("roles", {}) or {}).get(k, {}) or {}
            _, wsec = score_bot_summary(k, role.get("summary", ""))
            total += wsec
        secs.append(total)
        labels.append(BOT_LABELS.get(k, k))
    return {
        "labels": labels,
        "seconds": secs,
        "formatted": [fmt_duration(s) for s in secs],
    }


def build_employee_work_split(matrix: list[dict]) -> list[dict]:
    """Har xodim — rol bo'yicha ish vaqti (stacked)."""
    from time_display import fmt_duration

    out = []
    for row in matrix:
        parts = []
        for k in BOT_ORDER:
            role = (row.get("roles", {}) or {}).get(k, {}) or {}
            if not role.get("active"):
                continue
            _, sec = score_bot_summary(k, role.get("summary", ""))
            if sec > 0:
                parts.append(
                    {
                        "key": k,
                        "icon": BOT_ICONS.get(k, ""),
                        "label": BOT_LABELS.get(k, k),
                        "sec": sec,
                        "fmt": fmt_duration(sec),
                    }
                )
        if parts:
            out.append(
                {
                    "employee": row["employee"],
                    "short_name": row.get("short_name") or _short_name(row["employee"]),
                    "total_fmt": row.get("work_time", "00:00:00"),
                    "parts": parts,
                }
            )
    return out


def build_export_rows(matrix: list[dict], day: str) -> list[dict]:
    """CSV eksport qatorlari."""
    rows = []
    for row in matrix:
        r = {
            "day": day,
            "employee": row["employee"],
            "rank": row.get("rank"),
            "total": row.get("total"),
            "work_time": row.get("work_time"),
            "yordamchi": row.get("cat_total"),
        }
        for k in BOT_ORDER:
            r[k] = int((row.get("roles", {}).get(k, {}) or {}).get("points") or 0)
        rows.append(r)
    return rows
