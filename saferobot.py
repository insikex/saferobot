import logging
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters
from telegram.constants import ParseMode
import asyncio
from datetime import datetime, timedelta
import json
import os

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File untuk menyimpan konfigurasi grup
CONFIG_FILE = 'group_configs.json'

# Struktur data untuk menyimpan konfigurasi grup
group_configs = {}

def load_configs():
    """Load konfigurasi dari file"""
    global group_configs
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            group_configs = json.load(f)
    else:
        group_configs = {}

def save_configs():
    """Simpan konfigurasi ke file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(group_configs, f, indent=2)

def get_group_config(chat_id):
    """Dapatkan konfigurasi grup, buat default jika belum ada"""
    chat_id_str = str(chat_id)
    if chat_id_str not in group_configs:
        group_configs[chat_id_str] = {
            'welcome_enabled': True,
            'antiflood_enabled': True,
            'antiflood_limit': 5,
            'antiflood_time': 10,
            'antilink_enabled': False,
            'antispam_enabled': True,
            'verify_new_members': True,
            'warn_limit': 3,
            'user_warnings': {},
            'user_messages': {}
        }
        save_configs()
    return group_configs[chat_id_str]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    welcome_text = """
👮‍♂️ **Safeguard Bot - Pelindung Grup Telegram**

Halo! Saya adalah bot pelindung grup yang akan membantu menjaga keamanan grup Anda.

**Fitur Utama:**
🔹 Verifikasi member baru
🔹 Anti-flood (spam pesan)
🔹 Anti-link
🔹 Sistem peringatan (warn)
🔹 Pesan selamat datang
🔹 Auto-kick spam/bot

**Perintah Admin:**
/settings - Pengaturan bot
/warn - Beri peringatan ke user
/unwarn - Hapus peringatan
/kick - Kick user dari grup
/ban - Ban user dari grup
/mute - Bisu user
/unmute - Unbisu user

**Perintah Umum:**
/help - Bantuan
/rules - Lihat aturan grup

