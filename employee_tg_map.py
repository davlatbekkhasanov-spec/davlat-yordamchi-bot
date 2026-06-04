"""Telegram user_id → ism (hisobot biriktirish)."""

from __future__ import annotations

from employee_registry import (
    CANONICAL_TUVALOV,
    EMPLOYEE_NAME_ALIASES,
    SHORT_NAME_ALIASES,
    TG_EMPLOYEE,
    TUVALOV_FARRUX_TG_ID,
    canonical_employee_name,
    resolve_employee_tg_id as _registry_tg_id,
)

__all__ = [
    "TG_EMPLOYEE",
    "EMPLOYEE_NAME_ALIASES",
    "TUVALOV_FARRUX_TG_ID",
    "CANONICAL_TUVALOV",
    "canonical_employee_name",
    "resolve_owner_tg_id",
    "employee_name_variants",
    "resolve_tg_id",
    "tg_ids_for_employee",
]


def _norm_name(name: str) -> str:
    s = name.lower().strip()
    for ch in ("'", "'", "`", "ʻ", "ʼ", "’"):
        s = s.replace(ch, "")
    return " ".join(s.split())


def _last_name_match(a: str, b: str) -> bool:
    if a == b:
        return True
    return a.startswith(b) or b.startswith(a)


def resolve_owner_tg_id(name: str) -> int | None:
    """Xodimning o'z Telegram ID — hozir kim PIN bilan ulangan emas."""
    return resolve_tg_id(name, linked=None)


def employee_name_variants(name: str) -> list[str]:
    """Rasm jadvalida qidirish uchun ism variantlari."""
    seen: set[str] = set()
    out: list[str] = []

    def add(n: str) -> None:
        n = (n or "").strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)

    add(name)
    add(canonical_employee_name(name))
    owner = resolve_owner_tg_id(name)
    if owner:
        for alias, tid in EMPLOYEE_NAME_ALIASES.items():
            if tid == owner:
                add(alias)
        for tid, canonical in TG_EMPLOYEE.items():
            if tid == owner:
                add(canonical)
    return out


def resolve_tg_id(name: str, linked: dict[str, int] | None = None) -> int | None:
    """EMPLOYEES ro'yxati va TG_EMPLOYEE orasidagi ism farqlarini hal qiladi."""
    if not name:
        return None
    canon = canonical_employee_name(name)
    if linked and canon in linked:
        return int(linked[canon])
    if linked and name in linked:
        return int(linked[name])
    tid = _registry_tg_id(name)
    if tid:
        return tid
    target = _norm_name(canon)
    if linked:
        for emp, tg_id in linked.items():
            if _norm_name(emp) == target:
                return int(tg_id)
    for tg_id, emp in TG_EMPLOYEE.items():
        if _norm_name(emp) == target:
            return int(tg_id)

    tp = target.split()
    if len(tp) >= 2:
        for tg_id, emp in TG_EMPLOYEE.items():
            ep = _norm_name(emp).split()
            if len(ep) >= 2 and tp[0] == ep[0] and _last_name_match(tp[-1], ep[-1]):
                return int(tg_id)
        if linked:
            for emp, tg_id in linked.items():
                ep = _norm_name(emp).split()
                if len(ep) >= 2 and tp[0] == ep[0] and _last_name_match(tp[-1], ep[-1]):
                    return int(tg_id)
    return None


def tg_ids_for_employee(
    name: str,
    *,
    employee_tg_map: dict[str, int] | None = None,
    linked: dict[str, int] | None = None,
) -> set[int]:
    """Bir xodim uchun barcha mumkin tg_id (alias + PIN link + ro'yxat)."""
    out: set[int] = set()
    for n in employee_name_variants(name):
        if employee_tg_map and n in employee_tg_map:
            out.add(int(employee_tg_map[n]))
        tid = resolve_tg_id(n, linked=linked)
        if tid:
            out.add(int(tid))
    return out
