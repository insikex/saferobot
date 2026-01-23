import os
import re
import asyncio
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
from urllib.parse import urlparse

# ============================================
# KONFIGURASI
# ============================================
BOT_TOKEN = "7389890441:AAGkXEXHedGHYrmXq3Vp5RlT8Y5_kBChL5Q"
OWNER_ID = 6683929810  # GANTI DENGAN USER ID TELEGRAM ANDA
DOWNLOAD_PATH = "./downloads/"
DATABASE_PATH = "./users_database.json"

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ============================================
# DATABASE MANAGEMENT
# ============================================
class UserDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.load_database()
    
    def load_database(self):
        """Load database dari file JSON"""
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = {
                'users': {},
                'stats': {
                    'total_downloads': 0,
                    'video_downloads': 0,
                    'audio_downloads': 0
                }
            }
            self.save_database()
    
    def save_database(self):
        """Simpan database ke file JSON"""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def add_or_update_user(self, user_id, username, first_name, language_code):
        """Tambah atau update user"""
        user_id_str = str(user_id)
        now = datetime.now().isoformat()
        
        if user_id_str not in self.data['users']:
            # User baru
            self.data['users'][user_id_str] = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'language_code': language_code,
                'country': 'Indonesia' if language_code and language_code.lower().startswith('id') else 'International',
                'registered_at': now,
                'last_active': now,
                'download_count': 0,
                'video_downloads': 0,
                'audio_downloads': 0
            }
        else:
            # Update user yang sudah ada
            self.data['users'][user_id_str]['last_active'] = now
            self.data['users'][user_id_str]['username'] = username
            self.data['users'][user_id_str]['first_name'] = first_name
        
        self.save_database()
    
    def increment_download(self, user_id, download_type='video'):
        """Increment download counter"""
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['download_count'] += 1
            self.data['users'][user_id_str]['last_active'] = datetime.now().isoformat()
            
            if download_type == 'video':
                self.data['users'][user_id_str]['video_downloads'] += 1
                self.data['stats']['video_downloads'] += 1
            else:
                self.data['users'][user_id_str]['audio_downloads'] += 1
                self.data['stats']['audio_downloads'] += 1
            
            self.data['stats']['total_downloads'] += 1
            self.save_database()
    
    def get_stats(self):
        """Dapatkan statistik lengkap"""
        total_users = len(self.data['users'])
        
        # Hitung user aktif (aktif dalam 7 hari terakhir)
        now = datetime.now()
        active_threshold = now - timedelta(days=7)
        
        active_users = 0
        inactive_users = 0
        indonesia_users = 0
        international_users = 0
        
        for user_data in self.data['users'].values():
            last_active = datetime.fromisoformat(user_data['last_active'])
            
            if last_active >= active_threshold:
                active_users += 1
            else:
                inactive_users += 1
            
            if user_data['country'] == 'Indonesia':
                indonesia_users += 1
            else:
                international_users += 1
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'indonesia_users': indonesia_users,
            'international_users': international_users,
            'total_downloads': self.data['stats']['total_downloads'],
            'video_downloads': self.data['stats']['video_downloads'],
            'audio_downloads': self.data['stats']['audio_downloads']
        }
    
    def get_top_users(self, limit=10):
        """Dapatkan top users berdasarkan download"""
        sorted_users = sorted(
            self.data['users'].values(),
            key=lambda x: x['download_count'],
            reverse=True
        )
        return sorted_users[:limit]

# Inisialisasi database
db = UserDatabase(DATABASE_PATH)

