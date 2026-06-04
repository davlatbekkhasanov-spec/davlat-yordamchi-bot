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

from db_backup import restore_hub_from_json, restore_reports_from_json  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("json_path")
    p.add_argument("--hub", action="store_true", help="cross_bot_events ham tiklash")
    p.add_argument("--replace", action="store_true", help="Avval jadvalni tozalash")
    args = p.parse_args()

    db_path = os.getenv("DB_PATH", "/data/data.db").strip() or "data.db"
    if not os.path.isfile(db_path) and os.path.isfile("data.db"):
        db_path = "data.db"
    if not os.path.isfile(args.json_path):
        print(f"Backup topilmadi: {args.json_path}")
        return 1

    rep = restore_reports_from_json(db_path, args.json_path, replace=args.replace)
    print("reports:", rep)
    if args.hub:
        hub = restore_hub_from_json(db_path, args.json_path, replace=args.replace)
        print("hub:", hub)
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
