"""Kaizen analytics — SQLite + hub (sync, HTTP uchun)."""

from __future__ import annotations

import os
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from cross_bot_hub import BOT_LABELS, DB_PATH, _replay_merged_by_bot
from daily_report_card import BOT_ORDER, _bot_metrics, score_bot_summary
from employee_tg_map import employee_name_variants, resolve_owner_tg_id, resolve_tg_id, tg_ids_for_employee
from kaizen_analytics import build_kaizen_employee_hints, build_kaizen_report
from points_breakdown import explain_bot_formula
from ranking_broadcast import period_days_through

TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

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

CATEGORIES = [
    "Приход",
    "Перемещение",
    "Фото ТМЦ",
    "Счет ТСД",
    "Фасовка",
    "АРМ диспетчер",
    "Исправление пересортицы",
    "Переоценка",
    "Пересчет товаров",
    "Места хр",
]

ROLE_META = [
    {"key": "yordamchi", "label": "Ёрдамчи бот", "short": "Ёрд", "icon": "🧰", "color": "#00a8bc"},
    {"key": "omborga", "label": "Омборга киритиш", "short": "Омбг", "icon": "🚛", "color": "#00afca"},
    {"key": "ombor", "label": "Омбор хизмат", "short": "Омб", "icon": "📦", "color": "#ff822d"},
    {"key": "yuk", "label": "Юк жараёни", "short": "Юк", "icon": "🛒", "color": "#5fc355"},
    {"key": "sklad", "label": "Склад назорат", "short": "Скл", "icon": "📋", "color": "#9b6ef0"},
    {"key": "ishxona", "label": "Ишхона назорат", "short": "Ишх", "icon": "🔧", "color": "#f0556e"},
]

METRIC_LABELS_CYRL = {
    "holat": "Ҳолат",
    "reys": "Рейс",
    "ish vaqti": "Иш вақти",
    "jami vaqt": "Жами вақт",
    "dam": "Дам",
    "son": "Сония",
    "ma'lumot": "Маълумот",
    "shikoyat": "Шикоят",
    "info": "Маълумот",
}

ROLE_LABELS_CYRL = {
    "omborga": "Омборга киритиш",
    "ombor": "Омбор хизмат",
    "yuk": "Юк жараёни",
    "sklad": "Склад назорат",
    "ishxona": "Ишхона назорат",
}

ROLE_REPORTS = {
    "yordamchi": [
        "Кунлик категория очколари (10 йўналиш)",
        "Энг кучли категория",
        "Период жами (2-санадан)",
        "Кечага нисбат",
    ],
    "omborga": [
        "Рейслар сони",
        "Иш вақти / дам",
        "Юк масофаси (m)",
        "Очко: рейс×2 + иш÷2",
    ],
    "ombor": [
        "Аризалар / буюртмалар",
        "Бажариш вақти",
        "Кунлик жами иш вақти",
        "Очко: дақиқа×1",
    ],
    "yuk": [
        "Иш вақти (сония)",
        "Кунлик жараён",
        "Очко: дақиқа÷2",
    ],
    "sklad": [
        "Саналди / жой / хато",
        "Папка прогресс",
        "Очко: саналди×2",
    ],
    "ishxona": [
        "Очиқ шикоятлар",
        "Бартараф / рад",
        "Очко: −40 / шикоят",
    ],
}


def analytics_secret_ok(token: str) -> bool:
    secret = (
        os.getenv("ANALYTICS_SECRET", "").strip()
        or os.getenv("YORDAMCHI_HUB_SECRET", "").strip()
    )
    return bool(secret) and token.strip() == secret


def today_local() -> date:
    from datetime import datetime

    return datetime.now(TZ).date()


def get_period_key(d: date | None = None) -> str:
    d = d or today_local()
    if d.day >= 2:
        return d.strftime("%Y-%m")
    prev = d.replace(day=1) - timedelta(days=1)
    return prev.strftime("%Y-%m")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _employee_tg_map(conn: sqlite3.Connection) -> dict[str, int]:
    linked = {
        r["employee"]: int(r["tg_id"])
        for r in conn.execute("SELECT tg_id, employee FROM employee_links")
    }
    out: dict[str, int] = {}
    for emp in EMPLOYEES:
        tid = resolve_owner_tg_id(emp) or resolve_tg_id(emp, linked=linked)
        if tid:
            out[emp] = int(tid)
    return out


