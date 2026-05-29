"""Xodim rasmlari (Telegram ID bo'yicha)."""

from __future__ import annotations

from datetime import datetime


def init_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS employee_photos (
            tg_id INTEGER PRIMARY KEY,
            data BLOB NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


async def save_photo(db_execute, tg_id: int, data: bytes) -> None:
    await db_execute(
        """
        INSERT INTO employee_photos (tg_id, data, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(tg_id) DO UPDATE SET
            data = excluded.data,
            updated_at = excluded.updated_at
        """,
        (tg_id, data, datetime.now().isoformat(timespec="seconds")),
    )


async def load_photo(db_fetchone, tg_id: int) -> bytes | None:
    row = await db_fetchone("SELECT data FROM employee_photos WHERE tg_id = ?", (tg_id,))
    if not row:
        return None
    return row["data"]