# ============================================
# MULTI-LANGUAGE SUPPORT
# ============================================
LANGUAGES = {
    'id': {
        'welcome': """
🤖 *Selamat datang di SafeRobot!*

Bot downloader serba bisa untuk:
✅ TikTok
✅ Instagram (Post, Reels, Stories)
✅ Twitter/X
✅ YouTube
✅ Facebook
✅ Pinterest

🔥 *Cara Penggunaan:*
Cukup kirim link dari platform yang didukung, pilih format, dan file akan dikirim ke chat Anda!

Gunakan tombol menu di bawah untuk navigasi 👇
        """,
        'about': """
ℹ️ *Tentang SafeRobot*

@SafeRobot adalah bot Telegram yang memudahkan Anda mendownload konten dari berbagai platform media sosial dengan cepat dan mudah.

*Fitur Utama:*
⚡ Download cepat
🎯 Multi-platform
🔒 Aman & privat
📱 Mudah digunakan

Terima kasih telah menggunakan @SafeRobot! 🙏
        """,
        'invalid_url': "❌ Link tidak valid! Kirim link yang benar.",
        'unsupported': """❌ Platform tidak didukung!

Platform yang didukung:
• TikTok
• Instagram
• Twitter/X
• YouTube
• Facebook
• Pinterest""",
        'detected': "✅ Link dari *{}* terdeteksi!\n\nPilih format download:",
        'downloading': "⏳ Sedang mendownload {}...\nMohon tunggu sebentar...",
        'sending': "📤 Mengirim file...",
        'video_caption': "🎥 *{}*\n\n🔥 Downloaded by SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 Downloaded by SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 Downloaded by SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 Downloaded by SafeRobot",
        'download_failed': """❌ Download gagal!

Error: {}

Tips:
• Pastikan link dapat diakses
• Coba link lain
• Hubungi admin jika masalah berlanjut""",
        'error_occurred': """❌ Terjadi kesalahan!

Error: {}

Silakan coba lagi atau hubungi admin.""",
        'video_button': "🎥 Video (MP4)",
        'audio_button': "🎵 Audio (MP3)",
        'photo_button': "📷 Photo/Image",
        'photo_button': "📷 Foto/Gambar",
        'menu_about': "ℹ️ Tentang",
        'menu_start': "🏠 Menu Utama",
        'video': 'video',
        'audio': 'audio',
        'send_link': "🔎 Kirim link dari platform yang didukung untuk mulai download!"
    },
    'en': {
        'welcome': """
🤖 *Welcome to SafeRobot!*

All-in-one downloader bot for:
✅ TikTok
✅ Instagram (Post, Reels, Stories)
✅ Twitter/X
✅ YouTube
✅ Facebook
✅ Pinterest

🔥 *How to Use:*
Just send a link from supported platforms, choose format, and the file will be sent to your chat!

Use the menu buttons below for navigation 👇
        """,
        'about': """
ℹ️ *About SafeRobot*

@SafeRobot is a Telegram bot that makes it easy to download content from various social media platforms quickly and easily.

*Main Features:*
⚡ Fast download
🎯 Multi-platform
🔒 Safe & private
📱 Easy to use

Thank you for using @SafeRobot! 🙏
        """,
        'invalid_url': "❌ Invalid link! Send a valid link.",
        'unsupported': """❌ Platform not supported!

Supported platforms:
• TikTok
• Instagram
• Twitter/X
• YouTube
• Facebook
• Pinterest""",
        'detected': "✅ Link from *{}* detected!\n\nChoose download format:",
        'downloading': "⏳ Downloading {}...\nPlease wait...",
        'sending': "📤 Sending file...",
        'video_caption': "🎥 *{}*\n\n🔥 Downloaded by SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 Downloaded by SafeRobot",
        'download_failed': """❌ Download failed!

Error: {}

Tips:
• Make sure the link is accessible
• Try another link
• Contact admin if problem persists""",
        'error_occurred': """❌ An error occurred!

Error: {}

Please try again or contact admin.""",
        'video_button': "🎥 Video (MP4)",
        'audio_button': "🎵 Audio (MP3)",
        'menu_about': "ℹ️ About",
        'menu_start': "🏠 Main Menu",
        'video': 'video',
        'audio': 'audio',
        'send_link': "🔎 Send a link from supported platforms to start downloading!"
    }
}

def get_user_language(update: Update) -> str:
    """Deteksi bahasa user dari Telegram settings"""
    try:
        user_lang = update.effective_user.language_code
        if user_lang and user_lang.lower().startswith('id'):
            return 'id'
        return 'en'
    except:
        return 'en' 

def get_text(update: Update, key: str) -> str:
    """Ambil text sesuai bahasa user"""
    lang = get_user_language(update)
    return LANGUAGES[lang].get(key, LANGUAGES['en'].get(key, ''))

