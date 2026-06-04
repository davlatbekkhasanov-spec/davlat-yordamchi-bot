"""Period bo'yicha yig'ilgan ochko reytingi."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Awaitable, Callable

from daily_report_card import BOT_ORDER, LeaderRow, score_bot_summary, _fmt_clock
from cross_bot_hub import fetch_merged_latest_by_bot
from employee_tg_map import employee_name_variants, tg_ids_for_employee

def ranking_employees(employees: list[str]) -> list[str]:
    return list(employees)


def init_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ranking_broadcasts (
            day TEXT PRIMARY KEY,
            sent_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


async def ranking_already_sent(db_fetchone, day_iso: str) -> bool:
    row = await db_fetchone(
        "SELECT 1 AS ok FROM ranking_broadcasts WHERE day = ? LIMIT 1",
        (day_iso,),
    )
    return row is not None


async def mark_ranking_sent(db_execute, day_iso: str) -> None:
    await db_execute(
        """
        INSERT OR REPLACE INTO ranking_broadcasts(day, sent_at)
        VALUES (?, ?)
        """,
        (day_iso, datetime.now().isoformat(timespec="seconds")),
    )


def period_start(period: str) -> date:
    y, m = map(int, period.split("-"))
    return date(y, m, 2)


def period_days_through(period: str, ref: date) -> list[str]:
    start = period_start(period)
    if ref < start:
        return []
    out: list[str] = []
    d = start
    while d <= ref:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


async def _bot_points_in_period(tg_ids: set[int], days: list[str]) -> tuple[int, int]:
    bot_pts = 0
    work_sec = 0
    for day_iso in days:
        ev = await fetch_merged_latest_by_bot(tg_ids, day_iso)
        for key in BOT_ORDER:
            if key in ev:
                sc, ws = score_bot_summary(key, ev[key])
                bot_pts += sc
                work_sec += ws
    return bot_pts, work_sec


async def build_team_rankings(
    ref_date: date,
    *,
    employees: list[str],
    sum_period_total: Callable[[str, str], Awaitable[int]],
    get_period_key: Callable[[date | None], str],
    employee_tg_map: dict[str, int],
) -> tuple[list[LeaderRow], int, str]:
    period = get_period_key(ref_date)
    days = period_days_through(period, ref_date)
    scores: list[tuple[str, int, int]] = []

    for emp in employees:
        cat_pts = 0
        for name in employee_name_variants(emp):
            cat_pts += await sum_period_total(period, name)
        bot_pts = 0
        work_sec = 0
        tg_set = tg_ids_for_employee(emp, employee_tg_map=employee_tg_map)
        if tg_set and days:
            bot_pts, work_sec = await _bot_points_in_period(tg_set, days)
        scores.append((emp, cat_pts + bot_pts, work_sec))

    scores.sort(key=lambda x: (-x[1], x[0]))
    max_sc = max((s[1] for s in scores), default=0)
    active = len([s for s in scores if s[1] > 0])
    leaders: list[LeaderRow] = []
    for i, (name, pts, wsec) in enumerate(scores, 1):
        pct = int(100 * pts / max_sc) if max_sc and pts > 0 else 0
        leaders.append(
            LeaderRow(
                rank=i,
                name=name,
                score=pts,
                work_time=_fmt_clock(wsec),
                pct=pct,
            )
        )
    return leaders, active, period


_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def format_ranking_lines(
    period: str,
    ref_date: date,
    leaders: list[LeaderRow],
    active: int,
) -> list[str]:
    lines = [f"Период (2-sana): {period}", f"Holat: {ref_date.isoformat()}", ""]
    lines.append("🏆 REYTING:")
    for row in leaders:
        medal = _MEDALS.get(row.rank, f"{row.rank}.")
        wt = f" · ⏱ {row.work_time}" if row.work_time and row.work_time != "00:00" else ""
        lines.append(f"{medal} {row.name} — {row.score} ochko ({row.pct}%){wt}")
    lines.append("")
    lines.append(f"Jami faol: {active} / {len(leaders)}")
    lines.append("Ochko = period kategoriya + yordamchi botlar (yig'ilgan)")
    return lines
