import os
import re
import asyncio
import json
import requests
import subprocess
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
from urllib.parse import urlparse, parse_qs, urljoin
from bs4 import BeautifulSoup
import hashlib

# ============================================
# KONFIGURASI
# ============================================
BOT_TOKEN = "7389890441:AAGkXEXHedGHYrmXq3Vp5RlT8Y5_kBChL5Q"
OWNER_ID = 6683929810  # GANTI DENGAN USER ID TELEGRAM ANDA
DOWNLOAD_PATH = "./downloads/"
DATABASE_PATH = "./users_database.json"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit Telegram

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

📱 *SOSIAL MEDIA:*
✅ TikTok
✅ Instagram (Post, Reels, Stories)
✅ Twitter/X
✅ YouTube
✅ Facebook
✅ Pinterest

🎬 *STREAMING/HOSTING VIDEO:*
✅ DoodStream (dood.to, dood-hd.com, dll)
✅ TeraBox (terabox.com, 1024terabox.com)
✅ Videy (vidoy.com, videypro.live, dll)
✅ Videq (videq.io, videq.co, dll)
✅ LuluStream (lulustream.com, lulu.st)
✅ VidCloud, StreamTape, MixDrop
✅ Dan 50+ platform streaming lainnya!

🔥 *Cara Penggunaan:*
Cukup kirim link dari platform yang didukung, pilih format, dan file akan dikirim ke chat Anda!

Gunakan /platforms untuk melihat daftar lengkap platform.

Gunakan tombol menu di bawah untuk navigasi 👇
        """,
        'about': """
ℹ️ *Tentang SafeRobot*

@SafeRobot adalah bot Telegram yang memudahkan Anda mendownload konten dari berbagai platform media sosial dan streaming video dengan cepat dan mudah.

*Fitur Utama:*
⚡ Download cepat
🎯 Multi-platform (60+ platform)
🔒 Aman & privat
📱 Mudah digunakan
🎬 Support streaming platforms
📥 Download langsung ke Telegram

Terima kasih telah menggunakan @SafeRobot! 🙏
        """,
        'invalid_url': "❌ Link tidak valid! Kirim link yang benar.",
        'unsupported': """❌ Platform tidak didukung!

Platform yang didukung:
📱 *Sosial Media:*
• TikTok, Instagram, Twitter/X
• YouTube, Facebook, Pinterest

🎬 *Streaming Video:*
• DoodStream, TeraBox, Videy
• Videq, LuluStream, VidCloud
• Dan banyak lainnya...

Ketik /platforms untuk daftar lengkap.""",
        'detected': "✅ Link dari *{}* terdeteksi!\n\nPilih format download:",
        'detected_streaming': "🎬 Link streaming dari *{}* terdeteksi!\n\n⚠️ Platform streaming mungkin memerlukan waktu lebih lama.\n\nPilih format download:",
        'downloading': "⏳ Sedang mendownload {}...\nMohon tunggu sebentar...",
        'downloading_streaming': "⏳ Mengekstrak video dari streaming...\n\n📡 Platform: *{}*\n⌛ Proses ini mungkin memakan waktu 1-2 menit.\n\nMohon tunggu...",
        'sending': "📤 Mengirim file...",
        'video_caption': "🎥 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'download_failed': """❌ Download gagal!

Error: {}

Tips:
• Pastikan link dapat diakses
• Coba link lain
• Beberapa streaming platform memiliki proteksi
• Hubungi admin jika masalah berlanjut""",
        'error_occurred': """❌ Terjadi kesalahan!

Error: {}

Silakan coba lagi atau hubungi admin.""",
        'video_button': "🎥 Video (MP4)",
        'video_hd_button': "🎥 Video HD",
        'video_sd_button': "📹 Video SD",
        'audio_button': "🎵 Audio (MP3)",
        'photo_button': "📷 Foto/Gambar",
        'direct_download_button': "⬇️ Download Langsung",
        'menu_about': "ℹ️ Tentang",
        'menu_platforms': "📋 Platform",
        'menu_start': "🏠 Menu Utama",
        'video': 'video',
        'audio': 'audio',
        'send_link': "🔎 Kirim link dari platform yang didukung untuk mulai download!",
        'platforms_list': """📋 *DAFTAR PLATFORM YANG DIDUKUNG*

