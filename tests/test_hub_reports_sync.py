"""Hub mesta/inventarizatsiya → Места хр / Пересчет."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MUSTAFOEV_TG = 6931958983
DAY = "2026-06-17"
MESTA_SUMMARY = (
    "Mesta: poz 55, ish 17:04, dam 01:41, tejash 2:26:15, bekor 00:00, kaizen 48"
)


def _run():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        os.environ["DB_PATH"] = db

        import importlib

        import cross_bot_hub
        import daily_report_card as drc
        import hub_reports_sync

        importlib.reload(cross_bot_hub)
        importlib.reload(drc)
        importlib.reload(hub_reports_sync)

        from cross_bot_hub import init_schema, record_event
        from daily_report_card import build_card_data, score_bot_summary
        from hub_reports_sync import hub_category_points, sync_hub_categories_for_tg

        async def main():
            init_schema()
            await record_event(
                tg_id=MUSTAFOEV_TG,
                day=DAY,
                bot_key="mesta",
                summary=MESTA_SUMMARY,
            )
            pts = await sync_hub_categories_for_tg(MUSTAFOEV_TG, DAY)
            assert pts.get("Места хр") == 48, pts

            async def sum_day(d, emp, cat):
                import sqlite3

                conn = sqlite3.connect(db)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT COALESCE(SUM(value),0) AS s FROM reports WHERE day=? AND employee=? AND category=?",
                    (d, emp, cat),
                ).fetchone()
                conn.close()
                return int(row["s"])

            async def sum_period(*_):
                return 0

            async def get_plan(*_):
                return None

            async def sum_day_total(*_):
                return 0

            async def day_has_any(*_):
                return False

            card = await build_card_data(
                employee="Mustafoev Abdullo",
                day_iso=DAY,
                period="2026-06",
                yday_iso="2026-06-16",
                session_agg={},
                categories=[
                    "Приход",
                    "Перемещение",
                    "Фото ТСД",
                    "Счет ТСД",
                    "Фасовка",
                    "АРМ диспетчер",
                    "Исправление пересортицы",
                    "Переоценка",
                    "Пересчет товаров",
                    "Места хр",
                ],
                best_cat="",
                best_add=0,
                overall_text="test",
                employees=["Mustafoev Abdullo"],
                sum_day=sum_day,
                sum_period=sum_period,
                get_plan=get_plan,
                sum_day_total=sum_day_total,
                employee_tg_map={"Mustafoev Abdullo": MUSTAFOEV_TG},
                day_has_any=day_has_any,
            )
            names = [c.name for c in card.categories]
            assert "Места хр" in names, names
            mesta_row = next(c for c in card.categories if c.name == "Места хр")
            assert mesta_row.added == 48, mesta_row
            assert mesta_row.today == 55, mesta_row
            assert card.cat_total == 48, card.cat_total
            assert card.bot_total == 0, card.bot_total
            assert card.grand_total == 48, card.grand_total
            return card

        return asyncio.run(main())


if __name__ == "__main__":
    _run()
    print("PASS test_hub_reports_sync")
