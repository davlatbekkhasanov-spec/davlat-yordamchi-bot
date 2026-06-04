"""Chatdan yopishtirilgan hisobotlarni parse qilish."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from employee_tg_map import TG_EMPLOYEE, resolve_tg_id
from forward_import import aggregate_hub_events, parse_forward_text, parse_uz_duration
from metrics_import import resolve_employee_name

EMPLOYEES = [
    "Sagdullaev Yunus",
    "Toxirov Muslimbek",
    "Ravshanov Oxunjon",
    "Samadov To'lqin",
    "Shernazarov Tolib",
    "Ruziboev Sindor",
    "Ravshanov Ziyodullo",
    "Yadullaev Umidjon",
    "Mustafoev Abdullo",
    "Tuvalov Farrux",
]

ALIASES = {
    "охунжон": "Ravshanov Oxunjon",
    "охунжон ravshanov": "Ravshanov Oxunjon",
    "oxunjon": "Ravshanov Oxunjon",
    "ravshanov oxunjon": "Ravshanov Oxunjon",
    "ravshanov_z_": "Ravshanov Ziyodullo",
    "ravshanov z": "Ravshanov Ziyodullo",
    "ravshanov ziyodullo": "Ravshanov Ziyodullo",
    "ziyodullo": "Ravshanov Ziyodullo",
    "abdullo mustafoyev": "Mustafoev Abdullo",
    "mustafoyev abdullo": "Mustafoev Abdullo",
    "mustafoev abdullo": "Mustafoev Abdullo",
    "ruziboev sindorbek": "Ruziboev Sindor",
    "ruziboev sindor": "Ruziboev Sindor",
    "sindorbek": "Ruziboev Sindor",
    "тохиров муслимбек": "Toxirov Muslimbek",
    "toxirov muslimbek": "Toxirov Muslimbek",
    "толиб шерназаров": "Shernazarov Tolib",
    "shernazarov tolib": "Shernazarov Tolib",
    "толиб": "Shernazarov Tolib",
    "tolib": "Shernazarov Tolib",
    "samadov tõlqin": "Samadov To'lqin",
    "samadov to'lqin": "Samadov To'lqin",
    "samadov tolqin": "Samadov To'lqin",
    "samadov tulqin": "Samadov To'lqin",
    "tõlqin": "Samadov To'lqin",
    "to'lqin": "Samadov To'lqin",
    "sagdullaev": "Sagdullaev Yunus",
    "sagdullaev yunus": "Sagdullaev Yunus",
    "yunus": "Sagdullaev Yunus",
}


def _alias_key(raw: str) -> str:
    s = (raw or "").strip().lower()
    for ch in ("õ", "ö", "ó", "ô", "'", "'", "`", "ʻ", "ʼ", "’"):
        s = s.replace(ch, "o" if ch in ("õ", "ö", "ó", "ô") else "")
    s = re.sub(r"[_]+", " ", s)
    return " ".join(s.split())


def resolve_emp(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw or raw in ("(-_)", "(-_-)", "-_-", "(-_-"):
        return None
    key = _alias_key(raw)
    if key in ALIASES:
        return ALIASES[key]
    return resolve_employee_name(raw, EMPLOYEES)


def _skip_chunk(chunk: str) -> bool:
    cl = chunk.lower()
    if "ombor live" in cl and ("aktiv ishchi yo'q" in cl or "reys taqsimoti" in cl):
        return True
    if "live" in cl and any(
        x in cl
        for x in (
            "xizmatda",
            "jarayonda",
            "yangilan",
            "hozir ishlayapti",
            "⏱ vaqt:",
            "vaqt yangilanmoqda",
        )
    ):
        return True
    if re.search(r"holat:\s*(🔄|jarayonda|xizmatda)", chunk, re.I):
        return True
    if re.search(r"xizmat\s+ko.?rsat\w*", cl) and not re.search(
        r"(tugadi|yakunlandi|bajarildi|yakuniy)", cl
    ):
        return True
    return False


def _day_from_chunk(text: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"🕐\s*(\d{2})\.(\d{2})\.(\d{4})", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def _omborga_from_report(text: str, fallback_day: str | None) -> dict | None:
    if "ishini yakunladi" not in text.lower() and "yakuniy hisobot" not in text.lower():
        return None
    m = re.search(r"ishini\s+yakunladi", text, re.I)
    emp_raw = ""
    if m:
        head = text[: m.start()]
        emp_raw = head.split("\n")[-1].replace("🏁", "").strip()
        if not emp_raw:
            same = re.search(r"([^\n🏁]+?)\s+ishini\s+yakunladi", text, re.I)
            if same:
                emp_raw = same.group(1).strip()
    if not emp_raw:
        em = re.search(r"👤\s*(.+?)(?:\n|🪪)", text)
        if em:
            emp_raw = em.group(1).strip()
    emp = resolve_emp(emp_raw)
    if not emp:
        return None
    day = _day_from_chunk(text) or fallback_day
    if not day:
        return None
    reys_m = re.search(r"reyslar?\s*\n?\s*(\d+)", text, re.I)
    reys = int(reys_m.group(1)) if reys_m else 0
    ish_m = re.search(r"ish\s+vaqti\s*\n?\s*(.+?)(?:\n|📦)", text, re.I | re.S)
    dam_m = re.search(r"dam\s+olish[^0-9]*\n?\s*(.+?)(?:\n|📦)", text, re.I | re.S)
    ish_t = "0:00"
    dam_t = "0:00"
    if ish_m:
        ish_sec = parse_uz_duration(ish_m.group(1))
        h, r = divmod(max(0, ish_sec), 3600)
        m, s = divmod(r, 60)
        ish_t = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    if dam_m:
        dam_sec = parse_uz_duration(dam_m.group(1))
        m, s = divmod(max(0, dam_sec), 60)
        dam_t = f"{m}:{s:02d}"
    summary = f"Reys {reys}, ish {ish_t}, dam {dam_t}"
    return {
        "bot_key": "omborga",
        "employee": emp,
        "tg_id": int(resolve_tg_id(emp) or 0),
        "day": day,
        "summary_override": summary,
    }


def split_chunks(raw: str) -> list[tuple[str, str | None]]:
    """Matn bo'laklari va Telegram sarlavhasidagi kun (DD.MM.YYYY)."""
    pat = re.compile(
        r"\[(\d{1,2})\.(\d{1,2})\.(\d{4})\s+\d{1,2}:\d{1,2}\]\s+[^:]+:\s*",
        re.I,
    )
    out: list[tuple[str, str | None]] = []
    matches = list(pat.finditer(raw))
    for i, m in enumerate(matches):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        day_s = f"{y:04d}-{mo:02d}-{d:02d}"
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[m.end() : end].strip()
        if len(body) > 25:
            out.append((body, day_s))
    if not matches:
        body = raw.strip()
        if len(body) > 25:
            out.append((body, _day_from_chunk(raw)))
    return out


