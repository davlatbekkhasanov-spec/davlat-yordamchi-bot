"""Admin: bitta tugmada kanallar va integratsiya holati."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from cross_bot_hub import BOT_LABELS, count_employee_links, hub_stats_today
from yordamchi_push import today_iso

BTN_ADMIN_STATUS = "📊 Tizim holati"


def admin_status_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_ADMIN_STATUS)]],
        resize_keyboard=True,
    )


def _flag(ok: bool) -> str:
    return "✅" if ok else "❌"


def resolve_public_hub_url() -> str:
    """Boshqa botlar va /health uchun ochiq URL."""
    explicit = os.getenv("YORDAMCHI_HUB_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if domain:
        if domain.startswith("http"):
            return domain.rstrip("/")
        return f"https://{domain}"
    static = os.getenv("RAILWAY_STATIC_URL", "").strip().rstrip("/")
    if static:
        return static
    return ""


def _http_health(url: str) -> tuple[bool, str]:
    base = (url or "").strip().rstrip("/")
    if not base:
        return False, "URL aniqlanmadi"
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


async def _chat_ok(bot: Bot, chat_id: int) -> tuple[bool, str]:
    if not chat_id:
        return False, "sozlanmagan"
    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or chat.username or chat.first_name or str(chat_id)
        return True, title[:60]
    except TelegramAPIError as e:
        return False, str(e)[:80]


async def build_admin_status_report(bot: Bot, admin_uid: int) -> str:
    day = today_iso()
    lines: list[str] = [
        "📊 <b>Tizim holati</b>",
        f"📅 Kun: {day}",
        f"👤 Sizning ID: <code>{admin_uid}</code>",
        "",
    ]

    group_id = int(os.getenv("GROUP_ID", "0") or "0")
    ingest_id = int(os.getenv("YORDAMCHI_INGEST_CHAT_ID", "0") or "0")
    g_ok, g_info = await _chat_ok(bot, group_id)
    i_ok, i_info = await _chat_ok(bot, ingest_id) if ingest_id else (True, "HTTP rejim — shart emas")

    lines.append("📢 <b>Kanallar</b>")
    lines.append(f"  {_flag(g_ok)} Guruh (hisobot): <code>{group_id}</code>")
    if g_ok:
        lines.append(f"     → {g_info}")
    else:
        lines.append(f"     ⚠️ {g_info}")

    lines.append(f"  {_flag(i_ok)} Ingest chat: <code>{ingest_id or '—'}</code>")
    if ingest_id:
        lines.append(f"     → {i_info}")
    lines.append("")

    secret_ok = bool(os.getenv("YORDAMCHI_HUB_SECRET", "").strip())
    public_url = resolve_public_hub_url()
    port = os.getenv("PORT", "8080").strip() or "8080"

    local_ok, local_info = await asyncio.to_thread(_http_health, f"http://127.0.0.1:{port}")
    pub_ok, pub_info = (False, "ochiq domen yo'q")
    if public_url:
        pub_ok, pub_info = await asyncio.to_thread(_http_health, public_url)

    hub_receive_ok = secret_ok and (local_ok or pub_ok)
    tg_fb = bool(os.getenv("YORDAMCHI_BOT_TOKEN", "").strip()) and bool(ingest_id)

    lines.append("🔗 <b>Hub (bu bot — markaz)</b>")
    lines.append(f"  {_flag(secret_ok)} YORDAMCHI_HUB_SECRET (qabul qilish)")
    lines.append(f"  {_flag(local_ok)} Ichki server :{port} — {local_info}")
    if public_url:
        lines.append(f"  {_flag(pub_ok)} Tashqi URL — {pub_info}")
        lines.append(f"     <code>{public_url}</code>")
    else:
        lines.append("  ❌ Ochiq URL yo'q (Railway → Networking → Generate domain)")
    lines.append(f"  {_flag(hub_receive_ok)} Hub qabul qilmoqda (HTTP ingest)")
    if tg_fb:
        lines.append("  ✅ Telegram ingest (zaxira) ham yoqilgan")
    lines.append("")

    lines.append("📋 <b>Boshqa 5 ta ish botiga</b> (Railway Variables):")
    if public_url and secret_ok:
        lines.append(f"  <code>YORDAMCHI_HUB_URL={public_url}</code>")
        lines.append("  <code>YORDAMCHI_HUB_SECRET=…</code> (yordamchi bilan bir xil)")
        lines.append("  <code>TZ=Asia/Tashkent</code>")
    else:
        lines.append("  Avval yordamchi da SECRET + ochiq domen bo'lsin")
    lines.append("")

    links = await count_employee_links()
    stats = await hub_stats_today(day)
    total_events = sum(c for c, _ in stats.values())

    lines.append("💾 <b>Ma'lumotlar</b>")
    lines.append(f"  ✅ Ulangan xodimlar: {links}")
    lines.append(f"  📥 Bugun hub eventlari: {total_events}")
    lines.append("")

    lines.append("🤖 <b>Botlar (bugun)</b>")
    order = ("omborga", "ombor", "yuk", "sklad", "ishxona")
    problems: list[str] = []
    for key in order:
        label = BOT_LABELS.get(key, key)
        cnt, last_at = stats.get(key, (0, None))
        if cnt > 0:
            tail = f", oxirgi: {last_at}" if last_at else ""
            lines.append(f"  ✅ {label}: {cnt}{tail}")
        else:
            lines.append(f"  ⚪ {label}: event yo'q")

    lines.append("")
    if not secret_ok:
        problems.append("YORDAMCHI_HUB_SECRET yo'q — ingest o'chiq")
    if not public_url:
        problems.append("Ochiq domen yo'q — ish botlar URL bilmaydi")
    elif not pub_ok and not local_ok:
        problems.append("HTTP /health ishlamayapti — Web servis + PORT tekshiring")
    if not g_ok:
        problems.append("Guruhga yozib bo'lmayapti")
    if total_events == 0 and hub_receive_ok:
        problems.append(
            "Bugun event 0 — ish botlarda URL+SECRET qo'yilganmi? (yakunlangandan keyin yangilanadi)"
        )

    if problems:
        lines.append("⚠️ <b>Diqqat</b>")
        for p in problems[:7]:
            lines.append(f"  • {p}")
    else:
        lines.append("✅ <b>Hammasi yaxshi ko'rinadi.</b>")

    return "\n".join(lines)


async def handle_admin_status(message: Message, bot: Bot) -> None:
    uid = message.from_user.id if message.from_user else 0
    text = await build_admin_status_report(bot, uid)
    await message.answer(text, parse_mode="HTML")
