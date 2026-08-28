"""Jonli holat dashboard — Telegram Web App."""

from __future__ import annotations

import json
import logging
import os

from aiohttp import web

from active_sessions import list_active_sessions
from live_html import build_live_html

log = logging.getLogger(__name__)


def live_token_ok(token: str) -> bool:
    secret = os.getenv("LIVE_DASHBOARD_TOKEN", "").strip()
    if not secret:
        return True
    return str(token or "").strip() == secret


def _token_from_request(request: web.Request) -> str:
    return (request.query.get("token") or request.headers.get("X-Live-Token") or "").strip()


async def handle_live_page(request: web.Request) -> web.Response:
    token = _token_from_request(request)
    if not live_token_ok(token):
        return web.Response(text="401 — token kerak", status=401, charset="utf-8")
    try:
        html = build_live_html(token=token)
        return web.Response(text=html, content_type="text/html", charset="utf-8")
    except Exception as e:
        log.exception("live page")
        return web.Response(text=f"live error: {e}", status=500, charset="utf-8")


async def handle_live_api(request: web.Request) -> web.Response:
    token = _token_from_request(request)
    if not live_token_ok(token):
        return web.json_response({"ok": False, "message": "unauthorized"}, status=401)
    try:
        data = await list_active_sessions()
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            content_type="application/json",
            charset="utf-8",
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:
        log.exception("live api")
        return web.json_response({"ok": False, "message": str(e)}, status=500)


def register_live_routes(app: web.Application) -> None:
    app.router.add_get("/live", handle_live_page)
    app.router.add_get("/live.json", handle_live_api)
    app.router.add_get("/api/live", handle_live_api)
