import os
import re
import sys
import asyncio
import json
import requests
import subprocess
import base64
import time
from datetime import datetime, timedelta
from http.cookiejar import MozillaCookieJar
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
from urllib.parse import urlparse, parse_qs, urljoin, unquote, quote
from bs4 import BeautifulSoup
import hashlib
import zipfile
import concurrent.futures
from typing import List, Dict, Optional, Tuple, Any

# ============================================
# KONFIGURASI
# ============================================
BOT_TOKEN = "7389890441:AAGkXEXHedGHYrmXq3Vp5RlT8Y5_kBChL5Q"
OWNER_ID = 6683929810  # GANTI DENGAN USER ID TELEGRAM ANDA
DOWNLOAD_PATH = "./downloads/"
DATABASE_PATH = "./users_database.json"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit Telegram
MAX_ARCHIVE_ITEMS = int(os.getenv("MAX_ARCHIVE_ITEMS", "10"))
MAX_ARCHIVE_SIZE = int(os.getenv("MAX_ARCHIVE_SIZE", str(MAX_FILE_SIZE)))
ALLOW_PLAYLIST_ZIP = os.getenv("ALLOW_PLAYLIST_ZIP", "1") == "1"
COOKIE_FILE = os.getenv("COOKIE_FILE", "./cookies.txt")
AUTO_INSTALL_PLAYWRIGHT = os.getenv("AUTO_INSTALL_PLAYWRIGHT", "1") == "1"
PLAYWRIGHT_INSTALL_TIMEOUT = int(os.getenv("PLAYWRIGHT_INSTALL_TIMEOUT", "600"))

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ============================================
# UNIVERSAL VIDEO EXTRACTOR (Like 9xbuddy)
# ============================================
class UniversalVideoExtractor:
    """
    Universal video extractor that works like 9xbuddy.site
    Uses network interception to capture ALL video/audio streams
    """
    
    # External API services for downloading (like 9xbuddy uses)
    EXTERNAL_APIS = [
        # Cobalt API - reliable for many platforms
        {
            'name': 'cobalt',
            'url': 'https://co.wuk.sh/api/json',
            'method': 'POST',
            'headers': {'Accept': 'application/json', 'Content-Type': 'application/json'},
            'body_template': {'url': '{url}', 'vCodec': 'h264', 'vQuality': '720', 'aFormat': 'mp3'},
            'response_key': 'url'
        },
        {
            'name': 'cobalt-alt',
            'url': 'https://api.cobalt.tools/api/json',
            'method': 'POST',
            'headers': {'Accept': 'application/json', 'Content-Type': 'application/json'},
            'body_template': {'url': '{url}', 'vCodec': 'h264', 'vQuality': '720', 'aFormat': 'mp3'},
            'response_key': 'url'
        },
        # SaveFrom-like API
        {
            'name': 'savefrom-worker',
            'url': 'https://worker.sf-tools.com/savefrom.php',
            'method': 'POST',
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'data_template': 'sf_url={url}&sf_submit=&new=2&lang=en&app=&country=en&os=Windows&browser=Chrome&channel=main&sf-b=1',
            'response_path': ['url', 'hosting', 'url_info', 'src']
        },
        # AllTubeDownload
        {
            'name': 'alltubedownload',
            'url': 'https://alltubedownload.net/api/v1/video',
            'method': 'GET',
            'params': {'url': '{url}'},
            'response_key': 'url'
        },
        # Y2Mate-like API
        {
            'name': 'y2mate-worker',
            'url': 'https://yt1s.pro/api/json/search',
            'method': 'POST',
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'data_template': 'q={url}&vt=mp4',
            'response_path': ['links', 'mp4', 'auto', 'k']
        },
        # SnapSave-like API
        {
            'name': 'snapsave',
            'url': 'https://snapsave.app/action.php',
            'method': 'POST',
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'data_template': 'url={url}',
            'response_path': ['data', 'url', 'video_url']
        },
        # SSYouTube API
        {
            'name': 'ssyoutube',
            'url': 'https://ssyoutube.com/api/convert',
            'method': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body_template': {'url': '{url}', 'quality': 'highestvideo'},
            'response_key': 'url'
        },
        # 9xbuddy-style direct fetch
        {
            'name': '9xbuddy-fetch',
            'url': 'https://9xbuddy.in/process',
            'method': 'POST',
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'data_template': 'url={url}',
            'response_path': ['links', 'url', 'downloadUrl']
        },
        # Loader.to API
        {
            'name': 'loaderto',
            'url': 'https://loader.to/api/button/',
            'method': 'GET',
            'params': {'url': '{url}', 'f': 'mp4'},
            'response_key': 'download_url'
        }
    ]
    
    # Additional fallback services (tried after main APIs fail)
    FALLBACK_EXTRACTORS = [
        {
            'name': 'keepvid',
            'url': 'https://keepvid.works/api/json',
            'method': 'POST',
            'data': {'url': '{url}'}
        },
        {
            'name': 'tubeoffline',
            'url': 'https://www.tubeoffline.com/download.php',
            'method': 'POST', 
            'data': {'link': '{url}'}
        }
    ]
    
    # Videy/Videq family specific CDN patterns
    VIDEY_CDN_PATTERNS = [
        r'https?://[a-z0-9-]+\.(?:videy|videq|vidgo|vidoy|vide[0-9]|videypro|vidqy|vidbre|avdeq|vdaq|cdnvideq)\.[a-z]+/[^\s"\'<>]+',
        r'https?://cdn[0-9]*\.[^\s"\'<>]+/(?:v|e|d|f|stream)/[^\s"\'<>]+',
        r'https?://[a-z]+[0-9]*\.(?:xyz|pro|cc|to|io|co|me|net)/[^\s"\'<>]+\.mp4[^\s"\'<>]*',
        r'https?://[^\s"\'<>]+/hls/[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
        r'https?://[^\s"\'<>]+/embed/[^\s"\'<>]+',
    ]
    
    # Video URL patterns to look for (expanded for better detection)
    VIDEO_PATTERNS = [
        # Direct video files
        r'https?://[^\s"\'<>]+\.(?:mp4|webm|mkv|avi|mov|m4v|flv)(?:\?[^\s"\'<>]*)?',
        r'https?://[^\s"\'<>]+\.(?:m3u8|mpd)(?:\?[^\s"\'<>]*)?',
        r'https?://[^\s"\'<>]+\.ts(?:\?[^\s"\'<>]*)?',
        
        # Common video hosting patterns
        r'(?:src|source|file|video|stream|url|href)["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8|webm|mpd)[^"\']*)["\']',
        r'sources\s*:\s*\[\s*\{[^}]*(?:file|src|url)\s*:\s*["\']([^"\']+)["\']',
        r'player\.(?:src|load|setup)\s*\(\s*["\']([^"\']+)["\']',
        
        # JWPlayer patterns
        r'jwplayer\([^)]*\)\.setup\(\s*\{[^}]*sources\s*:\s*\[[^\]]*file\s*:\s*["\']([^"\']+)["\']',
        r'file\s*:\s*["\']([^"\']+\.(?:mp4|m3u8|webm))["\']',
        r'sources\s*:\s*\[\s*\{[^}]*src\s*:\s*["\']([^"\']+)["\']',
        
        # Video.js patterns  
        r'videojs\([^)]*\)\.src\(\s*["\']([^"\']+)["\']',
        r'data-video-src=["\']([^"\']+)["\']',
        
        # Plyr patterns
        r'Plyr\([^)]*,\s*\{[^}]*sources\s*:\s*\[[^\]]*src\s*:\s*["\']([^"\']+)["\']',
        
        # Generic player patterns
        r'Playerjs\s*\(\s*\{[^}]*file\s*:\s*["\']([^"\']+)["\']',
        r'player\.load\s*\(\s*["\']([^"\']+)["\']',
        r'(?:video|stream)(?:Url|URL|Src|SRC|Source|SOURCE)\s*[:=]\s*["\']([^"\']+)["\']',
        
        # CDN/streaming patterns
        r'https?://[^\s"\'<>]*(?:cdn|stream|video|media|player)[^\s"\'<>]*\.(?:mp4|m3u8|webm)[^\s"\'<>]*',
        
        # Base64 encoded URLs
        r'atob\s*\(\s*["\']([A-Za-z0-9+/=]+)["\']',
        r'btoa\s*\(\s*["\']([^"\']+)["\']',
        
        # Data attributes
        r'data-(?:src|video|url|file|stream)=["\']([^"\']+)["\']',
        
        # API endpoints
        r'(?:api|download|stream|get)[^\s"\'<>]*/(?:video|file|stream|media)/[a-zA-Z0-9_-]+',
        
        # Hex/Unicode encoded
        r'\\x68\\x74\\x74\\x70[^"\']+',
        r'\\u0068\\u0074\\u0074\\u0070[^"\']+',
        
        # New patterns for streaming sites
        r'(?:download|direct|link|source|stream)_?(?:url|link|src)["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'(?:hls|dash|mpd)_?(?:url|src|manifest)["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        
        # JSON embedded video URLs
        r'"(?:url|file|src|source|video|stream|download)":\s*"(https?://[^"]+)"',
        r"'(?:url|file|src|source|video|stream|download)':\s*'(https?://[^']+)'",
        
        # Videy/Videq specific patterns
        r'https?://[a-z0-9-]+\.[a-z]+/(?:v|e|d|f|embed|stream)/[a-zA-Z0-9]+',
        r'https?://cdn[0-9]*\.[^\s"\'<>]+/[^\s"\'<>]+\.mp4',
        
        # HLS segments and playlists
        r'https?://[^\s"\'<>]+/(?:hls|live|stream)/[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
        r'https?://[^\s"\'<>]+/(?:manifest|playlist)[^\s"\'<>]*\.m3u8[^\s"\'<>]*',
        
        # Common streaming domains
        r'https?://[^\s"\'<>]*(?:\.akamaized\.net|\.cloudfront\.net|\.fastly\.net)[^\s"\'<>]+\.(?:mp4|m3u8|ts)',
        
        # Eval/encoded function results often contain URLs
        r'(?:decodeURIComponent|unescape)\(["\']([^"\']+)["\']',
        
        # Video player configuration objects
        r'config\s*[:=]\s*\{[^}]*["\']?(?:url|file|src)["\']?\s*:\s*["\']([^"\']+)["\']',
        r'options\s*[:=]\s*\{[^}]*["\']?(?:url|file|src)["\']?\s*:\s*["\']([^"\']+)["\']',
        
        # Iframe with video
        r'<iframe[^>]+src=["\']([^"\']+(?:embed|player|video)[^"\']*)["\']',
    ]
    
    # MIME types that indicate video/audio content
    MEDIA_MIME_TYPES = [
        'video/', 'audio/',
        'application/x-mpegurl', 'application/vnd.apple.mpegurl',
        'application/dash+xml', 'application/octet-stream'
    ]
    
    def __init__(self):
        self._playwright_ready = False
        self._browser = None
    
    async def extract_videy_family(self, url: str) -> List[str]:
        """
        Specialized extractor for Videy/Videq family platforms
        These platforms use similar JavaScript obfuscation techniques
        """
        video_urls = []
        
        try:
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': url
            }
            
            # Step 1: Get the embed page
            print(f"[VideyExtractor] Fetching embed page: {url}")
            resp = session.get(url, headers=headers, timeout=30, allow_redirects=True)
            html = resp.text
            resolved_url = resp.url
            
            # Step 2: Extract video ID from URL
            video_id = None
            id_patterns = [
                r'/e/([a-zA-Z0-9]+)',
                r'/v/([a-zA-Z0-9]+)',
                r'/embed/([a-zA-Z0-9]+)',
                r'/watch/([a-zA-Z0-9]+)',
                r'/([a-zA-Z0-9]{8,12})(?:\?|$|/)',
            ]
            
            for pattern in id_patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    break
            
            print(f"[VideyExtractor] Video ID: {video_id}")
            
            # Step 3: Look for packed JavaScript and decode it
            packed_patterns = [
                r"eval\(function\(p,a,c,k,e,[rd]\).*?\.split\('\|'\)\)",
                r'<script[^>]*>([^<]*eval\(function[^<]+)</script>',
            ]
            
            decoded_parts = []
            for pattern in packed_patterns:
                matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    decoded = self._decode_packed_js(match if isinstance(match, str) else match[0])
                    if decoded:
                        decoded_parts.append(decoded)
            
            # Combine original HTML with decoded parts
            full_content = html + '\n'.join(decoded_parts)
            
            # Step 4: Look for video URLs in the content
            video_patterns = [
                # Direct MP4/M3U8 URLs
                r'https?://[^\s"\'<>]+\.mp4(?:\?[^\s"\'<>]*)?',
                r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?',
                
                # Videy CDN patterns
                r'https?://cdn[0-9]*\.[^\s"\'<>]+/[^\s"\'<>]+\.mp4[^\s"\'<>]*',
                r'https?://[a-z0-9-]+\.[a-z]+/v/[^\s"\'<>]+',
                r'https?://[a-z0-9-]+\.[a-z]+/d/[^\s"\'<>]+',
                
                # JavaScript source patterns
                r'(?:file|source|src|url|video)[\'":\s]+[\'"]?(https?://[^\s"\'<>]+\.(?:mp4|m3u8|webm)[^\s"\'<>]*)[\'"]?',
                r'sources\s*:\s*\[\s*\{[^}]*[\'"]?file[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]',
                r'player\.src\s*\([\'"]([^\'"]+)[\'"]',
            ]
            
            for pattern in video_patterns:
                matches = re.findall(pattern, full_content, re.IGNORECASE)
                video_urls.extend(matches)
            
            # Step 5: Try to find API endpoints
            parsed = urlparse(resolved_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            if video_id:
                # Common Videy family API endpoints
                api_endpoints = [
                    f'{base_url}/api/source/{video_id}',
                    f'{base_url}/api/video/{video_id}',
                    f'{base_url}/api/file/{video_id}',
                    f'{base_url}/dl?op=download_orig&id={video_id}',
                    f'{base_url}/download/{video_id}',
                    f'{base_url}/get/{video_id}',
                    f'{base_url}/source/{video_id}',
                    f'{base_url}/stream/{video_id}',
                ]
                
                for endpoint in api_endpoints:
                    try:
                        print(f"[VideyExtractor] Trying API: {endpoint}")
                        api_resp = session.get(endpoint, headers={**headers, 'Referer': resolved_url}, timeout=10)
                        
                        if api_resp.status_code == 200:
                            # Try JSON response
                            try:
                                data = api_resp.json()
                                for key in ['url', 'file', 'src', 'source', 'link', 'download', 'stream']:
                                    if key in data:
                                        val = data[key]
                                        if isinstance(val, str) and val.startswith('http'):
                                            video_urls.append(val)
                                        elif isinstance(val, list):
                                            for item in val:
                                                if isinstance(item, str):
                                                    video_urls.append(item)
                                                elif isinstance(item, dict):
                                                    for subkey in ['url', 'file', 'src', 'link']:
                                                        if subkey in item:
                                                            video_urls.append(item[subkey])
                            except json.JSONDecodeError:
                                # Plain text response
                                if api_resp.text.startswith('http'):
                                    video_urls.append(api_resp.text.strip())
                                else:
                                    # Look for URLs in response
                                    for pattern in video_patterns[:3]:
                                        matches = re.findall(pattern, api_resp.text, re.IGNORECASE)
                                        video_urls.extend(matches)
                    except:
                        continue
                
                # POST requests
                for endpoint in api_endpoints[:3]:
                    try:
                        api_resp = session.post(
                            endpoint,
                            headers={**headers, 'Referer': resolved_url, 'Content-Type': 'application/x-www-form-urlencoded'},
                            data={'id': video_id, 'op': 'download_orig'},
                            timeout=10
                        )
                        if api_resp.status_code == 200:
                            try:
                                data = api_resp.json()
                                for key in ['url', 'file', 'src', 'result']:
                                    if key in data:
                                        val = data[key]
                                        if isinstance(val, str) and val.startswith('http'):
                                            video_urls.append(val)
                            except:
                                pass
                    except:
                        continue
            
            # Step 6: Look for hidden iframes with video
            soup = BeautifulSoup(html, 'html.parser')
            for iframe in soup.find_all('iframe', src=True):
                iframe_url = iframe.get('src')
                if iframe_url:
                    if iframe_url.startswith('//'):
                        iframe_url = 'https:' + iframe_url
                    elif not iframe_url.startswith('http'):
                        iframe_url = urljoin(resolved_url, iframe_url)
                    
                    try:
                        iframe_resp = session.get(iframe_url, headers={**headers, 'Referer': resolved_url}, timeout=15)
                        iframe_content = iframe_resp.text
                        
                        # Decode packed JS in iframe
                        for pattern in packed_patterns:
                            matches = re.findall(pattern, iframe_content, re.DOTALL | re.IGNORECASE)
                            for match in matches:
                                decoded = self._decode_packed_js(match if isinstance(match, str) else match[0])
                                if decoded:
                                    iframe_content += '\n' + decoded
                        
                        for pattern in video_patterns:
                            matches = re.findall(pattern, iframe_content, re.IGNORECASE)
                            video_urls.extend(matches)
                    except:
                        pass
            
            print(f"[VideyExtractor] Found {len(video_urls)} potential URLs")
            
        except Exception as e:
            print(f"[VideyExtractor] Error: {e}")
            import traceback
            traceback.print_exc()
        
        return video_urls
        
    async def ensure_playwright_ready(self):
        """Ensure Playwright browsers are installed"""
        if self._playwright_ready:
            return True
            
        marker_file = os.path.join(DOWNLOAD_PATH, ".playwright_chromium_ready")
        
        if os.path.exists(marker_file):
            self._playwright_ready = True
            return True
        
        print("[Playwright] Installing Chromium browser...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                timeout=600,
                text=True
            )
            
            if result.returncode == 0:
                with open(marker_file, "w") as f:
                    f.write(f"installed_{datetime.now().isoformat()}")
                self._playwright_ready = True
                print("[Playwright] Chromium installed successfully")
                return True
            else:
                print(f"[Playwright] Installation failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"[Playwright] Installation error: {e}")
            return False
    
    async def extract_with_network_interception(self, url: str, timeout: int = 60) -> List[str]:
        """
        Extract video URLs by intercepting network requests (like browser apps do)
        This is the key feature that makes 9xbuddy and browser apps work
        Enhanced with longer waits and more triggers
        """
        video_urls = []
        
        try:
            from playwright.async_api import async_playwright
            
            await self.ensure_playwright_ready()
            
            print(f"[NetworkInterceptor] Starting browser for: {url}")
            
            async with async_playwright() as p:
                # Launch browser with stealth settings
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-site-isolation-trials',
                        '--allow-running-insecure-content',
                        '--disable-gpu'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    java_script_enabled=True,
                    ignore_https_errors=True,
                    bypass_csp=True
                )
                
                # Add cookies if available
                if COOKIE_FILE and os.path.exists(COOKIE_FILE):
                    try:
                        from http.cookiejar import MozillaCookieJar
                        jar = MozillaCookieJar(COOKIE_FILE)
                        jar.load(ignore_discard=True, ignore_expires=True)
                        cookies = []
                        for cookie in jar:
                            cookies.append({
                                'name': cookie.name,
                                'value': cookie.value,
                                'domain': cookie.domain,
                                'path': cookie.path
                            })
                        if cookies:
                            await context.add_cookies(cookies)
                    except:
                        pass
                
                # Network interception - this is the magic!
                captured_urls = []
                
                async def intercept_response(response):
                    """Capture all network responses that look like video/audio"""
                    try:
                        resp_url = response.url
                        content_type = response.headers.get('content-type', '').lower()
                        content_length = response.headers.get('content-length', '0')
                        
                        # Check if it's a media file
                        is_media = any(mime in content_type for mime in self.MEDIA_MIME_TYPES)
                        
                        # Check URL patterns for video files (expanded list)
                        video_indicators = [
                            '.mp4', '.m3u8', '.webm', '.mpd', '.ts', '.m4v',
                            '/video/', '/stream/', '/media/', '/cdn/', '/hls/',
                            '/dash/', '/manifest', '/playlist', '/chunk', '/source/',
                            '/download/', '/get/', '/dl/', '/file/', '/v/',
                            'videy', 'videq', 'vidgo', 'cdn'
                        ]
                        is_video_url = any(ext in resp_url.lower() for ext in video_indicators)
                        
                        # Check for large content (likely video)
                        try:
                            is_large = int(content_length) > 100000  # > 100KB
                        except:
                            is_large = False
                        
                        if is_media or is_video_url or (is_large and 'octet-stream' in content_type):
                            # Exclude tracking/ad URLs
                            exclude_patterns = [
                                'google', 'facebook', 'analytics', 'tracking',
                                'adsense', 'doubleclick', 'pixel', 'beacon',
                                'telemetry', 'fonts.', 'gtag', 'clarity'
                            ]
                            # Don't exclude .js for streaming players
                            if not any(ex in resp_url.lower() for ex in exclude_patterns):
                                captured_urls.append(resp_url)
                                print(f"[NetworkInterceptor] Captured: {resp_url[:100]}...")
                    except Exception:
                        pass
                
                async def intercept_request(request):
                    """Also capture requests that look like video requests"""
                    try:
                        req_url = request.url
                        video_exts = ['.mp4', '.m3u8', '.webm', '.ts', '.mpd']
                        if any(ext in req_url.lower() for ext in video_exts):
                            if req_url not in captured_urls:
                                captured_urls.append(req_url)
                                print(f"[NetworkInterceptor] Captured request: {req_url[:100]}...")
                    except:
                        pass
                
                page = await context.new_page()
                page.on('response', intercept_response)
                page.on('request', intercept_request)
                
                # Navigate and wait for network activity
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
                except Exception as e:
                    print(f"[NetworkInterceptor] Page load error (continuing): {e}")
                
                # Wait for initial content load
                await asyncio.sleep(3)
                
                # Try to wait for network idle
                try:
                    await page.wait_for_load_state('networkidle', timeout=15000)
                except:
                    pass
                
                # Wait longer for dynamic content and video player initialization
                await asyncio.sleep(5)
                
                # Try to trigger video playback with multiple attempts
                play_selectors = [
                    'video', 'audio',
                    '.play-button', '#play', '.btn-play', '.play-btn',
                    '[data-play]', '.vjs-big-play-button', '.plyr__control--play',
                    '.jw-icon-playback', 'button[aria-label*="Play"]', 'button[aria-label*="play"]',
                    '.player-play', '#player', '.video-js', '.plyr',
                    '[class*="play"]', '[id*="play"]', 'button svg',
                    '.overlay', '.poster', '.thumbnail', 'img[src*="thumb"]'
                ]
                
                for selector in play_selectors:
                    try:
                        elem = await page.query_selector(selector)
                        if elem:
                            await elem.click()
                            await asyncio.sleep(2)
                            # Check if we got new URLs
                            if len(captured_urls) > 0:
                                break
                    except:
                        pass
                
                # Try JavaScript play commands
                try:
                    await page.evaluate("""
                        () => {
                            // Try to play all videos
                            document.querySelectorAll('video').forEach(v => {
                                try { v.play(); } catch(e) {}
                            });
                            // Click any play-looking elements
                            document.querySelectorAll('[class*="play"], [id*="play"], .btn').forEach(el => {
                                try { el.click(); } catch(e) {}
                            });
                        }
                    """)
                    await asyncio.sleep(3)
                except:
                    pass
                
                # Scroll to trigger lazy loading
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await asyncio.sleep(2)
                except:
                    pass
                
                # Extract URLs from JavaScript context
                js_urls = await page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // Check video elements
                    document.querySelectorAll('video, audio').forEach(el => {
                        if (el.src) urls.add(el.src);
                        if (el.currentSrc) urls.add(el.currentSrc);
                        el.querySelectorAll('source').forEach(s => {
                            if (s.src) urls.add(s.src);
                        });
                    });
                    
                    // Check for common player objects
                    const players = [
                        () => typeof jwplayer !== 'undefined' && jwplayer().getPlaylist(),
                        () => typeof videojs !== 'undefined' && Object.values(videojs.getPlayers()),
                        () => typeof Plyr !== 'undefined' && document.querySelectorAll('.plyr'),
                        () => typeof player !== 'undefined' && player.src,
                        () => typeof Playerjs !== 'undefined' && window.Playerjs,
                    ];
                    
                    // JWPlayer
                    try {
                        if (typeof jwplayer !== 'undefined') {
                            const p = jwplayer();
                            if (p && p.getPlaylist) {
                                p.getPlaylist().forEach(item => {
                                    if (item.file) urls.add(item.file);
                                    (item.sources || []).forEach(s => {
                                        if (s.file) urls.add(s.file);
                                    });
                                });
                            }
                        }
                    } catch(e) {}
                    
                    // Video.js
                    try {
                        if (typeof videojs !== 'undefined') {
                            Object.values(videojs.getPlayers()).forEach(p => {
                                if (p && p.currentSrc) urls.add(p.currentSrc());
                            });
                        }
                    } catch(e) {}
                    
                    // Check performance entries for video requests
                    try {
                        performance.getEntries().forEach(entry => {
                            const name = entry.name.toLowerCase();
                            if (name.includes('.mp4') || name.includes('.m3u8') || 
                                name.includes('.webm') || name.includes('/video/') ||
                                name.includes('/stream/') || name.includes('.mpd')) {
                                urls.add(entry.name);
                            }
                        });
                    } catch(e) {}
                    
                    // Check global variables
                    const globalVars = ['videoUrl', 'videoSrc', 'streamUrl', 'playUrl', 
                                       'downloadUrl', 'source', 'sources', 'videoSource'];
                    globalVars.forEach(v => {
                        try {
                            if (window[v]) {
                                if (typeof window[v] === 'string') urls.add(window[v]);
                                else if (Array.isArray(window[v])) {
                                    window[v].forEach(item => {
                                        if (typeof item === 'string') urls.add(item);
                                        else if (item && item.file) urls.add(item.file);
                                        else if (item && item.src) urls.add(item.src);
                                    });
                                }
                            }
                        } catch(e) {}
                    });
                    
                    return Array.from(urls);
                }
                """)
                
                video_urls.extend(js_urls)
                video_urls.extend(captured_urls)
                
                # Also extract from page source
                content = await page.content()
                html_urls = self.extract_from_html(content, url)
                video_urls.extend(html_urls)
                
                await browser.close()
                
        except ImportError:
            print("[NetworkInterceptor] Playwright not installed")
        except Exception as e:
            print(f"[NetworkInterceptor] Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Clean and deduplicate URLs
        return self._clean_video_urls(video_urls, url)
    
    def extract_from_html(self, html: str, base_url: str) -> List[str]:
        """Extract video URLs from HTML content using regex patterns"""
        video_urls = []
        
        try:
            # Decode packed JavaScript
            decoded_html = self._decode_packed_js(html)
            
            for pattern in self.VIDEO_PATTERNS:
                try:
                    matches = re.findall(pattern, decoded_html, re.IGNORECASE | re.DOTALL)
                    for match in matches:
                        if match:
                            # Handle base64 encoded URLs
                            if 'atob' in pattern or len(match) > 50 and re.match(r'^[A-Za-z0-9+/=]+$', match):
                                try:
                                    decoded = base64.b64decode(match).decode('utf-8')
                                    if decoded.startswith('http'):
                                        video_urls.append(decoded)
                                except:
                                    pass
                            # Handle hex/unicode encoded
                            elif '\\x' in match or '\\u' in match:
                                try:
                                    decoded = match.encode().decode('unicode_escape')
                                    video_urls.append(decoded)
                                except:
                                    video_urls.append(match)
                            else:
                                video_urls.append(match)
                except:
                    pass
            
            # Parse with BeautifulSoup for structured extraction
            soup = BeautifulSoup(decoded_html, 'html.parser')
            
            # Video/audio elements
            for tag in soup.find_all(['video', 'audio']):
                if tag.get('src'):
                    video_urls.append(tag.get('src'))
                for source in tag.find_all('source'):
                    if source.get('src'):
                        video_urls.append(source.get('src'))
            
            # Data attributes
            for attr in ['data-src', 'data-video', 'data-url', 'data-file', 'data-stream']:
                for el in soup.find_all(attrs={attr: True}):
                    video_urls.append(el.get(attr))
            
            # Meta tags
            meta_keys = ['og:video', 'og:video:url', 'og:video:secure_url',
                        'twitter:player:stream', 'twitter:player']
            for meta in soup.find_all('meta'):
                prop = (meta.get('property') or meta.get('name') or '').lower()
                if prop in meta_keys:
                    content = meta.get('content')
                    if content:
                        video_urls.append(content)
            
            # JSON-LD
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string or '')
                    self._extract_from_json(data, video_urls)
                except:
                    pass
            
            # Inline scripts
            for script in soup.find_all('script'):
                if script.string:
                    # Look for video URLs in script content
                    script_text = script.string
                    for pattern in self.VIDEO_PATTERNS[:10]:  # Use main patterns
                        matches = re.findall(pattern, script_text, re.IGNORECASE)
                        video_urls.extend(matches)
                        
        except Exception as e:
            print(f"[HTMLExtractor] Error: {e}")
        
        return video_urls
    
    def _extract_from_json(self, data: Any, urls: List[str]):
        """Recursively extract URLs from JSON data"""
        if isinstance(data, dict):
            for key in ['contentUrl', 'embedUrl', 'url', 'fileUrl', 'file', 'src', 'source', 'stream']:
                if key in data and isinstance(data[key], str):
                    urls.append(data[key])
            for value in data.values():
                self._extract_from_json(value, urls)
        elif isinstance(data, list):
            for item in data:
                self._extract_from_json(item, urls)
    
    def _decode_packed_js(self, code: str) -> str:
        """Decode JavaScript that was packed with eval(function(p,a,c,k,e,d)...)"""
        try:
            packed_pattern = r"eval\(function\(p,a,c,k,e,[rd]\).*?\.split\('\|'\)\)"
            if not re.search(packed_pattern, code, re.DOTALL):
                return code
            
            payload_match = re.search(r"}\('(.+)',(\d+),(\d+),'([^']+)'", code, re.DOTALL)
            if not payload_match:
                return code
            
            payload = payload_match.group(1)
            radix = int(payload_match.group(2))
            keywords = payload_match.group(4).split('|')
            
            def replace_func(match):
                word = match.group(0)
                try:
                    index = int(word, radix)
                    if index < len(keywords) and keywords[index]:
                        return keywords[index]
                except:
                    pass
                return word
            
            decoded = re.sub(r'\b\w+\b', replace_func, payload)
            return code + "\n" + decoded
        except:
            return code
    
    async def try_direct_download(self, url: str, referer: str = None) -> Optional[str]:
        """
        Try to download directly from URL - checks if it's a valid video file
        Returns the URL if valid, None otherwise
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            if referer:
                headers['Referer'] = referer
                parsed = urlparse(referer)
                headers['Origin'] = f"{parsed.scheme}://{parsed.netloc}"
            
            # Do a HEAD request first to check content type
            resp = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
            
            content_type = resp.headers.get('content-type', '').lower()
            content_length = resp.headers.get('content-length', '0')
            
            # Check if it's a video
            if any(mime in content_type for mime in ['video/', 'audio/', 'octet-stream', 'mpegurl']):
                print(f"[DirectDownload] Valid video URL: {url[:100]}...")
                return url
            
            # Check by extension
            if any(ext in url.lower() for ext in ['.mp4', '.m3u8', '.webm', '.ts', '.mpd']):
                try:
                    size = int(content_length)
                    if size > 10000:  # > 10KB
                        print(f"[DirectDownload] Valid video URL by extension: {url[:100]}...")
                        return url
                except:
                    pass
            
            # Try GET with range to verify
            headers['Range'] = 'bytes=0-1024'
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            
            if resp.status_code in [200, 206]:
                content = resp.content
                # Check for video file signatures
                # MP4: starts with ftyp or moov
                # WebM: starts with 0x1A 0x45 0xDF 0xA3
                if content[:4] in [b'ftyp', b'moov', b'\x00\x00\x00\x18', b'\x00\x00\x00\x1c', b'\x00\x00\x00\x20']:
                    print(f"[DirectDownload] Valid MP4 by signature: {url[:100]}...")
                    return url
                if content[:4] == b'\x1a\x45\xdf\xa3':
                    print(f"[DirectDownload] Valid WebM by signature: {url[:100]}...")
                    return url
                if b'#EXTM3U' in content:
                    print(f"[DirectDownload] Valid M3U8 playlist: {url[:100]}...")
                    return url
                    
        except Exception as e:
            print(f"[DirectDownload] Error checking URL: {e}")
        
        return None
    
    def _clean_video_urls(self, urls: List[str], base_url: str) -> List[str]:
        """Clean, validate and deduplicate video URLs"""
        cleaned = []
        seen = set()
        
        parsed_base = urlparse(base_url)
        
        for url in urls:
            if not url or not isinstance(url, str):
                continue
            
            url = url.strip()
            
            # Unescape common escapes
            try:
                url = url.replace('\\/', '/')
                if '\\x' in url or '\\u' in url:
                    url = url.encode().decode('unicode_escape')
            except:
                pass
            
            # Skip invalid URLs
            if url.startswith(('data:', 'blob:', 'javascript:', '#')):
                continue
            
            # Handle relative URLs
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
            elif not url.startswith('http'):
                url = urljoin(base_url, url)
            
            # Validate URL
            if not url.startswith('http'):
                continue
            
            # Skip tracking/ad URLs
            skip_patterns = [
                'google', 'facebook', 'twitter', 'analytics', 'adsense',
                'doubleclick', 'pixel', 'tracking', 'beacon', 'telemetry',
                '.js', '.css', '.png', '.jpg', '.gif', '.ico', 'favicon'
            ]
            if any(p in url.lower() for p in skip_patterns):
                continue
            
            # Must contain video indicators
            video_indicators = [
                '.mp4', '.m3u8', '.webm', '.mkv', '.avi', '.mov', '.mpd', '.ts', '.m4v',
                'video', 'stream', 'media', 'cdn', 'download', 'play', 'source',
                'manifest', 'playlist', 'chunk', '/v/', '/e/', '/d/', '/f/',
                'videy', 'videq', 'vidgo', 'hls', 'dash', 'embed', '/get/'
            ]
            if not any(ind in url.lower() for ind in video_indicators):
                continue
            
            if url not in seen:
                seen.add(url)
                cleaned.append(url)
        
        # Sort by priority (MP4 first, then quality, prefer CDN URLs)
        def priority(u):
            u_lower = u.lower()
            score = 100
            
            # Prefer direct MP4 files
            if '.mp4' in u_lower:
                score = 10
                if '1080' in u_lower or 'hd' in u_lower: score = 0
                elif '720' in u_lower: score = 1
                elif '480' in u_lower: score = 2
                elif '360' in u_lower: score = 3
            elif '.webm' in u_lower:
                score = 15
            elif '.m3u8' in u_lower:
                score = 20
            elif '.mpd' in u_lower:
                score = 21
            elif '.ts' in u_lower:
                score = 25
            
            # Boost CDN URLs (more reliable)
            if 'cdn' in u_lower or any(cdn in u_lower for cdn in ['akamai', 'cloudfront', 'fastly']):
                score -= 5
            
            # Boost videy family CDN URLs
            if any(v in u_lower for v in ['videy', 'videq', 'vidgo', 'vidoy']):
                score -= 3
            
            # Penalize embed/player URLs (not direct video)
            if '/embed/' in u_lower or '/player/' in u_lower:
                score += 50
            
            return score
        
        cleaned.sort(key=priority)
        
        print(f"[URLCleaner] Cleaned {len(cleaned)} valid video URLs from {len(urls)} candidates")
        return cleaned
    
    async def try_external_apis(self, url: str) -> Optional[str]:
        """Try external download APIs as fallback (like 9xbuddy uses multiple APIs)"""
        from urllib.parse import quote
        
        for api in self.EXTERNAL_APIS:
            try:
                print(f"[ExternalAPI] Trying {api['name']}...")
                
                encoded_url = quote(url, safe='')
                
                if api['method'] == 'POST':
                    if 'body_template' in api:
                        # JSON body
                        body = json.dumps({k: v.replace('{url}', url) if isinstance(v, str) else v 
                                          for k, v in api['body_template'].items()})
                        resp = requests.post(
                            api['url'],
                            headers=api.get('headers', {}),
                            data=body,
                            timeout=30
                        )
                    elif 'data_template' in api:
                        # Form data
                        data = api['data_template'].replace('{url}', encoded_url)
                        resp = requests.post(
                            api['url'],
                            headers=api.get('headers', {}),
                            data=data,
                            timeout=30
                        )
                    else:
                        continue
                else:
                    params = {k: v.replace('{url}', url) for k, v in api.get('params', {}).items()}
                    resp = requests.get(
                        api['url'],
                        params=params,
                        headers=api.get('headers', {}),
                        timeout=30
                    )
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        
                        # Handle simple response key
                        if 'response_key' in api:
                            video_url = data.get(api['response_key'])
                            if video_url and isinstance(video_url, str) and video_url.startswith('http'):
                                print(f"[ExternalAPI] {api['name']} returned: {video_url[:100]}...")
                                return video_url
                        
                        # Handle complex response path
                        if 'response_path' in api:
                            for path in api['response_path']:
                                if path in data:
                                    val = data[path]
                                    if isinstance(val, str) and val.startswith('http'):
                                        print(f"[ExternalAPI] {api['name']} returned: {val[:100]}...")
                                        return val
                                    elif isinstance(val, dict):
                                        for key in ['url', 'file', 'src', 'link', 'download']:
                                            if key in val:
                                                v = val[key]
                                                if isinstance(v, str) and v.startswith('http'):
                                                    print(f"[ExternalAPI] {api['name']} returned: {v[:100]}...")
                                                    return v
                                    elif isinstance(val, list) and len(val) > 0:
                                        first = val[0]
                                        if isinstance(first, str) and first.startswith('http'):
                                            return first
                                        elif isinstance(first, dict):
                                            for key in ['url', 'file', 'src']:
                                                if key in first:
                                                    return first[key]
                        
                        # Generic search for video URL in response
                        video_url = self._find_video_url_in_json(data)
                        if video_url:
                            print(f"[ExternalAPI] {api['name']} found: {video_url[:100]}...")
                            return video_url
                            
                    except json.JSONDecodeError:
                        # Not JSON, check if direct URL
                        text = resp.text.strip()
                        if text.startswith('http') and any(ext in text.lower() for ext in ['.mp4', '.m3u8', '.webm']):
                            return text
                        
            except Exception as e:
                print(f"[ExternalAPI] {api['name']} failed: {e}")
                continue
        
        return None
    
    def _find_video_url_in_json(self, data, depth=0) -> Optional[str]:
        """Recursively search for video URLs in JSON data"""
        if depth > 5:
            return None
        
        if isinstance(data, str):
            if data.startswith('http') and any(ext in data.lower() for ext in ['.mp4', '.m3u8', '.webm', '.ts', 'video', 'stream']):
                return data
        elif isinstance(data, dict):
            # Priority keys
            for key in ['url', 'file', 'src', 'source', 'download', 'stream', 'video', 'link', 'mp4', 'hls']:
                if key in data:
                    result = self._find_video_url_in_json(data[key], depth + 1)
                    if result:
                        return result
            # Check all values
            for val in data.values():
                result = self._find_video_url_in_json(val, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data[:10]:  # Limit to first 10 items
                result = self._find_video_url_in_json(item, depth + 1)
                if result:
                    return result
        
        return None
    
    def is_videy_family(self, url: str) -> bool:
        """Check if URL belongs to Videy/Videq family platforms"""
        domain = urlparse(url).netloc.lower()
        videy_domains = [
            'videy', 'videq', 'vidgo', 'vidoy', 'vide-q', 'vide0', 'vide6',
            'videypro', 'vidqy', 'vidbre', 'avdeq', 'vdaq', 'cdnvideq',
            'videw', 'vidpy'
        ]
        return any(d in domain for d in videy_domains)
    
    async def extract_all(self, url: str) -> Tuple[List[str], str]:
        """
        Main extraction method - tries all methods to find video URLs
        Returns (list of video URLs, resolved URL)
        Like 9xbuddy, we try multiple methods and combine results
        """
        video_urls = []
        resolved_url = url
        
        # Check if this is a Videy family platform - use specialized extractor first
        if self.is_videy_family(url):
            print("[Extractor] Detected Videy family platform - using specialized extractor...")
            try:
                videy_urls = await self.extract_videy_family(url)
                video_urls.extend(videy_urls)
                if video_urls:
                    cleaned = self._clean_video_urls(video_urls, url)
                    if cleaned:
                        print(f"[Extractor] Videy extractor found {len(cleaned)} URLs")
                        return cleaned, url
            except Exception as e:
                print(f"[Extractor] Videy extractor failed: {e}")
        
        # Step 1: Try network interception (most reliable, like browser apps)
        print("[Extractor] Step 1: Network interception...")
        try:
            network_urls = await self.extract_with_network_interception(url)
            video_urls.extend(network_urls)
        except Exception as e:
            print(f"[Extractor] Network interception failed: {e}")
        
        # Step 2: Try direct HTTP extraction if network interception found nothing or little
        if len(video_urls) < 2:
            print("[Extractor] Step 2: Direct HTTP extraction...")
            try:
                session = requests.Session()
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': url
                }
                
                resp = session.get(url, headers=headers, timeout=30, allow_redirects=True)
                resolved_url = resp.url
                
                html_urls = self.extract_from_html(resp.text, resolved_url)
                video_urls.extend(html_urls)
                
                # Look for Videy CDN patterns specifically
                for pattern in self.VIDEY_CDN_PATTERNS:
                    matches = re.findall(pattern, resp.text, re.IGNORECASE)
                    video_urls.extend(matches)
                
                # Follow iframes
                soup = BeautifulSoup(resp.text, 'html.parser')
                for iframe in soup.find_all('iframe', src=True):
                    iframe_url = iframe.get('src')
                    if iframe_url:
                        if iframe_url.startswith('//'):
                            iframe_url = 'https:' + iframe_url
                        elif not iframe_url.startswith('http'):
                            iframe_url = urljoin(resolved_url, iframe_url)
                        
                        try:
                            iframe_resp = session.get(iframe_url, headers={**headers, 'Referer': resolved_url}, timeout=15)
                            iframe_urls = self.extract_from_html(iframe_resp.text, iframe_url)
                            video_urls.extend(iframe_urls)
                            
                            # Also check Videy patterns in iframe
                            for pattern in self.VIDEY_CDN_PATTERNS:
                                matches = re.findall(pattern, iframe_resp.text, re.IGNORECASE)
                                video_urls.extend(matches)
                        except:
                            pass
                
            except Exception as e:
                print(f"[Extractor] HTTP extraction failed: {e}")
        
        # Step 3: Try external APIs if nothing found
        if not video_urls:
            print("[Extractor] Step 3: External APIs...")
            try:
                api_url = await self.try_external_apis(url)
                if api_url:
                    video_urls.append(api_url)
            except Exception as e:
                print(f"[Extractor] External APIs failed: {e}")
        
        # Step 4: Try Videy family extractor as last resort if still nothing
        if not video_urls and not self.is_videy_family(url):
            # Try it anyway - might be a similar platform
            print("[Extractor] Step 4: Trying Videy-style extraction as fallback...")
            try:
                videy_urls = await self.extract_videy_family(url)
                video_urls.extend(videy_urls)
            except Exception as e:
                print(f"[Extractor] Videy-style extraction failed: {e}")
        
        # Final cleanup
        video_urls = self._clean_video_urls(video_urls, resolved_url)
        
        print(f"[Extractor] Final result: {len(video_urls)} video URLs found")
        return video_urls, resolved_url


