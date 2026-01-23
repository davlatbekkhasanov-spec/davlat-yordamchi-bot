from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "BOT_TOKENINGNI_BU_YERGA_QO‘Y"

# XO‘JAYINLAR IDsi
OWNER_IDS = [1432810519, 2624538]

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom!\n"
        "📦 Men omborxona bo‘yicha AI yordamchi botman.\n"
        "Savolingizni yozing."
    )

# /id — MUHIM
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = "👑 XO‘JAYIN" if user.id in OWNER_IDS else "👷 ISHCHI"

    await update.message.reply_text(
        f"🆔 Sizning ID: {user.id}\n"
        f"🔐 Rolingiz: {role}"
    )

# Oddiy xabarlar
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in OWNER_IDS:
        prefix = "👑 Rahbar uchun javob:\n"
    else:
        prefix = "👷 Ishchi uchun ko‘rsatma:\n"

    await update.message.reply_text(prefix + "Savolingiz qabul qilindi.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))  # 👈 ENG MUHIM QATOR
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