📱 *SOSIAL MEDIA:*
├ TikTok (tiktok.com, vm.tiktok.com)
├ Instagram (instagram.com)
├ Twitter/X (twitter.com, x.com)
├ YouTube (youtube.com, youtu.be)
├ Facebook (facebook.com, fb.watch)
└ Pinterest (pinterest.com, pin.it)

🎬 *STREAMING PLATFORMS:*

*DoodStream Family:*
├ doodstream.com, dood.to, dood.watch
├ dood-hd.com, dood.wf, dood.cx
└ dood.sh, dood.so, dood.ws

*TeraBox Family:*
├ terabox.com, 1024terabox.com
├ teraboxapp.com, 4funbox.com
└ mirrobox.com, nephobox.com

*Videy/Videq Family:*
├ vidoy.com, videypro.live, videy.la
├ videq.io, videq.co, videq.me
├ vide-q.com, vide0.me, vide6.com
└ Dan 40+ domain lainnya...

*LuluStream:*
├ lulustream.com, lulu.st
└ lixstream.com

*Lainnya:*
├ VidCloud, StreamTape, MixDrop
├ Upstream, MP4Upload, Vidoza
└ Dan masih banyak lagi!

💡 Kirim link untuk mulai download!"""
    },
    'en': {
        'welcome': """
🤖 *Welcome to SafeRobot!*

All-in-one downloader bot for:

📱 *SOCIAL MEDIA:*
✅ TikTok
✅ Instagram (Post, Reels, Stories)
✅ Twitter/X
✅ YouTube
✅ Facebook
✅ Pinterest

🎬 *VIDEO STREAMING/HOSTING:*
✅ DoodStream (dood.to, dood-hd.com, etc)
✅ TeraBox (terabox.com, 1024terabox.com)
✅ Videy (vidoy.com, videypro.live, etc)
✅ Videq (videq.io, videq.co, etc)
✅ LuluStream (lulustream.com, lulu.st)
✅ VidCloud, StreamTape, MixDrop
✅ And 50+ more streaming platforms!

🔥 *How to Use:*
Just send a link from supported platforms, choose format, and the file will be sent to your chat!

Use /platforms to see full platform list.

Use the menu buttons below for navigation 👇
        """,
        'about': """
ℹ️ *About SafeRobot*

@SafeRobot is a Telegram bot that makes it easy to download content from various social media and video streaming platforms quickly and easily.

*Main Features:*
⚡ Fast download
🎯 Multi-platform (60+ platforms)
🔒 Safe & private
📱 Easy to use
🎬 Streaming platform support
📥 Direct download to Telegram

Thank you for using @SafeRobot! 🙏
        """,
        'invalid_url': "❌ Invalid link! Send a valid link.",
        'unsupported': """❌ Platform not supported!

Supported platforms:
📱 *Social Media:*
• TikTok, Instagram, Twitter/X
• YouTube, Facebook, Pinterest

🎬 *Video Streaming:*
• DoodStream, TeraBox, Videy
• Videq, LuluStream, VidCloud
• And many more...

Type /platforms for full list.""",
        'detected': "✅ Link from *{}* detected!\n\nChoose download format:",
        'detected_streaming': "🎬 Streaming link from *{}* detected!\n\n⚠️ Streaming platforms may take longer to process.\n\nChoose download format:",
        'downloading': "⏳ Downloading {}...\nPlease wait...",
        'downloading_streaming': "⏳ Extracting video from streaming...\n\n📡 Platform: *{}*\n⌛ This process may take 1-2 minutes.\n\nPlease wait...",
        'sending': "📤 Sending file...",
        'video_caption': "🎥 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'download_failed': """❌ Download failed!

Error: {}

