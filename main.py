import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_full_name = update.effective_user.full_name
    await update.message.reply_text(f'Halo, {user_full_name}! Bot ini sudah aktif.')

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
<<<<<<< HEAD
    app.run_polling()
=======
    app.run_polling()
>>>>>>> 56e566e (Fix syntax error)
