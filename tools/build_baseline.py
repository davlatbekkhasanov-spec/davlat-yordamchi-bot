#!/usr/bin/env python3
"""backup JSON → baseline_history.json + seed fayllar (tuzatilgan hub bilan)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cross_bot_hub import _merge_hub_summary  # noqa: E402

BACKUP = Path(
    r"C:\Users\E-MaxPCShop\Downloads\Telegram Desktop\backup_20260609_115325.json"
)
OUT_JSON = ROOT / "data" / "baseline_history.json"
LOST = json.loads((ROOT / "tools" / "hub_lost_events.json").read_text(encoding="utf-8"))

SINDOR_OMBOR_FIX = "Ombor (bugun jami): 3 ta, ish vaqti 6892 soniya"

# Skrinshot / yakuniy hisobot bo'yicha tuzatishlar (SUM noto'g'ri bo'lsa)
METRIC_OVERRIDES: dict[tuple[str, str, str], int | None] = {
    ("2026-06-08", "Ravshanov Oxunjon", "Счет ТСД"): 73,
    ("2026-06-08", "Tuvalov Farrux", "Перемещение"): 2,
    ("2026-06-08", "Yadullaev Umid", "Фото ТМЦ"): None,
}

# 08.06 skrinshotdagi «бошқа ботлар» (kunlik hisobot)
HUB_DAY_OVERRIDES: dict[str, dict[int, dict[str, str]]] = {
    "2026-06-08": {
        5412958249: {
            "omborga": "Reys 7, yuk 105m, ish 2:45, dam 0:14",
            "sklad": "Papka Увлажнители воздуха: sanaldi 1, joy 1, xato 0, kun 17/28",
        },
        5465963344: {
            "omborga": "Reys 7, yuk 105m, ish 2:45, dam 0:14",
            "sklad": "Papka Увлажнители воздуха: sanaldi 1, joy 1, xato 0, kun 17/28",
        },
        5732350707: {
            "omborga": "Reys 39, yuk 1111m, ish 33:43, dam 17:22",
            "yuk": "Yuk (bugun jami): ish vaqti 0:00",
        },
        6931958983: {
            "omborga": "Reys 7, yuk 105m, ish 2:45, dam 0:14",
            "sklad": "Papka Увлажнители воздуха: sanaldi 1, joy 1, xato 0, kun 17/28",
        },
        7703650930: {"omborga": "Reys 5, yuk 87m, ish 1:52, dam 0:18"},
        8440127425: {"omborga": "Reys 5, yuk 151m, ish 7:56, dam 4:03"},
        8547365654: {
            "ombor": SINDOR_OMBOR_FIX,
            "omborga": "Reys 5, yuk 190m, ish 3:29, dam 1:10",
        },
        924612402: {"omborga": "Reys 8, yuk 216m, ish 9:22, dam 4:51"},
    },
}


def _replay(bot_key: str, summaries: list[str]) -> str:
    merged = ""
    for s in summaries:
        if not merged:
            merged = s
        else:
            merged = _merge_hub_summary(bot_key, merged, s)
    return merged


def _metrics_rows(reports: list[dict]) -> list[tuple[str, str, str, int]]:
    """Kun+xodim+kategoriya — jami (override bo'lsa u)."""
    sums: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in reports:
        key = (r["day"], r["employee"], r["category"])
        sums[key] += int(r["value"])
    out: list[tuple[str, str, str, int]] = []
    for key in sorted(sums.keys()):
        if key in METRIC_OVERRIDES:
            ov = METRIC_OVERRIDES[key]
            if ov is None:
                continue
            out.append((*key, int(ov)))
        else:
            out.append((*key, sums[key]))
    return out


def _hub_final_rows(events: list[dict]) -> list[tuple[str, int, str, str]]:
    groups: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    for e in events:
        groups[(e["day"], int(e["tg_id"]), e["bot_key"])].append(e)

    lost_extra: dict[tuple[str, int, str], list[str]] = defaultdict(list)
    for row in LOST:
        k = (row["day"], int(row["tg_id"]), row["bot_key"])
        lost_extra[k].append(row["summary"])

    out: list[tuple[str, int, str, str]] = []
    for (day, tg, bot), evs in sorted(groups.items()):
        evs = sorted(evs, key=lambda x: int(x.get("id") or 0))
        summaries = [e["summary"] for e in evs]
        for extra in lost_extra.get((day, tg, bot), []):
            if not any(extra in s for s in summaries):
                summaries.append(extra)
        merged = _replay(bot, summaries)
        day_ov = HUB_DAY_OVERRIDES.get(day, {}).get(tg, {})
        if bot in day_ov:
            merged = day_ov[bot]
        if merged:
            out.append((day, tg, bot, merged))
    # Skrinshotda bor, replayda yo'q botlar
    for day, tg_map in HUB_DAY_OVERRIDES.items():
        for tg, bots in tg_map.items():
            for bot, summary in bots.items():
                if not any(d == day and t == tg and b == bot for d, t, b, _ in out):
                    out.append((day, tg, bot, summary))
    return out


def _fmt_metrics_py(rows: list[tuple[str, str, str, int]]) -> str:
    lines = [
        '"""Yordamchi bot kategoriya yozuvlari — deployda avtomatik tiklash."""',
        "",
        "from __future__ import annotations",
        "",
        "METRICS_SEED_VERSION = 4",
        "",
        "# (day, employee, category, value)",
        "METRICS_SEED_ROWS: tuple[tuple[str, str, str, int], ...] = (",
    ]
    cur_day = ""
    for day, emp, cat, val in rows:
        if day != cur_day:
            lines.append(f"    # {day}")
            cur_day = day
        lines.append(f'    ("{day}", "{emp}", "{cat}", {val}),')
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def _fmt_hub_py(rows: list[tuple[str, int, str, str]]) -> str:
    lines = [
        '"""Boshlang\'ich hub ma\'lumotlari — deployda avtomatik tiklash."""',
        "",
        "from __future__ import annotations",
        "",
        "HUB_SEED_VERSION = 5",
        "",
        "# (day, tg_id, bot_key, summary)",
        "HUB_SEED_ROWS: tuple[tuple[str, int, str, str], ...] = (",
    ]
    cur_day = ""
    for day, tg, bot, summary in rows:
        if day != cur_day:
            lines.append(f"    # {day}")
            cur_day = day
        esc = summary.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    ("{day}", {tg}, "{bot}", "{esc}"),')
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if not BACKUP.is_file():
        print(f"Backup topilmadi: {BACKUP}")
        sys.exit(1)
    payload = json.loads(BACKUP.read_text(encoding="utf-8"))
    reports = payload["tables"]["reports"]
    events = payload["tables"]["cross_bot_events"]

    metrics = _metrics_rows(reports)
    hub = _hub_final_rows(events)

    tg_lookup: dict[tuple[str, str, str], int] = {}
    for r in reports:
        k = (r["day"], r["employee"], r["category"])
        if k not in tg_lookup:
            tg_lookup[k] = int(r.get("tg_id") or 0)
    clean_reports = []
    for i, (day, emp, cat, val) in enumerate(metrics, 1):
        clean_reports.append(
            {
                "id": i,
                "day": day,
                "period": day[:7],
                "tg_id": tg_lookup.get((day, emp, cat), 0),
                "employee": emp,
                "category": cat,
                "value": val,
                "created_at": f"{day}T23:59:00",
            }
        )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    baseline = {
        "exported_at": payload.get("exported_at"),
        "source": "backup_20260609_115325 + hub repair",
        "tables": {
            "reports": clean_reports,
            "cross_bot_events": [],
        },
    }
    # Hub: faqat tuzatilgan yakuniy qatorlar (seed bilan bir xil)
    for day, tg, bot, summary in hub:
        baseline["tables"]["cross_bot_events"].append(
            {
                "day": day,
                "tg_id": tg,
                "bot_key": bot,
                "summary": summary,
                "created_at": f"{day} 23:59:00",
            }
        )
    OUT_JSON.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")

    (ROOT / "metrics_seed.py").write_text(_fmt_metrics_py(metrics), encoding="utf-8")
    (ROOT / "hub_seed.py").write_text(_fmt_hub_py(hub), encoding="utf-8")

    print(f"reports: {len(metrics)} seed rows")
    print(f"hub: {len(hub)} final rows")
    print(f"baseline: {OUT_JSON}")


if __name__ == "__main__":
    main()