Tips:
• Make sure the link is accessible
• Try another link
• Some streaming platforms have protection
• Contact admin if problem persists""",
        'error_occurred': """❌ An error occurred!

Error: {}

Please try again or contact admin.""",
        'video_button': "🎥 Video (MP4)",
        'video_hd_button': "🎥 Video HD",
        'video_sd_button': "📹 Video SD",
        'audio_button': "🎵 Audio (MP3)",
        'photo_button': "📷 Photo/Image",
        'direct_download_button': "⬇️ Direct Download",
        'menu_about': "ℹ️ About",
        'menu_platforms': "📋 Platforms",
        'menu_start': "🏠 Main Menu",
        'video': 'video',
        'audio': 'audio',
        'send_link': "🔎 Send a link from supported platforms to start downloading!",
        'platforms_list': """📋 *SUPPORTED PLATFORMS LIST*

📱 *SOCIAL MEDIA:*
├ TikTok (tiktok.com, vm.tiktok.com)
├ Instagram (instagram.com)
├ Twitter/X (twitter.com, x.com)
├ YouTube (youtube.com, youtu.be)
├ Facebook (facebook.com, fb.watch)
└ Pinterest (pinterest.com, pin.it)

🎬 *STREAMING PLATFORMS:*

*DoodStream Family:*
├ doodstream.com, dood.to, dood.watch
├ dood-hd.com, dood.wf, dood.cx
└ dood.sh, dood.so, dood.ws

*TeraBox Family:*
├ terabox.com, 1024terabox.com
├ teraboxapp.com, 4funbox.com
└ mirrobox.com, nephobox.com

*Videy/Videq Family:*
├ vidoy.com, videypro.live, videy.la
├ videq.io, videq.co, videq.me
├ vide-q.com, vide0.me, vide6.com
└ And 40+ more domains...

*LuluStream:*
├ lulustream.com, lulu.st
└ lixstream.com

*Others:*
├ VidCloud, StreamTape, MixDrop
├ Upstream, MP4Upload, Vidoza
└ And many more!

