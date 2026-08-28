"""Active sessions tests."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest


class ActiveSessionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        os.environ["DB_PATH"] = self.tmp.name

        import cross_bot_hub as hub
        import active_sessions as live

        self.hub = hub
        self.live = live
        hub.DB_PATH = self.tmp.name
        hub._conn.close()
        hub._conn = sqlite3.connect(self.tmp.name, check_same_thread=False, timeout=30)
        hub._conn.row_factory = sqlite3.Row
        hub.init_schema()

    def tearDown(self) -> None:
        self.hub._conn.close()
        os.unlink(self.tmp.name)

    def test_session_lifecycle(self) -> None:
        live = self.live

        async def run() -> dict:
            await live.upsert_active_session(
                tg_id=5732350707,
                bot_key="mesta",
                user_name="Toxirov Muslimbek",
                metadata={"poz": 12},
            )
            await live.upsert_active_session(
                tg_id=7987730795,
                bot_key="inventarizatsiya",
                user_name="Rajabboev Pulat",
                summary="Приход: poz 5, ish 00:30",
            )
            data = await live.list_active_sessions()
            await live.end_active_session(tg_id=5732350707, bot_key="mesta")
            after = await live.list_active_sessions()
            return {"before": data, "after": after}

        result = asyncio.run(run())
        self.assertEqual(result["before"]["total_active"], 2)
        types = {s["activity_type"] for s in result["before"]["sessions"]}
        self.assertIn("mesta", types)
        self.assertIn("prihod", types)
        self.assertEqual(result["after"]["total_active"], 1)

    def test_process_ingest(self) -> None:
        live = self.live

        async def run() -> int:
            ok = await live.process_session_ingest(
                {
                    "tg_id": 6706402440,
                    "bot_key": "yuk",
                    "event_type": "session_start",
                    "user_name": "Ibodullaev Shoxijaxon",
                    "metadata": {"trip_count": 2},
                }
            )
            data = await live.list_active_sessions()
            await live.process_session_ingest(
                {
                    "tg_id": 6706402440,
                    "bot_key": "yuk",
                    "event_type": "session_end",
                }
            )
            after = await live.list_active_sessions()
            return int(ok) + data["total_active"] * 10 + after["total_active"]

        self.assertEqual(asyncio.run(run()), 11)


if __name__ == "__main__":
    unittest.main()
