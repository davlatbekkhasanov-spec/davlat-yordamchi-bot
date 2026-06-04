"""Reyting uchun bonus / jarima (kategoriya va bot ballariga ta'sir qilmaydi)."""

from __future__ import annotations

from datetime import datetime

from employee_tg_map import employee_name_variants

BTN_BONUS = "➕ Бонус очко"
BTN_PENALTY = "➖ Жарима очко"
BTN_ADJ_CONFIRM = "✅ Тасдиқлаш"


def init_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ranking_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            day TEXT NOT NULL,
            employee TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('bonus', 'penalty')),
            points INTEGER NOT NULL CHECK (points > 0),
            admin_tg_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rank_adj_period_emp
        ON ranking_adjustments(period, employee)
        """
    )
    conn.commit()


async def insert_adjustment(
    db_execute,
    *,
    period: str,
    day_iso: str,
    employee: str,
    kind: str,
    points: int,
    admin_tg_id: int,
) -> None:
    now_iso = datetime.now().isoformat(timespec="seconds")
    await db_execute(
        """
        INSERT INTO ranking_adjustments(period, day, employee, kind, points, admin_tg_id, created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (period, day_iso, employee, kind, int(points), int(admin_tg_id), now_iso),
    )


async def period_adjustment_net(db_fetchone, period: str, employee: str) -> int:
    """Bonus − jarima (faqat reyting)."""
    net = 0
    for name in employee_name_variants(employee):
        row = await db_fetchone(
            """
            SELECT
                COALESCE(SUM(CASE WHEN kind = 'bonus' THEN points ELSE 0 END), 0) AS b,
                COALESCE(SUM(CASE WHEN kind = 'penalty' THEN points ELSE 0 END), 0) AS p
            FROM ranking_adjustments
            WHERE period = ? AND employee = ?
            """,
            (period, name),
        )
        if row:
            net += int(row["b"] or 0) - int(row["p"] or 0)
    return net
