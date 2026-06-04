"""CLI: DB dan backup fayllarini yaratish.

Ishlatish:
  python tools/export_backup.py
  DB_PATH=/data/data.db python tools/export_backup.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db_backup import export_payload, write_backup_files  # noqa: E402


def main() -> int:
    db_path = os.getenv("DB_PATH", "/data/data.db").strip() or "data.db"
    if not os.path.isfile(db_path) and os.path.isfile("data.db"):
        db_path = "data.db"
    if not os.path.isfile(db_path):
        print(f"DB topilmadi: {db_path}")
        return 1

    out_dir = os.getenv("BACKUP_DIR", os.path.join(ROOT, "backups")).strip()
    files = write_backup_files(db_path, out_dir)
    payload = export_payload(db_path)
    counts = payload.get("counts", {})
    print(f"Backup OK: {db_path}")
    print(f"Out dir: {out_dir}")
    for k, p in files.items():
        print(f"  {k}: {p}")
    print("Counts:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
