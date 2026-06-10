#!/usr/bin/env python3
"""Hub analytics ishonchliligi — CI va qo'lda tekshiruv. Exit 0 = hammasi OK."""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cross_bot_hub import (  # noqa: E402
    _best_yuk_daily,
    _replay_merged_by_bot,
    init_schema,
    record_event,
)
from daily_report_card import BOT_ORDER, score_bot_summary  # noqa: E402
from hub_repair import repair_hub_db  # noqa: E402

ABDULLO_TG = 6931958983
MAX_YUK_SEC = 10800
MAX_DAILY_WORK_SEC = 12 * 3600


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def check_yuk_inflation_logic() -> None:
    rows = [f"Yuk (bugun jami): ish vaqti {i * 450} soniya" for i in range(1, 31)]
    out = _best_yuk_daily(rows)
    if "13500" in out:
        _fail("yuk inflation: 13500 still in merged output")
    if "0 soniya" not in out:
        _fail(f"yuk inflation: expected zero, got {out!r}")
    official = rows + ["Yuk (yakun): ish vaqti 1847 soniya"]
    out2 = _best_yuk_daily(official)
    if "1847" not in out2:
        _fail(f"yuk yakun: expected 1847, got {out2!r}")
    _ok("yuk inflation blocked; yakun 1847s accepted")


def check_abdullo_upsert() -> None:
    import asyncio
    import sqlite3

    import cross_bot_hub as ch

    td = tempfile.mkdtemp()
    db = os.path.join(td, "audit.db")
    ch.DB_PATH = db
    ch._conn.close()
    ch._conn = sqlite3.connect(db, check_same_thread=False, timeout=30)
    ch._conn.row_factory = sqlite3.Row
    init_schema()

    async def run() -> None:
        for i in range(1, 31):
            await record_event(
                tg_id=ABDULLO_TG,
                day="2026-06-09",
                bot_key="yuk",
                summary=f"Yuk (bugun jami): ish vaqti {i * 450} soniya",
            )
        await record_event(
            tg_id=ABDULLO_TG,
            day="2026-06-09",
            bot_key="yuk",
            summary="Yuk (yakun): ish vaqti 1847 soniya",
        )

    asyncio.run(run())
    n = ch._conn.execute(
        "SELECT COUNT(*) FROM cross_bot_events WHERE tg_id=? AND day=? AND bot_key='yuk'",
        (ABDULLO_TG, "2026-06-09"),
    ).fetchone()[0]
    row = ch._conn.execute(
        "SELECT summary FROM cross_bot_events WHERE tg_id=? AND day=? AND bot_key='yuk'",
        (ABDULLO_TG, "2026-06-09"),
    ).fetchone()
    ch._conn.close()
    if n != 1:
        _fail(f"abdullo upsert: expected 1 yuk row, got {n}")
    if not row or "1847" not in row[0]:
        _fail(f"abdullo upsert: bad summary {row}")
    _, sec = score_bot_summary("yuk", row[0])
    if sec != 1847:
        _fail(f"abdullo upsert: work sec {sec}, expected 1847")
    _ok("abdullo yuk upsert: single row 1847s")


def check_csv_replay(csv_path: str) -> None:
    if not os.path.isfile(csv_path):
        print(f"SKIP: CSV not found {csv_path}")
        return
    by_ud: dict[tuple[str, str], list] = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by_ud[(r["tg_id"], r["day"])].append(
                {"bot_key": r["bot_key"], "summary": r["summary"]}
            )
    bad = 0
    for (tg, day), rows in by_ud.items():
        hub = _replay_merged_by_bot(rows)
        work = sum(score_bot_summary(k, hub.get(k, ""))[1] for k in BOT_ORDER)
        _, yw = score_bot_summary("yuk", hub.get("yuk", ""))
        if yw >= MAX_YUK_SEC or work > MAX_DAILY_WORK_SEC:
            bad += 1
            print(f"  BAD tg={tg} day={day} yuk={yw} total={work}")
    if bad:
        _fail(f"CSV replay: {bad} inflated user-days")
    _ok(f"CSV replay: {len(by_ud)} user-days, 0 inflated")


def main() -> None:
    csv_path = os.environ.get(
        "HUB_CSV",
        os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            "Telegram Desktop",
            "hub_events_20260609_115325.csv",
        ),
    )
    check_yuk_inflation_logic()
    check_abdullo_upsert()
    check_csv_replay(csv_path)
    print("\n=== VERIFY HUB INTEGRITY: ALL PASS ===")


if __name__ == "__main__":
    main()
