"""Boshqa botlardan davlat-yordamchi hub ga event yuborish (nusxa har botga)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import date

log = logging.getLogger(__name__)

HUB_URL = os.getenv("YORDAMCHI_HUB_URL", "").strip().rstrip("/")
HUB_SECRET = os.getenv("YORDAMCHI_HUB_SECRET", "").strip()


def _post_sync(payload: dict) -> None:
    if not HUB_URL or not HUB_SECRET:
        return
    url = f"{HUB_URL}/ingest"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Secret": HUB_SECRET,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status >= 400:
                log.warning("Hub ingest HTTP %s", resp.status)
    except urllib.error.URLError as e:
        log.warning("Hub ingest failed: %s", e)
    except Exception as e:
        log.warning("Hub ingest error: %s", e)


async def push_to_yordamchi_hub(
    *,
    tg_id: int,
    bot_key: str,
    summary: str,
    day_iso: str | None = None,
) -> None:
    """Xato bo'lsa bot ishini to'xtatmaydi."""
    text = " ".join(str(summary or "").split())
    if not text or not tg_id:
        return
    if not HUB_URL or not HUB_SECRET:
        return
    day = day_iso or date.today().isoformat()
    payload = {
        "tg_id": int(tg_id),
        "bot_key": str(bot_key or "").strip().lower(),
        "summary": text[:420],
        "day": day,
    }
    try:
        await asyncio.to_thread(_post_sync, payload)
    except Exception as e:
        log.debug("push_to_yordamchi_hub: %s", e)


def push_to_yordamchi_hub_background(**kwargs) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(push_to_yordamchi_hub(**kwargs))
    except RuntimeError:
        asyncio.run(push_to_yordamchi_hub(**kwargs))
