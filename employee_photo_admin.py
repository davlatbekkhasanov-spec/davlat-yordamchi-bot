"""Admin: xodim tanlab rasm yuklash."""

from __future__ import annotations

from io import BytesIO

from aiogram import Bot
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from employee_tg_map import resolve_tg_id

BTN_PHOTO_CANCEL = "❌ Бекор қилиш"

admin_photo_state: dict[int, dict] = {}


def photo_employees_kb(employees: list[str]) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=e)] for e in employees]
    rows.append([KeyboardButton(text=BTN_PHOTO_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def photo_upload_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_PHOTO_CANCEL)]],
        resize_keyboard=True,
    )


async def start_photo_upload(message: Message, employees: list[str]) -> None:
    uid = message.from_user.id if message.from_user else 0
    admin_photo_state[uid] = {"step": "employee"}
    await message.answer(
        "📷 Qaysi xodim uchun rasm yuklaysiz?\nIsmini tanlang:",
        reply_markup=photo_employees_kb(employees),
    )


async def handle_photo_employee_pick(
    message: Message,
    *,
    employees: list[str],
    employee_tg_map: dict[str, int],
    admin_status_kb,
) -> bool:
    uid = message.from_user.id if message.from_user else 0
    st = admin_photo_state.get(uid)
    if not st or st.get("step") != "employee":
        return False

    text = (message.text or "").strip()
    if text == BTN_PHOTO_CANCEL:
        admin_photo_state.pop(uid, None)
        await message.answer("Bekor qilindi.", reply_markup=admin_status_kb())
        return True

    if text not in employees:
        await message.answer("Ro'yxatdan xodimni tanlang.")
        return True

    tg_id = resolve_tg_id(text, employee_tg_map)
    admin_photo_state[uid] = {"step": "upload", "employee": text, "tg_id": tg_id}

    if tg_id:
        await message.answer(
            f"👤 {text}\n📷 Endi rasm yuboring (caption shart emas).",
            reply_markup=photo_upload_kb(),
        )
    else:
        await message.answer(
            f"👤 {text}\n"
            "⚠️ Telegram ID topilmadi — rasm ism bo'yicha saqlanadi.\n"
            "📷 Endi rasm yuboring.",
            reply_markup=photo_upload_kb(),
        )
    return True


async def handle_photo_upload(
    message: Message,
    bot: Bot,
    *,
    save_photo,
    admin_status_kb,
) -> bool:
    uid = message.from_user.id if message.from_user else 0
    st = admin_photo_state.get(uid)
    if not st or st.get("step") != "upload" or not message.photo:
        return False

    name = st["employee"]
    tg_id = st.get("tg_id")
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    if not file.file_path:
        await message.answer("Fayl topilmadi, qayta yuboring.")
        return True

    buf = BytesIO()
    await bot.download_file(file.file_path, buf)
    await save_photo(employee=name, tg_id=tg_id, data=buf.getvalue())
    admin_photo_state.pop(uid, None)

    extra = f"\n🆔 {tg_id}" if tg_id else "\n(Saqlash: ism bo'yicha)"
    await message.answer(
        f"✅ Rasm saqlandi!\n👤 {name}{extra}",
        reply_markup=admin_status_kb(),
    )
    return True


async def handle_photo_cancel(message: Message, admin_status_kb) -> bool:
    uid = message.from_user.id if message.from_user else 0
    if uid not in admin_photo_state:
        return False
    if (message.text or "").strip() != BTN_PHOTO_CANCEL:
        return False
    admin_photo_state.pop(uid, None)
    await message.answer("Bekor qilindi.", reply_markup=admin_status_kb())
    return True
