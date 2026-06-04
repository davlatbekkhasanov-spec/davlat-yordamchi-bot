"""Admin: bonus / jarima — hozircha faqat lichkada (tanitanali xabar + ping)."""

from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from employee_tg_map import resolve_owner_tg_id
from ranking_adjustments import (
    BTN_ADJ_CONFIRM,
    insert_adjustment,
)

log = logging.getLogger(__name__)


def _adj_confirm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADJ_CONFIRM)],
            [KeyboardButton(text="❌ Бекор қилиш")],
        ],
        resize_keyboard=True,
    )


def _start_adj(uid: int, kind: str) -> dict:
    return {
        "admin_rank_adj": {
            "kind": kind,
            "step": "employee",
            "employee": None,
            "points": None,
        }
    }


def _kind_label(kind: str) -> str:
    return "Бонус" if kind == "bonus" else "Жарима"


def _employee_mention(employee: str, tg_id: int | None) -> str:
    safe = html.escape(employee)
    if tg_id:
        return f'<a href="tg://user?id={int(tg_id)}">{safe}</a>'
    return f"<b>{safe}</b>"


def format_bonus_announcement(
    *,
    employee: str,
    points: int,
    period: str,
    day_iso: str,
    tg_id: int | None,
) -> str:
    who = _employee_mention(employee, tg_id)
    return (
        "🎉✨ <b>ТАНТАНАВИЙ БОНУС!</b> ✨🎉\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {who}\n"
        f"💎 <b>+{points}</b> бонус очко <b>рейтингга қўшилди</b>\n\n"
        f"📈 Период: <code>{html.escape(period)}</code>\n"
        f"📅 Сана: <code>{html.escape(day_iso)}</code>\n\n"
        "🏆 <i>Аъло натижа — давом этинг, чемпион!</i> 🔥👏"
    )


def format_penalty_announcement(
    *,
    employee: str,
    points: int,
    period: str,
    day_iso: str,
    tg_id: int | None,
) -> str:
    who = _employee_mention(employee, tg_id)
    return (
        "⚠️🛑 <b>ЖАРИМА ОЧКО</b> 🛑⚠️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {who}\n"
        f"📉 <b>−{points}</b> очко <b>рейтингдан айирилди</b>\n\n"
        f"📈 Период: <code>{html.escape(period)}</code>\n"
        f"📅 Сана: <code>{html.escape(day_iso)}</code>\n\n"
        "⛔ <i>Диққат: қайта такрорланмасин — жамоа кутяпти.</i>"
    )


def format_admin_saved_note(*, kind: str, points: int) -> str:
    if kind == "bonus":
        return f"✅ Базага сақланди · рейтингга <b>+{points}</b>"
    return f"✅ Базага сақланди · рейтингдан <b>−{points}</b>"


async def _send_private_html(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
        return True
    except Exception:
        log.exception("Bonus/jarima xabar (chat=%s)", chat_id)
        return False


async def handle_bonus_start(
    message: Message,
    *,
    user_state: dict,
    employees: list[str],
    employees_kb,
    admin_status_kb,
    is_admin,
) -> None:
    if not is_admin(message.from_user.id):
        return
    uid = message.from_user.id
    user_state[uid] = _start_adj(uid, "bonus")
    await message.answer(
        "➕ <b>Бонус очко</b>\n\nХодимни танланг (рейтингга қўшилади):",
        parse_mode="HTML",
        reply_markup=employees_kb(with_all=False),
    )


async def handle_penalty_start(
    message: Message,
    *,
    user_state: dict,
    employees: list[str],
    employees_kb,
    is_admin,
) -> None:
    if not is_admin(message.from_user.id):
        return
    uid = message.from_user.id
    user_state[uid] = _start_adj(uid, "penalty")
    await message.answer(
        "➖ <b>Жарима очко</b>\n\nХодимни танланг (рейтингдан айрилади):",
        parse_mode="HTML",
        reply_markup=employees_kb(with_all=False),
    )


async def handle_employee_pick(
    message: Message,
    *,
    user_state: dict,
    employees: list[str],
    is_admin,
) -> bool:
    if not is_admin(message.from_user.id):
        return False
    uid = message.from_user.id
    st = user_state.get(uid, {}).get("admin_rank_adj")
    if not st or st.get("step") != "employee":
        return False
    text = (message.text or "").strip()
    if text not in employees:
        return False
    st["employee"] = text
    st["step"] = "points"
    kind = st["kind"]
    await message.answer(
        f"👤 {html.escape(text)}\n\n"
        f"{_kind_label(kind)} учун <b>очко сонини</b> киритинг (масалан 25):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Бекор қилиш")]],
            resize_keyboard=True,
        ),
    )
    return True