Tambahkan saya ke grup dan jadikan admin untuk mulai melindungi grup Anda!
    """
    
    if update.message.chat.type == 'private':
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Bot aktif! Gunakan /help untuk melihat perintah.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /help"""
    help_text = """
📖 **Bantuan Safeguard Bot**

**Perintah Admin:**
/settings - Buka menu pengaturan
/warn @user - Beri peringatan
/unwarn @user - Hapus peringatan
/kick @user - Kick dari grup
/ban @user - Ban dari grup
/mute @user - Bisu user
/unmute @user - Unbisu user

**Pengaturan yang Tersedia:**
• Welcome Message (Pesan selamat datang)
• Anti-Flood (Batasi spam pesan)
• Anti-Link (Blokir link)
• Member Verification (Verifikasi member baru)
• Warn System (Sistem peringatan)
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /settings"""
    if update.message.chat.type == 'private':
        await update.message.reply_text("Perintah ini hanya bisa digunakan di grup!")
        return
    
    # Cek apakah user adalah admin
    user = await update.effective_chat.get_member(update.effective_user.id)
    if user.status not in ['creator', 'administrator']:
        await update.message.reply_text("Hanya admin yang bisa mengubah pengaturan!")
        return
    
    config = get_group_config(update.effective_chat.id)
    
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if config['welcome_enabled'] else '❌'} Welcome Message",
            callback_data='toggle_welcome'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['antiflood_enabled'] else '❌'} Anti-Flood",
            callback_data='toggle_antiflood'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['antilink_enabled'] else '❌'} Anti-Link",
            callback_data='toggle_antilink'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['verify_new_members'] else '❌'} Verify New Members",
            callback_data='toggle_verify'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['antispam_enabled'] else '❌'} Anti-Spam",
            callback_data='toggle_antispam'
        )],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ **Pengaturan Grup**\n\nKlik tombol untuk mengaktifkan/menonaktifkan fitur:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk button callback"""
    query = update.callback_query
    await query.answer()
    
    # Cek apakah user adalah admin
    user = await update.effective_chat.get_member(update.effective_user.id)
    if user.status not in ['creator', 'administrator']:
        await query.answer("Hanya admin yang bisa mengubah pengaturan!", show_alert=True)
        return
    
    config = get_group_config(update.effective_chat.id)
    
    if query.data == 'toggle_welcome':
        config['welcome_enabled'] = not config['welcome_enabled']
    elif query.data == 'toggle_antiflood':
        config['antiflood_enabled'] = not config['antiflood_enabled']
    elif query.data == 'toggle_antilink':
        config['antilink_enabled'] = not config['antilink_enabled']
    elif query.data == 'toggle_verify':
        config['verify_new_members'] = not config['verify_new_members']
    elif query.data == 'toggle_antispam':
        config['antispam_enabled'] = not config['antispam_enabled']
    elif query.data.startswith('verify_'):
        user_id = int(query.data.split('_')[1])
        if query.from_user.id == user_id:
            # User berhasil verifikasi
            try:
                await context.bot.restrict_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=user_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True
                    )
                )
                await query.edit_message_text("✅ Verifikasi berhasil! Selamat datang di grup.")
            except Exception as e:
                logger.error(f"Error verifying user: {e}")
        return
    
    save_configs()
    
    # Update keyboard
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if config['welcome_enabled'] else '❌'} Welcome Message",
            callback_data='toggle_welcome'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['antiflood_enabled'] else '❌'} Anti-Flood",
            callback_data='toggle_antiflood'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['antilink_enabled'] else '❌'} Anti-Link",
            callback_data='toggle_antilink'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['verify_new_members'] else '❌'} Verify New Members",
            callback_data='toggle_verify'
        )],
        [InlineKeyboardButton(
            f"{'✅' if config['antispam_enabled'] else '❌'} Anti-Spam",
            callback_data='toggle_antispam'
        )],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "⚙️ **Pengaturan Grup**\n\nKlik tombol untuk mengaktifkan/menonaktifkan fitur:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk member baru"""
    config = get_group_config(update.effective_chat.id)
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
            
        # Verifikasi member baru
        if config['verify_new_members']:
            try:
                # Mute user sampai verifikasi
                await context.bot.restrict_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=member.id,
                    permissions=ChatPermissions(can_send_messages=False)
                )
                
                keyboard = [[InlineKeyboardButton(
                    "✅ Saya Manusia",
                    callback_data=f'verify_{member.id}'
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"👋 Selamat datang {member.mention_html()}!\n\n"
                    f"Silakan klik tombol di bawah untuk verifikasi bahwa Anda bukan bot.\n"
                    f"Anda memiliki waktu 2 menit.",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                
                # Auto kick jika tidak verifikasi dalam 2 menit
                context.job_queue.run_once(
                    kick_unverified,
                    120,
                    data={'chat_id': update.effective_chat.id, 'user_id': member.id}
                )
            except Exception as e:
                logger.error(f"Error muting new member: {e}")
        
        # Welcome message
        elif config['welcome_enabled']:
            await update.message.reply_text(
                f"👋 Selamat datang {member.mention_html()} di grup!\n"
                f"Silakan baca aturan grup dan nikmati diskusi.",
                parse_mode=ParseMode.HTML
            )

async def kick_unverified(context: ContextTypes.DEFAULT_TYPE):
    """Kick user yang tidak verifikasi"""
    chat_id = context.job.data['chat_id']
    user_id = context.job.data['user_id']
    
    try:
        # Cek apakah user sudah bisa kirim pesan (sudah verifikasi)
        member = await context.bot.get_chat_member(chat_id, user_id)
        if not member.can_send_messages:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)  # Unban agar bisa join lagi
            await context.bot.send_message(
                chat_id,
                "❌ User dikick karena tidak melakukan verifikasi."
            )
    except Exception as e:
        logger.error(f"Error kicking unverified user: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk semua pesan"""
    if not update.message or not update.message.text:
        return
    
    config = get_group_config(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Anti-flood
    if config['antiflood_enabled']:
        if 'user_messages' not in config:
            config['user_messages'] = {}
        
        if user_id not in config['user_messages']:
            config['user_messages'][user_id] = []
        
        now = datetime.now().timestamp()
        config['user_messages'][user_id].append(now)
        
        # Hapus pesan lama
        config['user_messages'][user_id] = [
            ts for ts in config['user_messages'][user_id]
            if now - ts < config['antiflood_time']
        ]
        
        if len(config['user_messages'][user_id]) > config['antiflood_limit']:
            try:
                await update.message.delete()
                await warn_user(update, context, "Spam/Flood detected")
            except Exception as e:
                logger.error(f"Error deleting flood message: {e}")
    
    # Anti-link
    if config['antilink_enabled']:
        if any(word in update.message.text.lower() for word in ['http://', 'https://', 't.me/', 'telegram.me/']):
            user = await update.effective_chat.get_member(update.effective_user.id)
            if user.status not in ['creator', 'administrator']:
                try:
                    await update.message.delete()
                    await update.message.reply_text(
                        f"⚠️ {update.effective_user.mention_html()}, link tidak diizinkan!",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Error deleting link: {e}")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, reason="No reason"):
    """Beri peringatan ke user"""
    config = get_group_config(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    
    if 'user_warnings' not in config:
        config['user_warnings'] = {}
    
    if user_id not in config['user_warnings']:
        config['user_warnings'][user_id] = 0
    
    config['user_warnings'][user_id] += 1
    warns = config['user_warnings'][user_id]
    
    save_configs()
    
    if warns >= config['warn_limit']:
        # Kick user
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, int(user_id))
            await context.bot.unban_chat_member(update.effective_chat.id, int(user_id))
            await update.message.reply_text(
                f"❌ {update.effective_user.mention_html()} telah di-kick karena mencapai batas peringatan!\n"
                f"Alasan: {reason}",
                parse_mode=ParseMode.HTML
            )
            config['user_warnings'][user_id] = 0
            save_configs()
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
    else:
        await update.message.reply_text(
            f"⚠️ {update.effective_user.mention_html()} mendapat peringatan [{warns}/{config['warn_limit']}]\n"
            f"Alasan: {reason}",
            parse_mode=ParseMode.HTML
        )

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command untuk memberi peringatan"""
    user = await update.effective_chat.get_member(update.effective_user.id)
    if user.status not in ['creator', 'administrator']:
        await update.message.reply_text("Hanya admin yang bisa memberi peringatan!")
        return
    
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        reason = ' '.join(context.args) if context.args else "No reason"
        
        config = get_group_config(update.effective_chat.id)
        user_id = str(target_user.id)
        
        if 'user_warnings' not in config:
            config['user_warnings'] = {}
        
        if user_id not in config['user_warnings']:
            config['user_warnings'][user_id] = 0
        
        config['user_warnings'][user_id] += 1
        warns = config['user_warnings'][user_id]
        save_configs()
        
        if warns >= config['warn_limit']:
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
                await context.bot.unban_chat_member(update.effective_chat.id, target_user.id)
                await update.message.reply_text(
                    f"❌ {target_user.mention_html()} telah di-kick!\n"
                    f"Alasan: {reason}",
                    parse_mode=ParseMode.HTML
                )
                config['user_warnings'][user_id] = 0
                save_configs()
            except Exception as e:
                logger.error(f"Error kicking user: {e}")
        else:
            await update.message.reply_text(
                f"⚠️ {target_user.mention_html()} mendapat peringatan [{warns}/{config['warn_limit']}]\n"
                f"Alasan: {reason}",
                parse_mode=ParseMode.HTML
            )
    else:
        await update.message.reply_text("Reply ke pesan user yang ingin diberi peringatan!")

def main():
    """Fungsi utama untuk menjalankan bot"""
    # Ganti dengan token bot Anda
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    # Load konfigurasi
    load_configs()
    
    # Buat aplikasi
    application = Application.builder().token(TOKEN).build()
    
    # Handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("warn", warn_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Jalankan bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
