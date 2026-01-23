import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Sen Davlatbek nomidan ishlaydigan professional yordamchisan.
Sen omborxona va logistika bo‘yicha yetuk mutaxassissan.

Vazifang:
— Ishchilarga buyruq ohangida javob berish
— Menejerlarga tahlil bilan javob berish
— Xo‘jayin savollariga juda qisqa javob berish

Qoidalar:
— Hech qachon “sun’iy intellektman” dema
— Har doim real ish muhitidagi kabi yoz
— Keraksiz gap yo‘q
"""

@dp.message()
async def handler(message: types.Message):
    if not message.text:
        return

    if message.chat.type in ["group", "supergroup"]:
        me = await bot.me()
        if f"@{me.username}" not in message.text:
            return
        user_text = message.text.replace(f"@{me.username}", "").strip()
    else:
        user_text = message.text.strip()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]
    )

    await message.reply(response.output_text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
