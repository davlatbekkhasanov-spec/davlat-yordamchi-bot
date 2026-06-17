"""Hub repair — mesta/inventarizatsiya birlashtirish."""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def test_repair_mesta_collapses_multi_session():
    import importlib

    import cross_bot_hub
    import daily_report_card as drc
    import hub_repair

    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        os.environ["DB_PATH"] = db
        importlib.reload(cross_bot_hub)
        importlib.reload(drc)
        importlib.reload(hub_repair)

        from cross_bot_hub import _merge_mesta_daily, init_schema
        from daily_report_card import score_bot_summary
        from hub_repair import repair_hub_db

        init_schema()
        conn = cross_bot_hub._conn
        sessions = [
            "Mesta: poz 13, ish 7:49, dam 0:00, tejash 31:11, bekor 0:00, kaizen 10",
            "Mesta: poz 15, ish 9:33, dam 0:00, tejash 35:27, bekor 0:00, kaizen 11",
        ]
        expected = score_bot_summary("mesta", _merge_mesta_daily(sessions))[0]
        for s in sessions:
            conn.execute(
                """
                INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
                VALUES ('2026-06-17', 1, 'mesta', ?, '2026-06-17 12:00:00')
                """,
                (s,),
            )
        conn.commit()

        fixes = repair_hub_db(db, day="2026-06-17", apply=True)
        assert fixes, fixes
        row = conn.execute(
            "SELECT summary FROM cross_bot_events WHERE tg_id=1 AND bot_key='mesta'"
        ).fetchone()
        merged = row[0]
        assert "poz 28" in merged
        assert score_bot_summary("mesta", merged)[0] == expected
        cnt = conn.execute(
            "SELECT COUNT(*) FROM cross_bot_events WHERE tg_id=1 AND bot_key='mesta'"
        ).fetchone()[0]
        assert cnt == 1
        conn.close()


if __name__ == "__main__":
    test_repair_mesta_collapses_multi_session()
    print("PASS test_hub_repair")
