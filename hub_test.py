"""Admin: hub integratsiyasini tekshirish."""

from __future__ import annotations

import os

from aiogram.types import Message

from cross_bot_hub import BOT_LABELS, build_appendix_lines_async, fetch_latest_by_bot, record_event
from yordamchi_push import today_iso, push_to_yordamchi_hub

BTN_HUB_TEST = "🧪 Test (admin)"


def _hub_config_lines() -> list[str]:
    url = os.getenv("YORDAMCHI_HUB_URL", "").strip()
    secret = bool(os.getenv("YORDAMCHI_HUB_SECRET", "").strip())
    tg = bool(os.getenv("YORDAMCHI_BOT_TOKEN", "").strip())
    chat = bool(int(os.getenv("YORDAMCHI_INGEST_CHAT_ID", "0") or "0"))
    lines = [
        "Hub sozlama:",
        f"• HTTP URL: {'✅' if url else '❌'} {url or '—'}",
        f"• HUB_SECRET: {'✅' if secret else '❌'}",
        f"• Telegram fallback: {'✅' if tg and chat else '❌'}",
    ]
    return lines


async def seed_local_test_events(tg_id: int) -> None:
    """Boshqa botlar ishlamasa ham yakunda ko'rish uchun (faqat shu server DB)."""
    day = today_iso()
    samples = [
        ("omborga", "[TEST] Reys 3, yuk 108m, ish 1:25:00, dam 7s"),
        ("ombor", "[TEST] #99 Xizmat: bajarildi, 12 daqiqa"),
        ("yuk", "[TEST] Yuk #7: ish vaqti 45 daqiqa"),
        ("sklad", "[TEST] Papka A-12: sanaldi OK, kun 3/10"),
        ("ishxona", "[TEST] Shikoyat (test): namuna matn"),
    ]
    for bot_key, summary in samples:
        await record_event(tg_id=tg_id, day=day, bot_key=bot_key, summary=summary)


async def handle_admin_hub_test(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    day = today_iso()

    ok_self, via_self = await push_to_yordamchi_hub(
        tg_id=uid,
        bot_key="yordamchi",
        summary="[TEST] Yordamchi bot hub tekshiruvi",
    )

    await seed_local_test_events(uid)
    events = await fetch_latest_by_bot(uid, day)
    appendix = await build_appendix_lines_async(uid, day)

    lines = _hub_config_lines()
    lines.append("")
    lines.append(f"O'z test yuborish: {'✅' if ok_self else '❌'} ({via_self})")
    lines.append("Lokal DB: 5 ta namuna event qo'shildi (barcha botlar).")
    lines.append("")
    if events:
        lines.append("Bugun saqlangan (bot bo'yicha):")
        for k, v in events.items():
            label = BOT_LABELS.get(k, k)
            lines.append(f"• {label}: {v[:80]}")
    else:
        lines.append("Bugun event yo'q.")

    if appendix:
        lines.append("")
        lines.append("Yakunlashda qo'shiladigan blok:")
        lines.extend(appendix)
    else:
        lines.append("")
        lines.append("Yakunlashda qo'shimcha blok bo'sh.")

    lines.append("")
    lines.append("Keyin ✅ Якунлаш bosing — guruhdagi hisobotda «Boshqa botlar» chiqishi kerak.")

    await message.answer("\n".join(lines))
