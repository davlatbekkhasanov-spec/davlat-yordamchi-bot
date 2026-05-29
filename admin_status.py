"""Admin: bitta tugmada kanallar va integratsiya holati."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from cross_bot_hub import BOT_LABELS, hub_stats_today, count_employee_links
from yordamchi_push import today_iso, hub_configured

BTN_ADMIN_STATUS = "📊 Tizim holati"


def admin_status_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_ADMIN_STATUS)]],
        resize_keyboard=True,
    )


def _flag(ok: bool) -> str:
    return "✅" if ok else "❌"


async def _chat_ok(bot: Bot, chat_id: int) -> tuple[bool, str]:
    if not chat_id:
        return False, "sozlanmagan"
    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or chat.username or chat.first_name or str(chat_id)
        return True, title[:60]
    except TelegramAPIError as e:
        return False, str(e)[:80]


def _http_health(url: str) -> tuple[bool, str]:
    base = (url or "").strip().rstrip("/")
    if not base:
        return False, "YORDAMCHI_HUB_URL yo'q"
    health_url = f"{base}/health"
    req = urllib.request.Request(health_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if 200 <= resp.status < 300:
                try:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        return True, "HTTP /health OK"
                except Exception:
                    return True, f"HTTP {resp.status}"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:80]


def _hub_config_block() -> list[str]:
    hub_url = os.getenv("YORDAMCHI_HUB_URL", "").strip()
    secret = bool(os.getenv("YORDAMCHI_HUB_SECRET", "").strip())
    tg_fb = bool(os.getenv("YORDAMCHI_BOT_TOKEN", "").strip()) and bool(
        int(os.getenv("YORDAMCHI_INGEST_CHAT_ID", "0") or "0")
    )
    port = os.getenv("PORT", "").strip()
    lines = [
        "⚙️ Hub sozlama:",
        f"  {_flag(bool(hub_url))} YORDAMCHI_HUB_URL: {hub_url or '—'}",
        f"  {_flag(secret)} YORDAMCHI_HUB_SECRET",
        f"  {_flag(tg_fb)} Telegram ingest (fallback)",
    ]
    if port:
        lines.append(f"  ℹ️ PORT={port} (ichki HTTP server)")
    if not hub_configured():
        lines.append("  ⚠️ Boshqa botlar event yubora olmaydi — URL+SECRET yoki TG fallback kerak")
    return lines


async def build_admin_status_report(bot: Bot, admin_uid: int) -> str:
    day = today_iso()
    lines: list[str] = [
        f"📊 <b>Tizim holati</b>",
        f"📅 Kun: {day}",
        f"👤 Sizning ID: <code>{admin_uid}</code>",
        "",
    ]

    # Kanallar
    group_id = int(os.getenv("GROUP_ID", "0") or "0")
    ingest_id = int(os.getenv("YORDAMCHI_INGEST_CHAT_ID", "0") or "0")
    g_ok, g_info = await _chat_ok(bot, group_id)
    i_ok, i_info = await _chat_ok(bot, ingest_id) if ingest_id else (False, "kerak emas (HTTP ishlatiladi)")

    lines.append("📢 <b>Kanallar</b>")
    lines.append(f"  {_flag(g_ok)} Guruh (hisobot): <code>{group_id}</code>")
    if g_ok:
        lines.append(f"     → {g_info}")
    else:
        lines.append(f"     ⚠️ {g_info}")
        lines.append("     Bot guruhga qo'shilgan va yozish huquqi bormi?")

    lines.append(f"  {_flag(i_ok or not ingest_id)} Ingest chat: <code>{ingest_id or '—'}</code>")
    if ingest_id:
        lines.append(f"     → {i_info}")
    lines.append("")

    # HTTP hub
    hub_url = os.getenv("YORDAMCHI_HUB_URL", "").strip()
    h_ok, h_info = await asyncio.to_thread(_http_health, hub_url)
    secret_ok = bool(os.getenv("YORDAMCHI_HUB_SECRET", "").strip())
    lines.append("🔗 <b>Integratsiya (hub)</b>")
    lines.append(f"  {_flag(h_ok)} Tashqi /health: {h_info}")
    lines.append(f"  {_flag(secret_ok)} Ingest secret (boshqa botlar uchun)")
    lines.append(f"  {_flag(hub_configured())} Boshqa botlar yubora oladi")
    if hub_url:
        lines.append(f"     URL: <code>{hub_url}</code>")
    elif not hub_configured():
        lines.append("     ⚠️ YORDAMCHI_HUB_URL + SECRET yoki TG fallback sozlang")
    lines.append("")

    # DB / xodimlar
    links = await count_employee_links()
    stats = await hub_stats_today(day)
    lines.append("💾 <b>Ma'lumotlar</b>")
    lines.append(f"  ✅ Ulangan xodimlar: {links}")
    lines.append(f"  📥 Bugun hub eventlari (jami): {sum(c for c, _ in stats.values())}")
    lines.append("")

    lines.append("🤖 <b>Botlar bo'yicha (bugun)</b>")
    order = ("omborga", "ombor", "yuk", "sklad", "ishxona")
    problems: list[str] = []
    for key in order:
        label = BOT_LABELS.get(key, key)
        cnt, last_at = stats.get(key, (0, None))
        if cnt > 0:
            tail = f", oxirgi: {last_at}" if last_at else ""
            lines.append(f"  ✅ {label}: {cnt} ta{tail}")
        else:
            lines.append(f"  ⚪ {label}: event yo'q")
            problems.append(label)

    for key, (cnt, last_at) in stats.items():
        if key in order:
            continue
        label = BOT_LABELS.get(key, key)
        lines.append(f"  ✅ {label}: {cnt} ta")

    lines.append("")
    if not hub_configured():
        problems.insert(0, "Hub sozlama to'liq emas")
    if not g_ok:
        problems.insert(0, "Guruhga yozib bo'lmayapti")
    if hub_url and not h_ok:
        problems.insert(0, "HTTP /health javob bermadi")

    if problems:
        lines.append("⚠️ <b>Diqqat</b>")
        for p in problems[:6]:
            lines.append(f"  • {p}")
        lines.append("")
        lines.append(
            "💡 Har bir ish botida <code>YORDAMCHI_HUB_URL</code> va "
            "<code>YORDAMCHI_HUB_SECRET</code> bir xil bo'lsin. "
            "Yordamchi — Web servis (Worker emas)."
        )
    else:
        lines.append("✅ <b>Asosiy kanallar va integratsiya sozlangan ko'rinadi.</b>")

    return "\n".join(lines)


async def handle_admin_status(message: Message, bot: Bot) -> None:
    uid = message.from_user.id if message.from_user else 0
    text = await build_admin_status_report(bot, uid)
    await message.answer(text, parse_mode="HTML")
