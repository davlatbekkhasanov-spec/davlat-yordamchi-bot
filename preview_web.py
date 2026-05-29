"""Brauzer va Telegram preview."""

from __future__ import annotations

from aiohttp import web

from daily_report_card import build_demo_card_data
from report_html import build_report_html
from report_png import render_demo_preview_png


async def handle_preview_page(_request: web.Request) -> web.Response:
    try:
        html = build_report_html(build_demo_card_data())
        return web.Response(text=html, content_type="text/html", charset="utf-8")
    except Exception as e:
        return web.Response(text=f"preview error: {e}", status=500, charset="utf-8")


async def handle_preview_png(_request: web.Request) -> web.Response:
    try:
        png = await render_demo_preview_png()
        return web.Response(body=png, content_type="image/png")
    except Exception as e:
        return web.Response(text=f"preview png error: {e}", status=500, charset="utf-8")


def register_preview_routes(app: web.Application) -> None:
    app.router.add_get("/preview", handle_preview_page)
    app.router.add_get("/preview.png", handle_preview_png)
