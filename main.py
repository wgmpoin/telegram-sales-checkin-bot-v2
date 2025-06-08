async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_full_name = update. # <--- Kode Anda terpotong di sini

    if user_id not in authorized_sales_ids:
        logger.warning(f"Unauthorized user {user_id} ({update.effective_user.full_name}) tried to send a message.")
        await update.message.reply_text("Maaf, Anda tidak memiliki izin untuk menggunakan bot ini.")
        return

    text = update.message.text
    if not text:
        await update.message.reply_text("Pesan kosong tidak valid. Mohon kirimkan nama dan jumlah sales.")
        return

    try:
        parts = text.split(',')
        if len(parts) != 2:
            raise ValueError("Format tidak sesuai. Contoh: Nama Lengkap, 1000000")

        sales_person_name = parts[0].strip()
        sales_amount_str = parts[1].strip()

        # Membersihkan jumlah sales dari karakter non-digit dan mengonversinya ke integer
        # Ini akan menghilangkan titik/koma ribuan dan hanya menyisakan angka
        cleaned_sales_amount = "".join(filter(str.isdigit, sales_amount_str))
        sales_amount = int(cleaned_sales_amount)

        # Mendapatkan waktu WIB (UTC+7)
        wib_timezone = timezone(timedelta(hours=7))
        current_time_wib = datetime.now(wib_timezone)
        
        # Format tanggal dan waktu
        date_str = current_time_wib.strftime("%Y-%m-%d")
        time_str = current_time_wib.strftime("%H:%M:%S")

        # Catat ke Google Sheets
        if worksheet:
            row_data = [date_str, time_str, sales_person_name, sales_amount, user_id, user_full_name]
            worksheet.append_row(row_data)
            await update.message.reply_text(
                f"Check-in berhasil dicatat! 🎉\n"
                f"Nama: *{sales_person_name}*\n"
                f"Sales: *Rp {sales_amount:,.0f}*\n"
                f"Waktu: *{current_time_wib.strftime('%d-%m-%Y %H:%M:%S WIB')}*",
                parse_mode='Markdown'
            )
            logger.info(f"Check-in dari {user_full_name} ({user_id}) dicatat: {sales_person_name}, Rp {sales_amount}")
        else:
            await update.message.reply_text("Maaf, bot tidak dapat terhubung ke Google Sheets. Mohon coba lagi nanti atau hubungi admin.")
            logger.error("Worksheet tidak terinisialisasi. Tidak bisa mencatat data.")

    except ValueError as ve:
        await update.message.reply_text(f"Format input salah: {ve}\nContoh yang benar: *Nama Lengkap, 1000000*", parse_mode='Markdown')
        logger.warning(f"Invalid input from {user_full_name} ({user_id}): {text} - {ve}")
    except Exception as e:
        await update.message.reply_text("Terjadi kesalahan saat mencatat data. Mohon coba lagi.")
        logger.error(f"Error saat handle_message dari {user_full_name} ({user_id}): {e}", exc_info=True)


# --- Register Handlers dan Mulai Bot ---
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("checkin", checkin_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Konfigurasi Flask untuk Webhook ---
app = Flask(__name__)

async def setup_webhook():
    if WEBHOOK_URL:
        # Menunggu hingga bot siap
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}/telegram")
        logger.info(f"Webhook berhasil diatur ke {WEBHOOK_URL}/telegram")
    else:
        logger.error("WEBHOOK_URL tidak tersedia. Webhook tidak dapat diatur.")
        logger.info("Bot akan mencoba menggunakan polling jika tidak ada webhook. (Tidak disarankan untuk Render)")

@app.route('/')
def home():
    return "Bot is running and listening for webhooks.", 200

@app.route('/telegram', methods=['POST'])
async def telegram_webhook():
    if request.method == 'POST':
        update_json = request.get_json()
        if not update_json:
            return jsonify({"status": "error", "message": "No JSON payload"}), 400
        
        # Proses update dari Telegram
        update = Update.de_json(update_json, application.bot)
        try:
            await application.process_update(update)
            return jsonify({"status": "success"}), 200
        except Exception as e:
            logger.error(f"Error processing update: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "method not allowed"}), 405

# Inisialisasi webhook saat aplikasi Flask dimulai
@app.before_request
def before_request():
    # Pastikan ini hanya dijalankan sekali setelah aplikasi dimulai
    # Atau biarkan Render yang menangani pemanggilan otomatis
    pass

# Jalankan setup webhook saat aplikasi pertama kali diakses, jika belum diatur
# Ini akan dijalankan di latar belakang
@app.before_request
def _run_once_on_startup():
    if not hasattr(app, '_webhook_set'):
        app._webhook_set = True
        asyncio.create_task(setup_webhook())
        logger.info("Memulai proses setup webhook...")

if __name__ == '__main__':
    # Ini hanya akan berjalan saat di lingkungan lokal, bukan di Render
    logger.info("Menjalankan bot dalam mode polling (lokal)...")
    application.run_polling(poll_interval=3, timeout=30)
