import os
import json
import base64
import logging
import sys
import asyncio
import traceback

import gspread
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
from datetime import datetime

# --- Tambahkan ini untuk Flask ---
from flask import Flask, request, abort
from telegram.error import InvalidToken
# ---------------------------------

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

logger.info("Script bot starting up...")

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT_B64 = os.getenv("GOOGLE_SERVICE_ACCOUNT")

# --- GOOGLE SHEET TAB NAMES ---
TAB_NAME_CHECKIN = "Sheet1"
AUTHORIZED_USERS_TAB_NAME = "AUTHORIZED_USERS"

# Global variables for worksheet
worksheet_checkin_data = None
worksheet_authorized_users = None

# Inisialisasi Application di luar fungsi main() karena akan digunakan oleh Flask
application = None

async def initialize_google_sheets():
    """Menginisialisasi koneksi Google Sheets."""
    global worksheet_checkin_data, worksheet_authorized_users
    
    logger.info("Memulai inisialisasi Google Sheets...")
    encoded = GOOGLE_SERVICE_ACCOUNT_B64
    if not encoded:
        logger.error("GOOGLE_SERVICE_ACCOUNT (Base64) belum diatur di environment.")
        raise ValueError("GOOGLE_SERVICE_ACCOUNT (Base64) belum diatur di environment")

    logger.info("Mencoba mendekode kredensial Google Service Account...")
    try:
        credentials_json = base64.b64decode(encoded).decode("utf-8")
        creds_dict = json.loads(credentials_json)
        logger.info("Kredensial berhasil didekode.")
    except Exception as e:
        logger.error(f"Error saat mendekode kredensial: {e}")
        raise

    logger.info("Mencoba mengotorisasi gspread...")
    try:
        gc = gspread.service_account_from_dict(creds_dict)
        logger.info("Otorisasi gspread berhasil.")
    except Exception as e:
        logger.error(f"Error saat otorisasi gspread: {e}")
        raise

    logger.info(f"Mencoba membuka spreadsheet dengan ID: {SPREADSHEET_ID}...")
    try:
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info("Spreadsheet berhasil dibuka.")
    except Exception as e:
        logger.error(f"Error saat membuka spreadsheet: {e}")
        raise

    logger.info(f"Mencoba membuka worksheet data utama: {TAB_NAME_CHECKIN}...")
    try:
        worksheet_checkin_data = spreadsheet.worksheet(TAB_NAME_CHECKIN)
        logger.info(f"Worksheet '{TAB_NAME_CHECKIN}' berhasil dibuka.")
    except Exception as e:
        logger.error(f"Error saat membuka worksheet '{TAB_NAME_CHECKIN}': {e}")
        raise

    logger.info(f"Mencoba membuka worksheet pengguna yang diotorisasi: {AUTHORIZED_USERS_TAB_NAME}...")
    try:
        worksheet_authorized_users = spreadsheet.worksheet(AUTHORIZED_USERS_TAB_NAME)
        logger.info(f"Worksheet '{AUTHORIZED_USERS_TAB_NAME}' berhasil dibuka.")
    except Exception as e:
        logger.error(f"Error saat membuka worksheet '{AUTHORIZED_USERS_TAB_NAME}': {e}")
        raise

    logger.info("Semua koneksi Google Sheet berhasil diinisialisasi.")


# Status untuk ConversationHandler
GET_STORE_NAME = 1
GET_STORE_REGION = 2
GET_LOCATION = 3

async def get_authorized_sales_list():
    """Mengambil daftar username sales yang diotorisasi dari Google Sheet."""
    if worksheet_authorized_users is None:
        logger.error("worksheet_authorized_users belum diinisialisasi. Tidak dapat mengambil daftar sales.")
        return []

    try:
        all_values = worksheet_authorized_users.get_all_values()
        if not all_values:
            logger.warning(f"Sheet '{AUTHORIZED_USERS_TAB_NAME}' kosong atau tidak dapat diakses.")
            return []

        authorized_sales = [row[0].strip() for row in all_values if row and row[0].strip()]
        
        if 'Username' in authorized_sales:
            authorized_sales.remove('Username')

        logger.info(f"Daftar sales yang diotorisasi: {authorized_sales}")
        return authorized_sales
    except Exception as e:
        logger.error(f"Error saat mengambil daftar sales yang diotorisasi dari sheet: {e}. Trace: {traceback.format_exc()}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menanggapi perintah /start."""
    logger.info(f"[{update.effective_user.username}] Menerima perintah /start")
    await update.message.reply_text("Gunakan /checkin untuk absen.")

async def checkin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai proses check-in dan meminta nama toko."""
    user = update.effective_user
    username = user.username or user.first_name

    logger.info(f"[{username}] Menerima perintah /checkin")

    authorized_sales_list = await get_authorized_sales_list()

    if username not in authorized_sales_list:
        logger.warning(f"[{username}] Percobaan check-in tidak sah. Bukan dalam daftar: {authorized_sales_list}")
        await update.message.reply_text("Maaf, Anda tidak diizinkan untuk check-in. Silakan hubungi admin.")
        return ConversationHandler.END

    context.user_data['username'] = username
    await update.message.reply_text("Baik, silakan masukkan **Nama Toko**:", parse_mode='Markdown')
    logger.info(f"[{username}] Meminta nama toko.")
    return GET_STORE_NAME

async def get_store_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima nama toko dan meminta wilayah toko."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Menerima nama toko: '{update.message.text}'")
    context.user_data['store_name'] = update.message.text
    await update.message.reply_text("Sekarang, silakan masukkan **Wilayah Toko**:", parse_mode='Markdown')
    logger.info(f"[{current_username}] Meminta wilayah toko.")
    return GET_STORE_REGION

async def get_store_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima wilayah toko dan meminta lokasi."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Menerima wilayah toko: '{update.message.text}'")
    context.user_data['store_region'] = update.message.text
    
    keyboard = [[KeyboardButton("Bagikan Lokasi Saya", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Terima kasih. Sekarang, silakan bagikan **Lokasi** Anda.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f"[{current_username}] Meminta lokasi.")
    return GET_LOCATION

async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima lokasi dan mencatat check-in."""
    current_username = context.user_data.get('username', 'N/A')
    logger.info(f"[{current_username}] Menerima lokasi.")
    user_location = update.message.location
    username = context.user_data.get('username')
    store_name = context.user_data.get('store_name')
    store_region = context.user_data.get('store_region')

    if not all([username, store_name, store_region]):
        logger.error(f"[{current_username}] Data tidak lengkap untuk check-in: username={username}, store_name={store_name}, store_