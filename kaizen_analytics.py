"""Kaizen tahlil — bot ma'lumotlari + kelishilgan ball qoidalari."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from typing import Any

from daily_report_card import BOT_ORDER, score_bot_summary
from employee_tg_map import employee_name_variants, tg_ids_for_employee

# 8 Muda — ombor/logistika kontekstida
MUDA_TYPES = (
    ("kutish", "Кутиш (дам)", "⏳"),
    ("ortiqcha", "Ортиқча ҳаракат", "🔄"),
    ("nosozlik", "Носозлик / шикоят", "⚠️"),
    ("bo_sh", "Бўш иш кучи", "💤"),
    ("nomuvozanat", "Номувозанат юк", "⚖️"),
    ("qisman", "Қисман рол", "🧩"),
    ("pasayish", "Пасайиш (тренд)", "📉"),
    ("standart", "Стандартдан чет", "📏"),
)


def _parse_dam_sec(summary: str) -> int:
    sl = (summary or "").lower()
    m = re.search(r"dam\s+([\d:]+)", sl)
    if not m:
        return 0
    token = m.group(1)
    parts = token.split(":")
    if len(parts) == 3:
        h, mi, s = (int(parts[0]), int(parts[1]), int(parts[2]))
        return h * 3600 + mi * 60 + s
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def _prev_active_days(conn: sqlite3.Connection, before_day: str, limit: int = 7) -> list[str]:
    rows = conn.execute(
        """
        SELECT day FROM (
            SELECT day FROM reports WHERE day < ?
            UNION
            SELECT day FROM cross_bot_events WHERE day < ?
        )
        GROUP BY day
        ORDER BY day DESC
        LIMIT ?
        """,
        (before_day, before_day, limit),
    ).fetchall()
    return [r["day"] for r in rows]


def _team_total_for_day(
    conn: sqlite3.Connection,
    day: str,
    *,
    employees: list[str],
    sum_day_total,
    hub_merged,
    etg: dict[str, int],
) -> int:
    total = 0
    for emp in employees:
        total += sum_day_total(conn, day, emp)
        tg_set = tg_ids_for_employee(emp, employee_tg_map=etg)
        if not tg_set:
            continue
        hub = hub_merged(conn, tg_set, day)
        for key in BOT_ORDER:
            if key in hub:
                sc, _ = score_bot_summary(key, hub[key])
                total += sc
    return total


def _employee_day_total(row: dict) -> int:
    return int(row.get("total") or 0)


def build_kaizen_report(
    *,
    conn: sqlite3.Connection,
    day: str,
    matrix: list[dict],
    employees: list[str],
    sum_day_total,
    hub_merged,
    employee_tg_map,
) -> dict[str, Any]:
    """Jamoa Kaizen hisoboti — PDCA, muda, balans, harakatlar."""
    etg = employee_tg_map(conn)
    active = [r for r in matrix if _employee_day_total(r) > 0]
    team_total = sum(_employee_day_total(r) for r in matrix)
    prev_days = _prev_active_days(conn, day, 5)
    yesterday = prev_days[0] if prev_days else None
    yesterday_total = (
        _team_total_for_day(
            conn, yesterday, employees=employees, sum_day_total=sum_day_total,
            hub_merged=hub_merged, etg=etg,
        )
        if yesterday
        else 0
    )

    avg_7 = 0
    if prev_days:
        vals = [
            _team_total_for_day(
                conn, d, employees=employees, sum_day_total=sum_day_total,
                hub_merged=hub_merged, etg=etg,
            )
            for d in prev_days[:7]
        ]
        avg_7 = int(sum(vals) / len(vals)) if vals else 0

    delta_y = team_total - yesterday_total if yesterday else 0
    delta_avg = team_total - avg_7 if avg_7 else 0

    # --- Muda ---
    muda: list[dict] = []
    total_dam_sec = 0
    yuk_active = sum(1 for r in active if int(r["roles"].get("yuk", {}).get("points") or 0) > 0)
    ishxona_neg = sum(
        int(r["roles"].get("ishxona", {}).get("points") or 0) for r in matrix if
        int(r["roles"].get("ishxona", {}).get("points") or 0) < 0
    )

    for row in matrix:
        omb = row["roles"].get("omborga", {})
        if omb.get("active"):
            dam = _parse_dam_sec(omb.get("summary", ""))
            total_dam_sec += dam
            if dam >= 600:
                muda.append(
                    {
                        "type": "kutish",
                        "icon": "⏳",
                        "title": "Омборга кутиш",
                        "detail": f"{row['employee']}: дам {_fmt_short(dam)}",
                        "severity": "high" if dam >= 1800 else "med",
                    }
                )
        yuk_pts = int(row["roles"].get("yuk", {}).get("points") or 0)
        if yuk_active >= 2 and yuk_pts == 0 and _employee_day_total(row) > 0:
            muda.append(
                {
                    "type": "bo_sh",
                    "icon": "💤",
                    "title": "Юкда иштирок йўқ",
                    "detail": f"{row['employee']} — бу кун юк жараёнида 0",
                    "severity": "med",
                }
            )
        if _employee_day_total(row) == 0:
            muda.append(
                {
                    "type": "bo_sh",
                    "icon": "💤",
                    "title": "Фаолият йўқ",
                    "detail": row["employee"],
                    "severity": "low",
                }
            )
        if row["cat_total"] > 0 and row["bot_total"] == 0:
            muda.append(
                {
                    "type": "qisman",
                    "icon": "🧩",
                    "title": "Фақат ёрдамчи категория",
                    "detail": row["employee"],
                    "severity": "med",
                }
            )
        if row["bot_total"] > 0 and row["cat_total"] == 0:
            muda.append(
                {
                    "type": "qisman",
                    "icon": "🧩",
                    "title": "Ёрдамчи киритилмаган",
                    "detail": row["employee"],
                    "severity": "low",
                }
            )

    if ishxona_neg < 0:
        muda.append(
            {
                "type": "nosozlik",
                "icon": "⚠️",
                "title": "Ишхона шикоятлари",
                "detail": f"Жами {ishxona_neg} очко",
                "severity": "high",
            }
        )

    if active and team_total > 0:
        top_share = _employee_day_total(active[0]) / team_total
        if top_share > 0.38 and len(active) >= 3:
            muda.append(
                {
                    "type": "nomuvozanat",
                    "icon": "⚖️",
                    "title": "Юк концентрация",
                    "detail": f"{active[0]['employee']} — жамининг {int(top_share * 100)}%",
                    "severity": "med",
                }
            )

    if delta_avg < -15 and avg_7 > 0:
        muda.append(
            {
                "type": "pasayish",
                "icon": "📉",
                "title": "7 кун ўртачадан паст",
                "detail": f"{team_total} vs ўрта {avg_7} ({delta_avg:+d})",
                "severity": "high",
            }
        )

    muda.sort(key=lambda x: {"high": 0, "med": 1, "low": 2}.get(x["severity"], 3))

    # --- Role coverage ---
    role_cov: dict[str, dict] = {}
    for meta_key in ("yordamchi", *BOT_ORDER):
        n = sum(
            1 for r in active
            if int(r["roles"].get(meta_key, {}).get("points") or 0) != 0
            or (meta_key == "yordamchi" and r["cat_total"] > 0)
            or (meta_key != "yordamchi" and r["roles"].get(meta_key, {}).get("active"))
        )
        pts = sum(
            int(r["roles"].get(meta_key, {}).get("points") or 0)
            if meta_key != "yordamchi"
            else r["cat_total"]
            for r in matrix
        )
        role_cov[meta_key] = {
            "active_employees": n,
            "points": pts,
            "coverage_pct": int(round(100 * n / len(employees))) if employees else 0,
        }

    # --- Balance index per employee ---
    balance: list[dict] = []
    for row in matrix:
        if _employee_day_total(row) <= 0:
            continue
        role_pts = [
            abs(int(row["roles"].get(k, {}).get("points") or 0) if k != "yordamchi" else row["cat_total"])
            for k in ("yordamchi", *BOT_ORDER)
        ]
        nonzero = [p for p in role_pts if p > 0]
        diversity = len(nonzero)
        balance.append(
            {
                "employee": row["employee"],
                "roles_active": diversity,
                "label": "Кўп ролли" if diversity >= 4 else ("Икки рол" if diversity == 2 else ("Битта рол" if diversity == 1 else "—")),
            }
        )

    # --- PDCA ---
    check_note = "стабил"
    if delta_y > 10:
        check_note = "ўсиш (кечагидан)"
    elif delta_y < -10:
        check_note = "пасайиш (кечагидан)"
    if delta_avg > 10:
        check_note = "ўртачадан юқори"
    elif delta_avg < -10:
        check_note = "ўртачадан паст"

    pdca = {
        "plan": f"Период мақсад: барча ролларда фаолият · {len(employees)} ходим",
        "do": f"Бугун: +{team_total} очко · {len(active)} фаол",
        "check": f"{check_note} · кеча {yesterday_total or '—'} · 7к ўрта {avg_7 or '—'}",
        "act": _pick_team_action(muda, role_cov, yuk_active, total_dam_sec),
    }

    # --- Prioritized actions ---
    actions = _build_actions(muda, matrix, role_cov, yuk_active, total_dam_sec)

    return {
        "pdca": pdca,
        "muda": muda[:12],
        "muda_count": len(muda),
        "role_coverage": role_cov,
        "balance": balance,
        "actions": actions,
        "stats": {
            "team_total": team_total,
            "active_count": len(active),
            "yuk_participants": yuk_active,
            "total_dam_min": total_dam_sec // 60,
            "delta_yesterday": delta_y,
            "delta_7d_avg": delta_avg,
        },
    }


def _fmt_short(sec: int) -> str:
    m, s = divmod(max(0, int(sec)), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _pick_team_action(muda: list, role_cov: dict, yuk_n: int, dam_sec: int) -> str:
    highs = [m for m in muda if m.get("severity") == "high"]
    if highs:
        return highs[0]["detail"][:80]
    if dam_sec >= 1200:
        return "Омборга дамни камайтириш — навбат / зоналар режаси"
    if yuk_n >= 2 and role_cov.get("yuk", {}).get("active_employees", 0) < yuk_n:
        return "Юк жараёни: барча иштирокчилар таймерга қўшилсин"
    skl = role_cov.get("sklad", {}).get("active_employees", 0)
    if skl == 0:
        return "Склад назорат бу кун ишланмади — жадвалга қўшинг"
    return "Жараён яхши — эртангги standart ni saqlang"


def _build_actions(
    muda: list, matrix: list[dict], role_cov: dict, yuk_n: int, dam_sec: int
) -> list[dict]:
    actions: list[dict] = []
    seen: set[str] = set()

    def add(priority: str, text: str) -> None:
        key = text[:40]
        if key in seen:
            return
        seen.add(key)
        actions.append({"priority": priority, "text": text})

    for m in muda:
        if m["severity"] == "high":
            add("A", f"{m['icon']} {m['title']}: {m['detail']}")

    if dam_sec >= 600:
        add("A", f"⏳ Жами дам {_fmt_short(dam_sec)} — омборга navbat optimallashtirish")

    if yuk_n >= 2:
        idle = [
            r["employee"] for r in matrix
            if _employee_day_total(r) > 0 and int(r["roles"].get("yuk", {}).get("points") or 0) == 0
        ]
        if idle:
            add("B", f"🛒 Юкда қатнашмаган: {', '.join(idle[:3])}")

    low_cov = [k for k, v in role_cov.items() if k != "yordamchi" and v.get("coverage_pct", 0) < 20 and v.get("points", 0) == 0]
    for k in low_cov[:2]:
        add("B", f"📋 {k} роли бу кун де-факто бўш — жадвал")

    for r in matrix:
        if r.get("rank", 99) >= max(3, len([x for x in matrix if _employee_day_total(x) > 0])):
            if _employee_day_total(r) > 0:
                add("C", f"🎯 Coaching: {r['employee']} (рейтинг #{r.get('rank')})")
                break

    if not actions:
        add("OK", "✅ Кун нормали — маълумотларни эртага солиштиринг")

    return actions[:8]


def build_kaizen_employee_hints(
    *,
    conn: sqlite3.Connection,
    day: str,
    matrix: list[dict],
    employees: list[str],
    sum_day_total,
    hub_merged,
    employee_tg_map,
) -> list[dict]:
    """Xodim bo'yicha Kaizen eslatmalar (trend + bot logikasi)."""
    etg = employee_tg_map(conn)
    prev_days = _prev_active_days(conn, day, 3)
    prev_day = prev_days[0] if prev_days else None
    hints: list[dict] = []
    active = [r for r in matrix if _employee_day_total(r) > 0]

    for row in matrix:
        emp = row["employee"]
        notes: list[str] = []
        total = _employee_day_total(row)

        if total == 0:
            notes.append("Бу кун фаолият йўқ — gemba: сабабни аниқлаш")
            hints.append({"employee": emp, "notes": notes, "priority": "low"})
            continue

        if prev_day:
            prev_total = 0
            for name in employee_name_variants(emp):
                row_p = conn.execute(
                    "SELECT COALESCE(SUM(value),0) FROM reports WHERE day=? AND employee=?",
                    (prev_day, name),
                ).fetchone()
                prev_total += int(row_p[0] or 0)
            tg_set = tg_ids_for_employee(emp, employee_tg_map=etg)
            if tg_set:
                hub = hub_merged(conn, tg_set, prev_day)
                for key in BOT_ORDER:
                    if key in hub:
                        sc, _ = score_bot_summary(key, hub[key])
                        prev_total += sc
            diff = total - prev_total
            if diff >= 15:
                notes.append(f"📈 Кечагидан +{diff} очко — yaxshi trend")
            elif diff <= -15:
                notes.append(f"📉 Кечагидан {diff} очко — sabab tahlil")

        if row["bot_total"] == 0 and row["cat_total"] > 0:
            notes.append("Фақат ёрдамчи — омбор/юк ролларига қўшилинг")

        if row["cat_total"] == 0 and row["bot_total"] > 0:
            notes.append("Ёрдамчи категория киритилмаган — standart to'ldirish")

        omb = row["roles"].get("omborga", {})
        if omb.get("active"):
            dam = _parse_dam_sec(omb.get("summary", ""))
            if dam >= 300:
                notes.append(f"⏳ Омборга дам {_fmt_short(dam)} — kutishni qisqartiring")

        yuk = row["roles"].get("yuk", {})
        if int(yuk.get("points") or 0) > 0:
            notes.append(f"🛒 Юк: +{yuk['points']} очко — jarayon qatnashgan")
        elif any(int(r["roles"].get("yuk", {}).get("points") or 0) > 0 for r in active):
            notes.append("🛒 Jamoa yukda ishladi — siz qatnashmadingiz")

        ish = row["roles"].get("ishxona", {})
        if int(ish.get("points") or 0) < 0:
            notes.append("⚠️ Ishxona shikoyati — darhol bartaraf rejasi")

        sk = row["roles"].get("sklad", {})
        if sk.get("active") and "xato" in (sk.get("summary") or "").lower():
            m = re.search(r"xato\s*(\d+)", (sk.get("summary") or "").lower())
            if m and int(m.group(1)) > 0:
                notes.append(f"📋 Sklad xato {m.group(1)} — qayta tekshiruv")

        if active and row.get("rank", 99) == 1:
            notes.append("🏆 Kun lideri — standartni hujjatlashtiring (yokoten)")

        if active and row.get("rank", 99) >= max(3, len(active)) and total > 0:
            notes.append(f"Рейтинг #{row.get('rank')}/{len(active)} — 1:1 coaching")

        priority = "high" if any("⚠️" in n or "📉" in n for n in notes) else ("med" if notes else "low")
        if notes:
            hints.append({"employee": emp, "notes": notes[:5], "priority": priority})

    hints.sort(key=lambda h: {"high": 0, "med": 1, "low": 2}.get(h.get("priority", "low"), 3))
    return hints
