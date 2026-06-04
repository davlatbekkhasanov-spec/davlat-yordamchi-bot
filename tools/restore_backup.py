"""CLI: backup JSON dan reports/hub tiklash.

Ishlatish:
  python tools/restore_backup.py backups/backup_20260602_120000.json
  python tools/restore_backup.py backups/backup_20260602_120000.json --hub
  python tools/restore_backup.py backups/backup_20260602_120000.json --replace
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db_backup import restore_all_from_json, restore_hub_from_json, restore_links_from_json, restore_reports_from_json  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("json_path")
    p.add_argument("--hub", action="store_true", help="cross_bot_events ham tiklash")
    p.add_argument("--links", action="store_true", help="employee_links va pins tiklash")
    p.add_argument("--all", action="store_true", help="Barcha mavjud jadvallarni tiklash")
    p.add_argument("--replace", action="store_true", help="Avval jadvalni tozalash")
    args = p.parse_args()

    db_path = os.getenv("DB_PATH", "/data/data.db").strip() or "data.db"
    if not os.path.isfile(db_path) and os.path.isfile("data.db"):
        db_path = "data.db"
    if not os.path.isfile(args.json_path):
        print(f"Backup topilmadi: {args.json_path}")
        return 1

    if args.all:
        res = restore_all_from_json(db_path, args.json_path, replace=args.replace)
        print("source counts:", res.get("counts_source"))
        print("reports:", res.get("reports"))
        print("hub:", res.get("hub"))
        print("links:", res.get("links"))
        return 0

    rep = restore_reports_from_json(db_path, args.json_path, replace=args.replace)
    print("reports:", rep)
    if args.hub:
        hub = restore_hub_from_json(db_path, args.json_path, replace=args.replace)
        print("hub:", hub)
    if args.links:
        links = restore_links_from_json(db_path, args.json_path, replace=args.replace)
        print("links:", links)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