def _sum_day(conn: sqlite3.Connection, day: str, employee: str, category: str) -> int:
    total = 0
    for name in employee_name_variants(employee):
        row = conn.execute(
            "SELECT COALESCE(SUM(value),0) AS s FROM reports WHERE day=? AND employee=? AND category=?",
            (day, name, category),
        ).fetchone()
        total += int(row["s"] or 0)
    return total


def _sum_day_total(conn: sqlite3.Connection, day: str, employee: str) -> int:
    return sum(_sum_day(conn, day, employee, cat) for cat in CATEGORIES)


def _day_has_activity(conn: sqlite3.Connection, day: str) -> bool:
    r = conn.execute("SELECT 1 FROM reports WHERE day=? LIMIT 1", (day,)).fetchone()
    if r:
        return True
    h = conn.execute("SELECT 1 FROM cross_bot_events WHERE day=? LIMIT 1", (day,)).fetchone()
    return bool(h)


def resolve_analytics_day(day: str | None) -> tuple[str, bool]:
    """Oxirgi faol kunga fallback."""
    conn = _connect()
    try:
        requested = (day or "").strip()
        if requested and _day_has_activity(conn, requested):
            return requested, False
        row = conn.execute(
            """
            SELECT day FROM (
                SELECT day FROM reports
                UNION
                SELECT day FROM cross_bot_events
            )
            ORDER BY day DESC LIMIT 1
            """
        ).fetchone()
        resolved = row["day"] if row else (requested or today_local().isoformat())
        fallback = bool(requested and requested != resolved)
        return resolved, fallback
    finally:
        conn.close()


