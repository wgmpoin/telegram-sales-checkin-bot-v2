import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Setup Google Sheets API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"

credentials = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

gc = gspread.authorize(credentials)

# Ganti dengan nama spreadsheet kamu
SPREADSHEET_NAME = "Telegram Check-In Bot"
worksheet = gc.open(SPREADSHEET_NAME).sheet1


# Fungsi /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selamat datang! Gunakan perintah /checkin untuk absen.")


# Fungsi /checkin
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = [user.id, user.username or "", user.first_name or "", timestamp]
    worksheet.append_row(data)

    await update.message.reply_text("✅ Check-in berhasil dicatat!")


# Main program
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("BOT_TOKEN belum diatur di file .env!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))

    app.run_polling()
