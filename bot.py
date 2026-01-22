import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")


SYSTEM_PROMPT = """
Sen 15 yillik tajribaga ega bo‘lgan omborxona, logistika va buxgalteriya bo‘yicha
yuqori malakali professional mutaxassissan.

Sen quyidagi rollarni mukammal bilasan:
- Omborchi
- Ombor hisobchisi
- Logist
- Buxgalter
- Ombor menejeri
- Audit va inventarizatsiya mutaxassisi
- Analitik
- Operator-maslahatchi

Javoblaring har doim:
- aniq
- mantiqli
- real hayotga mos
- kerak bo‘lsa bosqichma-bosqich bo‘ladi

Agar savol noto‘g‘ri bo‘lsa — to‘g‘rilaysan.
Agar savol noaniq bo‘lsa — aniqlashtirasan.
Har doim professional yordamchi bo‘lib qolasan.
"""


from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! 👋\n"
        "Men omborxona, logistika va buxgalteriya bo‘yicha professional yordamchiman.\n\n"
        "Savolingni yoz — yordam beraman."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )

    answer = response.choices[0].message.content
    await update.message.reply_text(answer)


async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
