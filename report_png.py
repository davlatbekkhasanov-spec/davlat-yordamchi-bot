"""HTML → PNG (Playwright, fallback PIL)."""

from __future__ import annotations

import asyncio
import logging

from daily_report_card import DailyReportCardData, render_daily_report_png
from report_html import build_report_html

log = logging.getLogger(__name__)

_playwright_ready = False


async def _ensure_playwright() -> bool:
    global _playwright_ready
    if _playwright_ready:
        return True
    try:
        from playwright.async_api import async_playwright  # noqa: F401

        _playwright_ready = True
        return True
    except Exception as e:
        log.warning("Playwright yo'q, PIL fallback: %s", e)
        return False


async def html_to_png(html: str, *, width: int = 1240, timeout: float = 25.0) -> bytes:
    from playwright.async_api import async_playwright

    async def _shot() -> bytes:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                page = await browser.new_page(viewport={"width": width, "height": 1754})
                await page.set_content(html, wait_until="load")
                height = await page.evaluate("() => document.documentElement.scrollHeight")
                await page.set_viewport_size({"width": width, "height": max(height, 1754)})
                return await page.screenshot(full_page=True, type="png")
            finally:
                await browser.close()

    return await asyncio.wait_for(_shot(), timeout=timeout)


async def render_report_png(data: DailyReportCardData, avatar: bytes | None = None) -> bytes:
    html = build_report_html(data, avatar=avatar)
    if await _ensure_playwright():
        try:
            return await html_to_png(html)
        except Exception as e:
            log.warning("HTML→PNG xato, PIL fallback: %s", e)
    return await asyncio.to_thread(render_daily_report_png, data, avatar)


async def render_demo_preview_png() -> bytes:
    from daily_report_card import build_demo_card_data

    return await render_report_png(build_demo_card_data())