def get_main_keyboard(update: Update):
    """Buat keyboard menu utama"""
    lang = get_user_language(update)
    keyboard = [
        [KeyboardButton(LANGUAGES[lang]['menu_about'])]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def is_owner(user_id: int) -> bool:
    """Check apakah user adalah owner"""
    return user_id == OWNER_ID

# ============================================
# SAFEROBOT MAIN CLASS
# ============================================
class SafeRobot:
    def __init__(self):
        self.supported_platforms = {
            'tiktok': ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'],
            'instagram': ['instagram.com', 'instagr.am'],
            'twitter': ['twitter.com', 'x.com', 't.co'],
            'youtube': ['youtube.com', 'youtu.be'],
            'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
            'pinterest': ['pinterest.com', 'pin.it']
        }
    
    def detect_platform(self, url):
        """Deteksi platform dari URL"""
        domain = urlparse(url).netloc.lower()
        for platform, domains in self.supported_platforms.items():
            if any(d in domain for d in domains):
                return platform
        return None
    
    async def download_media(self, url, format_type='video'):
        """Download media dari berbagai platform"""
        try:
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_PATH}%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
            }
            
            if format_type == 'audio':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            elif format_type == 'photo':
                # Untuk foto, ambil thumbnail terbaik atau gambar asli
                ydl_opts.update({
                    'format': 'best',
                    'writethumbnail': True,
                    'skip_download': False,
                })
            else:
                ydl_opts.update({
                    'format': 'best[ext=mp4]/best',
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if format_type == 'audio':
                    filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                elif format_type == 'photo':
                    # Cari file gambar yang didownload
                    base_filename = ydl.prepare_filename(info)
                    
                    # Cek berbagai ekstensi gambar
                    possible_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                    filename = None
                    
                    for ext in possible_extensions:
                        test_file = base_filename.rsplit('.', 1)[0] + ext
                        if os.path.exists(test_file):
                            filename = test_file
                            break
                    
                    # Jika tidak ada file gambar, gunakan file asli
                    if not filename:
                        filename = base_filename
                else:
                    filename = ydl.prepare_filename(info)
                
                return {
                    'success': True,
                    'filepath': filename,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0)
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

bot = SafeRobot()

# ============================================
# TELEGRAM BOT HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    user = update.effective_user
    
    # Simpan/update user ke database
    db.add_or_update_user(
        user.id,
        user.username,
        user.first_name,
        user.language_code
    )
    
    welcome_msg = get_text(update, 'welcome')
    keyboard = get_main_keyboard(update)
    await update.message.reply_text(
        welcome_msg, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /stats - Owner only"""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("❌ Perintah ini hanya untuk owner bot!")
        return
    
    stats = db.get_stats()
    top_users = db.get_top_users(5)
    
    stats_msg = f"""
📊 *SAFEROBOT STATISTICS*
━━━━━━━━━━━━━━━━━━━━

👥 *USER STATISTICS*
├ Total Users: `{stats['total_users']}`
├ Active Users (7d): `{stats['active_users']}`
├ Inactive Users: `{stats['inactive_users']}`
├ 🇮🇩 Indonesia: `{stats['indonesia_users']}`
└ 🌍 International: `{stats['international_users']}`

📥 *DOWNLOAD STATISTICS*
├ Total Downloads: `{stats['total_downloads']}`
├ 🎥 Video: `{stats['video_downloads']}`
└ 🎵 Audio: `{stats['audio_downloads']}`

🏆 *TOP 5 USERS*
"""
    
    for i, user in enumerate(top_users, 1):
        username = f"@{user['username']}" if user['username'] else user['first_name']
        stats_msg += f"{i}. {username} - `{user['download_count']}` downloads\n"
    
    stats_msg += "\n━━━━━━━━━━━━━━━━━━━━"
    
    # Keyboard untuk refresh
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_msg,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /broadcast - Owner only"""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("❌ Perintah ini hanya untuk owner bot!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 *Format Broadcast*\n\n"
            "Gunakan: `/broadcast <pesan>`\n\n"
            "Contoh: `/broadcast Halo semua! Bot sedang maintenance.`",
            parse_mode='Markdown'
        )
        return
    
    message = ' '.join(context.args)
    users = db.data['users']
    
    success = 0
    failed = 0
    
    status_msg = await update.message.reply_text(
        f"📡 Mengirim broadcast ke {len(users)} users..."
    )
    
    for user_id_str in users.keys():
        try:
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=f"📢 *BROADCAST MESSAGE*\n\n{message}",
                parse_mode='Markdown'
            )
            success += 1
            await asyncio.sleep(0.05)  # Delay untuk menghindari rate limit
        except Exception as e:
            failed += 1
            print(f"Failed to send to {user_id_str}: {e}")
    
    await status_msg.edit_text(
        f"✅ Broadcast selesai!\n\n"
        f"✅ Berhasil: {success}\n"
        f"❌ Gagal: {failed}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk semua pesan text"""
    user = update.effective_user
    text = update.message.text.strip()
    lang = get_user_language(update)
    
    # Update user activity
    db.add_or_update_user(
        user.id,
        user.username,
        user.first_name,
        user.language_code
    )
    
    # Handle menu buttons
    if text in [LANGUAGES['id']['menu_about'], LANGUAGES['en']['menu_about']]:
        about_msg = get_text(update, 'about')
        keyboard = get_main_keyboard(update)
        await update.message.reply_text(
            about_msg, 
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return
    
    elif text in [LANGUAGES['id']['menu_start'], LANGUAGES['en']['menu_start']]:
        await start(update, context)
        return
    
    # Validate URL
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    
    if not url_pattern.match(text):
        await update.message.reply_text(
            get_text(update, 'send_link'),
            reply_markup=get_main_keyboard(update)
        )
        return
    
    url = text
    platform = bot.detect_platform(url)
    
    if not platform:
        await update.message.reply_text(
            get_text(update, 'unsupported'),
            reply_markup=get_main_keyboard(update)
        )
        return
    
    # Store URL
    url_id = str(hash(url))[-8:]
    context.user_data[url_id] = url
    
    # Create download buttons
    keyboard = [
        [
            InlineKeyboardButton(
                LANGUAGES[lang]['video_button'], 
                callback_data=f"v|{url_id}|{lang}"
            ),
            InlineKeyboardButton(
                LANGUAGES[lang]['audio_button'], 
                callback_data=f"a|{url_id}|{lang}"
            )
        ]
    ]
    
    # Tambahkan button foto untuk Instagram, TikTok, dan Pinterest
    if platform in ['instagram', 'tiktok', 'pinterest']:
        keyboard.append([
            InlineKeyboardButton(
                LANGUAGES[lang]['photo_button'], 
                callback_data=f"p|{url_id}|{lang}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    detected_msg = get_text(update, 'detected').format(platform.upper())
    await update.message.reply_text(
        detected_msg,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk button callback"""
    query = update.callback_query
    await query.answer()
    
    # Handle refresh stats
    if query.data == "refresh_stats":
        user_id = query.from_user.id
        
        if not is_owner(user_id):
            await query.answer("❌ Hanya owner yang bisa refresh stats!", show_alert=True)
            return
        
        stats = db.get_stats()
        top_users = db.get_top_users(5)
        
        stats_msg = f"""
📊 *SAFEROBOT STATISTICS*
━━━━━━━━━━━━━━━━━━━━

👥 *USER STATISTICS*
├ Total Users: `{stats['total_users']}`
├ Active Users (7d): `{stats['active_users']}`
├ Inactive Users: `{stats['inactive_users']}`
├ 🇮🇩 Indonesia: `{stats['indonesia_users']}`
└ 🌍 International: `{stats['international_users']}`

📥 *DOWNLOAD STATISTICS*
├ Total Downloads: `{stats['total_downloads']}`
├ 🎥 Video: `{stats['video_downloads']}`
└ 🎵 Audio: `{stats['audio_downloads']}`

🏆 *TOP 5 USERS*
"""
        
        for i, user in enumerate(top_users, 1):
            username = f"@{user['username']}" if user['username'] else user['first_name']
            stats_msg += f"{i}. {username} - `{user['download_count']}` downloads\n"
        
        stats_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n🕐 Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_msg,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    data = query.data.split('|')
    format_code = data[0]
    url_id = data[1]
    lang = data[2] if len(data) > 2 else 'en'
    
    url = context.user_data.get(url_id)
    
    if not url:
        await query.message.reply_text(
            "❌ Link expired! Please send the link again." if lang == 'en' else "❌ Link kadaluarsa! Kirim ulang link-nya."
        )
        return
    
    # Tentukan format type
    if format_code == 'v':
        format_type = 'video'
    elif format_code == 'a':
        format_type = 'audio'
    elif format_code == 'p':
        format_type = 'photo'
    else:
        format_type = 'video'
    
    downloading_msg = LANGUAGES[lang]['downloading'].format(
        'foto' if format_type == 'photo' else LANGUAGES[lang][format_type]
    )
    status_msg = await query.message.reply_text(downloading_msg)
    
    try:
        result = await bot.download_media(url, format_type)
        
        if result['success']:
            await status_msg.edit_text(LANGUAGES[lang]['sending'])
            
            filepath = result['filepath']
            
            # Cek ukuran file
            file_size = os.path.getsize(filepath)
            max_size = 50 * 1024 * 1024  # 50MB limit Telegram
            
            # Kirim berdasarkan format type
            if format_type == 'photo':
                # Kirim sebagai foto
                caption = LANGUAGES[lang]['photo_caption'].format(result['title'])
                try:
                    with open(filepath, 'rb') as photo:
                        await query.message.reply_photo(
                            photo=photo,
                            caption=caption,
                            parse_mode='Markdown'
                        )
                except Exception as photo_error:
                    print(f"Photo send failed, trying as document: {photo_error}")
                    with open(filepath, 'rb') as document:
                        await query.message.reply_document(
                            document=document,
                            caption=caption,
                            parse_mode='Markdown'
                        )
            
            elif format_type == 'audio':
                caption = LANGUAGES[lang]['audio_caption'].format(result['title'])
                with open(filepath, 'rb') as audio:
                    await query.message.reply_audio(
                        audio=audio,
                        title=result['title'],
                        duration=int(result['duration']) if result['duration'] else None,
                        caption=caption,
                        parse_mode='Markdown'
                    )
            else:
                caption = LANGUAGES[lang]['video_caption'].format(result['title'])
                
                if file_size > max_size:
                    with open(filepath, 'rb') as document:
                        await query.message.reply_document(
                            document=document,
                            caption=caption + "\n\n⚠️ File terlalu besar untuk streaming, dikirim sebagai document.",
                            parse_mode='Markdown'
                        )
                else:
                    try:
                        with open(filepath, 'rb') as video:
                            await query.message.reply_video(
                                video=video,
                                width=1280,
                                height=720,
                                duration=int(result['duration']) if result['duration'] else None,
                                caption=caption,
                                parse_mode='Markdown',
                                supports_streaming=True
                            )
                    except Exception as video_error:
                        print(f"Video send failed, trying as document: {video_error}")
                        with open(filepath, 'rb') as document:
                            await query.message.reply_document(
                                document=document,
                                caption=caption + "\n\n📎 Dikirim sebagai document.",
                                parse_mode='Markdown'
                            )
            
            # Increment download counter
            db.increment_download(query.from_user.id, format_type)
            
            await status_msg.delete()
            
            # Cleanup
            if os.path.exists(filepath):
                os.remove(filepath)
            
            if url_id in context.user_data:
                del context.user_data[url_id]
        
        else:
            error_msg = LANGUAGES[lang]['download_failed'].format(result['error'])
            await status_msg.edit_text(error_msg)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = LANGUAGES[lang]['error_occurred'].format(str(e))
        await status_msg.edit_text(error_msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk error"""
    print(f"Error: {context.error}")
    import traceback
    traceback.print_exc()

def main():
    """Fungsi utama untuk menjalankan bot"""
    print("🤖 SafeRobot v3.0 Starting...")
    print("🌐 Multi-language support: ID/EN")
    print("🎨 Button menu interface enabled")
    print("📊 Owner stats & database enabled")
    print(f"👑 Owner ID: {OWNER_ID}")
    print("✅ Supported platforms: TikTok, Instagram, Twitter/X, YouTube, Facebook, Pinterest")
    print(f"💾 Database: {DATABASE_PATH}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Message and callback handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    print("✅ SafeRobot is running!")
    print("📝 Owner commands:")
    print("   /stats - Lihat statistik pengguna")
    print("   /broadcast <pesan> - Kirim pesan ke semua user")
    print("\nPress Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
