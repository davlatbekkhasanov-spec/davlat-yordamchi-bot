"""hub_lines_ready.txt → cross_bot_events (record_event)."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cross_bot_hub import init_schema, record_event  # noqa: E402
from employee_tg_map import resolve_tg_id  # noqa: E402


def parse_hub_file(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line.startswith("HUB|"):
            continue
        parts = line.split("|", 4)
        if len(parts) < 5:
            continue
        day_s, tg_s, bot_key, summary = parts[1], parts[2], parts[3], parts[4]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_s):
            continue
        tg_id = int(tg_s) if str(tg_s).isdigit() else 0
        if not tg_id:
            continue
        rows.append(
            {
                "day": day_s,
                "tg_id": tg_id,
                "bot_key": bot_key.strip().lower(),
                "summary": summary.strip(),
            }
        )
    return rows


async def import_rows(rows: list[dict], *, dry_run: bool) -> int:
    if not dry_run:
        init_schema()
    n = 0
    for row in rows:
        if dry_run:
            n += 1
            continue
        await record_event(
            tg_id=int(row["tg_id"]),
            day=row["day"],
            bot_key=row["bot_key"],
            summary=row["summary"],
        )
        n += 1
    return n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "hub_file",
        nargs="?",
        default=str(Path(__file__).parent / "hub_lines_ready.txt"),
    )
    p.add_argument("--dry-run", action="store_true", help="DB ga yozmasdan sanash")
    p.add_argument(
        "--db",
        default=os.getenv("DB_PATH", "").strip() or str(ROOT / "data.db"),
        help="SQLite yo'li (default: DB_PATH yoki data.db)",
    )
    args = p.parse_args()

    hub_path = Path(args.hub_file)
    if not hub_path.is_file():
        print(f"Fayl topilmadi: {hub_path}")
        return 1

    os.environ["DB_PATH"] = args.db
    rows = parse_hub_file(hub_path)
    if not rows:
        print("HUB qator topilmadi.")
        return 1

    n = asyncio.run(import_rows(rows, dry_run=args.dry_run))
    mode = "dry-run" if args.dry_run else "yozildi"
    print(f"{mode}: {n} ta HUB qator ({hub_path})")
    print(f"DB: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
