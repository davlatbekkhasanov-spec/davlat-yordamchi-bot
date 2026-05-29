"""HTTP: boshqa botlar event yuboradi (ixtiyoriy, YORDAMCHI_HUB_SECRET kerak)."""

from __future__ import annotations

import logging
import os

from aiohttp import web

from cross_bot_hub import hub_secret_ok, record_event

log = logging.getLogger(__name__)


async def handle_ingest(request: web.Request) -> web.Response:
    if not hub_secret_ok(request.headers.get("X-Hub-Secret", "")):
        return web.json_response({"ok": False, "message": "unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "message": "invalid json"}, status=400)

    try:
        tg_id = int(data.get("tg_id"))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "message": "tg_id required"}, status=400)

    bot_key = str(data.get("bot_key") or "").strip()
    summary = str(data.get("summary") or "").strip()
    day = str(data.get("day") or "").strip()

    if not bot_key or not summary:
        return web.json_response({"ok": False, "message": "bot_key and summary required"}, status=400)

    await record_event(tg_id=tg_id, day=day, bot_key=bot_key, summary=summary)
    return web.json_response({"ok": True})


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "yordamchi-hub"})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/ingest", handle_ingest)
    app.router.add_get("/health", handle_health)
    return app


async def start_ingest_server() -> web.AppRunner | None:
    secret = os.getenv("YORDAMCHI_HUB_SECRET", "").strip()
    if not secret:
        log.info("Hub ingest o'chirilgan (YORDAMCHI_HUB_SECRET yo'q)")
        return None

    port = int(os.getenv("PORT", os.getenv("HUB_PORT", "8080")) or 8080)
    app = make_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("Hub ingest listening on :%s /ingest", port)
    return runner