def process(raw: str) -> list[dict]:
    items: list[dict] = []
    for chunk, header_day in split_chunks(raw):
        if _skip_chunk(chunk):
            continue
        day = _day_from_chunk(chunk) or header_day

        ob = _omborga_from_report(chunk, day)
        if ob:
            items.append(ob)
            continue

        parsed = parse_forward_text(chunk, employees=EMPLOYEES, fallback_day=day)
        for it in parsed:
            if it.get("employee"):
                fixed = resolve_emp(it["employee"])
                if fixed:
                    it["employee"] = fixed
                    it["tg_id"] = int(resolve_tg_id(fixed) or 0)
            items.append(it)
    return items


def main() -> None:
    path = Path(__file__).parent / "paste_input.txt"
    if len(sys.argv) > 1:
        arg = Path(sys.argv[1])
        raw = arg.read_text(encoding="utf-8") if arg.exists() else sys.argv[1]
    elif path.is_file() and path.stat().st_size > 0:
        raw = path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        raw = path.read_text(encoding="utf-8") if path.is_file() else ""

    items = process(raw)
    merged = aggregate_hub_events(items)

    # Kun+bot+xodim uchun yana jamlash (bir nechta omborga yakun)
    final: dict[tuple, dict] = {}
    for row in merged:
        key = (row["day"], row["tg_id"], row["bot_key"])
        if key not in final:
            final[key] = {**row, "count": row.get("count", 1)}
        else:
            f = final[key]
            f["count"] += row.get("count", 1)
            if row["bot_key"] == "ombor" and "soniya" in row["summary"]:
                sm = re.search(r"(\d+)\s*soniya", row["summary"])
                if sm:
                    prev = re.search(r"(\d+)\s*soniya", f["summary"])
                    total = int(sm.group(1)) + (int(prev.group(1)) if prev else 0)
                    cnt = f["count"]
                    f["summary"] = f"Ombor (import jami): {cnt} ta, ish vaqti {total} soniya"
            elif row["bot_key"] == "yuk":
                sm = re.search(r"ish vaqti (\d+)", row["summary"])
                if sm:
                    prev = re.search(r"ish vaqti (\d+)", f["summary"])
                    total = int(sm.group(1)) + (int(prev.group(1)) if prev else 0)
                    f["summary"] = f"Yuk (import jami): ish vaqti {total} soniya"

    rows = sorted(final.values(), key=lambda r: (r["day"], r["employee"], r["bot_key"]))
    print(f"# {len(items)} parse -> {len(rows)} hub yozuv\n")
    for r in rows:
        tid = r["tg_id"] or resolve_tg_id(r["employee"]) or 0
        print(f"HUB|{r['day']}|{tid}|{r['bot_key']}|{r['summary']}")
        print(f"  # {r['employee']}")
    print("\n# Telegram: yordamchi botga shu HUB qatorlarni yuboring (yoki tools/import_hub_lines.py)")


if __name__ == "__main__":
    main()
