import os
import logging
import base64
import json
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

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CREDENTIALS_JSON_B64 = os.getenv("CREDENTIALS_JSON_B64")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if not TOKEN:
    raise ValueError("BOT_TOKEN belum diatur di environment")

if not CREDENTIALS_JSON_B64:
    raise ValueError("CREDENTIALS_JSON_B64 belum diatur di environment")

# Decode base64 JSON
decoded_json = base64.b64decode(CREDENTIALS_JSON_B64).decode("utf-8")
info = json.loads(decoded_json)

# Setup Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Gunakan open_by_key agar tidak butuh scope Google Drive
SPREADSHEET_ID = "1xx1WzEqrp2LYrg-VTgOPwAhk15DigpBodPM9Bm6pbD4"
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
worksheet = gc.open_by_key(SPREADSHEET_ID).sheet1


# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selamat datang! Gunakan /checkin untuk absen.")

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = [user.id, user.username or "", user.first_name or "", timestamp]
    worksheet.append_row(data)
    await update.message.reply_text("✅ Check-in berhasil!")

# Run bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.run_polling()
