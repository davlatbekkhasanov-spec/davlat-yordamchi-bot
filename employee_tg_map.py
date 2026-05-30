"""Telegram user_id → ism (hisobot biriktirish)."""

from __future__ import annotations

TG_EMPLOYEE: dict[int, str] = {
    924612402: "Yadullaev Umid",
    5412958249: "Ravshanov Oxunjon",
    8547365654: "Ruziboev Sindor",
    6931958983: "Mustafoev Abdullo",
    6991673998: "Sagdullaev Yunus",
    5465963344: "Shernazarov Tolib",
    6001619806: "Samadov Tulqin",
    5732350707: "Toxirov Muslimbek",
    8440127425: "Ravshanov Ziyodullo",
}

# Bot ro'yxatidagi ismlar (EMPLOYEES) → tg_id
EMPLOYEE_NAME_ALIASES: dict[str, int] = {
    "Yadullaev Umidjon": 924612402,
    "Yadullaev Umid": 924612402,
    "Samadov To'lqin": 6001619806,
    "Samadov Tulqin": 6001619806,
}


def _norm_name(name: str) -> str:
    s = name.lower().strip()
    for ch in ("'", "'", "`", "ʻ", "ʼ", "’"):
        s = s.replace(ch, "")
    return " ".join(s.split())


def _last_name_match(a: str, b: str) -> bool:
    if a == b:
        return True
    return a.startswith(b) or b.startswith(a)


def resolve_tg_id(name: str, linked: dict[str, int] | None = None) -> int | None:
    """EMPLOYEES ro'yxati va TG_EMPLOYEE orasidagi ism farqlarini hal qiladi."""
    if not name:
        return None
    if linked and name in linked:
        return int(linked[name])
    if name in EMPLOYEE_NAME_ALIASES:
        return EMPLOYEE_NAME_ALIASES[name]
    for tg_id, emp in TG_EMPLOYEE.items():
        if emp == name:
            return int(tg_id)

    target = _norm_name(name)
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
