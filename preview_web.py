"""Brauzer va Telegram preview."""

from __future__ import annotations

import os

from aiohttp import web

from daily_report_card import build_demo_card_data, render_daily_report_png, render_demo_preview_png

_DEMO_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Kunlik hisobot — preview</title>
  <style>
    body {{ margin:0; background:#060d1f; color:#e8f0ff; font-family:system-ui,sans-serif; }}
    .wrap {{ max-width:980px; margin:0 auto; padding:24px 16px 48px; }}
    h1 {{ font-size:1.25rem; font-weight:600; margin:0 0 8px; }}
    p {{ color:#8fa3c4; margin:0 0 20px; line-height:1.5; }}
    img {{ width:100%; height:auto; border-radius:12px; border:2px solid #00a8bc; box-shadow:0 8px 40px #0008; }}
    .links {{ margin-top:16px; font-size:14px; }}
    a {{ color:#5eead4; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>📊 Kunlik hisobot (yakun) — namuna</h1>
    <p>Guruhga ✅ Якунлаш bosilganda shu ko'rinishda PNG ketadi. Namuna ma'lumotlar.</p>
    <img src="/preview.png" alt="Kunlik hisobot preview"/>
    <div class="links">
      <a href="/preview.png" target="_blank">PNG to'g'ridan-to'g'ri ochish</a>
      · <a href="/health">/health</a>
    </div>
  </div>
</body>
</html>
"""


async def handle_preview_page(_request: web.Request) -> web.Response:
    return web.Response(text=_DEMO_HTML, content_type="text/html; charset=utf-8")


async def handle_preview_png(_request: web.Request) -> web.Response:
    png = render_demo_preview_png()
    return web.Response(body=png, content_type="image/png")


def register_preview_routes(app: web.Application) -> None:
    app.router.add_get("/preview", handle_preview_page)
    app.router.add_get("/preview.png", handle_preview_png)
