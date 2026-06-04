"""Admin: bonus / jarima — avval lichka, keyin guruh."""

from __future__ import annotations

import html
import logging
from datetime import date

from aiogram import Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from ranking_adjustments import (
    BTN_ADJ_CONFIRM,
    BTN_BONUS,
    BTN_PENALTY,
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
    box,
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
    await message.answer(
        box(
            [
                f"Ходим: {emp}",
                f"Turi: {_kind_label(kind)}",
                f"Очко: {sign}{pts}",
                "",
                "Тасдиқласангиз — аввал бу ерда, сўнг гуруҳга хабар юборилади.",
            ],
            title="ТАСДИҚ",
        ),
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
    box,
    get_period_key,
    today_local,
    group_id: int,
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

    sign = "+" if kind == "bonus" else "−"
    if kind == "bonus":
        group_line = f"➕ {emp} ходимга <b>+{pts}</b> бонус очко қўшилди (рейтинг)."
    else:
        group_line = f"➖ {emp} ходимдан <b>−{pts}</b> жарима очко айирилди (рейтинг)."

    private_lines = [
        f"✅ Сақланди: {_kind_label(kind)} {sign}{pts}",
        f"👤 {emp}",
        f"🗓 Период: {period}",
        f"📅 {day_iso}",
        "",
        "Гуруҳга хабар юборилди.",
    ]
    await message.answer(
        box(private_lines, title="РЕЙТИНГ БОНУС/ЖАРИМА"),
        parse_mode="HTML",
        reply_markup=admin_status_kb(),
    )

    group_html = box(
        [group_line, f"Период: {period}", f"Сана: {day_iso}"],
        title="🏆 РЕЙТИНГ",
    )
    try:
        await bot.send_message(group_id, group_html, parse_mode="HTML")
    except Exception:
        log.exception("Bonus/jarima guruh xabari (chat=%s)", group_id)
        await message.answer(f"⚠️ Guruhga yuborilmadi. GROUP_ID={group_id} ni tekshiring.")

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
