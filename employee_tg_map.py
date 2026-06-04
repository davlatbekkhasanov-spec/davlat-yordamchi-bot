"""Telegram user_id → ism (hisobot biriktirish)."""

from __future__ import annotations

import re

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
    8472656729: "Tuvalov Farrux",
}

# Bot ro'yxatidagi ismlar (EMPLOYEES) → tg_id
EMPLOYEE_NAME_ALIASES: dict[str, int] = {
    "Yadullaev Umidjon": 924612402,
    "Yadullaev Umid": 924612402,
    "Samadov To'lqin": 6001619806,
    "Samadov Tulqin": 6001619806,
    "Ravshanov Oxunjon": 5412958249,
    "Oxunjon": 5412958249,
    "Охунжон": 5412958249,
    "Ravshanov Ziyodullo": 8440127425,
    "Ravshanov_Z_": 8440127425,
    "Mustafoev Abdullo": 6931958983,
    "Abdullo Mustafoyev": 6931958983,
    "Ruziboev Sindor": 8547365654,
    "Ruziboev sindorbek": 8547365654,
    "Toxirov Muslimbek": 5732350707,
    "Тохиров Муслимбек": 5732350707,
    "Shernazarov Tolib": 5465963344,
    "Толиб Шерназаров": 5465963344,
    "Sagdullaev Yunus": 6991673998,
    "Sagdullaev": 6991673998,
    "Tuvalov Farrux": 8472656729,
    "Тувалов Фаррух": 8472656729,
    "Rajabboev Pulat": 8472656729,
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
    owner = resolve_owner_tg_id(name)
    if owner:
        for alias, tid in EMPLOYEE_NAME_ALIASES.items():
            if tid == owner:
                add(alias)
        for tid, canonical in TG_EMPLOYEE.items():
            if tid == owner:
                add(canonical)
    return out


# Guruh kartalaridagi qisqa ismlar → EMPLOYEES dagi to'liq ism
SHORT_NAME_ALIASES: dict[str, str] = {
    "охунжон": "Ravshanov Oxunjon",
    "oxunjon": "Ravshanov Oxunjon",
    "ravshanov oxunjon": "Ravshanov Oxunjon",
    "ravshanov_z_": "Ravshanov Ziyodullo",
    "ravshanov z": "Ravshanov Ziyodullo",
    "ziyodullo": "Ravshanov Ziyodullo",
    "abdullo mustafoyev": "Mustafoev Abdullo",
    "mustafoyev abdullo": "Mustafoev Abdullo",
    "mustafoev abdullo": "Mustafoev Abdullo",
    "ruziboev sindorbek": "Ruziboev Sindor",
    "sindorbek": "Ruziboev Sindor",
    "тохиров муслимбек": "Toxirov Muslimbek",
    "toxirov muslimbek": "Toxirov Muslimbek",
    "толиб шерназаров": "Shernazarov Tolib",
    "shernazarov tolib": "Shernazarov Tolib",
    "толиб": "Shernazarov Tolib",
    "tolib": "Shernazarov Tolib",
    "samadov tolqin": "Samadov To'lqin",
    "samadov to'lqin": "Samadov To'lqin",
    "to'lqin": "Samadov To'lqin",
    "sagdullaev": "Sagdullaev Yunus",
    "yunus": "Sagdullaev Yunus",
    "tuvalov farrux": "Tuvalov Farrux",
    "farrux": "Tuvalov Farrux",
    "тувалов фаррух": "Tuvalov Farrux",
    "rajabboev pulat": "Tuvalov Farrux",
}


def _alias_key(raw: str) -> str:
    s = (raw or "").strip().lower()
    for ch in ("õ", "ö", "ó", "ô", "'", "'", "`", "ʻ", "ʼ", "’"):
        s = s.replace(ch, "o" if ch in ("õ", "ö", "ó", "ô") else "")
    s = re.sub(r"[_]+", " ", s)
    return " ".join(s.split())


def resolve_employee_label(raw: str, employees: list[str] | None = None) -> str | None:
    """Karta/qisqa ism → ro'yxatdagi to'liq ism."""
    raw = (raw or "").strip()
    if not raw or raw in ("(-_)", "(-_-)", "-_-", "(-_-"):
        return None
    key = _alias_key(raw)
    if key in SHORT_NAME_ALIASES:
        return SHORT_NAME_ALIASES[key]
    if raw in EMPLOYEE_NAME_ALIASES:
        return TG_EMPLOYEE.get(int(EMPLOYEE_NAME_ALIASES[raw]))
    for alias, tid in EMPLOYEE_NAME_ALIASES.items():
        if _alias_key(alias) == key:
            return TG_EMPLOYEE.get(int(tid))
    if employees:
        from metrics_import import resolve_employee_name

        return resolve_employee_name(raw, employees)
    return None


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
