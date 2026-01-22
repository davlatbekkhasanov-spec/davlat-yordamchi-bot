import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

# ================== SOZLAMALAR ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. Render Environment Variables tekshir.")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== /start ==================
@dp.message(CommandStart())
async def start_handler(message: Message):
    text = (
        "Salom! 👋\n\n"
        "Men **Davlat Yordamchi Botman** 🤖\n\n"
        "Quyidagi yo‘nalishlar bo‘yicha professional yordam beraman:\n\n"
        "📦 **Omborxona**\n"
        "• Kirim / chiqim\n"
        "• Qoldiq nazorati\n"
        "• Inventarizatsiya\n"
        "• Ombor hisobotlari\n\n"
        "📊 **Buxgalteriya**\n"
        "• Xarajat va daromad tahlili\n"
        "• Hisobotlar\n"
        "• Hujjatlar bilan ishlash\n\n"
        "🎧 **Operator / Menejer**\n"
        "• Mijozlar bilan muloqot\n"
        "• Buyurtmalar\n"
        "• Tushuntirish va maslahat\n\n"
        "✍️ Savolingni yoz — aniq va dadil javob beraman."
    )
    await message.answer(text, parse_mode="Markdown")

# ================== ODDIY XABARLAR ==================
@dp.message()
async def all_messages_handler(message: Message):
    user_text = message.text.lower()

    if "ombor" in user_text:
        await message.answer(
            "📦 **Ombor bo‘yicha maslahat:**\n\n"
            "Omborda eng muhim 3 narsa:\n"
            "1️⃣ Kirim-chiqimning aniq yozilishi\n"
            "2️⃣ Qoldiqni doimiy tekshirish\n"
            "3️⃣ Hujjat va real mahsulot mosligi\n\n"
            "Agar xohlasang, misol bilan tushuntirib beraman."
        )

    elif "buxgalter" in user_text or "hisob" in user_text:
        await message.answer(
            "📊 **Buxgalteriya bo‘yicha maslahat:**\n\n"
            "Har bir operatsiya:\n"
            "• Sana\n"
            "• Summa\n"
            "• Izoh\n"
            "• Mas’ul shaxs\n"
            "bilan qayd etilishi shart.\n\n"
            "Qaysi hisob-kitob kerak — ayt."
        )

    elif "hisobot" in user_text:
        await message.answer(
            "📑 **Hisobot tayyorlash:**\n\n"
            "Men quyidagilarni tuzib bera olaman:\n"
            "• Kunlik\n"
            "• Oylik\n"
            "• Ombor qoldig‘i\n"
            "• Daromad-xarajat\n\n"
            "Qaysi biri kerak?"
        )

    else:
        await message.answer(
            "✅ Tushundim.\n\n"
            "Savolingni biroz aniqroq yoz:\n"
            "📦 Ombormi?\n"
            "📊 Buxgalteriyami?\n"
            "🎧 Operatorlik masalasimi?\n\n"
            "Men professional yordam beraman."
        )

# ================== ISHGA TUSHIRISH ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
