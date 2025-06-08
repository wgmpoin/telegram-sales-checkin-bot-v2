import os
import logging
import json
import asyncio
from datetime import datetime, timezone, timedelta

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Konfigurasi Logger ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Konfigurasi Google Sheets ---
worksheet = None # Inisialisasi worksheet sebagai None secara default
try:
    GSPREAD_SERVICE_ACCOUNT_KEY = os.environ.get('GSPREAD_SERVICE_ACCOUNT_KEY')
    if not GSPREAD_SERVICE_ACCOUNT_KEY:
        raise ValueError("GSPREAD_SERVICE_ACCOUNT_KEY environment variable not set.")

    # Kredensial adalah JSON string, perlu di-parse
    creds_json = json.loads(GSPREAD_SERVICE_ACCOUNT_KEY)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json,
                                                            scopes=[
                                                                'https://spreadsheets.google.com/feeds',
                                                                'https://www.googleapis.com/auth/drive'
                                                            ])
    client = gspread.authorize(creds)

    SPREADSHEET_ID = os.environ.get('GOOGLE_SHEET_ID')
    SHEET_TAB_NAME = os.environ.get('GOOGLE_SHEET_TAB_NAME', "Checkin") # Default ke "Checkin"

    if not SPREADSHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID environment variable not set.")

    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_TAB_NAME)
    logger.info(f"Berhasil terhubung ke Google Sheet (ID: '{SPREADSHEET_ID}', Tab: '{SHEET_TAB_NAME}')")

except Exception as e:
    logger.error(f"ERROR Gagal menginisialisasi Google Sheets: {e}")
    logger.error("Bot mungkin tidak dapat mencatat data ke Google Sheets.")


# --- Muat Authorized Sales IDs ---
authorized_sales_ids = set() # Set kosong default
authorized_sales_ids_str = os.environ.get('AUTHORIZED_SALES', '')
if authorized_sales_ids_str:
    try:
        authorized_sales_ids = {int(uid.strip()) for uid in authorized_sales_ids_str.split(',') if uid.strip().isdigit()}
        logger.info(f"Authorized sales IDs loaded: {authorized_sales_ids}")
    except ValueError as e:
        logger.error(f"ERROR: Gagal mem-parse AUTHORIZED_SALES IDs: {e}. Pastikan formatnya angka dipisahkan koma.")
        authorized_sales_ids = set() # Reset jika ada error parsing
else:
    logger.warning("Variabel lingkungan 'AUTHORIZED_SALES' tidak ditemukan atau kosong. Tidak ada sales ID yang diotorisasi.")


# --- Inisialisasi Bot Telegram ---
TOKEN = os.environ.get('BOT_TOKEN') # Menggunakan BOT_TOKEN seperti yang kita sepakati di env vars Render
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

if not TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN (BOT_TOKEN) belum diatur! Bot tidak dapat berjalan.")
    # Keluar dari aplikasi karena token adalah hal krusial
    exit(1)

# WEBHOOK_URL diperlukan untuk setup webhook, Render akan menyediakannya secara otomatis
# Kita tidak perlu keluar jika WEBHOOK_URL tidak ada di sini, karena Render akan mengisinya saat deploy.
# Logika set_webhook akan menangani ini saat startup aplikasi
if not WEBHOOK_URL:
    logger.warning("WEBHOOK_URL belum diatur di lingkungan. Ini akan diambil secara otomatis oleh Render.")


# Inisialisasi Application bot
application = Application.builder().token(TOKEN).build()
logger.info("Menginisialisasi bot Telegram Application...")

# --- Fungsi Handler Telegram ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in authorized_sales_ids:
        await update.message.reply_text(f"Halo {update.effective_user.first_name}! 👋 Saya bot pencatat sales harian Anda.")
    else:
        await update.message.reply_text("Maaf, Anda tidak memiliki izin untuk menjalankan bot ini.")
        logger.warning(f"Unauthorized user {user_id} ({update.effective_user.full_name}) tried to use /start.")

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in authorized_sales_ids:
        await update.message.reply_text("Silakan kirimkan nama Anda dan jumlah sales hari ini (contoh: *Nama Lengkap, 1000000*).", parse_mode='Markdown')
    else:
        await update.message.reply_text("Maaf, Anda tidak memiliki izin untuk melakukan check-in.")
        logger.warning(f"Unauthorized user {user_id} ({update.effective_user.full_name}) tried to use /checkin.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_full_name = update.