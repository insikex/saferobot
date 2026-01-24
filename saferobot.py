import os
import re
import asyncio
import json
import hashlib
import zipfile
import tempfile
import subprocess
import shutil
import base64
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse, urljoin, parse_qs, unquote
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
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = text
    for char in escape_chars:
        result = result.replace(char, f'\\{char}')
    return result

def safe_title(title: str, max_length: int = 50) -> str:
    """Buat judul yang aman untuk ditampilkan"""
    if not title:
        return "Media"
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
# JAVASCRIPT UNPACKER
# ============================================
class JSUnpacker:
    """
    Unpacker untuk JavaScript yang di-obfuscate.
    Banyak situs streaming menggunakan teknik packing untuk menyembunyikan URL video.
    """
    
    @staticmethod
    def detect_packed(source: str) -> bool:
        """Deteksi apakah JavaScript menggunakan P.A.C.K.E.R packing"""
        return bool(re.search(r"eval\(function\(p,a,c,k,e,(?:r|d)", source))
    
    @staticmethod
    def unpack(source: str) -> str:
        """Unpack JavaScript yang di-pack dengan P.A.C.K.E.R"""
        try:
            # Find the packed code
            match = re.search(
                r"}\('([^']+)',(\d+),(\d+),'([^']+)'\.split\('\|'\)",
                source
            )
            if not match:
                return source
            
            p, a, c, k = match.groups()
            a, c = int(a), int(c)
            k = k.split('|')
            
            # Base conversion
            def base_convert(num: int, base: int) -> str:
                result = ''
                while num > 0:
                    result = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"[num % base] + result
                    num //= base
                return result if result else '0'
            
            # Build replacement dictionary
            replacements = {}
            while c > 0:
                c -= 1
                key = base_convert(c, a) if c >= a else str(c)
                if c < len(k) and k[c]:
                    replacements[key] = k[c]
                else:
                    replacements[key] = key
            
            # Replace all words
            def replace_word(match):
                word = match.group(0)
                return replacements.get(word, word)
            
            unpacked = re.sub(r'\b\w+\b', replace_word, p)
            return unpacked
        except Exception as e:
            print(f"[JSUnpacker] Failed to unpack: {e}")
            return source
    
    @staticmethod
    def extract_urls_from_packed(source: str) -> List[str]:
        """Extract all URLs from packed/unpacked JavaScript"""
        urls = []
        
        # Unpack if needed
        if JSUnpacker.detect_packed(source):
            source = JSUnpacker.unpack(source)
        
        # Video URL patterns
        patterns = [
            r'(https?://[^\s<>"\'\\]+\.mp4[^\s<>"\'\\]*)',
            r'(https?://[^\s<>"\'\\]+\.m3u8[^\s<>"\'\\]*)',
            r'(https?://[^\s<>"\'\\]+\.webm[^\s<>"\'\\]*)',
            r'(https?://[^\s<>"\'\\]+\.mpd[^\s<>"\'\\]*)',
            r'["\']?(https?://[^\s<>"\'\\]*(?:video|stream|play|media|cdn)[^\s<>"\'\\]*)["\']?',
            r'file\s*[=:]\s*["\']([^"\']+)["\']',
            r'source\s*[=:]\s*["\']([^"\']+)["\']',
            r'src\s*[=:]\s*["\']([^"\']+\.(?:mp4|m3u8|webm))["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, source, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                url = url.replace('\\/', '/').replace('\\', '')
                if url.startswith('http') and len(url) > 20:
                    urls.append(url)
        
        return list(set(urls))

# ============================================
# EXTERNAL API DOWNLOADERS
# ============================================
class ExternalAPIDownloader:
    """
    Menggunakan API eksternal untuk download video.
    Ini adalah cara yang digunakan oleh banyak website downloader.
    """
    
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def try_cobalt_api(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Cobalt API - salah satu API terbaik untuk download video.
        Mendukung banyak platform termasuk TikTok, YouTube, Twitter, dll.
        """
        try:
            api_endpoints = [
                'https://api.cobalt.tools/api/json',
                'https://co.wuk.sh/api/json',
            ]
            
            for endpoint in api_endpoints:
                try:
                    session = await self.get_session()
                    payload = {
                        'url': url,
                        'vQuality': '1080',
                        'filenamePattern': 'basic',
                        'isAudioOnly': False,
                        'isNoTTWatermark': True,
                    }
                    
                    async with session.post(
                        endpoint,
                        json=payload,
                        headers={
                            **self.headers,
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        },
                        ssl=False
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == 'stream' or data.get('status') == 'redirect':
                                return {
                                    'success': True,
                                    'url': data.get('url'),
                                    'filename': data.get('filename', 'video.mp4')
                                }
                            elif data.get('status') == 'picker':
                                # Multiple options available
                                picker = data.get('picker', [])
                                if picker:
                                    return {
                                        'success': True,
                                        'url': picker[0].get('url'),
                                        'filename': 'video.mp4'
                                    }
                except Exception as e:
                    print(f"[Cobalt] Endpoint {endpoint} failed: {e}")
                    continue
            
            return None
        except Exception as e:
            print(f"[Cobalt API] Error: {e}")
            return None
    
    async def try_saveform_api(self, url: str) -> Optional[Dict[str, Any]]:
        """
        SaveFrom-style API untuk berbagai platform
        """
        try:
            session = await self.get_session()
            
            # Try different SaveFrom-style endpoints
            endpoints = [
                f'https://api.saveform.net/analysis?url={url}',
            ]
            
            for endpoint in endpoints:
                try:
                    async with session.get(endpoint, ssl=False) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('medias'):
                                medias = data['medias']
                                # Get best quality
                                best = max(medias, key=lambda x: x.get('quality', 0), default=None)
                                if best:
                                    return {
                                        'success': True,
                                        'url': best.get('url'),
                                        'filename': 'video.mp4'
                                    }
                except Exception as e:
                    continue
            
            return None
        except Exception as e:
            print(f"[SaveForm API] Error: {e}")
            return None
    
    async def try_allinonedownloader(self, url: str) -> Optional[Dict[str, Any]]:
        """
        AllInOne Downloader API
        """
        try:
            session = await self.get_session()
            
            # Encode URL
            encoded_url = base64.b64encode(url.encode()).decode()
            
            async with session.get(
                f'https://alldownloader.net/wp-json/aio-dl/video-data/?url={url}',
                ssl=False
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('medias'):
                        medias = data['medias']
                        for media in medias:
                            if media.get('url'):
                                return {
                                    'success': True,
                                    'url': media['url'],
                                    'filename': 'video.mp4'
                                }
            
            return None
        except Exception as e:
            print(f"[AllInOne API] Error: {e}")
            return None

# ============================================
# DATABASE MANAGEMENT
# ============================================
class UserDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.load_database()
    
    def load_database(self):
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
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def add_or_update_user(self, user_id, username, first_name, language_code):
        user_id_str = str(user_id)
        now = datetime.now().isoformat()
        
        if user_id_str not in self.data['users']:
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
            self.data['users'][user_id_str]['last_active'] = now
            self.data['users'][user_id_str]['username'] = username
            self.data['users'][user_id_str]['first_name'] = first_name
        
        self.save_database()
    
    def increment_download(self, user_id, download_type='video'):
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
        total_users = len(self.data['users'])
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
        sorted_users = sorted(
            self.data['users'].values(),
            key=lambda x: x['download_count'],
            reverse=True
        )
        return sorted_users[:limit]

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
✅ Wilday, Vidgo, dan streaming sites lainnya!
✅ SEMUA situs video apapun!

🔥 Fitur BARU:
• Advanced extraction seperti 9xbuddy
• JavaScript unpacking untuk bypass proteksi
• External API fallback
• Folder to ZIP support

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
🔒 JavaScript unpacking & deobfuscation
🌐 Multiple API fallback
📱 Support m3u8/HLS streams
🗜️ Auto-zip untuk multiple files

Terima kasih telah menggunakan SafeRobot! 🙏
        """,
        'invalid_url': "❌ Link tidak valid! Kirim link yang benar.",
        'universal_detected': """🎬 Link streaming terdeteksi!

⚠️ Platform ini menggunakan proteksi khusus.
Bot akan mencoba berbagai metode ekstraksi...

Pilih format download:""",
        'platform_detected': """🎬 Link dari {} terdeteksi!

Pilih format download:""",
        'downloading': "⏳ Sedang mendownload {}...\nMohon tunggu sebentar...",
        'extracting': "🔍 Mengekstrak video dari halaman...\nMencoba berbagai metode...",
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
✅ Wilday, Vidgo, and other streaming sites!
✅ ALL video sites!

🔥 NEW Features:
• Advanced extraction like 9xbuddy
• JavaScript unpacking to bypass protection
• External API fallback
• Folder to ZIP support

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
🔒 JavaScript unpacking & deobfuscation
🌐 Multiple API fallback
📱 Support m3u8/HLS streams
🗜️ Auto-zip for multiple files

Thank you for using SafeRobot! 🙏
        """,
        'invalid_url': "❌ Invalid link! Send a valid link.",
        'universal_detected': """🎬 Streaming link detected!

⚠️ This platform uses special protection.
Bot will try various extraction methods...

Choose download format:""",
        'platform_detected': """🎬 Link from {} detected!

Choose download format:""",
        'downloading': "⏳ Downloading {}...\nPlease wait...",
        'extracting': "🔍 Extracting video from page...\nTrying various methods...",
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
    try:
        user_lang = update.effective_user.language_code
        if user_lang and user_lang.lower().startswith('id'):
            return 'id'
        return 'en'
    except:
        return 'en' 

def get_text(update: Update, key: str) -> str:
    lang = get_user_language(update)
    return LANGUAGES[lang].get(key, LANGUAGES['en'].get(key, ''))

def get_text_by_lang(lang: str, key: str) -> str:
    return LANGUAGES.get(lang, LANGUAGES['en']).get(key, LANGUAGES['en'].get(key, ''))

def get_main_keyboard(update: Update):
    lang = get_user_language(update)
    keyboard = [
        [KeyboardButton(LANGUAGES[lang]['menu_about'])]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

# ============================================
# UNIVERSAL VIDEO EXTRACTOR v5
# ============================================
class UniversalExtractor:
    """
    Universal video extractor yang bekerja seperti 9xbuddy.site
    Menggunakan berbagai metode untuk mengekstrak video dari berbagai situs:
    1. yt-dlp untuk platform populer
    2. External APIs (Cobalt, dll)
    3. Playwright dengan network interception
    4. JavaScript unpacking
    5. Direct URL extraction
    """
    
    # Video URL patterns
    VIDEO_PATTERNS = [
        r'(https?://[^\s<>"\'\\]+\.mp4(?:\?[^\s<>"\'\\]*)?)',
        r'(https?://[^\s<>"\'\\]+\.m3u8(?:\?[^\s<>"\'\\]*)?)',
        r'(https?://[^\s<>"\'\\]+\.webm(?:\?[^\s<>"\'\\]*)?)',
        r'(https?://[^\s<>"\'\\]+\.mkv(?:\?[^\s<>"\'\\]*)?)',
        r'(https?://[^\s<>"\'\\]+\.mpd(?:\?[^\s<>"\'\\]*)?)',
        r'(https?://[^\s<>"\'\\]+\.ts(?:\?[^\s<>"\'\\]*)?)',
        r'(?:file|source|src|url|video|stream)\s*[=:]\s*["\']([^"\']+\.(?:mp4|m3u8|webm)[^"\']*)["\']',
        r'sources\s*:\s*\[\s*\{[^}]*["\']?(?:file|src|url)["\']?\s*:\s*["\']([^"\']+)["\']',
        r'player\.src\s*\(\s*["\']([^"\']+)["\']',
        r'["\']?(?:hls|dash|mp4)["\']?\s*:\s*["\']([^"\']+)["\']',
        r'data-(?:src|video|stream)\s*=\s*["\']([^"\']+)["\']',
        r'contentUrl["\']?\s*:\s*["\']([^"\']+)["\']',
    ]
    
    # Streaming platforms
    STREAMING_PLATFORMS = {
        'videy': ['videy.co', 'videy.net'],
        'vidgo': ['vidgo.blog'],
        'wilday': ['wilday.de'],
        'myvidplay': ['myvidplay.com'],
        'doodstream': ['doodstream.com', 'dood.to', 'dood.watch', 'dood.cx', 'dood.la', 'dood.pm', 'dood.so', 'dood.ws', 'dood.sh', 'dood.re', 'dood.wf', 'ds2play.com'],
        'streamsb': ['streamsb.net', 'streamsb.com', 'sbembed.com', 'sbplay.org', 'embedsb.com', 'pelistop.co', 'sbplay2.xyz', 'sbchill.com', 'streamsss.net', 'sbplay.one'],
        'upstream': ['upstream.to', 'upstreamcdn.co'],
        'mp4upload': ['mp4upload.com'],
        'vidoza': ['vidoza.net', 'vidoza.co'],
        'mixdrop': ['mixdrop.co', 'mixdrop.to', 'mixdrop.ch', 'mixdrop.sx'],
        'streamtape': ['streamtape.com', 'streamtape.net', 'streamta.pe', 'strtape.cloud', 'strcloud.link'],
        'fembed': ['fembed.com', 'feurl.com', 'femax20.com', 'fcdn.stream', 'diasfem.com'],
        'filemoon': ['filemoon.sx', 'filemoon.to', 'filemoon.in'],
        'voe': ['voe.sx', 'voe.to'],
        'vtube': ['vtube.to', 'vtbe.to'],
        'streamlare': ['streamlare.com'],
        'supervideo': ['supervideo.tv'],
        'other_streaming': []
    }
    
    # Platforms well-supported by yt-dlp
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
        'bilibili': ['bilibili.com', 'b23.tv'],
        'pornhub': ['pornhub.com'],
        'xvideos': ['xvideos.com'],
        'xnxx': ['xnxx.com'],
    }
    
    def __init__(self):
        self.session = None
        self.external_api = ExternalAPIDownloader()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
    
    def detect_platform(self, url: str) -> Tuple[str, bool]:
        """Deteksi platform dari URL, return (platform_name, is_streaming)"""
        try:
            domain = urlparse(url).netloc.lower()
            domain = domain.replace('www.', '')
            
            for platform, domains in self.YTDLP_PLATFORMS.items():
                if any(d in domain for d in domains):
                    return (platform.upper(), False)
            
            for platform, domains in self.STREAMING_PLATFORMS.items():
                if any(d in domain for d in domains):
                    return (platform.upper(), True)
            
            return ('OTHER_STREAMING', True)
        except:
            return ('UNKNOWN', True)
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            connector = aiohttp.TCPConnector(ssl=False, limit=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout, 
                headers=self.headers,
                connector=connector
            )
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
        await self.external_api.close_session()
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML page content"""
        try:
            session = await self.get_session()
            async with session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    return await response.text()
                return None
        except Exception as e:
            print(f"[Fetch Error] {e}")
            return None
    
    async def extract_video_urls_from_html(self, html: str, base_url: str) -> List[str]:
        """Extract video URLs dari HTML page dengan JS unpacking"""
        video_urls = []
        
        # Extract dari packed JavaScript
        packed_urls = JSUnpacker.extract_urls_from_packed(html)
        video_urls.extend(packed_urls)
        
        # Extract dengan patterns
        for pattern in self.VIDEO_PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                url = url.replace('\\/', '/').replace('\\', '')
                
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    parsed = urlparse(base_url)
                    url = f"{parsed.scheme}://{parsed.netloc}{url}"
                elif not url.startswith('http'):
                    url = urljoin(base_url, url)
                
                if self._is_valid_video_url(url):
                    video_urls.append(url)
        
        # Remove duplicates
        seen = set()
        unique_urls = []
        for url in video_urls:
            url_clean = url.split('?')[0]
            if url_clean not in seen and len(url) > 20:
                seen.add(url_clean)
                unique_urls.append(url)
        
        return unique_urls
    
    def _is_valid_video_url(self, url: str) -> bool:
        """Validasi apakah URL adalah video yang valid"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Skip tracking/analytics
            skip_domains = ['google', 'facebook', 'analytics', 'doubleclick', 'adsense', 'tracker', 'pixel']
            if any(skip in parsed.netloc.lower() for skip in skip_domains):
                return False
            
            video_extensions = ['.mp4', '.m3u8', '.webm', '.mkv', '.avi', '.mov', '.flv', '.mpd', '.ts']
            path_lower = parsed.path.lower()
            
            if any(ext in path_lower for ext in video_extensions):
                return True
            
            video_paths = ['/video', '/v/', '/stream', '/play', '/embed', '/media', '/hls/', '/dash/', '/cdn/']
            if any(vp in path_lower for vp in video_paths):
                return True
            
            if 'video' in url.lower() or 'stream' in url.lower() or 'media' in url.lower():
                return True
            
            return False
        except:
            return False
    
    async def download_with_ytdlp(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """Download menggunakan yt-dlp"""
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
                'geo_bypass': True,
                'nocheckcertificate': True,
                'extractor_args': {
                    'youtube': {'player_client': ['android', 'web']},
                },
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
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                })
            
            loop = asyncio.get_event_loop()
            
            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if format_type == 'audio':
                        filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                    else:
                        filename = ydl.prepare_filename(info)
                        if not os.path.exists(filename):
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
            if 'is not a valid URL' in error_msg:
                error_msg = 'Invalid URL'
            elif 'Video unavailable' in error_msg:
                error_msg = 'Video unavailable or private'
            elif 'Unsupported URL' in error_msg:
                error_msg = 'Platform not supported by yt-dlp'
            
            return {'success': False, 'error': error_msg}
    
    async def download_direct_url(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """Download dari direct URL"""
        try:
            parsed = urlparse(url)
            path_lower = parsed.path.lower()
            
            if '.m3u8' in path_lower or '.m3u8' in url.lower():
                return await self.download_hls_stream(url, format_type)
            
            extension = 'mp4'
            if '.webm' in path_lower:
                extension = 'webm'
            elif '.mkv' in path_lower:
                extension = 'mkv'
            elif '.ts' in path_lower:
                extension = 'ts'
            
            filename = get_unique_filename(DOWNLOAD_PATH, extension)
            
            timeout = aiohttp.ClientTimeout(total=300, connect=30)
            connector = aiohttp.TCPConnector(ssl=False)
            
            # Use referer from the same domain
            download_headers = {
                **self.headers,
                'Referer': f"{parsed.scheme}://{parsed.netloc}/",
                'Origin': f"{parsed.scheme}://{parsed.netloc}"
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=download_headers, connector=connector) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        content_length = int(response.headers.get('content-length', 0))
                        print(f"[Download] Downloading {content_length} bytes from {url[:80]}...")
                        
                        with open(filename, 'wb') as f:
                            downloaded = 0
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                f.write(chunk)
                                downloaded += len(chunk)
                        
                        if os.path.exists(filename) and os.path.getsize(filename) > 0:
                            # Convert .ts to .mp4 if needed
                            if extension == 'ts':
                                mp4_filename = filename.replace('.ts', '.mp4')
                                try:
                                    process = await asyncio.create_subprocess_exec(
                                        'ffmpeg', '-y', '-i', filename,
                                        '-c', 'copy', '-bsf:a', 'aac_adtstoasc', mp4_filename,
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE
                                    )
                                    await process.communicate()
                                    if os.path.exists(mp4_filename) and os.path.getsize(mp4_filename) > 0:
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
                            return {'success': False, 'error': 'Downloaded file is empty'}
                    
                    elif response.status == 403:
                        return {'success': False, 'error': 'Access forbidden - video is protected'}
                    elif response.status == 404:
                        return {'success': False, 'error': 'Video not found'}
                    else:
                        return {'success': False, 'error': f'HTTP {response.status}'}
                        
        except asyncio.TimeoutError:
            return {'success': False, 'error': 'Download timeout - file too large or slow connection'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def download_hls_stream(self, m3u8_url: str, format_type: str = 'video') -> Dict[str, Any]:
        """Download HLS/m3u8 stream menggunakan ffmpeg"""
        try:
            if format_type == 'audio':
                extension = 'mp3'
                ffmpeg_opts = ['-vn', '-acodec', 'libmp3lame', '-q:a', '2']
            else:
                extension = 'mp4'
                ffmpeg_opts = ['-c', 'copy', '-bsf:a', 'aac_adtstoasc']
            
            filename = get_unique_filename(DOWNLOAD_PATH, extension)
            
            # Get referer from URL
            parsed = urlparse(m3u8_url)
            referer = f"{parsed.scheme}://{parsed.netloc}/"
            
            cmd = [
                'ffmpeg',
                '-y',
                '-headers', f'User-Agent: {self.headers["User-Agent"]}\r\nReferer: {referer}\r\n',
                '-i', m3u8_url,
                *ffmpeg_opts,
                '-movflags', '+faststart',
                filename
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
            
            if process.returncode == 0 and os.path.exists(filename) and os.path.getsize(filename) > 0:
                return {
                    'success': True,
                    'filepath': filename,
                    'title': 'HLS Stream',
                    'duration': 0
                }
            else:
                stderr_text = stderr.decode()[:200] if stderr else 'Unknown error'
                return {'success': False, 'error': f'FFmpeg failed: {stderr_text}'}
                
        except asyncio.TimeoutError:
            return {'success': False, 'error': 'HLS download timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def extract_with_playwright(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """
        Extract video menggunakan Playwright dengan network interception.
        Ini adalah teknik yang sama digunakan browser apps untuk menangkap video.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {'success': False, 'error': 'Playwright not available'}
        
        captured_urls = []
        
        try:
            print(f"[Playwright] Starting browser for: {url}")
            
            async with async_playwright() as p:
                # Launch dengan stealth settings
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
                        '--disable-blink-features=AutomationControlled',
                        '--disable-infobars',
                        '--window-size=1920,1080',
                        '--disable-extensions',
                    ]
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    java_script_enabled=True,
                    bypass_csp=True,
                    ignore_https_errors=True,
                    locale='en-US',
                    timezone_id='America/New_York',
                )
                
                # Inject stealth scripts
                await context.add_init_script("""
                    // Webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Chrome runtime
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                
                page = await context.new_page()
                
                # Intercept ALL network requests
                async def handle_request(route, request):
                    await route.continue_()
                
                async def handle_response(response):
                    try:
                        response_url = response.url
                        content_type = response.headers.get('content-type', '')
                        
                        # Check if it's a video
                        is_video = (
                            '.mp4' in response_url.lower() or
                            '.m3u8' in response_url.lower() or
                            '.webm' in response_url.lower() or
                            '.ts' in response_url.lower() or
                            '.mpd' in response_url.lower() or
                            'video' in content_type.lower() or
                            'mpegurl' in content_type.lower() or
                            'octet-stream' in content_type.lower() or
                            '/video/' in response_url.lower() or
                            '/stream/' in response_url.lower() or
                            '/hls/' in response_url.lower() or
                            '/media/' in response_url.lower() or
                            '/cdn/' in response_url.lower()
                        )
                        
                        # Skip tracking
                        skip_domains = ['google', 'facebook', 'analytics', 'doubleclick', 'adsense', 'tracker']
                        should_skip = any(skip in response_url.lower() for skip in skip_domains)
                        
                        if is_video and response.status == 200 and not should_skip:
                            content_length = int(response.headers.get('content-length', 0))
                            print(f"[Playwright] Captured: {response_url[:80]}... (size: {content_length})")
                            captured_urls.append({
                                'url': response_url,
                                'content_type': content_type,
                                'size': content_length
                            })
                    except Exception:
                        pass
                
                page.on('response', handle_response)
                
                # Navigate to page
                try:
                    await page.goto(url, wait_until='networkidle', timeout=45000)
                except Exception:
                    try:
                        await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                    except Exception:
                        pass
                
                # Wait for video to load
                await asyncio.sleep(5)
                
                # Try to click play button
                play_selectors = [
                    'button[aria-label*="play" i]',
                    'button[aria-label*="Play" i]',
                    '.play-button',
                    '.vjs-big-play-button',
                    '.plyr__control--overlaid',
                    '[class*="play"]',
                    '.jw-icon-playback',
                    '.jw-icon-display',
                    'video',
                    '.video-js',
                ]
                
                for selector in play_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            await element.click()
                            await asyncio.sleep(3)
                            break
                    except:
                        continue
                
                # Extract from page scripts
                video_sources = await page.evaluate('''() => {
                    const sources = [];
                    
                    // Video elements
                    document.querySelectorAll('video').forEach(video => {
                        if (video.src) sources.push(video.src);
                        if (video.currentSrc) sources.push(video.currentSrc);
                        video.querySelectorAll('source').forEach(source => {
                            if (source.src) sources.push(source.src);
                        });
                    });
                    
                    // Iframes
                    document.querySelectorAll('iframe').forEach(iframe => {
                        if (iframe.src && iframe.src.includes('embed')) {
                            sources.push(iframe.src);
                        }
                    });
                    
                    // Search in all scripts for video URLs
                    document.querySelectorAll('script').forEach(script => {
                        const text = script.textContent || '';
                        const patterns = [
                            /["']([^"']*\.m3u8[^"']*)['"]/gi,
                            /["']([^"']*\.mp4[^"']*)['"]/gi,
                            /source\s*[=:]\s*["']([^"']+)['"]/gi,
                            /file\s*[=:]\s*["']([^"']+)['"]/gi,
                            /src\s*[=:]\s*["']([^"']+\.(?:mp4|m3u8))['"]/gi,
                            /url\s*[=:]\s*["']([^"']+\.(?:mp4|m3u8))['"]/gi,
                            /hls\s*[=:]\s*["']([^"']+)['"]/gi,
                            /dash\s*[=:]\s*["']([^"']+)['"]/gi,
                            /video_url\s*[=:]\s*["']([^"']+)['"]/gi,
                            /contentUrl['"]*\s*[=:]\s*["']([^"']+)['"]/gi,
                        ];
                        patterns.forEach(pattern => {
                            let match;
                            while ((match = pattern.exec(text)) !== null) {
                                const url = match[1].replace(/\\\//g, '/');
                                if (url.startsWith('http') || url.startsWith('//')) {
                                    sources.push(url);
                                }
                            }
                        });
                    });
                    
                    // Check window/global variables
                    const checkVars = ['source', 'videoUrl', 'video_url', 'file', 'src', 'streamUrl', 'hlsUrl', 'mp4Url'];
                    checkVars.forEach(varName => {
                        try {
                            const value = window[varName];
                            if (typeof value === 'string' && value.startsWith('http')) {
                                sources.push(value);
                            }
                        } catch(e) {}
                    });
                    
                    return sources;
                }''')
                
                # Add extracted sources
                for source in video_sources:
                    if source and ('mp4' in source.lower() or 'm3u8' in source.lower() or 'video' in source.lower()):
                        url_clean = source.replace('\\/', '/')
                        if url_clean.startswith('//'):
                            url_clean = 'https:' + url_clean
                        captured_urls.append({
                            'url': url_clean,
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
                url_clean = item['url'].split('?')[0]
                if url_clean not in seen:
                    seen.add(url_clean)
                    unique_urls.append(item)
            
            # Sort by priority
            def priority(item):
                url = item['url'].lower()
                size = item['size']
                if '.m3u8' in url:
                    return (0, -size)
                elif '.mp4' in url:
                    return (1, -size)
                elif 'video' in url or 'stream' in url:
                    return (2, -size)
                else:
                    return (3, -size)
            
            unique_urls.sort(key=priority)
            
            # Try to download each URL
            for item in unique_urls[:8]:
                video_url = item['url']
                print(f"[Playwright] Trying: {video_url[:80]}...")
                
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
    
    async def extract(self, url: str, format_type: str = 'video') -> Dict[str, Any]:
        """
        Main extraction method - mencoba berbagai metode secara berurutan:
        1. External APIs (Cobalt, dll) - untuk platform populer
        2. yt-dlp - untuk platform yang didukung
        3. Playwright browser automation - untuk streaming sites
        4. Direct HTML parsing dengan JS unpacking
        """
        platform, is_streaming = self.detect_platform(url)
        
        print(f"\n{'='*50}")
        print(f"[Extractor] Platform: {platform}, Is Streaming: {is_streaming}")
        print(f"[Extractor] URL: {url}")
        print(f"{'='*50}\n")
        
        errors = []
        
        # Method 1: Try External APIs first for popular platforms
        if not is_streaming:
            print(f"[Extractor] Method 1: Trying External APIs...")
            api_result = await self.external_api.try_cobalt_api(url)
            if api_result and api_result.get('success'):
                print(f"[Extractor] Cobalt API succeeded, downloading...")
                download_result = await self.download_direct_url(api_result['url'], format_type)
                if download_result['success']:
                    return download_result
                errors.append(f"Cobalt download: {download_result.get('error', 'Failed')}")
        
        # Method 2: yt-dlp for known platforms
        if not is_streaming or platform in ['YOUTUBE', 'TWITTER', 'INSTAGRAM', 'TIKTOK', 'FACEBOOK']:
            print(f"[Extractor] Method 2: Trying yt-dlp...")
            result = await self.download_with_ytdlp(url, format_type)
            if result['success']:
                print(f"[Extractor] yt-dlp succeeded!")
                return result
            errors.append(f"yt-dlp: {result.get('error', 'Unknown error')}")
        
        # Method 3: Playwright browser automation
        if PLAYWRIGHT_AVAILABLE:
            print(f"[Extractor] Method 3: Trying Playwright browser extraction...")
            result = await self.extract_with_playwright(url, format_type)
            if result['success']:
                print(f"[Extractor] Playwright succeeded!")
                return result
            errors.append(f"Playwright: {result.get('error', 'Unknown error')}")
        
        # Method 4: Direct HTML parsing with JS unpacking
        print(f"[Extractor] Method 4: Trying HTML parsing with JS unpacking...")
        html = await self.fetch_page(url)
        if html:
            video_urls = await self.extract_video_urls_from_html(html, url)
            print(f"[Extractor] Found {len(video_urls)} video URLs from HTML")
            
            for video_url in video_urls[:10]:
                print(f"[Extractor] Trying: {video_url[:80]}...")
                if '.m3u8' in video_url.lower():
                    result = await self.download_hls_stream(video_url, format_type)
                else:
                    result = await self.download_direct_url(video_url, format_type)
                
                if result['success']:
                    print(f"[Extractor] Direct URL download succeeded!")
                    return result
            
            errors.append("HTML parsing: No working video URLs found")
        else:
            errors.append("HTML parsing: Failed to fetch page")
        
        # Method 5: Final yt-dlp fallback
        if is_streaming:
            print(f"[Extractor] Method 5: Final yt-dlp fallback...")
            result = await self.download_with_ytdlp(url, format_type)
            if result['success']:
                return result
            errors.append(f"yt-dlp fallback: {result.get('error', 'Unknown error')}")
        
        # All methods failed
        combined_error = " | ".join(errors[-3:])
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
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            print(f"Failed to send to {user_id_str}: {e}")
    
    await status_msg.edit_text(
        f"✅ Broadcast selesai!\n\n"
        f"✅ Berhasil: {success}\n"
        f"❌ Gagal: {failed}"
    )

async def zip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /zip - ZIP folder downloads"""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("❌ Perintah ini hanya untuk owner bot!")
        return
    
    # Check if downloads folder has files
    files = [f for f in os.listdir(DOWNLOAD_PATH) if os.path.isfile(os.path.join(DOWNLOAD_PATH, f))]
    
    if not files:
        await update.message.reply_text("📁 Folder downloads kosong!")
        return
    
    status_msg = await update.message.reply_text(f"🗜️ Membuat ZIP dari {len(files)} file...")
    
    try:
        zip_path = await create_zip_from_folder(DOWNLOAD_PATH)
        
        file_size = os.path.getsize(zip_path)
        max_size = 50 * 1024 * 1024  # 50MB
        
        if file_size > max_size:
            await status_msg.edit_text(f"❌ File ZIP terlalu besar ({file_size / 1024 / 1024:.1f}MB)!\nMaksimal 50MB untuk Telegram.")
            os.remove(zip_path)
            return
        
        await status_msg.edit_text("📤 Mengirim file ZIP...")
        
        with open(zip_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                caption=f"📦 Downloads Archive\n{len(files)} files\nSize: {file_size / 1024 / 1024:.1f}MB"
            )
        
        await status_msg.delete()
        os.remove(zip_path)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk semua pesan text"""
    user = update.effective_user
    text = update.message.text.strip()
    lang = get_user_language(update)
    
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
    
    url_id = str(hash(url))[-8:]
    context.user_data[url_id] = {
        'url': url,
        'platform': platform,
        'is_streaming': is_streaming
    }
    
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
    
    if format_code == 'v':
        format_type = 'video'
    elif format_code == 'a':
        format_type = 'audio'
    elif format_code == 'd':
        format_type = 'video'
    else:
        format_type = 'video'
    
    if is_streaming:
        status_text = f"🔍 Mengekstrak video dari {platform}...\n\n⏳ Mencoba berbagai metode:\n1️⃣ External APIs\n2️⃣ yt-dlp\n3️⃣ Browser extraction\n4️⃣ HTML parsing\n\nMohon tunggu..."
    else:
        format_name = 'video' if format_type == 'video' else 'audio'
        status_text = f"⏳ Sedang mendownload {format_name}...\nMohon tunggu sebentar..."
    
    status_msg = await query.message.reply_text(status_text)
    
    try:
        result = await extractor.extract(url, format_type)
        
        if result['success']:
            await status_msg.edit_text("📤 Mengirim file...")
            
            filepath = result['filepath']
            title = safe_title(result.get('title', 'Media'))
            
            if not os.path.exists(filepath):
                await status_msg.edit_text("❌ File tidak ditemukan setelah download!")
                return
            
            file_size = os.path.getsize(filepath)
            max_size = 50 * 1024 * 1024
            
            if file_size == 0:
                await status_msg.edit_text("❌ File kosong! Video mungkin diproteksi.")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return
            
            if format_type == 'audio':
                caption = f"🎵 {title}\n\n🔥 Downloaded by @SafeRobot"
            else:
                caption = f"🎥 {title}\n\n🔥 Downloaded by @SafeRobot"
            
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
                
                db.increment_download(query.from_user.id, format_type)
                await status_msg.delete()
                
            except Exception as send_error:
                print(f"Send error: {send_error}")
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
            
            if os.path.exists(filepath):
                os.remove(filepath)
            
            if url_id in context.user_data:
                del context.user_data[url_id]
        
        else:
            error_text = result.get('error', 'Unknown error')
            if len(error_text) > 300:
                error_text = error_text[:300] + "..."
            
            error_msg = f"❌ Download gagal!\n\nError: {error_text}\n\nTips:\n• Pastikan link dapat diakses\n• Beberapa situs memiliki proteksi yang kuat\n• Coba kirim link lagi\n• Hubungi admin jika masalah berlanjut"
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
    print("🤖 SafeRobot v5.0 - Universal Downloader Starting...")
    print("🌐 Multi-language support: ID/EN")
    print("🎬 Universal video extraction enabled")
    print("🔧 Features:")
    print("   • External API fallback (Cobalt, etc)")
    print("   • JavaScript unpacking/deobfuscation")
    print("   • Playwright browser automation")
    print("   • Network request interception")
    print("   • ZIP folder support")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"💾 Database: {DATABASE_PATH}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("zip", zip_command))
    
    # Message and callback handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    print("\n✅ SafeRobot is running!")
    print("📝 Owner commands:")
    print("   /stats - Lihat statistik pengguna")
    print("   /broadcast <pesan> - Kirim pesan ke semua user")
    print("   /zip - ZIP semua file di folder downloads")
    print("\nPress Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
