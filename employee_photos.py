"""Xodim rasmlari (tg_id va ism bo'yicha)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from employee_registry import TG_EMPLOYEE, canonical_employee_name
from employee_tg_map import resolve_owner_tg_id

LEGACY_PHOTO_NAMES = (
    "Yadullaev Umidjon",
    "Yadullaev Umid",
    "Yadullaev Umid",
    "Ядуллаев Умид",
    "Ядуллаев Умиджон",
)
LEGACY_PHOTO_TG_ID = 924612402
OZODBEK_TG_ID = 7844168817
OZODBEK_CANONICAL = "Ergashev Ozodbek"

BUNDLED_PHOTOS_DIR = Path(__file__).resolve().parent / "assets" / "employee_photos"


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


async def load_photo_for_employee(
    db_fetchone,
    *,
    tg_id: int | None = None,
    employee: str | None = None,
) -> bytes | None:
    # Faqat rasmiy ism + owner tg_id — Yadullaev aliaslari eski rasm bermasligi uchun.
    if employee:
        canon = canonical_employee_name(employee)
        for name in (canon, employee):
            if not name:
                continue
            row = await db_fetchone(
                "SELECT data FROM employee_photos_by_name WHERE employee = ?",
                (name,),
            )
            if row:
                return row["data"]
        owner = resolve_owner_tg_id(employee)
        if owner:
            saved = await load_photo(db_fetchone, owner)
            if saved:
                return saved
    elif tg_id:
        saved = await load_photo(db_fetchone, tg_id)
        if saved:
            return saved
    return None


def _upsert_photo_sync(conn, *, employee: str, tg_id: int | None, data: bytes) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO employee_photos_by_name (employee, data, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(employee) DO UPDATE SET
            data = excluded.data,
            updated_at = excluded.updated_at
        """,
        (employee, data, now),
    )
    if tg_id:
        conn.execute(
            """
            INSERT INTO employee_photos (tg_id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (int(tg_id), data, now),
        )


def migrate_legacy_employee_photos(conn) -> int:
    """Yadullaev / eski tg_id rasmlarini o'chirish."""
    n = 0
    for name in LEGACY_PHOTO_NAMES:
        cur = conn.execute("DELETE FROM employee_photos_by_name WHERE employee = ?", (name,))
        n += cur.rowcount
    cur = conn.execute("DELETE FROM employee_photos WHERE tg_id = ?", (LEGACY_PHOTO_TG_ID,))
    n += cur.rowcount
    return n


def seed_bundled_employee_photos(conn) -> int:
    """Repo assets/employee_photos → DB (deployda yangilanadi)."""
    if not BUNDLED_PHOTOS_DIR.is_dir():
        return 0
    n = 0
    for path in sorted(BUNDLED_PHOTOS_DIR.iterdir()):
        if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        stem = path.stem.strip()
        data = path.read_bytes()
        if not data:
            continue
        employee = stem
        tg_id = None
        if stem.isdigit():
            tg_id = int(stem)
            employee = TG_EMPLOYEE.get(tg_id) or employee
        elif stem == OZODBEK_CANONICAL:
            tg_id = OZODBEK_TG_ID
        owner = resolve_owner_tg_id(employee) or tg_id
        canon = canonical_employee_name(employee)
        _upsert_photo_sync(conn, employee=canon, tg_id=owner, data=data)
        n += 1
    return n


def bootstrap_employee_photos(conn) -> dict[str, int]:
    removed = migrate_legacy_employee_photos(conn)
    seeded = seed_bundled_employee_photos(conn)
    conn.commit()
    return {"removed_legacy": removed, "seeded": seeded}
