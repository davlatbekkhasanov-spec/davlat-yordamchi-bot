"""HTTP: Kaizen analytics dashboard."""

from __future__ import annotations

import csv
import io
import json
import logging

from aiohttp import web

from analytics_extensions import build_export_rows
from analytics_html import build_analytics_html
from analytics_queries import analytics_secret_ok, build_dashboard

log = logging.getLogger(__name__)


def _token_from_request(request: web.Request) -> str:
    return (request.query.get("token") or request.headers.get("X-Analytics-Token") or "").strip()


async def handle_analytics_page(request: web.Request) -> web.Response:
    token = _token_from_request(request)
    if not analytics_secret_ok(token):
        return web.Response(text="401 — token kerak", status=401, charset="utf-8")
    day = (request.query.get("day") or "").strip() or None
    try:
        html = build_analytics_html(day=day, token=token)
        return web.Response(text=html, content_type="text/html", charset="utf-8")
    except Exception as e:
        log.exception("analytics page")
        return web.Response(text=f"analytics error: {e}", status=500, charset="utf-8")


async def handle_analytics_api(request: web.Request) -> web.Response:
    token = _token_from_request(request)
    if not analytics_secret_ok(token):
        return web.json_response({"ok": False, "message": "unauthorized"}, status=401)
    day = (request.query.get("day") or "").strip() or None
    try:
        data = build_dashboard(day)
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            content_type="application/json",
            charset="utf-8",
        )
    except Exception as e:
        log.exception("analytics api")
        return web.json_response({"ok": False, "message": str(e)}, status=500)


async def handle_analytics_export(request: web.Request) -> web.Response:
    token = _token_from_request(request)
    if not analytics_secret_ok(token):
        return web.Response(text="401", status=401)
    day = (request.query.get("day") or "").strip() or None
    try:
        data = build_dashboard(day)
        rows = build_export_rows(data["matrix"], data["day"])
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        else:
            buf.write("day,employee,rank,total\n")
        filename = f"kaizen_{data['day']}.csv"
        return web.Response(
            text=buf.getvalue(),
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        log.exception("analytics export")
        return web.Response(text=str(e), status=500)


def register_analytics_routes(app: web.Application) -> None:
    app.router.add_get("/analytics", handle_analytics_page)
    app.router.add_get("/analytics/api", handle_analytics_api)
    app.router.add_get("/analytics/export", handle_analytics_export)
