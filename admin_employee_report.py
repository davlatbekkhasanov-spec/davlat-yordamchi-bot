"""Admin: xodim tanlab bugungi hisobot kartochkasini shaxsiy chatda ko'rish."""

from __future__ import annotations

import html

from aiogram.types import BufferedInputFile, KeyboardButton, ReplyKeyboardMarkup

from employee_tg_map import resolve_owner_tg_id

BTN_ADMIN_EMP_REPORT = "👥 Xodim hisoboti"
BTN_ALL_EMPLOYEES = "✅ Ҳамма ходим"


def admin_emp_report_kb(employees: list[str]) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=e)] for e in employees]
    rows.append([KeyboardButton(text=BTN_ALL_EMPLOYEES)])
    rows.append([KeyboardButton(text="❌ Бекор қилиш")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def send_one_employee_report(
    message: Message,
    *,
    emp: str,
    session_agg_for_employee,
    build_report_png_for_user,
    today_local,
) -> bool:
    """Bitta xodim hisobotini admin DM ga yuboradi. True = yuborildi."""
    photo_uid = resolve_owner_tg_id(emp) or (message.from_user.id if message.from_user else 0)
    agg = await session_agg_for_employee(emp)
    built = await build_report_png_for_user(photo_uid, emp, agg)
    day_iso = today_local().isoformat()
    if not built:
        await message.answer(
            f"⚠️ <b>{html.escape(emp)}</b> — {day_iso}\n"
            "Bugun hali hisobot ma'lumoti yo'q.",
            parse_mode="HTML",
        )
        return False
    png, card = built
    cats = ", ".join(c.name for c in card.categories[:6]) if card.categories else "—"
    if len(card.categories) > 6:
        cats += "…"
    await message.answer_photo(
        BufferedInputFile(png, filename="report.png"),
        caption=(
            f"👥 <b>{html.escape(emp)}</b> · {day_iso}\n"
            f"🏆 Jami: <b>+{card.grand_total}</b> ochko\n"
            f"📋 {html.escape(cats)}"
        ),
        parse_mode="HTML",
    )
    return True
