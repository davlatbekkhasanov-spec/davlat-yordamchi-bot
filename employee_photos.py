"""Xodim rasmlari (tg_id va ism bo'yicha)."""

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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS employee_photos_by_name (
            employee TEXT PRIMARY KEY,
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


async def save_photo_by_name(db_execute, employee: str, data: bytes) -> None:
    await db_execute(
        """
        INSERT INTO employee_photos_by_name (employee, data, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(employee) DO UPDATE SET
            data = excluded.data,
            updated_at = excluded.updated_at
        """,
        (employee, data, datetime.now().isoformat(timespec="seconds")),
    )


async def save_employee_photo(
    db_execute,
    *,
    employee: str,
    data: bytes,
    tg_id: int | None = None,
) -> None:
    await save_photo_by_name(db_execute, employee, data)
    if tg_id:
        await save_photo(db_execute, int(tg_id), data)


async def load_photo(db_fetchone, tg_id: int) -> bytes | None:
    row = await db_fetchone("SELECT data FROM employee_photos WHERE tg_id = ?", (tg_id,))
    if not row:
        return None
    return row["data"]


async def load_photo_by_name(db_fetchone, employee: str) -> bytes | None:
    row = await db_fetchone(
        "SELECT data FROM employee_photos_by_name WHERE employee = ?",
        (employee,),
    )
    if not row:
        return None
    return row["data"]


async def load_photo_for_employee(
    db_fetchone,
    *,
    tg_id: int | None = None,
    employee: str | None = None,
) -> bytes | None:
    # Hisobotdagi xodim rasmi — avval ism, keyin shu xodimning tg_id (kiruvchi emas).
    if employee:
        saved = await load_photo_by_name(db_fetchone, employee)
        if saved:
            return saved
    if tg_id:
        saved = await load_photo(db_fetchone, tg_id)
        if saved:
            return saved
    return None
