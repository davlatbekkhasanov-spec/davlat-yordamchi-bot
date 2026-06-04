"""Guruh/CSV dan kategoriya ko'rsatkichlarini import qilish."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta


def period_key_for_day(day_iso: str) -> str:
    d = date.fromisoformat(day_iso)
    if d.day >= 2:
        return d.strftime("%Y-%m")
    prev = d.replace(day=1) - timedelta(days=1)
    return prev.strftime("%Y-%m")

# day|employee|category|value  yoki  day,employee,category,value


def _norm_name(name: str) -> str:
    s = name.lower().strip()
    for ch in ("'", "'", "`", "ʻ", "ʼ", "’"):
        s = s.replace(ch, "")
    return " ".join(s.split())


def resolve_employee_name(raw: str, employees: list[str]) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw in employees:
        return raw
    target = _norm_name(raw)
    for emp in employees:
        if _norm_name(emp) == target:
            return emp
    tp = target.split()
    if len(tp) >= 2:
        for emp in employees:
            ep = _norm_name(emp).split()
            if len(ep) >= 2 and tp[0] == ep[0] and (
                ep[-1].startswith(tp[-1]) or tp[-1].startswith(ep[-1])
            ):
                return emp
    return None


def _parse_day(raw: str) -> str | None:
    s = (raw or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d).isoformat()
    return None


def _parse_value(raw: str) -> int | None:
    s = (raw or "").strip().replace("+", "").replace(" ", "")
    if not s.isdigit():
        return None
    return int(s)


def parse_import_text(
    text: str,
    *,
    employees: list[str],
    categories: list[str],
    default_day: str | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Qatorlarni parse qiladi.
    Formatlar:
      2026-06-03|Mustafoev Abdullo|Приход|12
      2026-06-03,Mustafoev Abdullo,Приход,12
      03.06.2026  Mustafoev Abdullo  Приход  +12
    """
    rows: list[dict] = []
    errors: list[str] = []
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return [], ["Matn bo'sh"]

    # CSV header?
    if lines[0].lower().replace(" ", "") in {
        "day,employee,category,value",
        "sana,xodim,kategoriya,qiymat",
    }:
        lines = lines[1:]

    for i, line in enumerate(lines, 1):
        day_s = emp_s = cat_s = val_s = None
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                day_s, emp_s, cat_s, val_s = parts[0], parts[1], parts[2], parts[3]
        elif "," in line and line.count(",") >= 3:
            parts = next(csv.reader([line]))
            if len(parts) >= 4:
                day_s, emp_s, cat_s, val_s = parts[0], parts[1], parts[2], parts[3]
        else:
            m = re.match(
                r"^(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})\s+(.+?)\s+(.+?)\s+\+?(\d+)\s*$",
                line,
            )
            if m:
                day_s, emp_s, cat_s, val_s = m.group(1), m.group(2), m.group(3), m.group(4)
            else:
                # employee | category | value (bugun)
                parts = re.split(r"\s{2,}|\t+", line)
                if len(parts) >= 3:
                    emp_s, cat_s, val_s = parts[0], parts[1], parts[2]

        day_iso = _parse_day(day_s or "") if day_s else default_day
        if not day_iso:
            errors.append(f"{i}: sana noto'g'ri — {line[:60]}")
            continue

        emp = resolve_employee_name(emp_s or "", employees)
        if not emp:
            errors.append(f"{i}: xodim topilmadi — {emp_s}")
            continue

        cat = (cat_s or "").strip()
        if cat not in categories:
            errors.append(f"{i}: kategoriya topilmadi — {cat}")
            continue

        val = _parse_value(val_s or "")
        if val is None:
            errors.append(f"{i}: qiymat noto'g'ri — {val_s}")
            continue

        rows.append(
            {
                "day": day_iso,
                "period": period_key_for_day(day_iso),
                "employee": emp,
                "category": cat,
                "value": val,
            }
        )

    return rows, errors


def parse_import_csv_bytes(
    data: bytes,
    *,
    employees: list[str],
    categories: list[str],
    default_day: str | None = None,
) -> tuple[list[dict], list[str]]:
    text = data.decode("utf-8-sig", errors="replace")
    return parse_import_text(
        text, employees=employees, categories=categories, default_day=default_day
    )


async def insert_import_rows(
    db_execute,
    rows: list[dict],
    *,
    tg_id: int = 0,
) -> int:
    now_iso = datetime.now().isoformat(timespec="seconds")
    n = 0
    for r in rows:
        await db_execute(
            """
            INSERT INTO reports(day, period, tg_id, employee, category, value, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                r["day"],
                r["period"],
                int(tg_id),
                r["employee"],
                r["category"],
                int(r["value"]),
                now_iso,
            ),
        )
        n += 1
    return n
