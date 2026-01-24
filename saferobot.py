import os
import re
import asyncio
import json
import hashlib
import zipfile
import tempfile
import subprocess
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, urljoin, parse_qs
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
import yt_dlp
import aiohttp

# Optional Playwright import
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed. Advanced extraction disabled.")
    print("   Install with: pip install playwright && playwright install chromium")

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
# HELPER FUNCTIONS
# ============================================
def escape_markdown(text: str) -> str:
    """Escape karakter markdown untuk menghindari parse error"""
    if not text:
        return ""
    # Escape karakter khusus markdown
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = text
    for char in escape_chars:
        result = result.replace(char, f'\\{char}')
    return result

def safe_title(title: str, max_length: int = 50) -> str:
    """Buat judul yang aman untuk ditampilkan"""
    if not title:
        return "Media"
    # Hapus karakter berbahaya
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    safe = safe.strip()
    if len(safe) > max_length:
        safe = safe[:max_length] + "..."
    return safe if safe else "Media"

def get_unique_filename(base_path: str, extension: str) -> str:
    """Generate unique filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_hash = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
    return f"{base_path}/{timestamp}_{random_hash}.{extension}"

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
🤖 Selamat datang di SafeRobot!

Bot downloader UNIVERSAL untuk:
✅ TikTok, Instagram, Twitter/X
✅ YouTube, Facebook, Pinterest
✅ Videy, VidPlay, StreamSB
✅ DoodStream, Upstream, MP4Upload
✅ Dan SEMUA situs streaming lainnya!

🔥 Cara Penggunaan:
Kirim link APAPUN dan bot akan otomatis mendeteksi & mendownload video!

Gunakan tombol menu di bawah untuk navigasi 👇
        """,
        'about': """
ℹ️ Tentang SafeRobot

SafeRobot adalah bot Telegram yang dapat mendownload konten dari HAMPIR SEMUA platform dan situs streaming.

Fitur Utama:
⚡ Universal downloader - download dari link apapun
🎯 Auto-detect platform
🔒 Browser simulation untuk bypass proteksi
📱 Support m3u8/HLS streams
🗜️ Auto-zip untuk multiple files

Terima kasih telah menggunakan SafeRobot! 🙏
        """,
        'invalid_url': "❌ Link tidak valid! Kirim link yang benar.",
        'universal_detected': """🎬 Link streaming terdeteksi!

⚠️ Platform ini menggunakan proteksi khusus.
Bot akan mencoba mengekstrak video...

Pilih format download:""",
        'platform_detected': """🎬 Link dari {} terdeteksi!

Pilih format download:""",
        'downloading': "⏳ Sedang mendownload {}...\nMohon tunggu sebentar...",
        'extracting': "🔍 Mengekstrak video dari halaman...\nIni mungkin memerlukan waktu lebih lama...",
        'sending': "📤 Mengirim file...",
        'video_caption': "🎥 {}\n\n🔥 Downloaded by @SafeRobot",
        'audio_caption': "🎵 {}\n\n🔥 Downloaded by @SafeRobot",
        'photo_caption': "📷 {}\n\n🔥 Downloaded by @SafeRobot",
        'download_failed': """❌ Download gagal!

Error: {}

Tips:
• Pastikan link dapat diakses
• Beberapa situs memerlukan waktu lebih lama
• Coba kirim link lagi
• Hubungi admin jika masalah berlanjut""",
        'error_occurred': """❌ Terjadi kesalahan!

Error: {}

Silakan coba lagi atau hubungi admin.""",
        'video_button': "🎥 Video (MP4)",
        'audio_button': "🎵 Audio (MP3)",
        'direct_button': "⬇️ Download Langsung",
        'photo_button': "📷 Foto/Gambar",
        'menu_about': "ℹ️ Tentang",
        'menu_start': "🏠 Menu Utama",
        'video': 'video',
        'audio': 'audio',
        'send_link': "🔎 Kirim link dari platform APAPUN untuk mulai download!",
        'processing': "⏳ Memproses...",
        'stream_warning': "⚠️ Platform streaming mungkin memerlukan waktu lebih lama.",
        'multiple_files': "📦 Ditemukan {} file. Mengunduh semua...",
        'zipping': "🗜️ Membuat file ZIP..."
    },
    'en': {
        'welcome': """
🤖 Welcome to SafeRobot!

UNIVERSAL downloader bot for:
✅ TikTok, Instagram, Twitter/X
✅ YouTube, Facebook, Pinterest
✅ Videy, VidPlay, StreamSB
✅ DoodStream, Upstream, MP4Upload
✅ And ALL other streaming sites!

🔥 How to Use:
Send ANY link and the bot will auto-detect & download the video!

Use the menu buttons below for navigation 👇
        """,
        'about': """
ℹ️ About SafeRobot

SafeRobot is a Telegram bot that can download content from ALMOST ANY platform and streaming site.

Main Features:
⚡ Universal downloader - download from any link
🎯 Auto-detect platform
🔒 Browser simulation to bypass protection
📱 Support m3u8/HLS streams
🗜️ Auto-zip for multiple files

Thank you for using SafeRobot! 🙏
        """,
        'invalid_url': "❌ Invalid link! Send a valid link.",
        'universal_detected': """🎬 Streaming link detected!

⚠️ This platform uses special protection.
Bot will try to extract video...

Choose download format:""",
        'platform_detected': """🎬 Link from {} detected!

Choose download format:""",
        'downloading': "⏳ Downloading {}...\nPlease wait...",
        'extracting': "🔍 Extracting video from page...\nThis might take longer...",
        'sending': "📤 Sending file...",
        'video_caption': "🎥 {}\n\n🔥 Downloaded by @SafeRobot",
        'audio_caption': "🎵 {}\n\n🔥 Downloaded by @SafeRobot",
        'download_failed': """❌ Download failed!

Error: {}

Tips:
• Make sure the link is accessible
• Some sites take longer
• Try sending the link again
• Contact admin if problem persists""",
        'error_occurred': """❌ An error occurred!

Error: {}

Please try again or contact admin.""",
        'video_button': "🎥 Video (MP4)",
        'audio_button': "🎵 Audio (MP3)",
        'direct_button': "⬇️ Direct Download",
        'photo_button': "📷 Photo/Image",
        'menu_about': "ℹ️ About",
        'menu_start': "🏠 Main Menu",
        'video': 'video',
        'audio': 'audio',
        'send_link': "🔎 Send a link from ANY platform to start downloading!",
        'processing': "⏳ Processing...",
        'stream_warning': "⚠️ Streaming platform may take longer.",
        'multiple_files': "📦 Found {} files. Downloading all...",
        'zipping': "🗜️ Creating ZIP file..."
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

def get_text_by_lang(lang: str, key: str) -> str:
    """Ambil text berdasarkan kode bahasa"""
    return LANGUAGES.get(lang, LANGUAGES['en']).get(key, LANGUAGES['en'].get(key, ''))

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
# UNIVERSAL VIDEO EXTRACTOR
# ============================================
class UniversalExtractor:
    """
    Universal video extractor yang bekerja seperti 9xbuddy.site
    Menggunakan berbagai metode untuk mengekstrak video dari berbagai situs
    """
    
    # Pattern untuk mendeteksi URL video langsung
    VIDEO_PATTERNS = [
        r'(https?://[^\s<>"\']+\.mp4[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+\.m3u8[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+\.webm[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+\.mkv[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+\.avi[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+\.mov[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+\.flv[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+/video/[^\s<>"\']*)',
        r'(https?://[^\s<>"\']+/v/[^\s<>"\']*)',
        r'source[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']',
        r'file["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
        r'source["\']?\s*:\s*["\']([^"\']+)["\']',
        r'video["\']?\s*:\s*["\']([^"\']+)["\']',
        r'src["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
        r'url["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
        r'sources\s*:\s*\[\s*\{[^}]*["\']?file["\']?\s*:\s*["\']([^"\']+)["\']',
        r'player\.src\s*\(\s*\{[^}]*["\']?src["\']?\s*:\s*["\']([^"\']+)["\']',
        r'["\']?hls["\']?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'["\']?dash["\']?\s*:\s*["\']([^"\']+\.mpd[^"\']*)["\']',
    ]
    
    # Platform streaming yang dikenal
    STREAMING_PLATFORMS = {
        'videy': ['videy.co', 'videy.net'],
        'vidgo': ['vidgo.blog'],
        'myvidplay': ['myvidplay.com'],
        'doodstream': ['doodstream.com', 'dood.to', 'dood.watch', 'dood.cx', 'dood.la', 'dood.pm', 'dood.so', 'dood.ws', 'dood.sh', 'dood.re', 'dood.wf', 'ds2play.com'],
        'streamsb': ['streamsb.net', 'streamsb.com', 'sbembed.com', 'sbplay.org', 'embedsb.com', 'pelistop.co', 'sbplay2.xyz', 'sbchill.com', 'streamsss.net', 'sbplay.one'],
        'upstream': ['upstream.to', 'upstreamcdn.co'],
        'mp4upload': ['mp4upload.com'],
        'vidoza': ['vidoza.net', 'vidoza.co'],
        'mixdrop': ['mixdrop.co', 'mixdrop.to', 'mixdrop.ch'],
        'streamtape': ['streamtape.com', 'streamtape.net', 'streamta.pe', 'strtape.cloud', 'strcloud.link'],
        'fembed': ['fembed.com', 'feurl.com', 'femax20.com', 'fcdn.stream', 'diasfem.com'],
        'filemoon': ['filemoon.sx', 'filemoon.to'],
        'voe': ['voe.sx', 'voe.to'],
        'vtube': ['vtube.to', 'vtbe.to'],
        'other_streaming': []  # Untuk platform tidak dikenal
    }
    
    # Platform yang didukung yt-dlp dengan baik
    YTDLP_PLATFORMS = {
        'tiktok': ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'],
        'instagram': ['instagram.com', 'instagr.am'],
        'twitter': ['twitter.com', 'x.com', 't.co'],
        'youtube': ['youtube.com', 'youtu.be', 'youtube-nocookie.com'],
        'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
        'pinterest': ['pinterest.com', 'pin.it'],
        'vimeo': ['vimeo.com'],
        'dailymotion': ['dailymotion.com', 'dai.ly'],
        'twitch': ['twitch.tv'],
        'reddit': ['reddit.com', 'redd.it'],
        'bilibili': ['bilibili.com', 'b23.tv']
    }
    
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
    
    def detect_platform(self, url: str) -> tuple:
        """Deteksi platform dari URL, return (platform_name, is_streaming)"""
        try:
            domain = urlparse(url).netloc.lower()
            domain = domain.replace('www.', '')
            
            # Cek platform yt-dlp
            for platform, domains in self.YTDLP_PLATFORMS.items():
                if any(d in domain for d in domains):
                    return (platform.upper(), False)
            
            # Cek platform streaming
            for platform, domains in self.STREAMING_PLATFORMS.items():
                if any(d in domain for d in domains):
                    return (platform.upper(), True)
            
            # Platform tidak dikenal - coba sebagai streaming
            return ('OTHER_STREAMING', True)
        except:
            return ('UNKNOWN', True)
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def extract_video_urls_from_html(self, html: str, base_url: str) -> List[str]:
        """Extract video URLs dari HTML page"""
        video_urls = []
        
        for pattern in self.VIDEO_PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                # Make absolute URL
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    parsed = urlparse(base_url)
                    url = f"{parsed.scheme}://{parsed.netloc}{url}"
                elif not url.startswith('http'):
                    url = urljoin(base_url, url)
                
                # Validate URL
                if self._is_valid_video_url(url):
                    video_urls.append(url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in video_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def _is_valid_video_url(self, url: str) -> bool:
        """Validasi apakah URL adalah video yang valid"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Ekstensi video yang valid
            video_extensions = ['.mp4', '.m3u8', '.webm', '.mkv', '.avi', '.mov', '.flv', '.mpd']
            path_lower = parsed.path.lower()
            
            # Check if path contains video extension
            if any(ext in path_lower for ext in video_extensions):
                return True
            
            # Check for video-related paths
            video_paths = ['/video', '/v/', '/stream', '/play', '/embed', '/media', '/hls/', '/dash/']
            if any(vp in path_lower for vp in video_paths):
                return True
            
            # Check query parameters
            if 'video' in url.lower() or 'stream' in url.lower():
                return True
            
            return False
        except:
            return False
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML page content"""
        try:
            session = await self.get_session()
            async with session.get(url, ssl=False) as response:
                if response.status == 200:
                    return await response.text()
                return None
        except Exception as e:
            print(f"[Fetch Error] {e}")
            return None
    
    async def download_with_ytdlp(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """Download menggunakan yt-dlp dengan opsi yang dioptimalkan"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_hash = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
            output_base = f"{DOWNLOAD_PATH}{timestamp}_{random_hash}"
            
            ydl_opts = {
                'outtmpl': output_base + '.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'socket_timeout': 60,
                'retries': 5,
                'fragment_retries': 5,
                'http_headers': self.headers,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                    }
                },
                # Support untuk berbagai situs
                'allow_unplayable_formats': False,
                'check_formats': False,
                'geo_bypass': True,
                'nocheckcertificate': True,
                # Handling untuk age-restricted content
                'age_limit': None,
                # Cookie handling untuk situs yang memerlukan login
                'cookiesfrombrowser': None,
            }
            
            if format_type == 'audio':
                ydl_opts.update({
                    'format': 'bestaudio[ext=m4a]/bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                # Format priority untuk video
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                })
            
            # Run yt-dlp in executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if format_type == 'audio':
                        filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                    else:
                        filename = ydl.prepare_filename(info)
                        # Handle merged output
                        if not os.path.exists(filename):
                            # Cari file dengan nama serupa
                            base = filename.rsplit('.', 1)[0]
                            for ext in ['mp4', 'mkv', 'webm']:
                                test_file = f"{base}.{ext}"
                                if os.path.exists(test_file):
                                    filename = test_file
                                    break
                    
                    return {
                        'success': True,
                        'filepath': filename,
                        'title': safe_title(info.get('title', 'Media')),
                        'duration': info.get('duration', 0)
                    }
            
            result = await loop.run_in_executor(None, download)
            return result
            
        except Exception as e:
            error_msg = str(e)
            # Clean up error message
            if 'is not a valid URL' in error_msg:
                error_msg = 'Invalid URL'
            elif 'Video unavailable' in error_msg:
                error_msg = 'Video unavailable or private'
            elif 'Unsupported URL' in error_msg:
                error_msg = 'Platform not supported by yt-dlp'
            
            return {
                'success': False,
                'error': error_msg
            }
    
    async def download_direct_url(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """Download dari direct URL dengan streaming untuk file besar"""
        try:
            # Determine extension
            parsed = urlparse(url)
            path_lower = parsed.path.lower()
            
            if '.m3u8' in path_lower or '.m3u8' in url.lower():
                # HLS stream - use ffmpeg
                return await self.download_hls_stream(url, format_type)
            
            extension = 'mp4'
            if '.webm' in path_lower:
                extension = 'webm'
            elif '.mkv' in path_lower:
                extension = 'mkv'
            elif '.ts' in path_lower:
                extension = 'ts'
            
            filename = get_unique_filename(DOWNLOAD_PATH, extension)
            
            # Create new session with longer timeout for large files
            timeout = aiohttp.ClientTimeout(total=300, connect=30)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=self.headers) as session:
                async with session.get(url, ssl=False) as response:
                    if response.status == 200:
                        # Stream download untuk file besar
                        content_length = int(response.headers.get('content-length', 0))
                        print(f"[Download] Downloading {content_length} bytes...")
                        
                        with open(filename, 'wb') as f:
                            downloaded = 0
                            async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                                f.write(chunk)
                                downloaded += len(chunk)
                        
                        # Verify file
                        if os.path.exists(filename) and os.path.getsize(filename) > 0:
                            # Convert .ts to .mp4 if needed
                            if extension == 'ts':
                                mp4_filename = filename.replace('.ts', '.mp4')
                                try:
                                    process = await asyncio.create_subprocess_exec(
                                        'ffmpeg', '-y', '-i', filename,
                                        '-c', 'copy', mp4_filename,
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE
                                    )
                                    await process.communicate()
                                    if os.path.exists(mp4_filename):
                                        os.remove(filename)
                                        filename = mp4_filename
                                except Exception:
                                    pass
                            
                            return {
                                'success': True,
                                'filepath': filename,
                                'title': 'Downloaded Media',
                                'duration': 0
                            }
                        else:
                            return {
                                'success': False,
                                'error': 'Downloaded file is empty'
                            }
                    elif response.status == 403:
                        return {
                            'success': False,
                            'error': 'Access forbidden - video is protected'
                        }
                    elif response.status == 404:
                        return {
                            'success': False,
                            'error': 'Video not found'
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'HTTP {response.status}'
                        }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'Download timeout - file too large or slow connection'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def download_hls_stream(self, m3u8_url: str, format_type: str = 'video') -> Dict[str, Any]:
        """Download HLS/m3u8 stream menggunakan ffmpeg"""
        try:
            if format_type == 'audio':
                extension = 'mp3'
                ffmpeg_opts = ['-vn', '-acodec', 'libmp3lame', '-q:a', '2']
            else:
                extension = 'mp4'
                ffmpeg_opts = ['-c', 'copy']
            
            filename = get_unique_filename(DOWNLOAD_PATH, extension)
            
            cmd = [
                'ffmpeg',
                '-y',
                '-i', m3u8_url,
                '-headers', f'User-Agent: {self.headers["User-Agent"]}\r\n',
                *ffmpeg_opts,
                filename
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            
            if process.returncode == 0 and os.path.exists(filename) and os.path.getsize(filename) > 0:
                return {
                    'success': True,
                    'filepath': filename,
                    'title': 'HLS Stream',
                    'duration': 0
                }
            else:
                return {
                    'success': False,
                    'error': 'FFmpeg failed to download stream'
                }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'Download timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def extract_with_playwright(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """
        Extract video menggunakan Playwright browser automation.
        Ini adalah metode yang sama yang digunakan oleh 9xbuddy.site
        untuk menangkap video dari website apapun.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {'success': False, 'error': 'Playwright not available'}
        
        captured_urls = []
        
        try:
            print(f"[Playwright] Starting browser for: {url}")
            
            async with async_playwright() as p:
                # Launch browser with stealth settings
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    java_script_enabled=True,
                    bypass_csp=True,
                    ignore_https_errors=True
                )
                
                page = await context.new_page()
                
                # Intercept network requests
                async def handle_response(response):
                    try:
                        response_url = response.url
                        content_type = response.headers.get('content-type', '')
                        
                        # Capture video URLs
                        is_video = (
                            '.mp4' in response_url.lower() or
                            '.m3u8' in response_url.lower() or
                            '.webm' in response_url.lower() or
                            '.ts' in response_url.lower() or
                            '.mpd' in response_url.lower() or
                            'video' in content_type.lower() or
                            'mpegurl' in content_type.lower() or
                            '/video/' in response_url.lower() or
                            '/stream/' in response_url.lower() or
                            '/hls/' in response_url.lower()
                        )
                        
                        if is_video and response.status == 200:
                            # Filter out tracking/analytics
                            skip_domains = ['google', 'facebook', 'analytics', 'doubleclick', 'adsense', 'tracker']
                            if not any(skip in response_url.lower() for skip in skip_domains):
                                print(f"[Playwright] Captured: {response_url[:100]}...")
                                captured_urls.append({
                                    'url': response_url,
                                    'content_type': content_type,
                                    'size': int(response.headers.get('content-length', 0))
                                })
                    except Exception as e:
                        pass
                
                page.on('response', handle_response)
                
                # Navigate to page
                try:
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                except Exception:
                    # Try with domcontentloaded if networkidle times out
                    try:
                        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    except Exception:
                        pass
                
                # Wait for video elements to load
                await asyncio.sleep(3)
                
                # Try to click play button if exists
                try:
                    play_selectors = [
                        'button[aria-label*="play"]',
                        '.play-button',
                        '.vjs-big-play-button',
                        '.plyr__control--overlaid',
                        '[class*="play"]',
                        'video'
                    ]
                    for selector in play_selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element:
                                await element.click()
                                await asyncio.sleep(2)
                                break
                        except:
                            continue
                except:
                    pass
                
                # Extract video source from page
                video_sources = await page.evaluate('''() => {
                    const sources = [];
                    
                    // Get all video elements
                    document.querySelectorAll('video').forEach(video => {
                        if (video.src) sources.push(video.src);
                        if (video.currentSrc) sources.push(video.currentSrc);
                        
                        video.querySelectorAll('source').forEach(source => {
                            if (source.src) sources.push(source.src);
                        });
                    });
                    
                    // Get iframes that might contain video
                    document.querySelectorAll('iframe').forEach(iframe => {
                        if (iframe.src) sources.push(iframe.src);
                    });
                    
                    // Search for video URLs in scripts
                    document.querySelectorAll('script').forEach(script => {
                        const text = script.textContent || '';
                        const patterns = [
                            /["']([^"']+\.m3u8[^"']*)['"]/gi,
                            /["']([^"']+\.mp4[^"']*)['"]/gi,
                            /source\s*:\s*["']([^"']+)['"]/gi,
                            /file\s*:\s*["']([^"']+)['"]/gi,
                            /src\s*:\s*["']([^"']+\.mp4[^"']*)['"]/gi
                        ];
                        patterns.forEach(pattern => {
                            let match;
                            while ((match = pattern.exec(text)) !== null) {
                                sources.push(match[1]);
                            }
                        });
                    });
                    
                    return sources;
                }''')
                
                # Add page-extracted sources to captured URLs
                for source in video_sources:
                    if source and ('mp4' in source.lower() or 'm3u8' in source.lower() or 'video' in source.lower()):
                        captured_urls.append({
                            'url': source,
                            'content_type': 'video/mp4' if 'mp4' in source.lower() else 'application/x-mpegURL',
                            'size': 0
                        })
                
                await browser.close()
            
            print(f"[Playwright] Found {len(captured_urls)} potential video URLs")
            
            if not captured_urls:
                return {'success': False, 'error': 'No video URLs captured'}
            
            # Remove duplicates and prioritize
            seen = set()
            unique_urls = []
            for item in captured_urls:
                url_clean = item['url'].split('?')[0]  # Remove query params for dedup
                if url_clean not in seen:
                    seen.add(url_clean)
                    unique_urls.append(item)
            
            # Sort by priority: m3u8 > mp4 with size > mp4 without size
            def priority(item):
                url = item['url'].lower()
                if '.m3u8' in url:
                    return (0, item['size'])
                elif '.mp4' in url:
                    return (1, -item['size'])
                else:
                    return (2, -item['size'])
            
            unique_urls.sort(key=priority)
            
            # Try to download each URL
            for item in unique_urls[:5]:  # Try top 5
                video_url = item['url']
                print(f"[Playwright] Trying to download: {video_url[:80]}...")
                
                if '.m3u8' in video_url.lower():
                    result = await self.download_hls_stream(video_url, format_type)
                else:
                    result = await self.download_direct_url(video_url, format_type)
                
                if result['success']:
                    return result
            
            return {'success': False, 'error': 'All captured URLs failed to download'}
            
        except Exception as e:
            print(f"[Playwright Error] {e}")
            return {'success': False, 'error': str(e)}
    
    async def extract_from_streaming_site(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """Extract video dari streaming site generik"""
        try:
            # Step 1: Try Playwright first for JS-heavy sites
            if PLAYWRIGHT_AVAILABLE:
                print(f"[Extractor] Trying Playwright extraction...")
                result = await self.extract_with_playwright(url, format_type)
                if result['success']:
                    return result
            
            # Step 2: Fallback to HTML parsing
            print(f"[Extractor] Falling back to HTML parsing...")
            html = await self.fetch_page(url)
            if not html:
                return {
                    'success': False,
                    'error': 'Failed to fetch page'
                }
            
            # Step 3: Extract video URLs
            video_urls = await self.extract_video_urls_from_html(html, url)
            
            if not video_urls:
                # Try with yt-dlp as fallback
                return await self.download_with_ytdlp(url, format_type)
            
            # Step 4: Prioritas URL
            # Prioritaskan m3u8, lalu mp4
            m3u8_urls = [u for u in video_urls if '.m3u8' in u.lower()]
            mp4_urls = [u for u in video_urls if '.mp4' in u.lower()]
            
            # Coba m3u8 dulu
            for m3u8_url in m3u8_urls:
                result = await self.download_hls_stream(m3u8_url, format_type)
                if result['success']:
                    return result
            
            # Coba mp4
            for mp4_url in mp4_urls:
                result = await self.download_direct_url(mp4_url, format_type)
                if result['success']:
                    return result
            
            # Coba semua URL lain
            for video_url in video_urls:
                if video_url not in m3u8_urls and video_url not in mp4_urls:
                    result = await self.download_direct_url(video_url, format_type)
                    if result['success']:
                        return result
            
            # Fallback ke yt-dlp
            return await self.download_with_ytdlp(url, format_type)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def extract(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """
        Main extraction method - mencoba berbagai metode secara berurutan:
        1. yt-dlp untuk platform yang dikenal
        2. Playwright browser automation untuk streaming sites
        3. HTML parsing untuk fallback
        4. Direct URL download jika ditemukan
        """
        platform, is_streaming = self.detect_platform(url)
        
        print(f"[Extractor] Platform: {platform}, Is Streaming: {is_streaming}, Format: {format_type}")
        print(f"[Extractor] URL: {url}")
        
        errors = []
        
        # Method 1: yt-dlp untuk platform yang dikenal
        if not is_streaming:
            print(f"[Extractor] Method 1: Trying yt-dlp...")
            result = await self.download_with_ytdlp(url, format_type)
            if result['success']:
                print(f"[Extractor] yt-dlp succeeded!")
                return result
            errors.append(f"yt-dlp: {result.get('error', 'Unknown error')}")
        
        # Method 2: Streaming site extraction (Playwright + HTML parsing)
        print(f"[Extractor] Method 2: Trying streaming extraction...")
        result = await self.extract_from_streaming_site(url, format_type)
        if result['success']:
            print(f"[Extractor] Streaming extraction succeeded!")
            return result
        errors.append(f"Streaming: {result.get('error', 'Unknown error')}")
        
        # Method 3: Fallback yt-dlp dengan opsi berbeda
        if is_streaming:
            print(f"[Extractor] Method 3: Final yt-dlp fallback...")
            result = await self.download_with_ytdlp(url, format_type)
            if result['success']:
                print(f"[Extractor] yt-dlp fallback succeeded!")
                return result
            errors.append(f"yt-dlp fallback: {result.get('error', 'Unknown error')}")
        
        # All methods failed
        combined_error = " | ".join(errors[-2:])  # Show last 2 errors
        return {
            'success': False,
            'error': f"Semua metode gagal: {combined_error}"
        }

# Global extractor
extractor = UniversalExtractor()

# ============================================
# ZIP UTILITY
# ============================================
async def create_zip_from_files(files: List[str], output_name: str = None) -> str:
    """Buat file ZIP dari beberapa file"""
    if not output_name:
        output_name = get_unique_filename(DOWNLOAD_PATH, 'zip')
    else:
        output_name = os.path.join(DOWNLOAD_PATH, output_name)
    
    with zipfile.ZipFile(output_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            if os.path.exists(file_path):
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)
    
    return output_name

async def create_zip_from_folder(folder_path: str, output_name: str = None) -> str:
    """Buat file ZIP dari folder"""
    if not output_name:
        output_name = get_unique_filename(DOWNLOAD_PATH, 'zip')
    
    with zipfile.ZipFile(output_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
    
    return output_name

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
📊 SAFEROBOT STATISTICS
━━━━━━━━━━━━━━━━━━━━

👥 USER STATISTICS
├ Total Users: {stats['total_users']}
├ Active Users (7d): {stats['active_users']}
├ Inactive Users: {stats['inactive_users']}
├ 🇮🇩 Indonesia: {stats['indonesia_users']}
└ 🌍 International: {stats['international_users']}

📥 DOWNLOAD STATISTICS
├ Total Downloads: {stats['total_downloads']}
├ 🎥 Video: {stats['video_downloads']}
└ 🎵 Audio: {stats['audio_downloads']}

🏆 TOP 5 USERS
"""
    
    for i, user in enumerate(top_users, 1):
        username = f"@{user['username']}" if user['username'] else user['first_name']
        stats_msg += f"{i}. {username} - {user['download_count']} downloads\n"
    
    stats_msg += "\n━━━━━━━━━━━━━━━━━━━━"
    
    # Keyboard untuk refresh
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_msg,
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
            "📢 Format Broadcast\n\n"
            "Gunakan: /broadcast <pesan>\n\n"
            "Contoh: /broadcast Halo semua! Bot sedang maintenance."
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
                text=f"📢 BROADCAST MESSAGE\n\n{message}"
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
    platform, is_streaming = extractor.detect_platform(url)
    
    # Store URL
    url_id = str(hash(url))[-8:]
    context.user_data[url_id] = {
        'url': url,
        'platform': platform,
        'is_streaming': is_streaming
    }
    
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
        ],
        [
            InlineKeyboardButton(
                LANGUAGES[lang]['direct_button'], 
                callback_data=f"d|{url_id}|{lang}"
            )
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Pesan sesuai platform
    if is_streaming:
        detected_msg = f"🎬 Link streaming dari {platform} terdeteksi!\n\n⚠️ Platform streaming mungkin memerlukan waktu lebih lama.\n\nPilih format download:"
    else:
        detected_msg = f"🎬 Link dari {platform} terdeteksi!\n\nPilih format download:"
    
    await update.message.reply_text(
        detected_msg,
        reply_markup=reply_markup
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
📊 SAFEROBOT STATISTICS
━━━━━━━━━━━━━━━━━━━━

👥 USER STATISTICS
├ Total Users: {stats['total_users']}
├ Active Users (7d): {stats['active_users']}
├ Inactive Users: {stats['inactive_users']}
├ 🇮🇩 Indonesia: {stats['indonesia_users']}
└ 🌍 International: {stats['international_users']}

📥 DOWNLOAD STATISTICS
├ Total Downloads: {stats['total_downloads']}
├ 🎥 Video: {stats['video_downloads']}
└ 🎵 Audio: {stats['audio_downloads']}

🏆 TOP 5 USERS
"""
        
        for i, user in enumerate(top_users, 1):
            username = f"@{user['username']}" if user['username'] else user['first_name']
            stats_msg += f"{i}. {username} - {user['download_count']} downloads\n"
        
        stats_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n🕐 Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_msg,
            reply_markup=reply_markup
        )
        return
    
    data = query.data.split('|')
    format_code = data[0]
    url_id = data[1]
    lang = data[2] if len(data) > 2 else 'en'
    
    url_data = context.user_data.get(url_id)
    
    if not url_data:
        error_msg = "❌ Link expired! Please send the link again." if lang == 'en' else "❌ Link kadaluarsa! Kirim ulang link-nya."
        await query.message.reply_text(error_msg)
        return
    
    url = url_data['url']
    platform = url_data['platform']
    is_streaming = url_data['is_streaming']
    
    # Tentukan format type
    if format_code == 'v':
        format_type = 'video'
    elif format_code == 'a':
        format_type = 'audio'
    elif format_code == 'd':
        format_type = 'video'  # Direct download as video
    else:
        format_type = 'video'
    
    # Status message
    if is_streaming:
        status_text = f"🔍 Mengekstrak video dari {platform}...\n⏳ Ini mungkin memerlukan waktu lebih lama..."
    else:
        format_name = 'video' if format_type == 'video' else 'audio'
        status_text = f"⏳ Sedang mendownload {format_name}...\nMohon tunggu sebentar..."
    
    status_msg = await query.message.reply_text(status_text)
    
    try:
        # Download menggunakan universal extractor
        result = await extractor.extract(url, format_type)
        
        if result['success']:
            await status_msg.edit_text("📤 Mengirim file...")
            
            filepath = result['filepath']
            title = safe_title(result.get('title', 'Media'))
            
            # Cek apakah file ada
            if not os.path.exists(filepath):
                await status_msg.edit_text("❌ File tidak ditemukan setelah download!")
                return
            
            # Cek ukuran file
            file_size = os.path.getsize(filepath)
            max_size = 50 * 1024 * 1024  # 50MB limit Telegram
            
            if file_size == 0:
                await status_msg.edit_text("❌ File kosong! Video mungkin diproteksi.")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return
            
            # Buat caption sederhana tanpa markdown
            if format_type == 'audio':
                caption = f"🎵 {title}\n\n🔥 Downloaded by @SafeRobot"
            else:
                caption = f"🎥 {title}\n\n🔥 Downloaded by @SafeRobot"
            
            # Kirim file
            try:
                if format_type == 'audio':
                    with open(filepath, 'rb') as audio:
                        await query.message.reply_audio(
                            audio=audio,
                            title=title,
                            duration=int(result.get('duration', 0)) if result.get('duration') else None,
                            caption=caption
                        )
                else:
                    if file_size > max_size:
                        with open(filepath, 'rb') as document:
                            await query.message.reply_document(
                                document=document,
                                caption=caption + "\n\n⚠️ File terlalu besar, dikirim sebagai document."
                            )
                    else:
                        try:
                            with open(filepath, 'rb') as video:
                                await query.message.reply_video(
                                    video=video,
                                    duration=int(result.get('duration', 0)) if result.get('duration') else None,
                                    caption=caption,
                                    supports_streaming=True
                                )
                        except Exception as video_error:
                            print(f"Video send failed, trying as document: {video_error}")
                            with open(filepath, 'rb') as document:
                                await query.message.reply_document(
                                    document=document,
                                    caption=caption + "\n\n📎 Dikirim sebagai document."
                                )
                
                # Increment download counter
                db.increment_download(query.from_user.id, format_type)
                
                await status_msg.delete()
                
            except Exception as send_error:
                print(f"Send error: {send_error}")
                # Coba kirim sebagai document
                try:
                    with open(filepath, 'rb') as document:
                        await query.message.reply_document(
                            document=document,
                            caption=caption
                        )
                    db.increment_download(query.from_user.id, format_type)
                    await status_msg.delete()
                except Exception as doc_error:
                    await status_msg.edit_text(f"❌ Gagal mengirim file: {str(doc_error)[:100]}")
            
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
            
            error_msg = f"❌ Download gagal!\n\nError: {error_text}\n\nTips:\n• Pastikan link dapat diakses\n• Coba kirim link lagi\n• Hubungi admin jika masalah berlanjut"
            await status_msg.edit_text(error_msg)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_text = str(e)
        if len(error_text) > 200:
            error_text = error_text[:200] + "..."
        await status_msg.edit_text(f"❌ Terjadi kesalahan!\n\nError: {error_text}\n\nSilakan coba lagi.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk error"""
    print(f"Error: {context.error}")
    import traceback
    traceback.print_exc()

async def cleanup_on_shutdown():
    """Cleanup saat shutdown"""
    await extractor.close_session()

def main():
    """Fungsi utama untuk menjalankan bot"""
    print("🤖 SafeRobot v4.0 - Universal Downloader Starting...")
    print("🌐 Multi-language support: ID/EN")
    print("🎬 Universal video extraction enabled")
    print("📊 Owner stats & database enabled")
    print(f"👑 Owner ID: {OWNER_ID}")
    print("✅ Supported: ALL platforms including streaming sites!")
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