async def handle_points(
    message: Message,
    *,
    user_state: dict,
    is_admin,
) -> bool:
    if not is_admin(message.from_user.id):
        return False
    uid = message.from_user.id
    st = user_state.get(uid, {}).get("admin_rank_adj")
    if not st or st.get("step") != "points":
        return False
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("❌ Фақат мусбат сон (1, 2, 3 …).")
        return True
    st["points"] = int(raw)
    st["step"] = "confirm"
    emp = st["employee"]
    pts = st["points"]
    kind = st["kind"]
    sign = "+" if kind == "bonus" else "−"
    preview = (
        f"👤 {html.escape(emp or '')}\n"
        f"📌 {_kind_label(kind)}: <b>{sign}{pts}</b> (рейтинг)\n\n"
        "Тасдиқласангиз — <b>личкада</b> тантанали хabar chiqadi.\n"
        "(Guruhga hozircha yuborilmaydi.)"
    )
    await message.answer(
        preview,
        parse_mode="HTML",
        reply_markup=_adj_confirm_kb(),
    )
    return True


async def handle_confirm(
    message: Message,
    *,
    bot: Bot,
    user_state: dict,
    db_execute,
    is_admin,
    get_period_key,
    today_local,
    admin_status_kb,
) -> bool:
    if not is_admin(message.from_user.id):
        return False
    uid = message.from_user.id
    root = user_state.get(uid, {})
    st = root.get("admin_rank_adj")
    if not st or st.get("step") != "confirm":
        return False

    emp = st.get("employee")
    pts = st.get("points")
    kind = st.get("kind")
    if not emp or not pts or kind not in ("bonus", "penalty"):
        await message.answer("❌ Маълумот тўлиқ эмас. Қайта бошланг.")
        user_state.pop(uid, None)
        return True

    today = today_local()
    period = get_period_key(today)
    day_iso = today.isoformat()

    await insert_adjustment(
        db_execute,
        period=period,
        day_iso=day_iso,
        employee=emp,
        kind=kind,
        points=pts,
        admin_tg_id=uid,
    )

    emp_tg = resolve_owner_tg_id(emp)
    if kind == "bonus":
        announce = format_bonus_announcement(
            employee=emp,
            points=pts,
            period=period,
            day_iso=day_iso,
            tg_id=emp_tg,
        )
    else:
        announce = format_penalty_announcement(
            employee=emp,
            points=pts,
            period=period,
            day_iso=day_iso,
            tg_id=emp_tg,
        )

    await _send_private_html(bot, uid, announce)

    emp_notified = False
    if emp_tg and int(emp_tg) != int(uid):
        emp_notified = await _send_private_html(bot, int(emp_tg), announce)

    if emp_tg and int(emp_tg) != int(uid):
        tail = (
            "\n\n<i>Xodimga ham lichkada ping yuborildi.</i>"
            if emp_notified
            else "\n\n⚠️ <i>Xodimga lichkaga yuborilmadi (/start kerak).</i>"
        )
    elif emp_tg:
        tail = "\n\n<i>(Sizning profilingiz — bitta xabar.)</i>"
    else:
        tail = "\n\n<i>Telegram ID topilmadi — faqat sizda ko‘rinadi.</i>"

    await message.answer(
        format_admin_saved_note(kind=kind, points=pts) + tail,
        parse_mode="HTML",
        reply_markup=admin_status_kb(),
    )

    user_state.pop(uid, None)
    return True


async def handle_cancel(
    message: Message,
    *,
    user_state: dict,
    is_admin,
    admin_status_kb,
) -> bool:
    if not is_admin(message.from_user.id):
        return False
    uid = message.from_user.id
    if "admin_rank_adj" not in user_state.get(uid, {}):
        return False
    user_state.pop(uid, None)
    await message.answer("Бекор қилинди.", reply_markup=admin_status_kb())
    return True
