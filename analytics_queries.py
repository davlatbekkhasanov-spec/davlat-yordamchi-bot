"""Kaizen analytics — SQLite + hub (sync, HTTP uchun)."""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from cross_bot_hub import BOT_LABELS, DB_PATH, _replay_merged_by_bot
from daily_report_card import BOT_ORDER, _bot_metrics, score_bot_summary
from employee_tg_map import employee_name_variants, resolve_owner_tg_id, resolve_tg_id, tg_ids_for_employee
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
    "Yadullaev Umidjon",
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

ROLE_REPORTS = {
    "yordamchi": [
        "Кунлик категория очколари (10 йўналиш)",
        "Энг кучли категория",
        "Период жами (2-санадан)",
        "Кечага нисбатан",
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


def _fmt_hms(seconds: int) -> str:
    sec = max(0, int(seconds))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _role_block(key: str, summary: str, score: int, work_sec: int) -> dict:
    metrics = _bot_metrics(key, summary, work_sec)
    return {
        "key": key,
        "label": BOT_LABELS.get(key, key),
        "points": score,
        "summary": (summary or "")[:120],
        "metrics": [{"k": k, "v": v} for k, v in metrics],
        "active": bool(score or (summary or "").strip()),
    }


def build_shift_matrix(day: str) -> list[dict]:
    """Har bir xodim — har bir rol kesimida kunlik hisobot."""
    conn = _connect()
    try:
        etg = _employee_tg_map(conn)
        rows: list[dict] = []
        for emp in EMPLOYEES:
            cats: dict[str, int] = {}
            cat_lines: list[str] = []
            for cat in CATEGORIES:
                v = _sum_day(conn, day, emp, cat)
                if v:
                    cats[cat] = v
                    cat_lines.append(f"{cat} +{v}")
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
                "summary": "; ".join(cat_lines[:4]) if cat_lines else "",
                "metrics": [{"k": k[:18], "v": str(v)} for k, v in sorted(cats.items(), key=lambda x: -x[1])[:6]],
                "active": cat_total > 0,
                "best_category": best_cat[0],
                "best_points": best_cat[1],
            }

            total = cat_total + bot_total
            if total <= 0 and not any(r.get("active") for r in roles.values()):
                continue

            rows.append(
                {
                    "employee": emp,
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
            ct = 0
            bt = 0
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
        for day in days:
            for emp in EMPLOYEES:
                for cat in CATEGORIES:
                    v = _sum_day(conn, day, emp, cat)
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
        raw = conn.execute(
            "SELECT bot_key, COUNT(*) AS c FROM cross_bot_events WHERE day=? GROUP BY bot_key",
            (day,),
        ).fetchall()
        for r in raw:
            k = r["bot_key"]
            if k in by_bot:
                by_bot[k]["events"] = int(r["c"])

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
                out.append(
                    {
                        **meta,
                        "events": active,
                        "points": pts,
                        "active_employees": active,
                    }
                )
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
            for day in days:
                tg_set = tg_ids_for_employee(emp, employee_tg_map=etg)
                if not tg_set:
                    continue
                hub = _hub_merged(conn, tg_set, day)
                for key in BOT_ORDER:
                    if key in hub:
                        sc, _ = score_bot_summary(key, hub[key])
                        bot_by[key] += sc
            total = cat_pts + sum(bot_by.values())
            if total <= 0:
                continue
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


def kaizen_hints(matrix: list[dict], day: str) -> list[dict]:
    """Soddalashtirilgan Kaizen eslatmalari."""
    hints: list[dict] = []
    for row in matrix:
        emp = row["employee"]
        notes: list[str] = []
        omb = row["roles"].get("omborga", {})
        if row["bot_total"] == 0 and row["cat_total"] > 0:
            notes.append("Фақат ёрдамчи бот — бошқа ролларда фаолият йўқ")
        if row["cat_total"] == 0 and row["bot_total"] > 0:
            notes.append("Фақат операцион ботлар — ёрдамчи категория йўқ")
        for m in omb.get("metrics", []):
            if m.get("k") == "dam" and m.get("v") not in ("00:00", "0:00", "—"):
                notes.append(f"Омборга: дам {m['v']} — кутишни текширинг")
        if row["total"] > 0 and row["rank"] >= max(3, len(matrix) - 1):
            notes.append(f"Рейтинг паст ({row['rank']}/{len(matrix)}) — coaching")
        if notes:
            hints.append({"employee": emp, "notes": notes[:3]})
    return hints


def build_dashboard(day: str | None = None) -> dict:
    day = day or today_local().isoformat()
    ref = date.fromisoformat(day)
    period = get_period_key(ref)
    matrix = build_shift_matrix(day)
    return {
        "day": day,
        "period": period,
        "ref_date": ref.isoformat(),
        "team_size": len(EMPLOYEES),
        "matrix": matrix,
        "trend": daily_team_trend(day, 14),
        "pareto": category_pareto_period(period, ref),
        "hub_pulse": hub_pulse(day),
        "period_ranking": period_ranking(period, ref),
        "kaizen_hints": kaizen_hints(matrix, day),
        "roles": ROLE_META,
        "role_reports": ROLE_REPORTS,
        "categories": CATEGORIES,
    }
