import os
import json
import base64
import logging
import sys # Import sys untuk memastikan output logging ke stdout
import asyncio # Import asyncio untuk running secara asinkron

import gspread
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
from datetime import datetime

# Konfigurasi logging agar selalu muncul di console/log Render
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

logger.info("Script bot starting up...")

# Mengambil environment variables (menggunakan nama yang Anda miliki)
BOT_TOKEN = os.getenv("BOT_TOKEN") # Menggunakan BOT_TOKEN agar konsisten dengan sebelumnya
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT_B64 = os.getenv("GOOGLE_SERVICE_ACCOUNT") # Menggunakan GOOGLE_SERVICE_ACCOUNT

# Nama tab di Google Sheet
# Pastikan nama tab untuk data check-in Anda benar (misal: "Sheet1", "Checkin Data")
TAB_NAME_CHECKIN = "Sheet1" # <--- UBAH INI JIKA NAMA TAB CHECK-IN ANDA BEDA
AUTHORIZED_USERS_TAB_NAME = "AUTHORIZED_USERS" # Menggunakan nama tab dari kode Anda

# Global variables untuk worksheet
worksheet_checkin_data = None
worksheet_authorized_users = None

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
        # Menggunakan from_service_account_info sebagai alternatif
        # Pastikan gspread versi terbaru untuk support ini
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
            logger.warning("Sheet AUTHORIZED_SALES kosong atau tidak dapat diakses.")
            return []

        # Ambil kolom pertama (index 0) dan strip spasi
        authorized_sales = [row[0].strip() for row in all_values if row and row[0].strip()]
        
        # Hapus header jika ada. Sesuaikan 'Username' dengan teks header yang sebenarnya di sheet AUTHORIZED_SALES.
        if 'Username' in authorized_sales: # Ganti 'Username' jika header Anda berbeda
            authorized_sales.remove('Username')

        logger.info(f"Daftar sales yang diotorisasi: {authorized_sales}")
        return authorized_sales
    except Exception as e:
        logger.error(f"Error saat mengambil daftar sales yang diotorisasi dari sheet: {e}")
        return [] 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menanggapi perintah /start."""
    logger.info(f"[{update.effective_user.username}] Menerima perintah /start")
    # Poin 1: Menghilangkan "Selamat datang."
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
    # Poin 2: Kembali ke state GET_STORE_NAME
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
        logger.error(f"[{current_username}] Data tidak lengkap untuk check-in: username={username}, store_name={store_name}, store_region={store_region}")
        await update.message.reply_text("Terjadi kesalahan. Silakan mulai ulang dengan /checkin.")
        return ConversationHandler.END

    lat_rounded = round(user_location.latitude, 5) 
    lon_rounded = round(user_location.longitude, 5) 
    Maps_link = f"http://www.google.com/maps/place/{lat_rounded},{lon_rounded}" # Perbaikan link Google Maps
    
    now = datetime.now()
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S") 
    
    if worksheet_checkin_data is None:
        logger.error("Worksheet utama (data check-in) belum diinisialisasi. Tidak dapat menulis data.")
        await update.message.reply_text("Terjadi kesalahan sistem. Silakan coba lagi nanti.")
        return ConversationHandler.END

    try:
        worksheet_checkin_data.append_row([ # Menggunakan worksheet_checkin_data
            username,             # Kolom A
            store_name,           # Kolom B
            store_region,         # Kolom C
            datetime_str,         # Kolom D (Gabungan Tanggal & Waktu)
            Maps_link      # Kolom E
        ])

        await update.message.reply_text(
            f"**Check-in berhasil!**\n"
            f"Nama Toko: {store_name}\n"
            f"Wilayah: {store_region}\n"
            f"Waktu Check-in: {datetime_str}\n"
            f"Lokasi: [Lihat Peta]({Maps_link})", 
            parse_mode='Markdown',
            disable_web_page_preview=True 
        )
        logger.info(f"[{username}] Check-in berhasil: {store_name}, {store_region} pada {datetime_str}.")
    except Exception as e:
        logger.error(f"[{username}] Error saat menulis ke Google Sheet: {e}")
        await update.message.reply_text("Terjadi kesalahan saat menyimpan check-in Anda. Silakan coba lagi nanti.")
    
    return ConversationHandler.END

async def cancel_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membatalkan proses check-in."""
    logger.info(f"[{update.effective_user.username}] Check-in dibatalkan.")
    await update.message.reply_text("Proses check-in dibatalkan.")
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menanggapi perintah/pesan yang tidak dikenali."""
    # Menambahkan pengecekan untuk menghindari log error saat message tidak punya text (misal: lokasi)
    message_text = update.message.text if update.message.text else "Non-text message"
    logger.warning(f"[{update.effective_user.username}] Menerima pesan tidak dikenal: '{message_text}'")
    await update.message.reply_text("Maaf, saya tidak mengerti perintah itu.")

async def main():
    logger.info("Fungsi main() dimulai.")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN belum diatur di environment.")
        raise ValueError("BOT_TOKEN harus diatur di environment")
    if not SPREADSHEET_ID:
        logger.critical("SPREADSHEET_ID belum diatur di environment.")
        raise ValueError("SPREADSHEET_ID harus diatur di environment")
    if not GOOGLE_SERVICE_ACCOUNT_B64: # Menambahkan validasi untuk kredensial GSA
        logger.critical("GOOGLE_SERVICE_ACCOUNT belum diatur di environment.")
        raise ValueError("GOOGLE_SERVICE_ACCOUNT harus diatur di environment")
    
    try:
        await initialize_google_sheets()
    except Exception as e:
        logger.critical(f"Gagal menginisialisasi Google Sheets. Bot tidak dapat memulai: {e}")
        return # Keluar dari fungsi main jika GSheet gagal

    logger.info("Membangun ApplicationBuilder...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    logger.info("ApplicationBuilder berhasil dibangun.")

    checkin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin_start)],
        states={
            GET_STORE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_store_name)],
            GET_STORE_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_store_region)],
            GET_LOCATION: [MessageHandler(filters.LOCATION, receive_location)],
        },
        fallbacks=[CommandHandler("cancel", cancel_checkin), MessageHandler(filters.TEXT & ~filters.COMMAND, unknown)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(checkin_conv_handler) 
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown)) 
    application.add_handler(MessageHandler(filters.ALL, unknown)) 

    logger.info("Bot dimulai dan mendengarkan pembaruan... (run_polling)")
    await application.run_polling(poll_interval=1.0, timeout=10)
    logger.info("application.run_polling() selesai.")

if __name__ == "__main__":
    logger.info("Memulai asyncio event loop.")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot dihentikan secara manual (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Terjadi error fatal saat menjalankan bot: {e}", exc_info=True)
    logger.info("Asyncio event loop selesai.")