💡 Send a link to start downloading!"""
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
        [
            KeyboardButton(LANGUAGES[lang]['menu_platforms']),
            KeyboardButton(LANGUAGES[lang]['menu_about'])
        ]
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
        # Platform sosial media utama
        self.social_platforms = {
            'tiktok': ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'],
            'instagram': ['instagram.com', 'instagr.am'],
            'twitter': ['twitter.com', 'x.com', 't.co'],
            'youtube': ['youtube.com', 'youtu.be'],
            'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
            'pinterest': ['pinterest.com', 'pin.it']
        }
        
        # Platform streaming/hosting video yang didukung
        self.streaming_platforms = {
            'doodstream': [
                'doodstream.com', 'dood.to', 'dood.watch', 'dood.pm', 
                'dood.wf', 'dood.cx', 'dood.sh', 'dood.so', 
                'dood.ws', 'dood.yt', 'dood.re', 'dood-hd.com',
                'dood.la', 'ds2play.com', 'd0o0d.com', 'do0od.com'
            ],
            'terabox': [
                'terabox.com', '1024terabox.com', 'teraboxapp.com',
                'terabox.fun', 'terabox.link', '4funbox.com',
                'mirrobox.com', 'nephobox.com', '1024tera.com'
            ],
            'videy': [
                'vidoy.com', 'vidoy.cam', 'videypro.live', 'videyaio.com',
                'videy.co', 'videy.la', 'vide-q.com', 'vide0.me',
                'vide6.com', 'videw.online', 'vidqy.co', 'vidbre.org'
            ],
            'videq': [
                'videq.io', 'videq.pw', 'videqs.com', 'videq.info',
                'videq.tel', 'videq.wtf', 'videq.app', 'videq.video',
                'videq.my', 'videq.boo', 'videq.cloud', 'videq.net',
                'videq.co', 'videq.me', 'videq.org', 'videq.pro',
                'videq.xyz', 'cdnvideq.net', 'avdeq.ink'
            ],
            'lulu': [
                'lulustream.com', 'lulu.st', 'lixstream.com'
            ],
            'twimg': [
                'videotwimg.app', 'video.twlmg.org', 'cdn.twlmg.org',
                'twlmg.org', 'tvidey.tv', 'cdn.tvidey.tv', 
                'tvimg.net', 'video.tvimg.net'
            ],
            'vidcloud': [
                'vidcloudmv.org', 'vidcloud.co', 'vidcloud9.com'
            ],
            'vidpy': [
                'cdn.vidpy.co', 'cdn.vidpy.cc', 'vidpy.co', 'vidpy.cc'
            ],
            'other_streaming': [
                'upl.ad', 'vide.cx', 'vid.boats', 'vid.promo',
                'video.twing.plus', 'myvidplay.com', 'streamtape.com',
                'mixdrop.to', 'mixdrop.co', 'upstream.to', 'mp4upload.com',
                'streamlare.com', 'fembed.com', 'femax20.com', 'fcdn.stream',
                'embedsito.com', 'embedstream.me', 'vidoza.net', 'vidlox.me'
            ]
        }
        
        # Gabungkan semua platform
        self.supported_platforms = {**self.social_platforms}
        for platform, domains in self.streaming_platforms.items():
            self.supported_platforms[platform] = domains
    
    def detect_platform(self, url):
        """Deteksi platform dari URL"""
        domain = urlparse(url).netloc.lower().replace('www.', '')
        
        # Cek sosial media dulu
        for platform, domains in self.social_platforms.items():
            if any(d in domain for d in domains):
                return platform
        
        # Cek streaming platforms
        for platform, domains in self.streaming_platforms.items():
            if any(d in domain for d in domains):
                return platform
        
        # Jika tidak dikenali tapi masih URL valid, coba sebagai generic
        if domain:
            return 'generic'
        
        return None
    
    def is_streaming_platform(self, platform):
        """Cek apakah platform adalah streaming platform"""
        return platform in self.streaming_platforms or platform == 'generic'
    
    def get_platform_category(self, platform):
        """Dapatkan kategori platform"""
        if platform in self.social_platforms:
            return 'social'
        elif platform in self.streaming_platforms or platform == 'generic':
            return 'streaming'
        return 'unknown'
    
    async def extract_direct_video_url(self, url):
        """Ekstrak URL video langsung dari halaman streaming"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Referer': url
            }
            
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            html = response.text
            
            # Parse dengan BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Cari video URL dari berbagai sumber
            video_urls = []
            
            # 1. Cari tag video langsung
            video_tags = soup.find_all('video')
            for video in video_tags:
                if video.get('src'):
                    video_urls.append(video.get('src'))
                sources = video.find_all('source')
                for source in sources:
                    if source.get('src'):
                        video_urls.append(source.get('src'))
            
            # 2. Cari di JavaScript untuk URL video
            scripts = soup.find_all('script')
            video_patterns = [
                r'(?:src|source|file|video_url|videoUrl|mp4|stream)["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8|webm)[^"\']*)["\']',
                r'(?:https?://[^\s"\'<>]+\.(?:mp4|m3u8|webm)(?:\?[^\s"\'<>]*)?)',
                r'data-src=["\']([^"\']+)["\']',
                r'player\.src\(["\']([^"\']+)["\']',
            ]
            
            for script in scripts:
                script_text = script.string or ''
                for pattern in video_patterns:
                    matches = re.findall(pattern, script_text, re.IGNORECASE)
                    video_urls.extend(matches)
            
            # 3. Cari iframe embed
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                iframe_src = iframe.get('src') or iframe.get('data-src')
                if iframe_src and any(ext in iframe_src.lower() for ext in ['.mp4', '.m3u8', 'embed', 'player']):
                    video_urls.append(iframe_src)
            
            # 4. Cari link download
            download_links = soup.find_all('a', href=True)
            for link in download_links:
                href = link.get('href', '')
                text = link.get_text().lower()
                if any(word in text for word in ['download', 'unduh', '720p', '1080p', '480p', 'mp4']):
                    video_urls.append(href)
            
            # Bersihkan dan validasi URL
            cleaned_urls = []
            for video_url in video_urls:
                if video_url:
                    # Handle relative URLs
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    elif video_url.startswith('/'):
                        parsed = urlparse(url)
                        video_url = f"{parsed.scheme}://{parsed.netloc}{video_url}"
                    
                    if video_url.startswith('http') and any(ext in video_url.lower() for ext in ['.mp4', '.m3u8', '.webm', 'download', 'stream']):
                        cleaned_urls.append(video_url)
            
            return list(set(cleaned_urls))  # Remove duplicates
            
        except Exception as e:
            print(f"Error extracting video URL: {e}")
            return []
    
    async def download_with_custom_extractor(self, url, format_type='video'):
        """Download menggunakan custom extractor untuk platform yang tidak didukung yt-dlp"""
        try:
            video_urls = await self.extract_direct_video_url(url)
            
            if not video_urls:
                return {'success': False, 'error': 'Tidak dapat menemukan URL video'}
            
            # Pilih URL terbaik (prefer MP4)
            best_url = None
            for v_url in video_urls:
                if '.mp4' in v_url.lower():
                    best_url = v_url
                    break
            
            if not best_url:
                best_url = video_urls[0]
            
            # Download file
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': url
            }
            
            # Generate filename
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type == 'audio':
                filename = f"{DOWNLOAD_PATH}audio_{timestamp}_{url_hash}.mp3"
            else:
                filename = f"{DOWNLOAD_PATH}video_{timestamp}_{url_hash}.mp4"
            
            response = requests.get(best_url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Jika audio, convert dengan ffmpeg
            if format_type == 'audio':
                video_file = filename.replace('.mp3', '_temp.mp4')
                os.rename(filename, video_file)
                
                try:
                    subprocess.run([
                        'ffmpeg', '-i', video_file, '-vn', '-acodec', 'libmp3lame',
                        '-ab', '192k', '-y', filename
                    ], capture_output=True, timeout=300)
                    os.remove(video_file)
                except Exception as e:
                    os.rename(video_file, filename)
                    print(f"FFmpeg conversion failed: {e}")
            
            # Extract title dari URL
            title = url.split('/')[-1].split('?')[0] or 'Downloaded Video'
            
            return {
                'success': True,
                'filepath': filename,
                'title': title,
                'duration': 0
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def download_media(self, url, format_type='video'):
        """Download media dari berbagai platform"""
        platform = self.detect_platform(url)
        
        try:
            # Untuk streaming platforms, coba yt-dlp dulu, jika gagal gunakan custom extractor
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_PATH}%(title).100s_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 60,
                'retries': 3,
                'fragment_retries': 3,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web']
                    }
                }
            }
            
            # Tambahkan opsi khusus untuk streaming platforms
            if self.is_streaming_platform(platform):
                ydl_opts.update({
                    'noplaylist': True,
                    'geo_bypass': True,
                    'nocheckcertificate': True,
                })
            
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
                ydl_opts.update({
                    'format': 'best',
                    'writethumbnail': True,
                    'skip_download': False,
                })
            else:
                # Untuk video, prioritaskan format yang bagus tapi tidak terlalu besar
                ydl_opts.update({
                    'format': 'best[filesize<50M]/best[height<=720]/best',
                })
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if format_type == 'audio':
                        filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                    elif format_type == 'photo':
                        base_filename = ydl.prepare_filename(info)
                        possible_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                        filename = None
                        
                        for ext in possible_extensions:
                            test_file = base_filename.rsplit('.', 1)[0] + ext
                            if os.path.exists(test_file):
                                filename = test_file
                                break
                        
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
                    
            except Exception as yt_error:
                print(f"yt-dlp failed for {platform}: {yt_error}")
                
                # Jika yt-dlp gagal untuk streaming platform, coba custom extractor
                if self.is_streaming_platform(platform):
                    print("Trying custom extractor...")
                    return await self.download_with_custom_extractor(url, format_type)
                else:
                    raise yt_error
        
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

