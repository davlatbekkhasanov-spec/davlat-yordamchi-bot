"""Guruhdan forward qilingan xabarlarni avtomatik ajratish (barcha ish botlari)."""

from __future__ import annotations

import html
import re

from employee_tg_map import TG_EMPLOYEE, resolve_tg_id
from metrics_import import resolve_employee_name


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(t).replace("\xa0", " ")


def _plain(text: str) -> str:
    return " ".join(_strip_html(text).split())


def parse_uz_duration(text: str) -> int:
    """'1 soat 38 daqiqa 27 soniya', '1 soat 38 daq', '45:30' → soniya."""
    sl = (text or "").lower()
    total = 0
    h = re.search(r"(\d+)\s*soat", sl)
    m = re.search(r"(\d+)\s*daqi?qa", sl)
    s = re.search(r"(\d+)\s*son", sl)
    if h:
        total += int(h.group(1)) * 3600
    if m:
        total += int(m.group(1)) * 60
    if s:
        total += int(s.group(1))
    if total:
        return total
    tok = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", sl)
    if tok:
        a, b = int(tok.group(1)), int(tok.group(2))
        c = int(tok.group(3)) if tok.group(3) else 0
        if tok.group(3):
            return a * 3600 + b * 60 + c
        return a * 60 + b
    return 0


