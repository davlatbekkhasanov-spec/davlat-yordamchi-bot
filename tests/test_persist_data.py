"""persist_data — migratsiya va zaxira."""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from persist_data import bootstrap_persistence, migrate_legacy_db, resolve_db_path


def test_migrate_legacy_when_target_empty():
    with tempfile.TemporaryDirectory() as tmp:
        legacy = os.path.join(tmp, "data.db")
        target = os.path.join(tmp, "data", "data.db")
        with open(legacy, "wb") as f:
            f.write(b"x" * 2000)
        src = migrate_legacy_db(target, legacy)
        assert src == os.path.abspath(legacy)
        assert os.path.isfile(target)
        assert os.path.getsize(target) >= 2000


def test_bootstrap_creates_backup():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "data.db")
        with open(db, "wb") as f:
            f.write(b"y" * 3000)
        info = bootstrap_persistence(db)
        assert info["startup_backup"]
        assert os.path.isfile(info["startup_backup"])


def test_resolve_db_path_uses_env():
    os.environ["DB_PATH"] = "/tmp/custom.db"
    try:
        assert resolve_db_path() == "/tmp/custom.db"
    finally:
        os.environ.pop("DB_PATH", None)


if __name__ == "__main__":
    test_migrate_legacy_when_target_empty()
    test_bootstrap_creates_backup()
    test_resolve_db_path_uses_env()
    print("PASS test_persist_data")
