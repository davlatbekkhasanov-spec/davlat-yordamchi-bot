"""HTML → PNG (Playwright, fallback PIL)."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date

from daily_report_card import DailyReportCardData, render_daily_report_png
from report_html import build_report_html

log = logging.getLogger(__name__)

A4_WIDTH = 1240
A4_HEIGHT = 1754
DEVICE_SCALE = max(1, min(3, int(os.getenv("REPORT_DEVICE_SCALE", "2"))))

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


async def html_to_png(
    html: str,
    *,
    timeout: float = 25.0,
    width: int | None = None,
    height: int | None = None,
    page_selector: str = ".page",
    min_height: int | None = None,
) -> bytes:
    from playwright.async_api import async_playwright

    vw = width or A4_WIDTH
    vh = height or A4_HEIGHT
    floor_h = min_height if min_height is not None else (1754 if vw == A4_WIDTH else vh)

    async def _shot() -> bytes:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=DEVICE_SCALE,
                )
                await page.set_content(html, wait_until="networkidle")
                await page.evaluate("() => document.fonts.ready")
                await page.emulate_media(media="screen")
                sel = page_selector.replace("'", "\\'")
                page_height = await page.evaluate(
                    f"""() => Math.max(
                        {floor_h},
                        Math.ceil(document.querySelector('{sel}').getBoundingClientRect().height) + 4
                    )"""
                )
                await page.set_viewport_size({"width": vw, "height": page_height})
                return await page.locator(page_selector).screenshot(
                    type="png",
                    animations="disabled",
                )
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


async def render_ranking_png(
    period: str,
    ref_date: date,
    leaders,
    active: int,
) -> bytes:
    from ranking_html import build_ranking_html

    html = build_ranking_html(period, ref_date, leaders, active)
    if await _ensure_playwright():
        try:
            return await html_to_png(html)
        except Exception as e:
            log.warning("Reyting HTML→PNG xato: %s", e)
    raise RuntimeError("Reyting PNG uchun Playwright kerak")
