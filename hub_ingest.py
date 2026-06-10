"""HTTP: ingest + brauzer preview."""

from __future__ import annotations

import logging
import os

from aiohttp import web

from cross_bot_hub import hub_secret_ok, record_event
from analytics_web import register_analytics_routes
from preview_web import register_preview_routes

log = logging.getLogger(__name__)


async def handle_ingest(request: web.Request) -> web.Response:
    raw_secret = (
        request.headers.get("X-Hub-Secret", "")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )
    if not hub_secret_ok(raw_secret):
        log.warning("Hub ingest unauthorized from %s", request.remote)
        return web.json_response({"ok": False, "message": "unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        log.warning("Hub ingest invalid json from %s", request.remote)
        return web.json_response({"ok": False, "message": "invalid json"}, status=400)

    def _pick(*keys: str) -> str:
        for k in keys:
            if k in data and data.get(k) not in (None, ""):
                return str(data.get(k))
        return ""

    try:
        tg_id = int(_pick("tg_id", "telegram_id", "user_id", "chat_id"))
    except (TypeError, ValueError):
        log.warning("Hub ingest tg_id missing: keys=%s", sorted(list(data.keys()))[:12])
        return web.json_response({"ok": False, "message": "tg_id required"}, status=400)

    bot_key = _pick("bot_key", "bot", "key", "source").strip()
    summary = _pick("summary", "text", "message", "result").strip()
    day = _pick("day", "date", "day_iso").strip()

    if not bot_key or not summary:
        log.warning("Hub ingest required fields missing: bot_key=%s summary=%s", bool(bot_key), bool(summary))
        return web.json_response({"ok": False, "message": "bot_key and summary required"}, status=400)

    await record_event(tg_id=tg_id, day=day, bot_key=bot_key, summary=summary)
    log.info("Hub ingest ok: tg=%s bot=%s day=%s", tg_id, bot_key, day or "auto")
    return web.json_response({"ok": True})


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "yordamchi-hub"})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/ingest", handle_ingest)
    app.router.add_get("/health", handle_health)
    register_preview_routes(app)
    register_analytics_routes(app)
    return app


async def start_ingest_server() -> web.AppRunner | None:
    port = int(os.getenv("PORT", os.getenv("HUB_PORT", "8080")) or 8080)
    app = make_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    secret = os.getenv("YORDAMCHI_HUB_SECRET", "").strip()
    log.info(
        "HTTP :%s — /health /preview /analytics%s",
        port,
        " /ingest" if secret else " (ingest o'chiq: SECRET yo'q)",
    )
    return runner
