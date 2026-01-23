import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# =========================
# TOKEN
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN topilmadi")

# =========================
# XO‘JAYINLAR
# =========================
OWNER_IDS = [
    1432810519,  # SEN
    2624538      # XO‘JAYINING
]

# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom!\n"
        "📦 Men omborxona bo‘yicha AI yordamchi botman.\n"
        "Savolingizni yozing."
    )

# =========================
# /id
# =========================
async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Sizning ID: {update.effective_user.id}")

# =========================
# ASOSIY MANTIQ
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # ROL ANIQLASH
    if user_id in OWNER_IDS:
        reply = (
            "👑 Hurmatli rahbar,\n"
            "Savolingiz qabul qilindi.\n\n"
            f"📌 Savol: {text}\n\n"
            "Tahlil qilib, eng to‘g‘ri yechimni taklif qilaman."
        )
    else:
        reply = (
            "👷 Ishchi uchun ko‘rsatma:\n"
            f"📌 Savol: {text}\n\n"
            "Amaldagi ombor tartibiga rioya qiling va natijani rahbarga xabar qiling."
        )

    await update.message.reply_text(reply)

# =========================
# RUN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", my_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
