"""Har kuni 00:01 da kunlik ochko reytingini yuborish."""

from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable

from daily_report_card import BOT_ORDER, LeaderRow, score_bot_summary, _fmt_clock
from cross_bot_hub import fetch_latest_by_bot
from employee_tg_map import resolve_owner_tg_id


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


def owner_tg_map(employees: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for emp in employees:
        tid = resolve_owner_tg_id(emp)
        if tid:
            out[emp] = tid
    return out


async def build_team_rankings(
    day_iso: str,
    *,
    employees: list[str],
    sum_day_total: Callable[[str, str], Awaitable[int]],
) -> tuple[list[LeaderRow], int]:
    etg_map = owner_tg_map(employees)
    scores: list[tuple[str, int, int]] = []

    for emp in employees:
        cat_pts = await sum_day_total(day_iso, emp)
        bot_pts = 0
        work_sec = 0
        etg = etg_map.get(emp)
        if etg:
            ev = await fetch_latest_by_bot(etg, day_iso)
            for key in BOT_ORDER:
                if key in ev:
                    sc, ws = score_bot_summary(key, ev[key])
                    bot_pts += sc
                    work_sec += ws
        total = cat_pts + bot_pts
        if total > 0:
            scores.append((emp, total, work_sec))

    scores.sort(key=lambda x: (-x[1], x[0]))
    max_sc = max((s[1] for s in scores), default=1) or 1
    leaders: list[LeaderRow] = []
    for i, (name, pts, wsec) in enumerate(scores, 1):
        pct = int(100 * pts / max_sc) if max_sc else 0
        leaders.append(
            LeaderRow(
                rank=i,
                name=name,
                score=pts,
                work_time=_fmt_clock(wsec),
                pct=pct,
            )
        )
    return leaders, len(scores)


_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def format_ranking_lines(day_iso: str, leaders: list[LeaderRow], active: int) -> list[str]:
    lines = [f"📅 {day_iso}", ""]
    if not leaders:
        lines.append("Бу кун учун очко йўқ.")
        return lines

    lines.append("🏆 РЕЙТИНГ:")
    for row in leaders:
        medal = _MEDALS.get(row.rank, f"{row.rank}.")
        wt = f" · ⏱ {row.work_time}" if row.work_time and row.work_time != "00:00" else ""
        lines.append(f"{medal} {row.name} — {row.score} очко{wt}")

    lines.append("")
    lines.append(f"Жами фаол: {active} \u043d\u0430\u0444\u0430\u0440")
    lines.append("Очко = категория + yordamchi botlar")
    return lines