async def platforms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /platforms"""
    lang = get_user_language(update)
    platforms_msg = LANGUAGES[lang]['platforms_list']
    
    # Keyboard dengan tombol kembali
    keyboard = [[InlineKeyboardButton("🏠 Menu Utama" if lang == 'id' else "🏠 Main Menu", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        platforms_msg,
        parse_mode='Markdown',
        reply_markup=reply_markup
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
    
    elif text in [LANGUAGES['id']['menu_platforms'], LANGUAGES['en']['menu_platforms']]:
        await platforms_command(update, context)
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
    
    # Store URL dan platform info
    url_id = str(hash(url))[-8:]
    context.user_data[url_id] = {
        'url': url,
        'platform': platform,
        'is_streaming': bot.is_streaming_platform(platform)
    }
    
    # Buat keyboard berdasarkan tipe platform
    is_streaming = bot.is_streaming_platform(platform)
    
    if is_streaming:
        # Untuk streaming platforms - tombol lebih sederhana
        keyboard = [
            [
                InlineKeyboardButton(
                    LANGUAGES[lang]['video_button'], 
                    callback_data=f"v|{url_id}|{lang}"
                )
            ],
            [
                InlineKeyboardButton(
                    LANGUAGES[lang]['audio_button'], 
                    callback_data=f"a|{url_id}|{lang}"
                )
            ]
        ]
        
        # Tambahkan tombol download langsung untuk streaming
        keyboard.append([
            InlineKeyboardButton(
                LANGUAGES[lang]['direct_download_button'], 
                callback_data=f"d|{url_id}|{lang}"
            )
        ])
        
        detected_msg = LANGUAGES[lang]['detected_streaming'].format(platform.upper())
    else:
        # Untuk sosial media - tombol standar
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
        
        detected_msg = get_text(update, 'detected').format(platform.upper())
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        detected_msg,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk button callback"""
    query = update.callback_query
    await query.answer()
    
    # Handle back to menu
    if query.data == "back_to_menu":
        lang = 'id' if query.from_user.language_code and query.from_user.language_code.lower().startswith('id') else 'en'
        welcome_msg = LANGUAGES[lang]['welcome']
        await query.message.edit_text(
            welcome_msg,
            parse_mode='Markdown'
        )
        return
    
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
    
    # Ambil data URL (format baru dengan dict)
    url_data = context.user_data.get(url_id)
    
    if not url_data:
        await query.message.reply_text(
            "❌ Link expired! Please send the link again." if lang == 'en' else "❌ Link kadaluarsa! Kirim ulang link-nya."
        )
        return
    
    # Handle format lama (string) dan baru (dict)
    if isinstance(url_data, str):
        url = url_data
        platform = bot.detect_platform(url)
        is_streaming = bot.is_streaming_platform(platform)
    else:
        url = url_data.get('url')
        platform = url_data.get('platform', 'unknown')
        is_streaming = url_data.get('is_streaming', False)
    
    # Tentukan format type
    if format_code == 'v':
        format_type = 'video'
    elif format_code == 'a':
        format_type = 'audio'
    elif format_code == 'p':
        format_type = 'photo'
    elif format_code == 'd':
        format_type = 'video'  # Direct download = video
    else:
        format_type = 'video'
    
    # Pesan download berbeda untuk streaming
    if is_streaming:
        downloading_msg = LANGUAGES[lang]['downloading_streaming'].format(platform.upper())
    else:
        downloading_msg = LANGUAGES[lang]['downloading'].format(
            'foto' if format_type == 'photo' else LANGUAGES[lang][format_type]
        )
    
    status_msg = await query.message.reply_text(downloading_msg, parse_mode='Markdown')
    
    try:
        result = await bot.download_media(url, format_type)
        
        if result['success']:
            await status_msg.edit_text(LANGUAGES[lang]['sending'])
            
            filepath = result['filepath']
            
            # Cek apakah file exists
            if not os.path.exists(filepath):
                await status_msg.edit_text(
                    LANGUAGES[lang]['download_failed'].format("File tidak ditemukan setelah download")
                )
                return
            
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
                try:
                    with open(filepath, 'rb') as audio:
                        await query.message.reply_audio(
                            audio=audio,
                            title=result['title'],
                            duration=int(result['duration']) if result['duration'] else None,
                            caption=caption,
                            parse_mode='Markdown'
                        )
                except Exception as audio_error:
                    print(f"Audio send failed, trying as document: {audio_error}")
                    with open(filepath, 'rb') as document:
                        await query.message.reply_document(
                            document=document,
                            caption=caption,
                            parse_mode='Markdown'
                        )
            else:
                caption = LANGUAGES[lang]['video_caption'].format(result['title'])
                
                # Tambah info platform untuk streaming
                if is_streaming:
                    caption += f"\n\n📡 Platform: {platform.upper()}"
                
                if file_size > max_size:
                    with open(filepath, 'rb') as document:
                        await query.message.reply_document(
                            document=document,
                            caption=caption + ("\n\n⚠️ File too large for streaming, sent as document." if lang == 'en' else "\n\n⚠️ File terlalu besar untuk streaming, dikirim sebagai document."),
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
                                caption=caption + ("\n\n📎 Sent as document." if lang == 'en' else "\n\n📎 Dikirim sebagai document."),
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
            error_text = result.get('error', 'Unknown error')
            # Truncate long errors
            if len(error_text) > 200:
                error_text = error_text[:200] + "..."
            error_msg = LANGUAGES[lang]['download_failed'].format(error_text)
            await status_msg.edit_text(error_msg)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_text = str(e)
        if len(error_text) > 200:
            error_text = error_text[:200] + "..."
        error_msg = LANGUAGES[lang]['error_occurred'].format(error_text)
        await status_msg.edit_text(error_msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk error"""
    print(f"Error: {context.error}")
    import traceback
    traceback.print_exc()

def main():
    """Fungsi utama untuk menjalankan bot"""
    print("=" * 60)
    print("🤖 SafeRobot v4.0 - Multi-Platform Video Downloader")
    print("=" * 60)
    print()
    print("📋 CONFIGURATION:")
    print(f"   👑 Owner ID: {OWNER_ID}")
    print(f"   💾 Database: {DATABASE_PATH}")
    print(f"   📁 Downloads: {DOWNLOAD_PATH}")
    print()
    print("🌐 FEATURES:")
    print("   ✅ Multi-language support: ID/EN")
    print("   ✅ Button menu interface")
    print("   ✅ Owner stats & database")
    print()
    print("📱 SOCIAL MEDIA PLATFORMS:")
    print("   • TikTok, Instagram, Twitter/X")
    print("   • YouTube, Facebook, Pinterest")
    print()
    print("🎬 STREAMING PLATFORMS:")
    print("   • DoodStream (dood.to, dood-hd.com, dll)")
    print("   • TeraBox (terabox.com, 1024terabox.com)")
    print("   • Videy (vidoy.com, videypro.live, dll)")
    print("   • Videq (videq.io, videq.co, dll)")
    print("   • LuluStream (lulustream.com, lulu.st)")
    print("   • VidCloud, StreamTape, MixDrop")
    print("   • Dan 50+ platform streaming lainnya!")
    print()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("platforms", platforms_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Message and callback handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    print("=" * 60)
    print("✅ SafeRobot is running!")
    print("=" * 60)
    print()
    print("📝 USER COMMANDS:")
    print("   /start     - Menu utama")
    print("   /platforms - Daftar platform yang didukung")
    print()
    print("👑 OWNER COMMANDS:")
    print("   /stats           - Lihat statistik pengguna")
    print("   /broadcast <msg> - Kirim pesan ke semua user")
    print()
    print("🔗 Kirim link untuk mulai download!")
    print("Press Ctrl+C to stop")
    print()
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