# Global instance
universal_extractor = UniversalVideoExtractor()

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
🤖 *Selamat datang di SafeRobot v6.0!*

Bot downloader UNIVERSAL seperti 9xbuddy.site!

🔥 *FITUR BARU v6.0:*
✅ Download video dari WEBSITE APAPUN
✅ Network Interception (seperti browser app)
✅ Ekstraksi khusus untuk Videy/Videq family
✅ Multiple API fallbacks (cobalt, savefrom, dll)
✅ Auto-zip untuk folder/playlist

📱 *SOSIAL MEDIA:*
✅ TikTok, Instagram, Twitter/X
✅ YouTube, Facebook, Pinterest

🎬 *STREAMING (100+ Platform):*
✅ DoodStream, TeraBox, Videy, Videq, VidGo
✅ LuluStream, VidCloud, StreamTape
✅ MyVidPlay, Filemoon, StreamWish
✅ Dan masih banyak lagi!

🔥 *Cara Penggunaan:*
Kirim link dari website APAPUN yang memiliki video, pilih format, dan file akan dikirim!

Gunakan /platforms untuk info lebih lanjut.

Gunakan tombol menu di bawah 👇
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
        'unsupported': """⚠️ URL tidak terdeteksi otomatis.

Tapi jangan khawatir! Bot ini dapat mencoba download dari website APAPUN.

Pastikan:
• Link dimulai dengan http:// atau https://
• Website memiliki video yang dapat diputar
• Tidak memerlukan login

Kirim ulang link dengan format lengkap untuk mencoba ekstraksi universal.""",
        'detected': "✅ Link dari *{}* terdeteksi!\n\nPilih format download:",
        'detected_streaming': "🎬 Link streaming dari *{}* terdeteksi!\n\n⚠️ Platform streaming mungkin memerlukan waktu lebih lama.\n\nPilih format download:",
        'downloading': "⏳ Sedang mendownload {}...\nMohon tunggu sebentar...",
        'downloading_streaming': "⏳ Mengekstrak video dari streaming...\n\n📡 Platform: *{}*\n⌛ Proses ini mungkin memakan waktu 1-2 menit.\n\nMohon tunggu...",
        'sending': "📤 Mengirim file...",
        'video_caption': "🎥 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'archive_caption': "📦 *{}* ({} file)\n\n🔥 Downloaded by @SafeRobot",
        'download_failed': """❌ Download gagal!

Error: Tidak dapat menemukan URL video. Platform ini mungkin memerlukan login atau memiliki proteksi anti-bot.

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
🤖 *Welcome to SafeRobot v6.0!*

UNIVERSAL downloader bot like 9xbuddy.site!

🔥 *NEW FEATURES v6.0:*
✅ Download video from ANY WEBSITE
✅ Network Interception (like browser apps)
✅ Specialized Videy/Videq family extractor
✅ Multiple API fallbacks (cobalt, savefrom, etc)
✅ Auto-zip for folders/playlists

📱 *SOCIAL MEDIA:*
✅ TikTok, Instagram, Twitter/X
✅ YouTube, Facebook, Pinterest

🎬 *STREAMING (100+ Platforms):*
✅ DoodStream, TeraBox, Videy, Videq, VidGo
✅ LuluStream, VidCloud, StreamTape
✅ MyVidPlay, Filemoon, StreamWish
✅ And many more!

🔥 *How to Use:*
Send a link from ANY website that has video, choose format, and the file will be sent!

Use /platforms for more info.

Use the menu buttons below 👇
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
        'unsupported': """⚠️ URL not auto-detected.