def _parse_day_from_text(text: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def _norm_in_text(employee: str, text_lower: str) -> bool:
    parts = employee.lower().split()
    if len(parts) < 2:
        return employee.lower() in text_lower
    return parts[0] in text_lower and parts[-1][:4] in text_lower


def _find_employee(raw: str, employees: list[str]) -> str | None:
    return resolve_employee_name(raw, employees)


def _event(
    *,
    bot_key: str,
    employee: str,
    day: str,
    service_sec: int = 0,
    summary_override: str | None = None,
    sklad_count: int = 0,
    ishxona_count: int = 0,
    order_id: int | None = None,
    raw_hint: str = "",
) -> dict:
    tid = int(resolve_tg_id(employee) or 0)
    return {
        "bot_key": bot_key,
        "employee": employee,
        "tg_id": tid,
        "day": day,
        "service_sec": int(service_sec or 0),
        "sklad_count": int(sklad_count or 0),
        "ishxona_count": int(ishxona_count or 0),
        "order_id": order_id,
        "summary_override": summary_override,
        "raw_hint": raw_hint or bot_key,
    }


def _try_hub_line(text: str, employees: list[str], fallback_day: str | None) -> list[dict]:
    line = (text or "").strip()
    if not line.startswith("HUB|"):
        return []
    parts = line.split("|", 4)
    if len(parts) < 5:
        return []
    day_s, tg_s, bot_key, summary = parts[1], parts[2], parts[3], parts[4]
    day = _parse_day_from_text(day_s) or fallback_day
    if not day:
        return []
    tg_id = int(tg_s) if str(tg_s).isdigit() else 0
    emp = None
    for name, tid in TG_EMPLOYEE.items():
        if int(tid) == tg_id:
            emp = name
            break
    if not emp:
        for e in employees:
            if int(resolve_tg_id(e) or 0) == tg_id:
                emp = e
                break
    if not emp:
        emp = f"tg_{tg_id}"
    return [
        _event(
            bot_key=bot_key.strip().lower(),
            employee=emp,
            day=day,
            summary_override=summary.strip(),
            raw_hint="hub_line",
        )
    ]


def _try_ombor(raw: str, plain: str, employees: list[str], fallback_day: str | None) -> list[dict]:
    tl = plain.lower()
    if not any(
        x in tl
        for x in (
            "mijozga qarang",
            "xizmat ko'rsat",
            "xizmat korsat",
            "xizmat yakunlandi",
            "bajarildi",
        )
    ):
        return []

    emp = None
    for pat in (
        r"(?:Xizmat|xizmat)\s+ko.?rsat\w*\s*:\s*(.+?)(?:\n|🔗|⏱|✅|$)",
        r"Jamoa[^:]*:\s*(.+?)(?:\n|⏱|👤|$)",
        r"👷\s+Jamoa[^:]*:\s*(.+?)(?:\n|⏱|$)",
    ):
        m = re.search(pat, raw, re.I | re.S)
        if m:
            emp = _find_employee(m.group(1).strip(), employees)
            if emp:
                break

    if not emp:
        for e in employees:
            if _norm_in_text(e, tl):
                emp = e
                break
    if not emp:
        return []

    day = None
    done_m = re.search(r"tugadi\s*:\s*(\d{4}-\d{2}-\d{2})", raw, re.I)
    if done_m:
        day = done_m.group(1)
    if not day:
        day = _parse_day_from_text(raw) or fallback_day
    if not day:
        return []

    sec = 0
    for pat in (
        r"(?:Xizmat|xizmat)\s+vaqti\s*:\s*(.+?)(?:\n|✅|$)",
        r"Vaqt\s*:\s*(.+?)(?:\n|👤|$)",
        r"⏱\s+Vaqt\s*:\s*(.+?)(?:\n|👤|$)",
    ):
        dm = re.search(pat, raw, re.I | re.S)
        if dm:
            sec = parse_uz_duration(dm.group(1))
            if sec:
                break
    if not sec:
        sec = parse_uz_duration(raw)

    oid_m = re.search(r"#\s*(\d+)", raw)
    order_id = int(oid_m.group(1)) if oid_m else None
    return [
        _event(
            bot_key="ombor",
            employee=emp,
            day=day,
            service_sec=sec,
            order_id=order_id,
            raw_hint=f"ombor #{order_id or '?'}",
        )
    ]


def _try_omborga(raw: str, plain: str, employees: list[str], fallback_day: str | None) -> list[dict]:
    tl = plain.lower()
    compact = re.search(
        r"reys\s+(\d+).*?ish\s+([\d:]+).*?dam\s+([\d:]+)",
        tl,
        re.I | re.S,
    )
    yakun = "ishini yakunladi" in tl or "yakuniy hisobot" in tl or "ish muvaffaqiyatli yakunlandi" in tl

    if not compact and not (yakun and re.search(r"reys", tl)):
        if not (re.search(r"reys\s+\d+", tl) and re.search(r"\bish\b", tl)):
            return []

    emp = None
    m = re.search(r"([\w\s'.-]+)\s+ishini\s+yakunladi", raw, re.I)
    if m:
        emp = _find_employee(m.group(1).strip(), employees)
    if not emp:
        m = re.search(r"👤\s+(.+?)(?:\n|🪪)", raw, re.S)
        if m:
            emp = _find_employee(_strip_html(m.group(1)).strip(), employees)
    if not emp:
        for e in employees:
            if _norm_in_text(e, tl):
                emp = e
                break
    if not emp:
        return []

    day = _parse_day_from_text(raw) or fallback_day
    if not day:
        return []

    if compact:
        reys_n = int(compact.group(1))
        ish_t = compact.group(2)
        dam_t = compact.group(3)
        summary = f"Reys {reys_n}, ish {ish_t}, dam {dam_t}"
    else:
        reys_m = re.search(r"reys\s*(\d+)", tl)
        reys_n = int(reys_m.group(1)) if reys_m else 0
        trips_m = re.search(r"reyslar?\s+(\d+)", tl)
        if trips_m:
            reys_n = max(reys_n, int(trips_m.group(1)))
        ish_m = re.search(r"ish\s+([\d:]+)", tl)
        dam_m = re.search(r"dam\s+([\d:]+)", tl)
        if not ish_m:
            ish_m = re.search(r"ish\s+vaqti\s+([\d:\s]+?)(?:\n|$)", raw, re.I)
        if not dam_m:
            dam_m = re.search(r"dam\s+olish[^0-9]*([\d:]+)", raw, re.I)
        parts = []
        if reys_n:
            parts.append(f"Reys {reys_n}")
        if ish_m:
            parts.append(f"ish {ish_m.group(1).strip()}")
        if dam_m:
            parts.append(f"dam {dam_m.group(1).strip()}")
        summary = ", ".join(parts) if parts else "Reys 0"

    return [
        _event(
            bot_key="omborga",
            employee=emp,
            day=day,
            summary_override=summary,
            raw_hint="omborga",
        )
    ]


def _try_yuk(raw: str, plain: str, employees: list[str], fallback_day: str | None) -> list[dict]:
    tl = plain.lower()
    if not any(
        x in tl
        for x in (
            "reyting",
            "yuk #",
            "yuk keldi",
            "jarayon yakunlandi",
            "yuk muvaffaqiyatli",
            "jamoa ish vaqti",
        )
    ):
        return []

    day = _parse_day_from_text(raw) or fallback_day
    if not day:
        return []

    out: list[dict] = []
    # Reyting: har bir qator — alohida xodim
    if "reyting" in tl:
        for m in re.finditer(
            r"(?:│\s*)?(?:\d+\.|🥇|🥈|🥉)?\s*(.+?)\s*\n\s*(?:│\s*)?.*?⏱\s+([\d:\s]+?(?:soat|daq|soniya)?[\d:\s]*)",
            raw,
            re.I | re.S,
        ):
            name = _strip_html(m.group(1)).strip()
            emp = _find_employee(name, employees)
            if not emp:
                continue
            sec = parse_uz_duration(m.group(2))
            if sec:
                out.append(
                    _event(
                        bot_key="yuk",
                        employee=emp,
                        day=day,
                        service_sec=sec,
                        raw_hint="yuk reyting",
                    )
                )

    # Jamoa ish vaqti (kaizen)
    jm = re.search(r"jamoa\s+ish\s+vaqti\s*:\s*(.+?)(?:\n|$)", raw, re.I)
    if jm and not out:
        sec = parse_uz_duration(jm.group(1))
        masul_m = re.search(r"mas.?ul\s+(.+?)(?:\n|📡)", raw, re.I)
        emp = _find_employee(masul_m.group(1).strip(), employees) if masul_m else None
        if not emp:
            for e in employees:
                if _norm_in_text(e, tl):
                    emp = e
                    break
        if emp and sec:
            out.append(
                _event(
                    bot_key="yuk",
                    employee=emp,
                    day=day,
                    service_sec=sec,
                    raw_hint="yuk kaizen",
                )
            )

    # Guruh kartasidagi jamoa qatorlari (HTML)
    if not out:
        for m in re.finditer(
            r"<b>([^<]+)</b>\s+<i>(?:FAOL|PAUZA)</i>.*?⏱\s+<b>([^<]+)</b>",
            raw,
            re.I | re.S,
        ):
            emp = _find_employee(_strip_html(m.group(1)).strip(), employees)
            sec = parse_uz_duration(m.group(2))
            if emp and sec:
                out.append(
                    _event(
                        bot_key="yuk",
                        employee=emp,
                        day=day,
                        service_sec=sec,
                        raw_hint="yuk jamoa",
                    )
                )

    # Oddiy matn: ism qatori + keyingi qatorda ⏱ / vaqt
    if not out:
        lines = [_strip_html(x).strip() for x in raw.splitlines()]
        for i, line in enumerate(lines):
            if "⏱" not in line and not re.search(r"\d{1,2}:\d{2}", line):
                continue
            dur_m = re.search(r"⏱\s+(.+)$", line) or re.search(
                r"(\d+\s*soat.+|\d{1,2}:\d{2}(?::\d{2})?)", line, re.I
            )
            if not dur_m:
                continue
            sec = parse_uz_duration(dur_m.group(1))
            if not sec:
                continue
            emp = None
            for j in range(i - 1, max(-1, i - 4), -1):
                if j < 0:
                    break
                cand = re.sub(r"^[│\s🥇🥈🥉\d.]+\s*", "", lines[j]).strip()
                if len(cand) < 4:
                    continue
                emp = _find_employee(cand, employees)
                if emp:
                    break
            if emp:
                out.append(
                    _event(
                        bot_key="yuk",
                        employee=emp,
                        day=day,
                        service_sec=sec,
                        raw_hint="yuk line",
                    )
                )

    return out


def _try_sklad(raw: str, plain: str, employees: list[str], fallback_day: str | None) -> list[dict]:
    tl = plain.lower()
    if not any(x in tl for x in ("tekshiruv", "sanaldi", "саналди", "papka", "папка", "📁")):
        return []

    emp = None
    m = re.search(r"👤\s*(?:<b>)?([^<\n]+)", raw, re.I)
    if m:
        emp = _find_employee(_strip_html(m.group(1)).strip(), employees)
    if not emp:
        for e in employees:
            if _norm_in_text(e, tl):
                emp = e
                break
    if not emp:
        return []

    day = _parse_day_from_text(raw) or fallback_day
    if not day:
        return []

    cnt = 0
    sm = re.search(r"(?:✅\s*)?(?:[СсС]аналди|sanaldi)\s*:\s*(\d+)", raw, re.I)
    if sm:
        cnt = int(sm.group(1))
    if not cnt:
        sm = re.search(r"(?:sanaldi|саналди)\s+(\d+)", tl)
        if sm:
            cnt = int(sm.group(1))
    if not cnt:
        cnt = 1

    return [
        _event(
            bot_key="sklad",
            employee=emp,
            day=day,
            sklad_count=cnt,
            raw_hint="sklad",
        )
    ]


def _try_ishxona(raw: str, plain: str, employees: list[str], fallback_day: str | None) -> list[dict]:
    tl = plain.lower()
    if "шикоят" not in tl and "shikoyat" not in tl:
        return []

    emp = None
    for pat in (r"ходим\s*:\s*(.+?)(?:\n|кимдан|$)", r"Ходим\s*:\s*(.+?)(?:\n|Кимдан|$)"):
        m = re.search(pat, raw, re.I)
        if m:
            emp = _find_employee(_strip_html(m.group(1)).strip(), employees)
            if emp:
                break
    if not emp:
        for e in employees:
            if _norm_in_text(e, tl):
                emp = e
                break
    if not emp:
        return []

    day = _parse_day_from_text(raw) or fallback_day
    if not day:
        return []

    preview = ""
    pm = re.search(r"шикоят\s+мазмуни\s*:\s*(.+)$", raw, re.I | re.S)
    if pm:
        preview = _plain(pm.group(1))[:80]
    if not preview:
        preview = "forward"

    return [
        _event(
            bot_key="ishxona",
            employee=emp,
            day=day,
            ishxona_count=1,
            summary_override=f"Shikoyat ({emp}): {preview}",
            raw_hint="ishxona",
        )
    ]


def parse_forward_text(
    text: str,
    *,
    employees: list[str],
    fallback_day: str | None = None,
) -> list[dict]:
    """
    Bitta forward xabardan 0..n ta event.
    Bot turi avtomatik aniqlanadi; aralash forwardlar /forwarddone da jamlanadi.
    """
    if not text or len(text.strip()) < 12:
        return []

    raw = text.strip()
    plain = _plain(raw)

    for parser in (
        lambda: _try_hub_line(raw, employees, fallback_day),
        lambda: _try_ombor(raw, plain, employees, fallback_day),
        lambda: _try_omborga(raw, plain, employees, fallback_day),
        lambda: _try_yuk(raw, plain, employees, fallback_day),
        lambda: _try_sklad(raw, plain, employees, fallback_day),
        lambda: _try_ishxona(raw, plain, employees, fallback_day),
    ):
        found = parser()
        if found:
            return found
    return []


def aggregate_hub_events(items: list[dict]) -> list[dict]:
    """Kun + xodim + bot bo'yicha jamlash."""
    buckets: dict[tuple[str, int, str], dict] = {}
    for it in items:
        key = (it["day"], int(it["tg_id"]), it["bot_key"])
        if key not in buckets:
            buckets[key] = {
                "day": it["day"],
                "tg_id": int(it["tg_id"]),
                "bot_key": it["bot_key"],
                "employee": it["employee"],
                "total_sec": 0,
                "sklad_sum": 0,
                "ishxona_n": 0,
                "count": 0,
                "summaries": [],
            }
        b = buckets[key]
        b["count"] += 1
        if it.get("summary_override"):
            b["summaries"].append(it["summary_override"])
        else:
            b["total_sec"] += int(it.get("service_sec") or 0)
        b["sklad_sum"] += int(it.get("sklad_count") or 0)
        b["ishxona_n"] += int(it.get("ishxona_count") or 0)

    out: list[dict] = []
    for b in buckets.values():
        key = b["bot_key"]
        if b["summaries"] and key in ("omborga", "ishxona"):
            summary = b["summaries"][-1]
        elif key == "ombor":
            summary = (
                f"Ombor (forward jami): {b['count']} ta, "
                f"ish vaqti {b['total_sec']} soniya"
            )
        elif key == "yuk":
            summary = f"Yuk (forward jami): ish vaqti {b['total_sec']} soniya"
        elif key == "sklad":
            n = b["sklad_sum"] or b["count"]
            summary = f"Sklad (forward jami): sanaldi {n}"
        elif key == "ishxona":
            n = b["ishxona_n"] or b["count"]
            summary = f"Ishxona (forward jami): shikoyat {n}"
        elif b["summaries"]:
            summary = b["summaries"][-1]
        else:
            summary = f"{key}: {b['count']} ta event"
        out.append(
            {
                "day": b["day"],
                "tg_id": b["tg_id"],
                "bot_key": key,
                "employee": b["employee"],
                "summary": summary,
                "count": b["count"],
            }
        )
    return out