def _hub_merged(conn: sqlite3.Connection, tg_ids: set[int], day: str) -> dict[str, str]:
    ids = sorted({int(x) for x in tg_ids if x})
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT bot_key, summary, id FROM cross_bot_events
        WHERE day = ? AND tg_id IN ({ph})
        ORDER BY id ASC
        """,
        (day, *ids),
    ).fetchall()
    return _replay_merged_by_bot(rows)


def _is_empty_hub_summary(key: str, summary: str) -> bool:
    """0 очко + шаблон бўш хабар — панелда кўрсатилмайди (хар ходимда бир хил 0:00 юк)."""
    sl = (summary or "").lower()
    if not sl:
        return True
    if key == "yuk":
        if re.search(r"ish\s+vaqti\s+0(?::00)?(?:\s|$|,)", sl):
            return True
        if re.search(r"ish\s+vaqti\s+0\s*soniya", sl):
            return True
        if "jami" in sl and re.search(r"\b0\s*soniya\b", sl):
            return True
    if key == "ombor":
        if "0 ta" in sl and ("0 soniya" in sl or "ish vaqti 0" in sl):
            return True
    if key == "omborga":
        if not re.search(r"reys\s*[1-9]", sl):
            if re.search(r"ish\s+0", sl) or "reys 0" in sl:
                return True
    return False


def _role_meaningful(key: str, summary: str, score: int, work_sec: int) -> bool:
    if score != 0 or work_sec > 0:
        return True
    if _is_empty_hub_summary(key, summary):
        return False
    return bool((summary or "").strip())


def _fmt_hms(seconds: int) -> str:
    from time_display import fmt_duration_hms

    return fmt_duration_hms(seconds)


def _role_block(key: str, summary: str, score: int, work_sec: int) -> dict:
    meaningful = _role_meaningful(key, summary, score, work_sec)
    metrics = _bot_metrics(key, summary, work_sec) if meaningful else []
    formula = ""
    if meaningful and summary.strip():
        _, formula = explain_bot_formula(key, summary)
    return {
        "key": key,
        "label": ROLE_LABELS_CYRL.get(key, BOT_LABELS.get(key, key)),
        "points": score,
        "summary": (summary or "").strip(),
        "formula": formula,
        "metrics": [
            {"k": METRIC_LABELS_CYRL.get(k.lower(), k), "v": v} for k, v in metrics
        ],
        "active": meaningful,
    }


def build_shift_matrix(day: str) -> list[dict]:
    """Barcha 10 xodim — har bir rol kesimida."""
    from hub_integrity import ensure_hub_repaired_for_day

    ensure_hub_repaired_for_day(DB_PATH, day=day)
    conn = _connect()
    try:
        etg = _employee_tg_map(conn)
        rows: list[dict] = []
        for emp in EMPLOYEES:
            cats: dict[str, int] = {}
            for cat in CATEGORIES:
                v = _sum_day(conn, day, emp, cat)
                if v:
                    cats[cat] = v
            cat_total = sum(cats.values())
            best_cat = max(cats.items(), key=lambda x: x[1]) if cats else ("—", 0)

            tg_set = tg_ids_for_employee(emp, employee_tg_map=etg)
            hub = _hub_merged(conn, tg_set, day) if tg_set else {}
            roles: dict[str, dict] = {}
            bot_total = 0
            work_sec = 0
            for key in BOT_ORDER:
                summary = hub.get(key, "")
                score, wsec = score_bot_summary(key, summary)
                bot_total += score
                work_sec += wsec
                roles[key] = _role_block(key, summary, score, wsec)

            roles["yordamchi"] = {
                "key": "yordamchi",
                "label": "Ёрдамчи бот",
                "points": cat_total,
                "summary": "",
                "formula": f"{len(cats)} категория" if cats else "",
                "metrics": [{"k": k[:20], "v": f"+{v}"} for k, v in sorted(cats.items(), key=lambda x: -x[1])],
                "active": cat_total > 0,
                "best_category": best_cat[0],
                "best_points": best_cat[1],
            }

            total = cat_total + bot_total
            rows.append(
                {
                    "employee": emp,
                    "short_name": emp.split()[-1] if emp else emp,
                    "roles": roles,
                    "cat_total": cat_total,
                    "bot_total": bot_total,
                    "total": total,
                    "work_time": _fmt_hms(work_sec),
                    "categories": cats,
                }
            )

        rows.sort(key=lambda x: (-x["total"], x["employee"]))
        for i, row in enumerate(rows, 1):
            row["rank"] = i
        return rows
    finally:
        conn.close()


def build_employee_details(matrix: list[dict]) -> list[dict]:
    """Har bir xodim uchun батафсил рол ҳисоботи."""
    out: list[dict] = []
    for row in matrix:
        sections: list[dict] = []
        for meta in ROLE_META:
            block = row["roles"].get(meta["key"], {})
            lines: list[dict] = []
            if meta["key"] == "yordamchi":
                for cat, pts in sorted(row.get("categories", {}).items(), key=lambda x: -x[1]):
                    lines.append({"label": cat, "value": f"{pts} бирлик", "points": f"+{pts}"})
                if not lines:
                    lines.append({"label": "Фаолият", "value": "йўқ", "points": "—"})
            else:
                if block.get("active"):
                    for m in block.get("metrics", []):
                        lines.append({"label": m["k"], "value": m["v"], "points": ""})
                    if block.get("formula"):
                        lines.append({"label": "Ҳисоб", "value": block["formula"], "points": ""})
                    if block.get("summary"):
                        lines.append({"label": "Хулоса", "value": block["summary"][:100], "points": ""})
                if not lines:
                    note = "йўқ"
                    if meta["key"] == "yuk":
                        note = "йўқ — бу кун юк ботида иш вақти 0"
                    lines.append({"label": "Фаолият", "value": note, "points": "—"})
            pts = int(block.get("points") or 0)
            sections.append(
                {
                    "key": meta["key"],
                    "icon": meta["icon"],
                    "title": meta["label"],
                    "color": meta["color"],
                    "points": pts,
                    "points_fmt": f"+{pts}" if pts > 0 else (str(pts) if pts < 0 else "—"),
                    "lines": lines,
                    "active": bool(block.get("active")),
                }
            )
        out.append(
            {
                "employee": row["employee"],
                "rank": row["rank"],
                "total": row["total"],
                "work_time": row["work_time"],
                "sections": sections,
            }
        )
    return out


def daily_team_trend(end_day: str, days: int = 14) -> dict:
    end = date.fromisoformat(end_day)
    labels: list[str] = []
    totals: list[int] = []
    yord: list[int] = []
    bots: list[int] = []
    conn = _connect()
    try:
        etg = _employee_tg_map(conn)
        for i in range(days - 1, -1, -1):
            d = (end - timedelta(days=i)).isoformat()
            labels.append(d[5:])
            ct = bt = 0
            for emp in EMPLOYEES:
                ct += _sum_day_total(conn, d, emp)
                tg_set = tg_ids_for_employee(emp, employee_tg_map=etg)
                if not tg_set:
                    continue
                hub = _hub_merged(conn, tg_set, d)
                for key in BOT_ORDER:
                    if key in hub:
                        sc, _ = score_bot_summary(key, hub[key])
                        bt += sc
            totals.append(ct + bt)
            yord.append(ct)
            bots.append(bt)
    finally:
        conn.close()
    return {"labels": labels, "totals": totals, "yordamchi": yord, "bots": bots}


def category_pareto_period(period: str, ref: date) -> list[dict]:
    days = period_days_through(period, ref)
    conn = _connect()
    try:
        agg: dict[str, int] = defaultdict(int)
        for d in days:
            for emp in EMPLOYEES:
                for cat in CATEGORIES:
                    v = _sum_day(conn, d, emp, cat)
                    if v:
                        agg[cat] += v
        items = sorted(agg.items(), key=lambda x: -x[1])
        return [{"name": n, "value": v} for n, v in items if v > 0]
    finally:
        conn.close()


def hub_pulse(day: str) -> list[dict]:
    conn = _connect()
    try:
        etg = _employee_tg_map(conn)
        by_bot: dict[str, dict] = {k: {"events": 0, "points": 0, "active_employees": 0} for k in BOT_ORDER}
        for r in conn.execute(
            "SELECT bot_key, COUNT(*) AS c FROM cross_bot_events WHERE day=? GROUP BY bot_key",
            (day,),
        ):
            if r["bot_key"] in by_bot:
                by_bot[r["bot_key"]]["events"] = int(r["c"])

        for emp in EMPLOYEES:
            tg_set = tg_ids_for_employee(emp, employee_tg_map=etg)
            hub = _hub_merged(conn, tg_set, day) if tg_set else {}
            for key in BOT_ORDER:
                if key not in hub:
                    continue
                sc, _ = score_bot_summary(key, hub[key])
                if sc or hub[key].strip():
                    by_bot[key]["points"] += sc
                    by_bot[key]["active_employees"] += 1

        out = []
        for meta in ROLE_META:
            k = meta["key"]
            if k == "yordamchi":
                pts = sum(_sum_day_total(conn, day, e) for e in EMPLOYEES)
                active = sum(1 for e in EMPLOYEES if _sum_day_total(conn, day, e) > 0)
                out.append({**meta, "events": active, "points": pts, "active_employees": active})
            elif k in by_bot:
                out.append({**meta, **by_bot[k]})
        return out
    finally:
        conn.close()


def period_ranking(period: str, ref: date) -> list[dict]:
    days = period_days_through(period, ref)
    conn = _connect()
    try:
        etg = _employee_tg_map(conn)
        rows: list[dict] = []
        for emp in EMPLOYEES:
            cat_pts = 0
            for name in employee_name_variants(emp):
                row = conn.execute(
                    "SELECT COALESCE(SUM(value),0) AS s FROM reports WHERE period=? AND employee=?",
                    (period, name),
                ).fetchone()
                cat_pts += int(row["s"] or 0)

            bot_by: dict[str, int] = {k: 0 for k in BOT_ORDER}
            for d in days:
                tg_set = tg_ids_for_employee(emp, employee_tg_map=etg)
                if not tg_set:
                    continue
                hub = _hub_merged(conn, tg_set, d)
                for key in BOT_ORDER:
                    if key in hub:
                        sc, _ = score_bot_summary(key, hub[key])
                        bot_by[key] += sc
            total = cat_pts + sum(bot_by.values())
            rows.append(
                {
                    "employee": emp,
                    "yordamchi": cat_pts,
                    "bots": bot_by,
                    "total": total,
                }
            )
        rows.sort(key=lambda x: (-x["total"], x["employee"]))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows
    finally:
        conn.close()


def db_snapshot() -> dict:
    conn = _connect()
    try:
        reports = int(conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0])
        hub = int(conn.execute("SELECT COUNT(*) FROM cross_bot_events").fetchone()[0])
        days = conn.execute(
            "SELECT COUNT(DISTINCT day) FROM (SELECT day FROM reports UNION SELECT day FROM cross_bot_events)"
        ).fetchone()[0]
        return {"reports": reports, "hub_events": hub, "active_days": int(days or 0)}
    finally:
        conn.close()


def build_dashboard(day: str | None = None) -> dict:
    from analytics_extensions import (
        build_alerts,
        build_benchmark,
        build_bot_activity_strip,
        build_bottleneck,
        build_cat_bot_matrix,
        build_complaints_trend,
        build_dam_analysis,
        build_employee_work_split,
        build_integrity_panel,
        build_norms_vs_fact,
        build_period_summary,
        build_role_heatmap,
        build_role_work_times,
        build_session_analysis,
        build_shift_timeline,
        build_sklad_progress,
        build_team_goal,
    )

    resolved, day_fallback = resolve_analytics_day(day)
    ref = date.fromisoformat(resolved)
    period = get_period_key(ref)
    matrix = build_shift_matrix(resolved)
    team_total = sum(r["total"] for r in matrix)
    active_count = sum(1 for r in matrix if r["total"] > 0)
    leader = matrix[0] if matrix and matrix[0]["total"] > 0 else None
    period_rows = period_ranking(period, ref)

    conn = _connect()
    try:
        etg = _employee_tg_map(conn)
        kaizen_report = build_kaizen_report(
            conn=conn,
            day=resolved,
            matrix=matrix,
            employees=EMPLOYEES,
            sum_day_total=_sum_day_total,
            hub_merged=_hub_merged,
            employee_tg_map=_employee_tg_map,
        )
        kaizen_hints = build_kaizen_employee_hints(
            conn=conn,
            day=resolved,
            matrix=matrix,
            employees=EMPLOYEES,
            sum_day_total=_sum_day_total,
            hub_merged=_hub_merged,
            employee_tg_map=_employee_tg_map,
        )
        timeline = build_shift_timeline(conn, resolved, employees=EMPLOYEES, employee_tg_map=etg)
        dam_rows = build_dam_analysis(matrix)
        heatmap = build_role_heatmap(matrix, ROLE_META)
        cat_bot = build_cat_bot_matrix(matrix)
        integrity = build_integrity_panel(conn, resolved)
        summary = build_period_summary(
            period=period,
            ref=ref,
            matrix=matrix,
            period_ranking=period_rows,
            team_total=team_total,
        )
        sessions = build_session_analysis(conn, resolved, employees=EMPLOYEES, employee_tg_map=etg)
        norms = build_norms_vs_fact(matrix)
        team_goal = build_team_goal(period, period_rows)
        complaints = build_complaints_trend(conn, resolved, employees=EMPLOYEES, employee_tg_map=etg)
        sklad_prog = build_sklad_progress(conn, resolved, employees=EMPLOYEES, employee_tg_map=etg)
        benchmark = build_benchmark(matrix)
        bottleneck = build_bottleneck(matrix)
        alerts = build_alerts(
            conn, resolved, matrix, employees=EMPLOYEES, employee_tg_map=etg
        )
        bot_feed = build_bot_activity_strip(
            conn, resolved, employees=EMPLOYEES, employee_tg_map=etg
        )
        role_work = build_role_work_times(matrix)
        work_split = build_employee_work_split(matrix)
    finally:
        conn.close()

    return {
        "day": resolved,
        "requested_day": (day or "").strip() or resolved,
        "day_fallback": day_fallback,
        "period": period,
        "ref_date": ref.isoformat(),
        "team_size": len(EMPLOYEES),
        "team_total": team_total,
        "active_count": active_count,
        "leader": leader,
        "matrix": matrix,
        "employee_details": build_employee_details(matrix),
        "trend": daily_team_trend(resolved, 14),
        "pareto": category_pareto_period(period, ref),
        "hub_pulse": hub_pulse(resolved),
        "period_ranking": period_rows,
        "kaizen_report": kaizen_report,
        "kaizen_hints": kaizen_hints,
        "roles": ROLE_META,
        "role_reports": ROLE_REPORTS,
        "categories": CATEGORIES,
        "db": db_snapshot(),
        "timeline": timeline,
        "dam_analysis": dam_rows,
        "heatmap": heatmap,
        "cat_bot_matrix": cat_bot,
        "integrity": integrity,
        "period_summary": summary,
        "sessions": sessions,
        "norms": norms,
        "team_goal": team_goal,
        "complaints": complaints,
        "sklad_progress": sklad_prog,
        "benchmark": benchmark,
        "bottleneck": bottleneck,
        "alerts": alerts,
        "bot_feed": bot_feed,
        "role_work": role_work,
        "work_split": work_split,
    }
