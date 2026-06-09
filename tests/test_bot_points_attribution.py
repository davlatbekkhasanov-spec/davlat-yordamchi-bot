"""Mustafoev +300 boshqa xodimlarga yopishmasligi — unit test."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MUSTAFOEV_TG = 6931958983
DAY = "2026-06-03"
OMBORGA_SUMMARY = "Reys 5, yuk 125m, ish 8:33, dam 5:37"
OMBOR_SUMMARY = "Ombor (bugun jami): ish vaqti 1377 soniya"


def _run():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        os.environ["DB_PATH"] = db

        # DB_PATH importdan oldin
        import importlib

        import cross_bot_hub
        import daily_report_card as drc
        import employee_tg_map as etm

        importlib.reload(cross_bot_hub)
        importlib.reload(drc)

        from cross_bot_hub import init_schema, record_event, fetch_merged_latest_by_bot
        from daily_report_card import score_bot_summary
        from employee_tg_map import TG_EMPLOYEE, tg_ids_for_employee

        async def seed():
            init_schema()
            await record_event(
                tg_id=MUSTAFOEV_TG,
                day=DAY,
                bot_key="omborga",
                summary=OMBORGA_SUMMARY,
            )
            await record_event(
                tg_id=MUSTAFOEV_TG,
                day=DAY,
                bot_key="ombor",
                summary=OMBOR_SUMMARY,
            )

        asyncio.run(seed())

        etg_map = {name: tid for tid, name in TG_EMPLOYEE.items()}
        mustafoev_tgs = tg_ids_for_employee("Mustafoev Abdullo", employee_tg_map=etg_map)
        oxunjon_tgs = tg_ids_for_employee("Ravshanov Oxunjon", employee_tg_map=etg_map)

        assert MUSTAFOEV_TG in mustafoev_tgs, mustafoev_tgs
        assert MUSTAFOEV_TG not in oxunjon_tgs, oxunjon_tgs

        async def pts(tg_set):
            ev = await fetch_merged_latest_by_bot(tg_set, DAY)
            return sum(score_bot_summary(k, v)[0] for k, v in ev.items())

        pts_m = asyncio.run(pts(mustafoev_tgs))
        pts_o = asyncio.run(pts(oxunjon_tgs))
        pts_bad = asyncio.run(pts(oxunjon_tgs | {MUSTAFOEV_TG}))

        assert pts_m > 0, pts_m
        assert pts_o == 0, pts_o
        assert pts_bad >= pts_m, pts_bad

        # Kodda viewer_tg_id qolganmi
        import pathlib

        root = pathlib.Path(ROOT)
        for rel in ("bot.py", "daily_report_card.py"):
            text = (root / rel).read_text(encoding="utf-8")
            assert "viewer_tg_id" not in text, rel
            assert "tg_set.add(int(tg_id))" not in text, rel

        tolib_tgs = tg_ids_for_employee(
            "Shernazarov Tolib",
            employee_tg_map={**etg_map, "Shernazarov Tolib": MUSTAFOEV_TG},
        )
        assert 5465963344 in tolib_tgs, tolib_tgs

        return pts_m, pts_o, pts_bad


if __name__ == "__main__":
    m, o, b = _run()
    print(f"PASS: Mustafoev={m} ochko, Oxunjon={o}, eski xato (operator qo'shilsa)={b}")