But don't worry! This bot can try to download from ANY website.

Make sure:
• Link starts with http:// or https://
• Website has playable video
• No login required

Send the link again with full format to try universal extraction.""",
        'detected': "✅ Link from *{}* detected!\n\nChoose download format:",
        'detected_streaming': "🎬 Streaming link from *{}* detected!\n\n⚠️ Streaming platforms may take longer to process.\n\nChoose download format:",
        'downloading': "⏳ Downloading {}...\nPlease wait...",
        'downloading_streaming': "⏳ Extracting video from streaming...\n\n📡 Platform: *{}*\n⌛ This process may take 1-2 minutes.\n\nPlease wait...",
        'sending': "📤 Sending file...",
        'video_caption': "🎥 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 Downloaded by @SafeRobot",
        'archive_caption': "📦 *{}* ({} files)\n\n🔥 Downloaded by @SafeRobot",
        'download_failed': """❌ Download failed!

Error: Could not find video URL. This platform may require login or has anti-bot protection.

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
                'dood.la', 'ds2play.com', 'd0o0d.com', 'do0od.com',
                'd000d.com', 'dooood.com', 'dood.video'
            ],
            'terabox': [
                'terabox.com', '1024terabox.com', 'teraboxapp.com',
                'terabox.fun', 'terabox.link', '4funbox.com',
                'mirrobox.com', 'nephobox.com', '1024tera.com',
                'teraboxlink.com', 'terafileshare.com'
            ],
            'videy': [
                'vidoy.com', 'vidoy.cam', 'videypro.live', 'videyaio.com',
                'videy.co', 'videy.la', 'vide-q.com', 'vide0.me',
                'vide6.com', 'videw.online', 'vidqy.co', 'vidbre.org',
                'vidgo.blog', 'vidgo.pro', 'vidgo.cc', 'vidgo.to'
            ],
            'videq': [
                'videq.io', 'videq.pw', 'videqs.com', 'videq.info',
                'videq.tel', 'videq.wtf', 'videq.app', 'videq.video',
                'videq.my', 'videq.boo', 'videq.cloud', 'videq.net',
                'videq.co', 'videq.me', 'videq.org', 'videq.pro',
                'videq.xyz', 'cdnvideq.net', 'avdeq.ink',
                'vdaq.de', 'vdaq.co', 'vdaq.cc', 'vdaq.io'
            ],
            'lulu': [
                'lulustream.com', 'lulu.st', 'lixstream.com',
                'luluvdo.com', 'luluhost.com'
            ],
            'twimg': [
                'videotwimg.app', 'video.twlmg.org', 'cdn.twlmg.org',
                'twlmg.org', 'tvidey.tv', 'cdn.tvidey.tv', 
                'tvimg.net', 'video.tvimg.net'
            ],
            'vidcloud': [
                'vidcloudmv.org', 'vidcloud.co', 'vidcloud9.com',
                'vidcloud.pro', 'vidcloud.icu'
            ],
            'vidpy': [
                'cdn.vidpy.co', 'cdn.vidpy.cc', 'vidpy.co', 'vidpy.cc'
            ],
            'uplad': [
                'upl.ad', 'upl.io', 'upload.do', 'uploaddo.com'
            ],
            'filemoon': [
                'filemoon.sx', 'filemoon.to', 'filemoon.in',
                'filemoon.link', 'filemoon.nl', 'kerapoxy.cc'
            ],
            'streamwish': [
                'streamwish.to', 'streamwish.com', 'swdyu.com',
                'wishembed.pro', 'strwish.xyz', 'awish.pro'
            ],
            'vidhide': [
                'vidhide.com', 'vidhidepro.com', 'vidhideplus.com',
                'vidhidevip.com'
            ],
            'other_streaming': [
                'vide.cx', 'vid.boats', 'vid.promo',
                'video.twing.plus', 'myvidplay.com', 'streamtape.com',
                'mixdrop.to', 'mixdrop.co', 'upstream.to', 'mp4upload.com',
                'streamlare.com', 'fembed.com', 'femax20.com', 'fcdn.stream',
                'embedsito.com', 'embedstream.me', 'vidoza.net', 'vidlox.me',
                'voe.sx', 'voe-unblock.com', 'voeunbl0ck.com',
                'supervideo.cc', 'supervideo.tv', 'vidmoly.to', 'vidmoly.me',
                'vtube.to', 'vtube.network', 'streamsb.net', 'sbembed.com',
                'sbcloud.pro', 'sbplay.org', 'cloudemb.com', 'tubeload.co',
                'vidfast.co', 'fastupload.io', 'hexupload.net', 'turboviplay.com',
                # Additional platforms for universal support
                'gdriveplayer.to', 'gdriveplayer.us', 'gdriveplay.com',
                'playerx.stream', 'embedplayer.live', 'embedplay.net',
                'playertv.net', 'playercdn.net', 'playvid.host',
                'videobin.co', 'highstream.tv', 'uqload.com', 'uqload.to',
                'megaupload.nz', 'filepress.top', 'racaty.net', 'pixeldrain.com',
                'streamz.ws', 'streamzz.to', 'vidstream.pro', 'vidsrc.me',
                'gofile.io', 'anonfiles.com', 'bayfiles.com', 'krakenfiles.com',
                'send.cm', 'sendvid.com', 'evoload.io', 'wolfstream.tv'
            ]
        }
        
        # Gabungkan semua platform
        self.supported_platforms = {**self.social_platforms}
        for platform, domains in self.streaming_platforms.items():
            self.supported_platforms[platform] = domains
        
        self._playwright_install_attempted = False
    
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
    
    def _build_headers(self, referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        if referer:
            headers['Referer'] = referer
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                headers['Origin'] = f"{parsed.scheme}://{parsed.netloc}"
        return headers
    
    def _load_cookies(self, session):
        if COOKIE_FILE and os.path.exists(COOKIE_FILE):
            try:
                jar = MozillaCookieJar(COOKIE_FILE)
                jar.load(ignore_discard=True, ignore_expires=True)
                session.cookies.update(jar)
                return True
            except Exception as e:
                print(f"[Cookie] Failed to load cookies: {e}")
        return False
    
    def _format_cookie_header(self, session):
        try:
            cookie_dict = requests.utils.dict_from_cookiejar(session.cookies)
            if not cookie_dict:
                return ""
            return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
        except Exception:
            return ""
    
    def resolve_url(self, url, max_hops=5):
        """Resolve shortener/redirect URLs to final destination"""
        try:
            session = requests.Session()
            self._load_cookies(session)
            current_url = url
            
            for _ in range(max_hops):
                if not current_url:
                    break
                
                headers = self._build_headers(current_url)
                
                try:
                    head_resp = session.head(
                        current_url,
                        headers=headers,
                        allow_redirects=False,
                        timeout=10
                    )
                    if head_resp.is_redirect and head_resp.headers.get('Location'):
                        next_url = urljoin(current_url, head_resp.headers.get('Location'))
                        if next_url == current_url:
                            break
                        current_url = next_url
                        continue
                except requests.RequestException:
                    pass
                
                try:
                    resp = session.get(
                        current_url,
                        headers=headers,
                        allow_redirects=False,
                        timeout=15
                    )
                except requests.RequestException:
                    break
                
                if resp.is_redirect and resp.headers.get('Location'):
                    next_url = urljoin(current_url, resp.headers.get('Location'))
                    if next_url == current_url:
                        break
                    current_url = next_url
                    continue
                
                content_type = resp.headers.get('content-type', '').lower()
                if 'text/html' in content_type:
                    html = resp.text
                    meta_match = re.search(
                        r'http-equiv=["\']refresh["\']\s*content=["\'][^"\']*url=([^"\']+)',
                        html,
                        re.IGNORECASE
                    )
                    if meta_match:
                        next_url = urljoin(current_url, meta_match.group(1).strip())
                        if next_url == current_url:
                            break
                        current_url = next_url
                        continue
                    
                    js_match = re.search(
                        r'window\.location(?:\.href)?\s*=\s*[\'"]([^\'"]+)',
                        html
                    )
                    if js_match:
                        next_url = urljoin(current_url, js_match.group(1).strip())
                        if next_url == current_url:
                            break
                        current_url = next_url
                        continue
                
                break
            
            return current_url
        except Exception as e:
            print(f"[Resolver] Error resolving URL: {e}")
            return url
    
    def _is_stream_manifest(self, url, content_type=""):
        target = (url or "").lower()
        if any(ext in target for ext in ['.m3u8', '.mpd']):
            return True
        ct = (content_type or "").lower()
        return any(marker in ct for marker in [
            'mpegurl',
            'application/vnd.apple.mpegurl',
            'application/x-mpegurl',
            'application/dash+xml'
        ])

    def _looks_like_collection_url(self, url):
        parsed = urlparse(url)
        path = (parsed.path or "").lower()
        query = parse_qs(parsed.query or "")
        if any(key in query for key in ['list', 'playlist', 'album', 'collection', 'folder', 'surl']):
            return True
        collection_tokens = [
            '/playlist', '/album', '/collection', '/folder', '/folders',
            '/dir/', '/directory', '/drive/'
        ]
        return any(token in path for token in collection_tokens)

    def _should_allow_playlist(self, url, platform):
        if not ALLOW_PLAYLIST_ZIP:
            return False
        return self._looks_like_collection_url(url)

    def _looks_like_direct_media(self, url, content_type="", content_disposition=""):
        if self._is_stream_manifest(url, content_type):
            return True
        path = urlparse(url).path.lower()
        media_exts = [
            '.mp4', '.webm', '.mkv', '.mov', '.m4a', '.mp3',
            '.m3u8', '.mpd', '.jpg', '.jpeg', '.png', '.webp'
        ]
        if any(path.endswith(ext) for ext in media_exts):
            return True
        ct = (content_type or "").lower()
        if ct.startswith(('video/', 'audio/')):
            return True
        if 'application/octet-stream' in ct and 'attachment' in (content_disposition or '').lower():
            return True
        return False

    def _resolve_downloaded_file(self, filename, format_type):
        if filename and os.path.exists(filename):
            return filename
        if not filename:
            return None
        base = filename.rsplit('.', 1)[0]
        if format_type == 'audio':
            candidates = ['.mp3', '.m4a', '.aac', '.ogg', '.webm']
        elif format_type == 'photo':
            candidates = ['.jpg', '.jpeg', '.png', '.webp']
        else:
            candidates = ['.mp4', '.mkv', '.webm', '.mov', '.m4a']
        for ext in candidates:
            candidate = base + ext
            if os.path.exists(candidate):
                return candidate
        return None

    def _create_zip_archive(self, files, title):
        if not files:
            return None, "No files to archive"
        total_size = 0
        for path in files:
            if os.path.exists(path):
                total_size += os.path.getsize(path)
        if total_size > MAX_ARCHIVE_SIZE:
            total_mb = total_size / (1024 * 1024)
            limit_mb = MAX_ARCHIVE_SIZE / (1024 * 1024)
            return None, f"Archive too large ({total_mb:.1f}MB > {limit_mb:.1f}MB)"

        safe_title = re.sub(r'[^A-Za-z0-9._-]+', '_', title or "download").strip('_')
        if not safe_title:
            safe_title = "download"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        title_hash = hashlib.md5((safe_title + timestamp).encode()).hexdigest()[:8]
        archive_path = f"{DOWNLOAD_PATH}{safe_title[:50]}_{timestamp}_{title_hash}.zip"

        name_counts = {}
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
            for path in files:
                if not os.path.exists(path):
                    continue
                name = os.path.basename(path)
                if name in name_counts:
                    name_counts[name] += 1
                    root, ext = os.path.splitext(name)
                    name = f"{root}_{name_counts[name]}{ext}"
                else:
                    name_counts[name] = 1
                zipf.write(path, arcname=name)

        return archive_path, None

    def _collect_downloaded_files(self, ydl, info, format_type):
        def collect_from_info(item):
            if isinstance(item, dict):
                candidates = []
                if item.get('_filename'):
                    candidates.append(self._resolve_downloaded_file(item.get('_filename'), format_type))
                for req in (item.get('requested_downloads') or []):
                    candidates.append(self._resolve_downloaded_file(req.get('filepath'), format_type))
                for candidate in candidates:
                    if candidate and os.path.exists(candidate):
                        return [candidate]
            try:
                expected = ydl.prepare_filename(item)
            except Exception:
                return []
            resolved = self._resolve_downloaded_file(expected, format_type)
            if resolved and os.path.exists(resolved):
                return [resolved]
            return []

        files = []
        entries = info.get('entries') if isinstance(info, dict) else None
        if entries:
            for entry in entries:
                if not entry:
                    continue
                files.extend(collect_from_info(entry))
        else:
            files.extend(collect_from_info(info))

        unique = []
        seen = set()
        for path in files:
            if path and path not in seen and os.path.exists(path):
                seen.add(path)
                unique.append(path)
        return unique
    
    def _ensure_playwright_browsers(self):
        if not AUTO_INSTALL_PLAYWRIGHT:
            return False
        if self._playwright_install_attempted:
            return False
        self._playwright_install_attempted = True
        
        marker = os.path.join(DOWNLOAD_PATH, ".playwright_installed")
        if os.path.exists(marker):
            return True
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                timeout=PLAYWRIGHT_INSTALL_TIMEOUT
            )
            if result.returncode == 0:
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("installed")
                return True
            stderr = result.stderr.decode(errors="ignore")
            if stderr:
                print(f"[Playwright] install failed: {stderr}")
        except Exception as e:
            print(f"[Playwright] install error: {e}")
        
        return False
    
    async def extract_with_selenium(self, url):
        """
        Deprecated: Use Playwright-based universal extractor instead.
        Selenium has ChromeDriver version compatibility issues.
        This method now just returns empty as Playwright handles extraction.
        """
        print("[Selenium] Deprecated - using Playwright-based extraction instead")
        # Don't use Selenium due to ChromeDriver version mismatch issues
        # The universal_extractor with Playwright handles this better
        return []
    
    async def extract_with_playwright(self, url):
        """Use universal extractor with network interception (like 9xbuddy)"""
        video_urls = []
        try:
            # Use the universal extractor which has network interception
            video_urls = await universal_extractor.extract_with_network_interception(url)
            print(f"[Playwright] Found {len(video_urls)} video URLs via network interception")
            return video_urls
        except Exception as e:
            print(f"[Playwright] Error: {e}")
        
        return video_urls
    
    def decode_packed_js(self, packed_code):
        """Decode JavaScript yang di-pack dengan eval(function(p,a,c,k,e,d)...)"""
        try:
            # Pattern untuk packed JavaScript
            packed_pattern = r"eval\(function\(p,a,c,k,e,[rd]\).*?\.split\('\|'\)\)"
            match = re.search(packed_pattern, packed_code, re.DOTALL)
            
            if not match:
                return packed_code
            
            # Extract komponen packed code
            payload_match = re.search(r"}\('(.+)',(\d+),(\d+),'([^']+)'", packed_code, re.DOTALL)
            if not payload_match:
                return packed_code
            
            payload = payload_match.group(1)
            radix = int(payload_match.group(2))
            count = int(payload_match.group(3))
            keywords = payload_match.group(4).split('|')
            
            # Decode dengan mengganti placeholder
            def replace_func(match):
                word = match.group(0)
                try:
                    index = int(word, radix)
                    if index < len(keywords) and keywords[index]:
                        return keywords[index]
                except:
                    pass
                return word
            
            decoded = re.sub(r'\b\w+\b', replace_func, payload)
            return decoded
        except Exception as e:
            print(f"Error decoding packed JS: {e}")
            return packed_code
    
    def extract_from_obfuscated_js(self, html, url):
        """Ekstrak video URL dari JavaScript yang di-obfuscate"""
        video_urls = []
        
        try:
            # Pattern untuk berbagai jenis obfuscation
            patterns = [
                # Standard video URL patterns
                r'(?:src|source|file|video_url|videoUrl|mp4|stream|url)["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8|webm|mpd)[^"\']*)["\']',
                r'(?:https?://[^\s"\'<>]+\.(?:mp4|m3u8|webm|mkv|avi|mpd)(?:\?[^\s"\'<>]*)?)',
                
                # HLS/M3U8 patterns
                r'["\']([^"\']*\.m3u8[^"\']*)["\']',
                r'["\']([^"\']*\.mpd[^"\']*)["\']',
                r'source:\s*["\']([^"\']+)["\']',
                
                # Video hosting specific patterns
                r'file:\s*["\']([^"\']+)["\']',
                r'sources:\s*\[\s*\{[^}]*url:\s*["\']([^"\']+)["\']',
                r'sources:\s*\[\s*\{[^}]*file:\s*["\']([^"\']+)["\']',
                r'player\.src\s*\(\s*["\']([^"\']+)["\']',
                r'player\.load\s*\(\s*["\']([^"\']+)["\']',
                r'Playerjs\s*\(\s*\{[^}]*file:\s*["\']([^"\']+)["\']',
                
                # Base64 encoded URLs
                r'atob\(["\']([A-Za-z0-9+/=]+)["\']',
                
                # JSON sources
                r'"sources":\s*\[\s*\{\s*"file":\s*"([^"]+)"',
                r'"src":\s*"([^"]+\.(?:mp4|m3u8|webm))"',
                r'"url":\s*"([^"]+\.(?:mp4|m3u8|webm))"',
                
                # Common streaming site patterns
                r'vidsrc["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'videoSrc["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'playUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'streamUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'downloadUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'directUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                
                # Data attributes
                r'data-src=["\']([^"\']+)["\']',
                r'data-video=["\']([^"\']+)["\']',
                r'data-url=["\']([^"\']+)["\']',
                r'data-file=["\']([^"\']+)["\']',
                
                # Encoded/escaped URLs
                r'\\x68\\x74\\x74\\x70[^"\']+',  # Hex encoded http
                r'\\u0068\\u0074\\u0074\\u0070[^"\']+',  # Unicode encoded http
            ]
            
            # Decode packed JavaScript first
            decoded_html = self.decode_packed_js(html)
            
            for pattern in patterns:
                matches = re.findall(pattern, decoded_html, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    if match:
                        # Try to decode base64 if it looks like base64
                        if pattern == r'atob\(["\']([A-Za-z0-9+/=]+)["\']':
                            try:
                                import base64
                                decoded = base64.b64decode(match).decode('utf-8')
                                if decoded.startswith('http'):
                                    video_urls.append(decoded)
                            except:
                                pass
                        else:
                            # Decode unicode/hex escapes
                            try:
                                decoded_url = match.encode().decode('unicode_escape')
                                video_urls.append(decoded_url)
                            except:
                                video_urls.append(match)
            
            # Look for API endpoints that might return video URLs
            api_patterns = [
                r'(/api/[^"\']+)',
                r'(/embed/[^"\']+)',
                r'(/stream/[^"\']+)',
                r'(/player/[^"\']+)',
                r'(/video/[^"\']+)',
                r'(/download/[^"\']+)',
                r'(/get[^"\']*video[^"\']*)',
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, decoded_html, re.IGNORECASE)
                for match in matches:
                    parsed = urlparse(url)
                    api_url = f"{parsed.scheme}://{parsed.netloc}{match}"
                    video_urls.append(api_url)
            
        except Exception as e:
            print(f"Error extracting from obfuscated JS: {e}")
        
        return video_urls
    
    async def try_api_extraction(self, url):
        """Coba ekstrak video URL via API calls"""
        video_urls = []
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': url,
                'Origin': urlparse(url).scheme + '://' + urlparse(url).netloc
            }
            
            session = requests.Session()
            self._load_cookies(session)
            
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # Extract video ID from URL
            video_id = None
            id_patterns = [
                r'/e/([a-zA-Z0-9]+)',
                r'/v/([a-zA-Z0-9]+)',
                r'/embed/([a-zA-Z0-9]+)',
                r'/video/([a-zA-Z0-9]+)',
                r'/watch/([a-zA-Z0-9]+)',
                r'\?v=([a-zA-Z0-9]+)',
                r'/([a-zA-Z0-9]{8,})',
            ]
            
            for pattern in id_patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    break
            
            if video_id:
                # Common API endpoints to try
                api_endpoints = [
                    f'{base_url}/api/source/{video_id}',
                    f'{base_url}/api/video/{video_id}',
                    f'{base_url}/api/stream/{video_id}',
                    f'{base_url}/api/file/{video_id}',
                    f'{base_url}/dl/{video_id}',
                    f'{base_url}/download/{video_id}',
                    f'{base_url}/get/{video_id}',
                    f'{base_url}/source/{video_id}',
                ]
                
                for endpoint in api_endpoints:
                    try:
                        resp = session.get(endpoint, headers=headers, timeout=10)
                        if resp.status_code == 200:
                            # Try to parse as JSON
                            try:
                                data = resp.json()
                                # Look for video URL in common response structures
                                for key in ['url', 'file', 'src', 'source', 'video', 'stream', 'download', 'link']:
                                    if key in data and isinstance(data[key], str):
                                        video_urls.append(data[key])
                                    elif key in data and isinstance(data[key], list):
                                        for item in data[key]:
                                            if isinstance(item, str):
                                                video_urls.append(item)
                                            elif isinstance(item, dict):
                                                for subkey in ['url', 'file', 'src']:
                                                    if subkey in item:
                                                        video_urls.append(item[subkey])
                            except:
                                # Not JSON, check if direct URL
                                if resp.text.startswith('http'):
                                    video_urls.append(resp.text.strip())
                    except:
                        pass
                
                # POST request to common API endpoints
                post_endpoints = [
                    f'{base_url}/api/source/{video_id}',
                    f'{base_url}/download',
                    f'{base_url}/get-link',
                ]
                
                for endpoint in post_endpoints:
                    try:
                        resp = session.post(
                            endpoint,
                            headers=headers,
                            data={'id': video_id, 'video_id': video_id},
                            timeout=10
                        )
                        if resp.status_code == 200:
                            try:
                                data = resp.json()
                                for key in ['url', 'file', 'src', 'source', 'data']:
                                    if key in data:
                                        if isinstance(data[key], str):
                                            video_urls.append(data[key])
                                        elif isinstance(data[key], list):
                                            for item in data[key]:
                                                if isinstance(item, dict) and 'file' in item:
                                                    video_urls.append(item['file'])
                            except:
                                pass
                    except:
                        pass
                        
        except Exception as e:
            print(f"Error in API extraction: {e}")
        
        return video_urls
    
    async def extract_direct_video_url(self, url):
        """Ekstrak URL video langsung dari halaman streaming - uses universal extractor"""
        resolved_url = url
        try:
            # Use the universal extractor for better results
            video_urls, resolved_url = await universal_extractor.extract_all(url)
            if video_urls:
                return video_urls, resolved_url
            
            # Fallback to legacy extraction if universal extractor fails
            print("[Extractor] Universal extractor found nothing, trying legacy method...")
            
            resolved_url = self.resolve_url(url)
            if resolved_url != url:
                print(f"[Resolver] Resolved URL: {resolved_url}")
            url = resolved_url
            
            headers = self._build_headers(url)
            headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            session = requests.Session()
            self._load_cookies(session)

            # Quick check: direct media file or manifest
            try:
                head_resp = session.head(url, headers=headers, timeout=10, allow_redirects=True)
                content_type = head_resp.headers.get('content-type', '')
                content_disp = head_resp.headers.get('content-disposition', '')
                final_url = head_resp.url or url
                if self._looks_like_direct_media(final_url, content_type, content_disp):
                    return [final_url], resolved_url
            except requests.RequestException:
                pass
            
            # Try to get the page with session to handle cookies
            response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
            html = response.text
            
            # Parse dengan BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Cari video URL dari berbagai sumber
            video_urls = []
            
            # 0. Meta tags (og:video, twitter player, etc)
            meta_keys = {
                'og:video', 'og:video:url', 'og:video:secure_url',
                'twitter:player:stream', 'twitter:player:stream:url',
                'twitter:player', 'twitter:player:stream:content_url',
                'contenturl', 'embedurl'
            }
            for meta in soup.find_all('meta'):
                key = (meta.get('property') or meta.get('name') or '').lower()
                content = meta.get('content')
                if key in meta_keys and content:
                    video_urls.append(content)
            
            # 0b. Preload links for video
            for link in soup.find_all('link', href=True):
                rel = ' '.join(link.get('rel', [])).lower()
                as_attr = (link.get('as') or '').lower()
                if 'preload' in rel and as_attr in ['video', 'fetch']:
                    video_urls.append(link.get('href'))
            
            # 0c. JSON-LD data (contentUrl/embedUrl)
            def collect_from_ld(data):
                if isinstance(data, dict):
                    for key in ['contentUrl', 'embedUrl', 'url', 'fileUrl']:
                        value = data.get(key)
                        if isinstance(value, str):
                            video_urls.append(value)
                    for value in data.values():
                        collect_from_ld(value)
                elif isinstance(data, list):
                    for item in data:
                        collect_from_ld(item)
            
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    script_text = script.string or script.get_text()
                    if not script_text:
                        continue
                    data = json.loads(script_text)
                    collect_from_ld(data)
                except Exception:
                    pass
            
            # 1. Cari tag video langsung
            video_tags = soup.find_all('video')
            for video in video_tags:
                if video.get('src'):
                    video_urls.append(video.get('src'))
                sources = video.find_all('source')
                for source in sources:
                    if source.get('src'):
                        video_urls.append(source.get('src'))
            
            # 2. Cari di JavaScript untuk URL video (advanced extraction)
            video_urls.extend(self.extract_from_obfuscated_js(html, url))
            
            # 3. Cari iframe embed
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                iframe_src = iframe.get('src') or iframe.get('data-src')
                if iframe_src:
                    # Handle relative URLs
                    if iframe_src.startswith('//'):
                        iframe_src = 'https:' + iframe_src
                    elif iframe_src.startswith('/'):
                        parsed = urlparse(url)
                        iframe_src = f"{parsed.scheme}://{parsed.netloc}{iframe_src}"
                    elif not iframe_src.startswith('http'):
                        iframe_src = urljoin(url, iframe_src)
                    
                    # Follow iframe and extract from there
                    if 'embed' in iframe_src.lower() or 'player' in iframe_src.lower():
                        try:
                            iframe_resp = session.get(iframe_src, headers={**headers, 'Referer': url}, timeout=15)
                            iframe_urls = self.extract_from_obfuscated_js(iframe_resp.text, iframe_src)
                            video_urls.extend(iframe_urls)
                        except:
                            pass
                    
                    if any(ext in iframe_src.lower() for ext in ['.mp4', '.m3u8', 'stream']):
                        video_urls.append(iframe_src)
            
            # 4. Cari link download
            download_links = soup.find_all('a', href=True)
            for link in download_links:
                href = link.get('href', '')
                text = link.get_text().lower()
                class_attr = ' '.join(link.get('class', []))
                
                if any(word in text.lower() for word in ['download', 'unduh', '720p', '1080p', '480p', '360p', 'mp4', 'original']):
                    video_urls.append(href)
                if any(word in class_attr.lower() for word in ['download', 'btn-download']):
                    video_urls.append(href)
            
            # 5. Try API extraction
            api_urls = await self.try_api_extraction(url)
            video_urls.extend(api_urls)
            
            # 6. Look for redirect URLs in meta tags
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta_refresh:
                content = meta_refresh.get('content', '')
                url_match = re.search(r'url=([^"\']+)', content, re.IGNORECASE)
                if url_match:
                    video_urls.append(url_match.group(1))
            
            # Bersihkan dan validasi URL
            cleaned_urls = []
            for video_url in video_urls:
                if video_url and isinstance(video_url, str):
                    video_url = video_url.strip()
                    
                    if video_url.startswith(('data:', 'blob:', 'javascript:')):
                        continue
                    
                    # Handle relative URLs
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    if not video_url.startswith('http'):
                        video_url = urljoin(url, video_url)
                    
                    # Validate URL
                    if video_url.startswith('http'):
                        # Check for video extensions or streaming indicators
                        video_indicators = ['.mp4', '.m3u8', '.webm', '.mkv', '.avi', '.mov', '.mpd',
                                           'download', 'stream', 'video', 'media', 'cdn',
                                           'manifest', '/dl/', '/get/', '/source/']
                        
                        if any(ind in video_url.lower() for ind in video_indicators):
                            # Avoid tracking/ad URLs
                            avoid = ['google', 'facebook', 'twitter', 'analytics', 'adsense', 
                                    'doubleclick', 'pixel', 'tracking', '.js', '.css']
                            if not any(avoid_word in video_url.lower() for avoid_word in avoid):
                                cleaned_urls.append(video_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for u in cleaned_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)
            
            print(f"Found {len(unique_urls)} potential video URLs from basic extraction")
            
            # If no URLs found, try Selenium or Playwright as fallback
            if len(unique_urls) == 0:
                print("No URLs found with basic extraction, trying browser automation...")
                
                # Try Playwright first (faster and more reliable)
                try:
                    playwright_urls = await self.extract_with_playwright(url)
                    for u in playwright_urls:
                        if u and isinstance(u, str) and u.startswith('http') and u not in seen:
                            seen.add(u)
                            unique_urls.append(u)
                except Exception as e:
                    print(f"Playwright extraction failed: {e}")
                
                # If still no URLs, try Selenium
                if len(unique_urls) == 0:
                    try:
                        selenium_urls = await self.extract_with_selenium(url)
                        for u in selenium_urls:
                            if u and isinstance(u, str) and u.startswith('http') and u not in seen:
                                seen.add(u)
                                unique_urls.append(u)
                    except Exception as e:
                        print(f"Selenium extraction failed: {e}")
            
            print(f"Total: {len(unique_urls)} potential video URLs found")
            return unique_urls, resolved_url
            
        except Exception as e:
            print(f"Error extracting video URL: {e}")
            import traceback
            traceback.print_exc()
            return [], resolved_url
    
    async def download_with_custom_extractor(self, url, format_type='video'):
        """Download menggunakan universal extractor (like 9xbuddy)"""
        try:
            # Use the new universal extractor with network interception
            print(f"[CustomExtractor] Using universal extractor for: {url}")
            video_urls, resolved_url = await universal_extractor.extract_all(url)
            url = resolved_url
            
            if not video_urls:
                return {'success': False, 'error': 'Tidak dapat menemukan URL video. Platform ini mungkin memerlukan login atau memiliki proteksi anti-bot.'}
            
            print(f"Trying to download from {len(video_urls)} potential URLs")
            
            session = requests.Session()
            self._load_cookies(session)
            cookie_header = self._format_cookie_header(session)
            
            # Sort URLs by priority (MP4 first, then M3U8, then others)
            def url_priority(u):
                u_lower = u.lower()
                if '.mp4' in u_lower:
                    # Prefer higher quality
                    if '1080' in u_lower: return 0
                    if '720' in u_lower: return 1
                    if '480' in u_lower: return 2
                    return 3
                elif '.m3u8' in u_lower:
                    return 10
                elif '.webm' in u_lower:
                    return 5
                return 20
            
            video_urls.sort(key=url_priority)
            
            # Generate filename
            url_hash = hashlib.md5(resolved_url.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type == 'audio':
                filename = f"{DOWNLOAD_PATH}audio_{timestamp}_{url_hash}.mp3"
                temp_video = f"{DOWNLOAD_PATH}temp_{timestamp}_{url_hash}.mp4"
            else:
                filename = f"{DOWNLOAD_PATH}video_{timestamp}_{url_hash}.mp4"
                temp_video = filename
            
            # Try each URL until one works
            last_error = None
            for video_url in video_urls[:5]:  # Try first 5 URLs
                try:
                    print(f"Trying URL: {video_url[:100]}...")
                    
                    headers = self._build_headers(resolved_url)
                    headers.update({
                        'Accept-Encoding': 'identity',
                        'Range': 'bytes=0-'
                    })
                    
                    # Check if it's a streaming manifest (HLS/DASH)
                    if self._is_stream_manifest(video_url):
                        # Use ffmpeg to download stream
                        try:
                            print("Downloading HLS stream with ffmpeg...")
                            header_lines = (
                                f"Referer: {resolved_url}\r\n"
                                "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
                            )
                            if cookie_header:
                                header_lines += f"Cookie: {cookie_header}\r\n"
                            
                            result = subprocess.run([
                                'ffmpeg', '-y',
                                '-headers', header_lines,
                                '-i', video_url,
                                '-c', 'copy',
                                '-bsf:a', 'aac_adtstoasc',
                                temp_video
                            ], capture_output=True, timeout=300)
                            
                            if os.path.exists(temp_video) and os.path.getsize(temp_video) > 10000:
                                print("HLS download successful")
                                break
                            else:
                                last_error = "HLS download produced empty file"
                                if os.path.exists(temp_video):
                                    os.remove(temp_video)
                                continue
                        except Exception as e:
                            last_error = str(e)
                            print(f"FFmpeg HLS download failed: {e}")
                            continue
                    
                    # Regular HTTP download
                    response = session.get(video_url, headers=headers, stream=True, timeout=120, allow_redirects=True)
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    content_length = int(response.headers.get('content-length', 0))
                    
                    print(f"Response: {response.status_code}, Content-Type: {content_type}, Size: {content_length}")
                    
                    # Skip if it's not a video
                    if response.status_code != 200 and response.status_code != 206:
                        last_error = f"HTTP {response.status_code}"
                        continue
                    
                    if self._is_stream_manifest(video_url, content_type):
                        response.close()
                        try:
                            print("Detected streaming manifest, downloading with ffmpeg...")
                            header_lines = (
                                f"Referer: {resolved_url}\r\n"
                                "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
                            )
                            if cookie_header:
                                header_lines += f"Cookie: {cookie_header}\r\n"
                            
                            result = subprocess.run([
                                'ffmpeg', '-y',
                                '-headers', header_lines,
                                '-i', video_url,
                                '-c', 'copy',
                                '-bsf:a', 'aac_adtstoasc',
                                temp_video
                            ], capture_output=True, timeout=300)
                            
                            if os.path.exists(temp_video) and os.path.getsize(temp_video) > 10000:
                                print("Stream download successful")
                                break
                            last_error = "Stream download produced empty file"
                            if os.path.exists(temp_video):
                                os.remove(temp_video)
                            continue
                        except Exception as e:
                            last_error = str(e)
                            print(f"FFmpeg stream download failed: {e}")
                            continue
                    
                    if 'text/html' in content_type and content_length < 100000:
                        last_error = "Response is HTML, not video"
                        continue
                    
                    # Download the file
                    downloaded_size = 0
                    with open(temp_video, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                    
                    # Verify file is valid
                    if downloaded_size < 10000:  # Less than 10KB is probably an error page
                        last_error = f"Downloaded file too small ({downloaded_size} bytes)"
                        if os.path.exists(temp_video):
                            os.remove(temp_video)
                        continue
                    
                    print(f"Downloaded {downloaded_size} bytes successfully")
                    
                    # Verify it's a valid video file
                    try:
                        result = subprocess.run(
                            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1', temp_video],
                            capture_output=True,
                            timeout=30
                        )
                        if result.returncode != 0:
                            # Try to fix with ffmpeg
                            fixed_file = temp_video.replace('.mp4', '_fixed.mp4')
                            subprocess.run(['ffmpeg', '-y', '-i', temp_video, '-c', 'copy', fixed_file], 
                                         capture_output=True, timeout=120)
                            if os.path.exists(fixed_file) and os.path.getsize(fixed_file) > 10000:
                                os.remove(temp_video)
                                os.rename(fixed_file, temp_video)
                    except:
                        pass  # ffprobe might not be available, continue anyway
                    
                    # File downloaded successfully
                    break
                    
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    print(f"Download failed: {e}")
                    continue
                except Exception as e:
                    last_error = str(e)
                    print(f"Error: {e}")
                    continue
            
            # Check if we got a valid file
            if not os.path.exists(temp_video) or os.path.getsize(temp_video) < 10000:
                return {'success': False, 'error': last_error or 'Gagal mendownload video dari semua sumber yang ditemukan'}
            
            # Convert to audio if needed
            if format_type == 'audio':
                try:
                    print("Converting to audio...")
                    result = subprocess.run([
                        'ffmpeg', '-y', '-i', temp_video, 
                        '-vn', '-acodec', 'libmp3lame',
                        '-ab', '192k', filename
                    ], capture_output=True, timeout=300)
                    
                    if os.path.exists(filename) and os.path.getsize(filename) > 1000:
                        os.remove(temp_video)
                    else:
                        # If audio conversion failed, rename video to mp3 extension
                        os.rename(temp_video, filename)
                        print("Audio conversion failed, using original file")
                except Exception as e:
                    print(f"FFmpeg conversion failed: {e}")
                    if os.path.exists(temp_video):
                        os.rename(temp_video, filename)
            
            # Extract title from URL
            path_parts = urlparse(url).path.split('/')
            title = 'Downloaded Video'
            for part in reversed(path_parts):
                if part and len(part) > 3:
                    title = part.split('.')[0].split('?')[0]
                    break
            
            return {
                'success': True,
                'filepath': filename,
                'title': title,
                'duration': 0
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    async def download_media(self, url, format_type='video'):
        """Download media dari berbagai platform"""
        platform = self.detect_platform(url)
        if platform == 'generic':
            resolved_url = self.resolve_url(url)
            if resolved_url != url:
                print(f"[Resolver] Expanded URL: {resolved_url}")
                url = resolved_url
                platform = self.detect_platform(url)
        is_streaming = self.is_streaming_platform(platform)
        allow_playlist = self._should_allow_playlist(url, platform)
        
        print(f"[Download] Platform: {platform}, Is Streaming: {is_streaming}, Format: {format_type}")
        
        # Untuk streaming platforms, langsung gunakan custom extractor karena yt-dlp biasanya gagal
        if is_streaming and platform not in ['youtube', 'twitter', 'instagram', 'tiktok', 'facebook']:
            yt_first = None
            if allow_playlist:
                try:
                    yt_first = await self._download_with_ytdlp(
                        url,
                        format_type,
                        platform,
                        force_generic=(platform == 'generic'),
                        allow_playlist=allow_playlist
                    )
                    if yt_first.get('success'):
                        return yt_first
                except Exception as e:
                    print(f"[Download] yt-dlp playlist attempt failed: {e}")

            print(f"[Download] Using custom extractor for streaming platform: {platform}")
            result = await self.download_with_custom_extractor(url, format_type)
            
            # Jika custom extractor gagal, coba yt-dlp sebagai fallback
            if not result['success']:
                print(f"[Download] Custom extractor failed, trying yt-dlp as fallback...")
                try:
                    if yt_first is not None:
                        yt_result = yt_first
                    else:
                        yt_result = await self._download_with_ytdlp(
                            url,
                            format_type,
                            platform,
                            force_generic=(platform == 'generic'),
                            allow_playlist=allow_playlist
                        )
                    if yt_result['success']:
                        return yt_result
                    if "Unsupported URL" in (yt_result.get('error') or ""):
                        yt_generic = await self._download_with_ytdlp(
                            url,
                            format_type,
                            platform,
                            force_generic=True,
                            allow_playlist=allow_playlist
                        )
                        if yt_generic['success']:
                            return yt_generic
                except Exception as e:
                    print(f"[Download] yt-dlp fallback also failed: {e}")
            
            return result
        
        # Untuk social media platforms, gunakan yt-dlp terlebih dahulu
        try:
            result = await self._download_with_ytdlp(
                url,
                format_type,
                platform,
                force_generic=(platform == 'generic'),
                allow_playlist=allow_playlist
            )
            if result['success']:
                return result
        except Exception as yt_error:
            print(f"[Download] yt-dlp failed for {platform}: {yt_error}")
        
        # Fallback ke custom extractor jika yt-dlp gagal
        print(f"[Download] Falling back to custom extractor...")
        return await self.download_with_custom_extractor(url, format_type)
    
    async def _download_with_ytdlp(self, url, format_type, platform, force_generic=False, allow_playlist=False):
        """Download menggunakan yt-dlp"""
        try:
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_PATH}%(title).100s_%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 60,
                'retries': 5,
                'fragment_retries': 5,
                'file_access_retries': 5,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web']
                    }
                }
            }
            
            if COOKIE_FILE and os.path.exists(COOKIE_FILE):
                ydl_opts['cookiefile'] = COOKIE_FILE
            
            if force_generic:
                ydl_opts['force_generic_extractor'] = True

            if allow_playlist:
                ydl_opts['noplaylist'] = False
                ydl_opts['playlist_items'] = f"1-{MAX_ARCHIVE_ITEMS}"
                ydl_opts['ignoreerrors'] = True
            else:
                ydl_opts['noplaylist'] = True

            # Tambahkan opsi khusus untuk streaming platforms
            if self.is_streaming_platform(platform):
                ydl_opts.update({
                    'geo_bypass': True,
                    'nocheckcertificate': True,
                    'allow_unplayable_formats': True,
                    'extractor_retries': 3,
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
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if info is None:
                    return {'success': False, 'error': 'No video info extracted'}

                files = self._collect_downloaded_files(ydl, info, format_type)
                if not files:
                    return {'success': False, 'error': 'Downloaded file not found'}

                if len(files) > 1:
                    archive_title = info.get('title') or info.get('playlist_title') or 'Downloaded Files'
                    archive_path, archive_error = self._create_zip_archive(files, archive_title)
                    for path in files:
                        if os.path.exists(path):
                            os.remove(path)
                    if archive_error:
                        return {'success': False, 'error': archive_error}
                    return {
                        'success': True,
                        'filepath': archive_path,
                        'title': archive_title,
                        'duration': 0,
                        'is_archive': True,
                        'item_count': len(files)
                    }

                filename = files[0]
                if not os.path.exists(filename):
                    return {'success': False, 'error': 'Downloaded file not found'}

                return {
                    'success': True,
                    'filepath': filename,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0)
                }
                
        except Exception as e:
            error_msg = str(e)
            # Truncate long error messages
            if len(error_msg) > 300:
                error_msg = error_msg[:300] + "..."
            return {
                'success': False,
                'error': error_msg
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
    
    url = text
    if not url_pattern.match(url):
        if re.match(r'^[\w.-]+\.[a-zA-Z]{2,}(/\S*)?$', url):
            url = 'https://' + url
        else:
            await update.message.reply_text(
                get_text(update, 'send_link'),
                reply_markup=get_main_keyboard(update)
            )
            return
    
    try:
        resolved_url = await asyncio.to_thread(bot.resolve_url, url)
        if resolved_url:
            url = resolved_url
    except Exception as e:
        print(f"[Resolver] Failed to resolve URL: {e}")
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
        'original_url': text,
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
            max_size = MAX_FILE_SIZE
            
            if result.get('is_archive'):
                item_count = result.get('item_count', 0)
                caption = LANGUAGES[lang]['archive_caption'].format(result.get('title', 'Downloaded Files'), item_count)
                if file_size > max_size:
                    size_mb = file_size / (1024 * 1024)
                    error_text = f"Archive too large ({size_mb:.1f}MB)"
                    await status_msg.edit_text(LANGUAGES[lang]['download_failed'].format(error_text))
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    if url_id in context.user_data:
                        del context.user_data[url_id]
                    return
                with open(filepath, 'rb') as document:
                    await query.message.reply_document(
                        document=document,
                        caption=caption,
                        parse_mode='Markdown'
                    )
            # Kirim berdasarkan format type
            elif format_type == 'photo':
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
    print("🤖 SafeRobot v6.0 - Universal Video Downloader")
    print("   Like 9xbuddy.site - Download from ANY website!")
    print("=" * 60)
    print()
    print("📋 CONFIGURATION:")
    print(f"   👑 Owner ID: {OWNER_ID}")
    print(f"   💾 Database: {DATABASE_PATH}")
    print(f"   📁 Downloads: {DOWNLOAD_PATH}")
    print()
    print("🌐 NEW FEATURES v5.0:")
    print("   ✅ Universal Video Extraction (like 9xbuddy)")
    print("   ✅ Network Interception - captures ALL video streams")
    print("   ✅ Playwright-based browser automation")
    print("   ✅ External API fallbacks (cobalt, etc)")
    print("   ✅ Multi-language support: ID/EN")
    print("   ✅ Auto-zip for playlists/folders")
    print()
    print("📱 SOCIAL MEDIA PLATFORMS:")
    print("   • TikTok, Instagram, Twitter/X")
    print("   • YouTube, Facebook, Pinterest")
    print()
    print("🎬 STREAMING PLATFORMS:")
    print("   • DoodStream, TeraBox, Videy, Videq")
    print("   • LuluStream, VidCloud, StreamTape, MixDrop")
    print("   • MyVidPlay, Filemoon, StreamWish, VidHide")
    print("   • Dan 100+ platform lainnya!")
    print()
    print("🔥 UNIVERSAL EXTRACTION:")
    print("   • Can extract video from ANY website")
    print("   • Network request interception")
    print("   • JavaScript player detection")
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
