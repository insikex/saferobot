#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SafeRobot v5.0 - Telegram Bot
Multi-platform downloader & Sticker maker with WhatsApp support
Enhanced features: YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter
"""

import os
import re
import asyncio
import json
import zipfile
import io
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, PreCheckoutQueryHandler, ConversationHandler
import yt_dlp
from urllib.parse import urlparse
from PIL import Image

# ============================================
# KONFIGURASI
# ============================================
BOT_TOKEN = "7389890441:AAGkXEXHedGHYrmXq3Vp5RlT8Y5_kBChL5Q"
OWNER_ID = 6683929810
DOWNLOAD_PATH = "./downloads/"
STICKER_PATH = "./stickers/"
DATABASE_PATH = "./users_database.json"
PREMIUM_PRICE_STARS = 200
PROVIDER_TOKEN = ""

# Default sticker pack name for branding
DEFAULT_STICKER_PACK_TITLE = "Made in @SafeRobot"
SAFEROBOT_STICKER_PACK = "https://t.me/addstickers/saferobot"

FREE_STICKER_LIMIT = 30
FREE_VIDEO_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB
PREMIUM_VIDEO_SIZE_LIMIT = 250 * 1024 * 1024  # 250 MB untuk premium

# State untuk conversation handler
WAITING_PACK_NAME = 1
WAITING_CUSTOM_NAME = 2

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)
if not os.path.exists(STICKER_PATH):
    os.makedirs(STICKER_PATH)

# ============================================
# DATABASE - ENHANCED WITH CUSTOM NAME SUPPORT
# ============================================
class UserDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.load_database()
    
    def load_database(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
                # Pastikan sticker_packs ada di database lama
                if 'sticker_packs' not in self.data:
                    self.data['sticker_packs'] = {}
                    self.save_database()
        else:
            self.data = {
                'users': {},
                'stats': {
                    'total_downloads': 0,
                    'video_downloads': 0,
                    'audio_downloads': 0,
                    'total_stickers': 0,
                    'premium_users': 0
                },
                'sticker_packs': {}
            }
            self.save_database()
    
    def save_database(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def save_sticker_pack(self, user_id, pack_name, sticker_count, sticker_set_name=None):
        """Simpan sticker pack ke favorites"""
        user_id_str = str(user_id)
        if user_id_str not in self.data['sticker_packs']:
            self.data['sticker_packs'][user_id_str] = []
        
        pack_data = {
            'pack_name': pack_name,
            'created_at': datetime.now().isoformat(),
            'sticker_count': sticker_count,
            'sticker_set_name': sticker_set_name
        }
        
        self.data['sticker_packs'][user_id_str].append(pack_data)
        self.save_database()
        return pack_data
    
    def get_sticker_packs(self, user_id):
        """Get all saved sticker packs"""
        user_id_str = str(user_id)
        return self.data['sticker_packs'].get(user_id_str, [])
    
    def delete_sticker_pack(self, user_id, pack_index):
        """Delete sticker pack"""
        user_id_str = str(user_id)
        if user_id_str in self.data['sticker_packs']:
            if 0 <= pack_index < len(self.data['sticker_packs'][user_id_str]):
                deleted = self.data['sticker_packs'][user_id_str].pop(pack_index)
                self.save_database()
                return deleted
        return None
    
    def set_current_pack_name(self, user_id, pack_name):
        """Set current working pack name"""
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['current_pack_name'] = pack_name
            self.save_database()
    
    def get_current_pack_name(self, user_id):
        """Get current working pack name"""
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            return self.data['users'][user_id_str].get('current_pack_name', DEFAULT_STICKER_PACK_TITLE)
        return DEFAULT_STICKER_PACK_TITLE
    
    def set_custom_sticker_name(self, user_id, custom_name):
        """Set custom sticker pack title (premium only)"""
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['custom_sticker_name'] = custom_name
            self.save_database()
    
    def get_custom_sticker_name(self, user_id):
        """Get custom sticker pack title"""
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            return self.data['users'][user_id_str].get('custom_sticker_name', DEFAULT_STICKER_PACK_TITLE)
        return DEFAULT_STICKER_PACK_TITLE
    
    def set_current_sticker_set_name(self, user_id, sticker_set_name):
        """Set current sticker set name for Telegram"""
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['current_sticker_set_name'] = sticker_set_name
            self.save_database()
    
    def get_current_sticker_set_name(self, user_id):
        """Get current sticker set name for Telegram"""
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            return self.data['users'][user_id_str].get('current_sticker_set_name')
        return None
    
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
                'audio_downloads': 0,
                'sticker_count': 0,
                'is_premium': False,
                'premium_until': None,
                'current_sticker_pack_count': 0,
                'current_pack_name': DEFAULT_STICKER_PACK_TITLE,
                'custom_sticker_name': DEFAULT_STICKER_PACK_TITLE,
                'current_sticker_set_name': None
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
    
    def increment_sticker(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['sticker_count'] += 1
            self.data['users'][user_id_str]['current_sticker_pack_count'] += 1
            self.data['stats']['total_stickers'] += 1
            self.save_database()
    
    def reset_sticker_pack_count(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['current_sticker_pack_count'] = 0
            self.data['users'][user_id_str]['current_sticker_set_name'] = None
            self.save_database()
    
    def get_user(self, user_id):
        user_id_str = str(user_id)
        return self.data['users'].get(user_id_str)
    
    def is_premium(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            user = self.data['users'][user_id_str]
            if user.get('is_premium') and user.get('premium_until'):
                premium_until = datetime.fromisoformat(user['premium_until'])
                if datetime.now() < premium_until:
                    return True
                else:
                    self.data['users'][user_id_str]['is_premium'] = False
                    self.data['stats']['premium_users'] = max(0, self.data['stats']['premium_users'] - 1)
                    self.save_database()
        return False
    
    def set_premium(self, user_id, months=1):
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            was_premium = self.data['users'][user_id_str].get('is_premium', False)
            
            now = datetime.now()
            current_premium = self.data['users'][user_id_str].get('premium_until')
            
            if current_premium:
                premium_until = datetime.fromisoformat(current_premium)
                if premium_until > now:
                    new_premium_until = premium_until + timedelta(days=30 * months)
                else:
                    new_premium_until = now + timedelta(days=30 * months)
            else:
                new_premium_until = now + timedelta(days=30 * months)
            
            self.data['users'][user_id_str]['is_premium'] = True
            self.data['users'][user_id_str]['premium_until'] = new_premium_until.isoformat()
            
            if not was_premium:
                self.data['stats']['premium_users'] += 1
            
            self.save_database()
            return new_premium_until
    
    def get_stats(self):
        total_users = len(self.data['users'])
        now = datetime.now()
        active_threshold = now - timedelta(days=7)
        
        active_users = 0
        inactive_users = 0
        indonesia_users = 0
        international_users = 0
        active_premium = 0
        
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
            
            if user_data.get('is_premium') and user_data.get('premium_until'):
                premium_until = datetime.fromisoformat(user_data['premium_until'])
                if now < premium_until:
                    active_premium += 1
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'indonesia_users': indonesia_users,
            'international_users': international_users,
            'total_downloads': self.data['stats']['total_downloads'],
            'video_downloads': self.data['stats']['video_downloads'],
            'audio_downloads': self.data['stats']['audio_downloads'],
            'total_stickers': self.data['stats']['total_stickers'],
            'premium_users': active_premium
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
# LANGUAGES - ENHANCED
# ============================================
LANGUAGES = {
    'id': {
        'welcome': f"""🤖 *Selamat datang di SafeRobot!*

Bot downloader & sticker maker serba bisa!

🔥 *Fitur:*
• Download YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter
• Sticker Maker dari foto
• Export stiker ke WhatsApp
• Simpan sticker pack favorit

📦 *Sticker Pack Official:*
{SAFEROBOT_STICKER_PACK}

Kirim link atau foto untuk mulai! 👇""",
        'newpack_prompt': "📦 *Buat Sticker Pack Baru*\n\nKirim nama untuk pack sticker Anda:\n(contoh: My Cool Stickers)\n\nAtau /cancel untuk batal",
        'pack_created': "✅ Pack *'{}'* berhasil dibuat!\n\nSekarang kirim foto untuk menambah sticker.",
        'pack_saved': "💾 *Pack Tersimpan!*\n\n📦 Nama: {}\n🎨 Sticker: {} buah\n\n✅ Pack sudah tersimpan di favorites!",
        'my_packs_empty': f"📦 Anda belum punya pack tersimpan.\n\nKetik /newpack untuk membuat pack baru!\n\n📦 *Sticker Pack Official:*\n{SAFEROBOT_STICKER_PACK}",
        'my_packs_list': "📦 *Sticker Pack Anda*\n\nTotal: {} pack\n\n",
        'pack_deleted': "🗑️ Pack berhasil dihapus!",
        'save_pack_button': "💾 Simpan Pack",
        'delete_pack_button': "🗑️ Hapus",
        'cancel_button': "❌ Batal",
        'pack_name_cancelled': "❌ Pembuatan pack dibatalkan.",
        'sticker_with_save': "✅ Sticker berhasil dibuat!\n\n{}",
        'menu_mypacks': "📦 Pack Saya",
        'whatsapp_export': "📲 Export ke WhatsApp",
        'whatsapp_info': """📲 *Export Sticker ke WhatsApp*

Sticker pack sudah siap! Download file .zip di bawah ini.

*Cara menambahkan ke WhatsApp:*
1. Download file zip
2. Extract file
3. Gunakan aplikasi Sticker Maker di Play Store/App Store
4. Import stiker dari folder hasil extract

📦 Nama Pack: {}
🎨 Jumlah: {} stiker""",
        'custom_name_prompt': """✏️ *Custom Nama Sticker Pack*

Anda adalah user Premium! 👑

Kirim nama custom untuk sticker pack Anda:
(maksimal 50 karakter)

Nama saat ini: {}

Atau /cancel untuk batal""",
        'custom_name_set': "✅ Nama sticker pack berhasil diubah ke: *{}*",
        'custom_name_free': f"❌ Fitur ini hanya untuk user Premium!\n\nNama default Anda: *{DEFAULT_STICKER_PACK_TITLE}*\n\n💡 Upgrade ke Premium untuk custom nama!",
        'about': f"""ℹ️ *Tentang SafeRobot*

@SafeRobot adalah bot Telegram untuk download konten dan membuat sticker!

*Fitur Utama:*
⚡ Download cepat dari multi-platform
🎯 YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter
🎨 Sticker Maker + Export ke WhatsApp
🔒 Aman & privat

📦 *Sticker Pack Official:*
{SAFEROBOT_STICKER_PACK}

Terima kasih! 🙏""",
        'premium_info': f"""👑 *PREMIUM FEATURES*

*FREE USER:*
• Video/Audio max 50MB
• 30 stiker/pack
• Nama pack: "{DEFAULT_STICKER_PACK_TITLE}"
• Export ke WhatsApp ✅

*PREMIUM (200 ⭐/bulan):*
• Video/Audio max 250MB
• Unlimited stickers
• Custom nama pack
• Export ke WhatsApp ✅
• Priority support

💎 Upgrade sekarang!""",
        'detected': "✅ Link *{}* terdeteksi!\n\nPilih format:",
        'downloading': "⏳ Download {}...",
        'sending': "📤 Mengirim...",
        'video_caption': "🎥 *{}*\n\n🔥 by SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 by SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 by SafeRobot",
        'sticker_limit_reached': "⚠️ *Limit tercapai!*\n\nAnda sudah buat {} stiker.\n\n💡 Ketik /newpack untuk pack baru\n👑 Atau upgrade PREMIUM!",
        'processing_sticker': "🎨 Memproses gambar...",
        'download_failed': "❌ Download gagal!\n\nError: {}\n\nCoba link lain.",
        'error_occurred': "❌ Error: {}",
        'video_button': "🎥 Video (MP4)",
        'audio_button': "🎵 Audio (MP3)",
        'photo_button': "📷 Foto",
        'menu_about': "ℹ️ Tentang",
        'menu_premium': "👑 Premium",
        'menu_start': "🏠 Menu Utama",
        'menu_mystatus': "📊 Status",
        'send_link': "🔎 Kirim link atau foto!",
        'premium_active': "👑 *PREMIUM AKTIF*\n\n✅ Hingga: {}\n\n*Benefit:*\n• 250MB download\n• Unlimited stickers\n• Custom nama pack\n• WhatsApp export",
        'free_user': f"📊 *STATUS*\n\n🆓 FREE User\n📊 Download: {{}}\n🎨 Sticker: {{}}\n📦 Nama Pack: {DEFAULT_STICKER_PACK_TITLE}\n\n💡 Upgrade Premium untuk custom nama!",
        'payment_success': "✅ *Pembayaran Berhasil!*\n\n👑 Anda Premium!\n⏰ Hingga: {}\n\nSelamat! 🎉\n\n💡 Gunakan /customname untuk custom nama sticker pack!",
        'unsupported': "❌ Platform tidak didukung!\n\n✅ Didukung: YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter",
        'file_too_large': "⚠️ File terlalu besar ({:.1f}MB)!\n\n{}\n\n💡 {}",
        'file_too_large_free': "Limit free user: 50MB",
        'file_too_large_premium': "Limit premium: 250MB",
        'upgrade_hint': "Upgrade ke Premium untuk download hingga 250MB!",
        'try_smaller': "Coba video yang lebih pendek."
    },
    'en': {
        'welcome': f"""🤖 *Welcome to SafeRobot!*

All-in-one downloader & sticker maker bot!

🔥 *Features:*
• Download from YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter
• Sticker Maker from photos
• Export stickers to WhatsApp
• Save favorite sticker packs

📦 *Official Sticker Pack:*
{SAFEROBOT_STICKER_PACK}

Send link or photo to start! 👇""",
        'newpack_prompt': "📦 *Create New Sticker Pack*\n\nSend name for your sticker pack:\n(example: My Cool Stickers)\n\nOr /cancel to cancel",
        'pack_created': "✅ Pack *'{}'* created successfully!\n\nNow send photos to add stickers.",
        'pack_saved': "💾 *Pack Saved!*\n\n📦 Name: {}\n🎨 Stickers: {} pcs\n\n✅ Pack saved to favorites!",
        'my_packs_empty': f"📦 You don't have any saved packs yet.\n\nType /newpack to create a new pack!\n\n📦 *Official Sticker Pack:*\n{SAFEROBOT_STICKER_PACK}",
        'my_packs_list': "📦 *Your Sticker Packs*\n\nTotal: {} packs\n\n",
        'pack_deleted': "🗑️ Pack deleted successfully!",
        'save_pack_button': "💾 Save Pack",
        'delete_pack_button': "🗑️ Delete",
        'cancel_button': "❌ Cancel",
        'pack_name_cancelled': "❌ Pack creation cancelled.",
        'sticker_with_save': "✅ Sticker created successfully!\n\n{}",
        'menu_mypacks': "📦 My Packs",
        'whatsapp_export': "📲 Export to WhatsApp",
        'whatsapp_info': """📲 *Export Sticker to WhatsApp*

Sticker pack is ready! Download the .zip file below.

*How to add to WhatsApp:*
1. Download the zip file
2. Extract the file
3. Use Sticker Maker app from Play Store/App Store
4. Import stickers from extracted folder

📦 Pack Name: {}
🎨 Count: {} stickers""",
        'custom_name_prompt': """✏️ *Custom Sticker Pack Name*

You are a Premium user! 👑

Send a custom name for your sticker pack:
(max 50 characters)

Current name: {}

Or /cancel to cancel""",
        'custom_name_set': "✅ Sticker pack name changed to: *{}*",
        'custom_name_free': f"❌ This feature is for Premium users only!\n\nYour default name: *{DEFAULT_STICKER_PACK_TITLE}*\n\n💡 Upgrade to Premium for custom name!",
        'about': f"""ℹ️ *About SafeRobot*

@SafeRobot is a Telegram bot for downloading content and creating stickers!

*Main Features:*
⚡ Fast download from multi-platform
🎯 YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter
🎨 Sticker Maker + WhatsApp Export
🔒 Safe & private

📦 *Official Sticker Pack:*
{SAFEROBOT_STICKER_PACK}

Thank you! 🙏""",
        'premium_info': f"""👑 *PREMIUM FEATURES*

*FREE USER:*
• Video/Audio max 50MB
• 30 stickers/pack
• Pack name: "{DEFAULT_STICKER_PACK_TITLE}"
• WhatsApp export ✅

*PREMIUM (200 ⭐/month):*
• Video/Audio max 250MB
• Unlimited stickers
• Custom pack name
• WhatsApp export ✅
• Priority support

💎 Upgrade now!""",
        'detected': "✅ Link *{}* detected!\n\nChoose format:",
        'downloading': "⏳ Downloading {}...",
        'sending': "📤 Sending...",
        'video_caption': "🎥 *{}*\n\n🔥 by SafeRobot",
        'audio_caption': "🎵 *{}*\n\n🔥 by SafeRobot",
        'photo_caption': "📷 *{}*\n\n🔥 by SafeRobot",
        'sticker_limit_reached': "⚠️ *Limit reached!*\n\nYou've created {} stickers.\n\n💡 Type /newpack for new pack\n👑 Or upgrade PREMIUM!",
        'processing_sticker': "🎨 Processing image...",
        'download_failed': "❌ Download failed!\n\nError: {}\n\nTry another link.",
        'error_occurred': "❌ Error: {}",
        'video_button': "🎥 Video (MP4)",
        'audio_button': "🎵 Audio (MP3)",
        'photo_button': "📷 Photo",
        'menu_about': "ℹ️ About",
        'menu_premium': "👑 Premium",
        'menu_start': "🏠 Main Menu",
        'menu_mystatus': "📊 Status",
        'send_link': "🔎 Send link or photo!",
        'premium_active': "👑 *PREMIUM ACTIVE*\n\n✅ Until: {}\n\n*Benefits:*\n• 250MB download\n• Unlimited stickers\n• Custom pack name\n• WhatsApp export",
        'free_user': f"📊 *STATUS*\n\n🆓 FREE User\n📊 Downloads: {{}}\n🎨 Stickers: {{}}\n📦 Pack Name: {DEFAULT_STICKER_PACK_TITLE}\n\n💡 Upgrade Premium for custom name!",
        'payment_success': "✅ *Payment Successful!*\n\n👑 You're Premium!\n⏰ Until: {}\n\nEnjoy! 🎉\n\n💡 Use /customname to customize your sticker pack name!",
        'unsupported': "❌ Platform not supported!\n\n✅ Supported: YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter",
        'file_too_large': "⚠️ File too large ({:.1f}MB)!\n\n{}\n\n💡 {}",
        'file_too_large_free': "Free user limit: 50MB",
        'file_too_large_premium': "Premium limit: 250MB",
        'upgrade_hint': "Upgrade to Premium for downloads up to 250MB!",
        'try_smaller': "Try a shorter video."
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

def get_main_keyboard(update: Update):
    lang = get_user_language(update)
    keyboard = [
        [KeyboardButton(LANGUAGES[lang]['menu_about']), KeyboardButton(LANGUAGES[lang]['menu_premium'])],
        [KeyboardButton(LANGUAGES[lang]['menu_mystatus']), KeyboardButton(LANGUAGES[lang]['menu_mypacks'])]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

# ============================================
# STICKER FUNCTIONS - ENHANCED FOR WHATSAPP
# ============================================
async def process_image_to_sticker(image_path: str, output_path: str) -> bool:
    try:
        img = Image.open(image_path)
        
        if img.mode != 'RGBA':
            if img.mode == 'P' and 'transparency' in img.info:
                img = img.convert('RGBA')
            else:
                img = img.convert('RGBA')
        
        original_width, original_height = img.size
        max_size = 512
        
        if original_width > original_height:
            new_width = max_size
            new_height = int((max_size / original_width) * original_height)
        else:
            new_height = max_size
            new_width = int((max_size / original_height) * original_width)
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
        
        offset_x = (512 - new_width) // 2
        offset_y = (512 - new_height) // 2
        canvas.paste(img, (offset_x, offset_y), img)
        
        canvas.save(output_path, 'PNG', optimize=True)
        return True
    except Exception as e:
        print(f"Error processing image: {e}")
        return False

async def process_image_for_whatsapp(image_path: str, output_path: str) -> bool:
    """Process image for WhatsApp sticker format (512x512 WebP)"""
    try:
        img = Image.open(image_path)
        
        if img.mode != 'RGBA':
            if img.mode == 'P' and 'transparency' in img.info:
                img = img.convert('RGBA')
            else:
                img = img.convert('RGBA')
        
        original_width, original_height = img.size
        max_size = 512
        
        if original_width > original_height:
            new_width = max_size
            new_height = int((max_size / original_width) * original_height)
        else:
            new_height = max_size
            new_width = int((max_size / original_height) * original_width)
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
        
        offset_x = (512 - new_width) // 2
        offset_y = (512 - new_height) // 2
        canvas.paste(img, (offset_x, offset_y), img)
        
        # Save as WebP for WhatsApp
        canvas.save(output_path, 'WEBP', quality=90)
        return True
    except Exception as e:
        print(f"Error processing image for WhatsApp: {e}")
        return False

# ============================================
# SAFEROBOT CLASS - ENHANCED DOWNLOAD
# ============================================
class SafeRobot:
    def __init__(self):
        self.supported_platforms = {
            'tiktok': ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'],
            'instagram': ['instagram.com', 'instagr.am'],
            'twitter': ['twitter.com', 'x.com', 't.co'],
            'youtube': ['youtube.com', 'youtu.be', 'youtube.com/shorts'],
            'facebook': ['facebook.com', 'fb.watch', 'fb.com', 'm.facebook.com'],
            'pinterest': ['pinterest.com', 'pin.it', 'id.pinterest.com']
        }
    
    def detect_platform(self, url):
        domain = urlparse(url).netloc.lower()
        for platform, domains in self.supported_platforms.items():
            if any(d in domain for d in domains):
                return platform
        return None
    
    async def download_media(self, url, format_type='video', max_size=FREE_VIDEO_SIZE_LIMIT):
        """Enhanced download with better error handling and format support"""
        try:
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_PATH}%(title)s.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                'socket_timeout': 30,
                'retries': 3,
            }
            
            # Add cookies handling for some platforms
            cookies_file = './cookies.txt'
            if os.path.exists(cookies_file):
                ydl_opts['cookiefile'] = cookies_file
            
            if format_type == 'audio':
                # Enhanced audio configuration
                ydl_opts.update({
                    'format': 'bestaudio[ext=m4a]/bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'prefer_ffmpeg': True,
                    'keepvideo': False,
                })
            elif format_type == 'photo':
                ydl_opts.update({
                    'format': 'best',
                    'writethumbnail': True,
                })
            else:  # video
                if max_size == PREMIUM_VIDEO_SIZE_LIMIT:
                    ydl_opts.update({
                        'format': 'best[ext=mp4][filesize<?250M]/best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
                    })
                else:
                    ydl_opts.update({
                        'format': 'best[ext=mp4][filesize<?50M]/best[ext=mp4][height<=720]/bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best',
                    })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if format_type == 'audio':
                    # Find the resulting MP3 file
                    base_filename = ydl.prepare_filename(info)
                    filename = base_filename.rsplit('.', 1)[0] + '.mp3'
                    
                    # Wait for conversion to complete
                    await asyncio.sleep(1)
                    
                    if not os.path.exists(filename):
                        # Try other extensions
                        for ext in ['.m4a', '.opus', '.ogg', '.webm', '.mp4']:
                            test_file = base_filename.rsplit('.', 1)[0] + ext
                            if os.path.exists(test_file):
                                filename = test_file
                                break
                    
                    if not os.path.exists(filename):
                        # Try original filename
                        if os.path.exists(base_filename):
                            filename = base_filename
                        else:
                            raise Exception(f"Audio file not found after download")
                
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
                    # Handle webm to mp4 conversion
                    if not os.path.exists(filename):
                        base = filename.rsplit('.', 1)[0]
                        for ext in ['.mp4', '.webm', '.mkv']:
                            test_file = base + ext
                            if os.path.exists(test_file):
                                filename = test_file
                                break
                
                return {
                    'success': True,
                    'filepath': filename,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0)
                }
        
        except Exception as e:
            print(f"Download error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }

bot = SafeRobot()

# ============================================
# HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_or_update_user(user.id, user.username, user.first_name, user.language_code)
    
    welcome_msg = get_text(update, 'welcome')
    keyboard = get_main_keyboard(update)
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

# Handler untuk /newpack dengan conversation
async def newpack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new pack creation process"""
    lang = get_user_language(update)
    
    keyboard = [[InlineKeyboardButton(LANGUAGES[lang]['cancel_button'], callback_data="cancel_newpack")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        LANGUAGES[lang]['newpack_prompt'],
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return WAITING_PACK_NAME

async def receive_pack_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive pack name from user"""
    user_id = update.effective_user.id
    pack_name = update.message.text.strip()
    lang = get_user_language(update)
    
    # Validate pack name
    if len(pack_name) > 50:
        await update.message.reply_text("❌ Nama pack terlalu panjang! Maksimal 50 karakter." if lang == 'id' else "❌ Pack name too long! Max 50 characters.")
        return WAITING_PACK_NAME
    
    if len(pack_name) < 3:
        await update.message.reply_text("❌ Nama pack terlalu pendek! Minimal 3 karakter." if lang == 'id' else "❌ Pack name too short! Min 3 characters.")
        return WAITING_PACK_NAME
    
    # Reset counter and set pack name
    db.reset_sticker_pack_count(user_id)
    db.set_current_pack_name(user_id, pack_name)
    
    # Get the title based on premium status
    is_premium = db.is_premium(user_id)
    if is_premium:
        custom_name = db.get_custom_sticker_name(user_id)
        title_info = f"\n\n📛 Judul Pack: *{custom_name}*" if lang == 'id' else f"\n\n📛 Pack Title: *{custom_name}*"
    else:
        title_info = f"\n\n📛 Judul Pack: *{DEFAULT_STICKER_PACK_TITLE}*" if lang == 'id' else f"\n\n📛 Pack Title: *{DEFAULT_STICKER_PACK_TITLE}*"
    
    msg = LANGUAGES[lang]['pack_created'].format(pack_name) + title_info
    msg += f"\n\n💡 Kirim foto untuk membuat sticker pertama!" if lang == 'id' else "\n\n💡 Send a photo to create your first sticker!"
    
    await update.message.reply_text(
        msg,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def cancel_newpack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel pack creation"""
    query = update.callback_query
    await query.answer()
    
    lang = get_user_language(update)
    await query.edit_message_text(LANGUAGES[lang]['pack_name_cancelled'])
    
    return ConversationHandler.END

# Handler untuk /customname (premium only)
async def customname_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom name setting process (premium only)"""
    user_id = update.effective_user.id
    lang = get_user_language(update)
    
    if not db.is_premium(user_id):
        await update.message.reply_text(
            LANGUAGES[lang]['custom_name_free'],
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    current_name = db.get_custom_sticker_name(user_id)
    
    keyboard = [[InlineKeyboardButton(LANGUAGES[lang]['cancel_button'], callback_data="cancel_customname")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        LANGUAGES[lang]['custom_name_prompt'].format(current_name),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return WAITING_CUSTOM_NAME

async def receive_custom_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive custom name from user"""
    user_id = update.effective_user.id
    custom_name = update.message.text.strip()
    lang = get_user_language(update)
    
    # Validate custom name
    if len(custom_name) > 50:
        await update.message.reply_text("❌ Nama terlalu panjang! Maksimal 50 karakter." if lang == 'id' else "❌ Name too long! Max 50 characters.")
        return WAITING_CUSTOM_NAME
    
    if len(custom_name) < 3:
        await update.message.reply_text("❌ Nama terlalu pendek! Minimal 3 karakter." if lang == 'id' else "❌ Name too short! Min 3 characters.")
        return WAITING_CUSTOM_NAME
    
    # Set custom name
    db.set_custom_sticker_name(user_id, custom_name)
    
    await update.message.reply_text(
        LANGUAGES[lang]['custom_name_set'].format(custom_name),
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def cancel_customname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel custom name setting"""
    query = update.callback_query
    await query.answer()
    
    lang = get_user_language(update)
    await query.edit_message_text("❌ Dibatalkan." if lang == 'id' else "❌ Cancelled.")
    
    return ConversationHandler.END

# Handler untuk /mypacks
async def mypacks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all saved sticker packs"""
    user_id = update.effective_user.id
    lang = get_user_language(update)
    
    try:
        packs = db.get_sticker_packs(user_id)
        
        if not packs or len(packs) == 0:
            keyboard = [[InlineKeyboardButton(f"📦 Official Pack", url=SAFEROBOT_STICKER_PACK)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                LANGUAGES[lang]['my_packs_empty'],
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
        
        msg = LANGUAGES[lang]['my_packs_list'].format(len(packs))
        
        keyboard = []
        for i, pack in enumerate(packs):
            try:
                created_date = datetime.fromisoformat(pack['created_at']).strftime('%d/%m/%Y')
            except:
                created_date = "Unknown"
            
            pack_name = pack.get('pack_name', 'Unnamed')
            sticker_count = pack.get('sticker_count', 0)
            sticker_set_name = pack.get('sticker_set_name')
            
            pack_text = f"{i+1}. 📦 {pack_name} ({sticker_count} stiker) - {created_date}"
            msg += pack_text + "\n"
            
            # Button row for each pack
            row = []
            if sticker_set_name:
                row.append(InlineKeyboardButton(
                    f"➕ Add",
                    url=f"https://t.me/addstickers/{sticker_set_name}"
                ))
            
            row.append(InlineKeyboardButton(
                f"🗑️",
                callback_data=f"delpack_{i}"
            ))
            
            keyboard.append(row)
        
        # Add official pack button
        keyboard.append([InlineKeyboardButton(f"📦 Official SafeRobot Pack", url=SAFEROBOT_STICKER_PACK)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            msg,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error in mypacks_command: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            f"❌ Error: {str(e)}\n\nCoba lagi dengan /newpack untuk membuat pack baru."
        )

async def mystatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user status"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    lang = get_user_language(update)
    
    if not user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    if db.is_premium(user_id):
        premium_until = datetime.fromisoformat(user_data['premium_until'])
        custom_name = db.get_custom_sticker_name(user_id)
        msg = LANGUAGES[lang]['premium_active'].format(
            premium_until.strftime('%Y-%m-%d %H:%M')
        )
        msg += f"\n\n📛 Nama Pack: *{custom_name}*"
    else:
        msg = LANGUAGES[lang]['free_user'].format(
            user_data['download_count'],
            user_data['sticker_count']
        )
    
    keyboard = [[InlineKeyboardButton(f"📦 Official Pack", url=SAFEROBOT_STICKER_PACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium info and payment button"""
    lang = get_user_language(update)
    
    keyboard = [[
        InlineKeyboardButton(
            "💎 Upgrade ke Premium (200 ⭐)" if lang == 'id' else "💎 Upgrade to Premium (200 ⭐)",
            callback_data="buy_premium"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        LANGUAGES[lang]['premium_info'],
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
├ 🌍 International: `{stats['international_users']}`
└ 👑 Premium Users: `{stats['premium_users']}`

🔥 *DOWNLOAD STATISTICS*
├ Total Downloads: `{stats['total_downloads']}`
├ 🎥 Video: `{stats['video_downloads']}`
└ 🎵 Audio: `{stats['audio_downloads']}`

🎨 *STICKER STATISTICS*
└ Total Stickers: `{stats['total_stickers']}`

🏆 *TOP 5 USERS*
"""
    
    for i, user in enumerate(top_users, 1):
        username = f"@{user['username']}" if user['username'] else user['first_name']
        premium = "👑" if user.get('is_premium') else ""
        stats_msg += f"{i}. {username} {premium}- `{user['download_count']}` downloads\n"
    
    stats_msg += "\n━━━━━━━━━━━━━━━━━━━━"
    
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
            "Contoh: `/broadcast Halo semua!`",
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
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
    
    await status_msg.edit_text(
        f"✅ Broadcast selesai!\n\n"
        f"✅ Berhasil: {success}\n"
        f"❌ Gagal: {failed}"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk foto - membuat sticker dan tambahkan ke sticker set Telegram"""
    user = update.effective_user
    user_id = user.id
    lang = get_user_language(update)
    
    db.add_or_update_user(user.id, user.username, user.first_name, user.language_code)
    
    user_data = db.get_user(user_id)
    is_premium = db.is_premium(user_id)
    
    if not is_premium:
        if user_data['current_sticker_pack_count'] >= FREE_STICKER_LIMIT:
            await update.message.reply_text(
                LANGUAGES[lang]['sticker_limit_reached'].format(FREE_STICKER_LIMIT),
                parse_mode='Markdown'
            )
            return
    
    status_msg = await update.message.reply_text(LANGUAGES[lang]['processing_sticker'])
    
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        original_width = photo.width
        original_height = photo.height
        file_size_mb = file.file_size / (1024 * 1024) if file.file_size else 0
        
        timestamp = datetime.now().timestamp()
        photo_path = f"{STICKER_PATH}temp_{user_id}_{timestamp}.jpg"
        sticker_path = f"{STICKER_PATH}sticker_{user_id}_{timestamp}.png"
        whatsapp_path = f"{STICKER_PATH}wa_{user_id}_{timestamp}.webp"
        
        await file.download_to_drive(photo_path)
        
        # Process for Telegram sticker
        success = await process_image_to_sticker(photo_path, sticker_path)
        
        # Also process for WhatsApp
        await process_image_for_whatsapp(photo_path, whatsapp_path)
        
        if success:
            pack_name = db.get_current_pack_name(user_id)
            
            # Get sticker pack title based on premium status
            if is_premium:
                pack_title = db.get_custom_sticker_name(user_id)
            else:
                pack_title = DEFAULT_STICKER_PACK_TITLE
            
            # Upload sticker file to get file_id
            with open(sticker_path, 'rb') as sticker_file:
                sticker_msg = await update.message.reply_sticker(sticker=sticker_file)
                sticker_file_id = sticker_msg.sticker.file_id
            
            # Create unique sticker set name
            bot_username = (await context.bot.get_me()).username
            safe_pack_name = re.sub(r'[^a-zA-Z0-9]', '', pack_name.lower())[:20]
            if not safe_pack_name:
                safe_pack_name = "pack"
            sticker_set_name = f"u{user_id}_{safe_pack_name}_by_{bot_username}".lower()
            
            sticker_set_url = None
            sticker_set_created = False
            
            try:
                # Check if sticker set exists
                sticker_set = await context.bot.get_sticker_set(sticker_set_name)
                
                # Set exists, add new sticker
                try:
                    from telegram import InputSticker
                    await context.bot.add_sticker_to_set(
                        user_id=user_id,
                        name=sticker_set_name,
                        sticker=InputSticker(
                            sticker=sticker_file_id,
                            emoji_list=["😀"],
                            format="static"
                        )
                    )
                    sticker_set_url = f"https://t.me/addstickers/{sticker_set_name}"
                    sticker_set_created = True
                    db.set_current_sticker_set_name(user_id, sticker_set_name)
                except Exception as add_error:
                    print(f"Error adding to existing set: {add_error}")
                    pass
                
            except Exception as get_error:
                # Sticker set doesn't exist, create new one
                try:
                    from telegram import InputSticker
                    
                    # Pack title with branding for free users
                    full_pack_title = f"{pack_name} - {pack_title}"
                    if len(full_pack_title) > 64:
                        full_pack_title = full_pack_title[:64]
                    
                    await context.bot.create_new_sticker_set(
                        user_id=user_id,
                        name=sticker_set_name,
                        title=full_pack_title,
                        stickers=[
                            InputSticker(
                                sticker=sticker_file_id,
                                emoji_list=["😀"],
                                format="static"
                            )
                        ],
                        sticker_type="regular"
                    )
                    sticker_set_url = f"https://t.me/addstickers/{sticker_set_name}"
                    sticker_set_created = True
                    db.set_current_sticker_set_name(user_id, sticker_set_name)
                except Exception as create_error:
                    print(f"Error creating sticker set: {create_error}")
                    import traceback
                    traceback.print_exc()
                    pass
            
            db.increment_sticker(user_id)
            
            # Get updated count
            user_data = db.get_user(user_id)
            current_count = user_data['current_sticker_pack_count']
            
            remaining = "Unlimited ♾️" if is_premium else f"{FREE_STICKER_LIMIT - current_count}"
            
            info_text = (
                f"📦 Pack: {pack_name}\n"
                f"📛 Judul: {pack_title}\n"
                f"🎨 Stiker di pack: {current_count}\n"
                f"🎯 Sisa: {remaining}\n"
                f"📏 Original: {original_width}x{original_height}px ({file_size_mb:.2f}MB)\n"
                f"✨ Sticker: 512x512px"
            )
            
            # Build keyboard buttons
            keyboard = []
            if sticker_set_url and sticker_set_created:
                keyboard.append([
                    InlineKeyboardButton(
                        f"➕ Tambahkan {current_count} stiker ke Telegram" if lang == 'id' else f"➕ Add {current_count} stickers to Telegram",
                        url=sticker_set_url
                    )
                ])
            
            # WhatsApp export button
            keyboard.append([
                InlineKeyboardButton(
                    LANGUAGES[lang]['whatsapp_export'],
                    callback_data=f"wa_export_{user_id}_{current_count}"
                )
            ])
            
            # Save pack button if 3+ stickers
            if current_count >= 3:
                keyboard.append([
                    InlineKeyboardButton(
                        LANGUAGES[lang]['save_pack_button'],
                        callback_data=f"savepack_{user_id}_{current_count}"
                    )
                ])
            
            # Official pack link
            keyboard.append([
                InlineKeyboardButton(
                    "📦 Official SafeRobot Pack",
                    url=SAFEROBOT_STICKER_PACK
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            await status_msg.edit_text(
                LANGUAGES[lang]['sticker_with_save'].format(info_text),
                reply_markup=reply_markup
            )
            
            # Store WhatsApp sticker path for export
            if 'wa_stickers' not in context.user_data:
                context.user_data['wa_stickers'] = {}
            if user_id not in context.user_data['wa_stickers']:
                context.user_data['wa_stickers'][user_id] = []
            context.user_data['wa_stickers'][user_id].append(whatsapp_path)
            
            # Cleanup temp files
            if os.path.exists(photo_path):
                os.remove(photo_path)
            if os.path.exists(sticker_path):
                os.remove(sticker_path)
        else:
            await status_msg.edit_text("❌ Gagal memproses gambar!")
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        await status_msg.edit_text(
            LANGUAGES[lang]['error_occurred'].format(str(e))
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk semua pesan text"""
    user = update.effective_user
    text = update.message.text.strip()
    lang = get_user_language(update)
    
    db.add_or_update_user(user.id, user.username, user.first_name, user.language_code)
    
    # Handle menu buttons
    if text in [LANGUAGES['id']['menu_about'], LANGUAGES['en']['menu_about']]:
        about_msg = get_text(update, 'about')
        keyboard = [[InlineKeyboardButton(f"📦 Official Pack", url=SAFEROBOT_STICKER_PACK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(about_msg, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    elif text in [LANGUAGES['id']['menu_premium'], LANGUAGES['en']['menu_premium']]:
        await premium_command(update, context)
        return
    
    elif text in [LANGUAGES['id']['menu_mystatus'], LANGUAGES['en']['menu_mystatus']]:
        await mystatus_command(update, context)
        return
    
    elif text in [LANGUAGES['id']['menu_mypacks'], LANGUAGES['en']['menu_mypacks']]:
        await mypacks_command(update, context)
        return
    
    elif text in [LANGUAGES['id']['menu_start'], LANGUAGES['en']['menu_start']]:
        await start(update, context)
        return
    
    # Check if it's a URL
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
    
    url_id = str(hash(url))[-8:]
    context.user_data[url_id] = url
    
    # Build keyboard based on platform
    if platform == 'instagram':
        keyboard = [
            [
                InlineKeyboardButton(
                    LANGUAGES[lang]['video_button'], 
                    callback_data=f"v|{url_id}|{lang}"
                ),
                InlineKeyboardButton(
                    LANGUAGES[lang]['photo_button'], 
                    callback_data=f"p|{url_id}|{lang}"
                )
            ]
        ]
    else:
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
        
        # Add photo for TikTok and Pinterest
        if platform in ['tiktok', 'pinterest']:
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
    
    # Handle WhatsApp export
    if query.data.startswith("wa_export_"):
        try:
            parts = query.data.split('_')
            user_id = int(parts[2])
            sticker_count = int(parts[3]) if len(parts) > 3 else 0
            lang = get_user_language(update)
            
            is_premium = db.is_premium(user_id)
            pack_name = db.get_current_pack_name(user_id)
            
            # Get pack title for branding
            if is_premium:
                pack_title = db.get_custom_sticker_name(user_id)
            else:
                pack_title = DEFAULT_STICKER_PACK_TITLE
            
            # Get WhatsApp stickers from user data
            wa_stickers = context.user_data.get('wa_stickers', {}).get(user_id, [])
            
            if not wa_stickers:
                await query.answer("❌ Tidak ada stiker untuk di-export!" if lang == 'id' else "❌ No stickers to export!", show_alert=True)
                return
            
            # Create ZIP file with stickers
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for i, sticker_path in enumerate(wa_stickers):
                    if os.path.exists(sticker_path):
                        # Name format: packname_001.webp
                        filename = f"{pack_title}_{i+1:03d}.webp"
                        zip_file.write(sticker_path, filename)
            
            zip_buffer.seek(0)
            
            # Send the ZIP file
            await query.message.reply_document(
                document=zip_buffer,
                filename=f"{pack_title}_WhatsApp_Stickers.zip",
                caption=LANGUAGES[lang]['whatsapp_info'].format(pack_title, len(wa_stickers)),
                parse_mode='Markdown'
            )
            
            # Cleanup WhatsApp sticker files
            for sticker_path in wa_stickers:
                if os.path.exists(sticker_path):
                    try:
                        os.remove(sticker_path)
                    except:
                        pass
            
            # Clear the list
            context.user_data['wa_stickers'][user_id] = []
            
        except Exception as e:
            print(f"Error exporting to WhatsApp: {e}")
            import traceback
            traceback.print_exc()
            await query.answer("❌ Error exporting stickers", show_alert=True)
        return
    
    # Handle save pack button
    if query.data.startswith("savepack_"):
        try:
            parts = query.data.split('_')
            user_id = int(parts[1])
            sticker_count = int(parts[2]) if len(parts) > 2 else 0
            
            lang = get_user_language(update)
            
            user_data = db.get_user(user_id)
            if not user_data:
                await query.answer("❌ User not found!", show_alert=True)
                return
            
            pack_name = db.get_current_pack_name(user_id)
            sticker_set_name = db.get_current_sticker_set_name(user_id)
            
            # If sticker_count is 0, get from database
            if sticker_count == 0:
                sticker_count = user_data['current_sticker_pack_count']
            
            # Save pack to database
            db.save_sticker_pack(user_id, pack_name, sticker_count, sticker_set_name)
            
            await query.answer("✅ Pack tersimpan!" if lang == 'id' else "✅ Pack saved!", show_alert=True)
            await query.edit_message_text(
                LANGUAGES[lang]['pack_saved'].format(pack_name, sticker_count),
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error saving pack: {e}")
            import traceback
            traceback.print_exc()
            await query.answer("❌ Error saving pack", show_alert=True)
        return
    
    # Handle delete pack button
    if query.data.startswith("delpack_"):
        pack_index = int(query.data.split('_')[1])
        user_id = query.from_user.id
        lang = get_user_language(update)
        
        deleted = db.delete_sticker_pack(user_id, pack_index)
        
        if deleted:
            await query.answer(LANGUAGES[lang]['pack_deleted'], show_alert=True)
            # Create a fake update object for mypacks_command
            # Instead, just edit the message
            packs = db.get_sticker_packs(user_id)
            
            if not packs or len(packs) == 0:
                await query.edit_message_text(
                    LANGUAGES[lang]['my_packs_empty'],
                    parse_mode='Markdown'
                )
            else:
                msg = LANGUAGES[lang]['my_packs_list'].format(len(packs))
                keyboard = []
                for i, pack in enumerate(packs):
                    try:
                        created_date = datetime.fromisoformat(pack['created_at']).strftime('%d/%m/%Y')
                    except:
                        created_date = "Unknown"
                    
                    pack_name = pack.get('pack_name', 'Unnamed')
                    sticker_count = pack.get('sticker_count', 0)
                    sticker_set_name = pack.get('sticker_set_name')
                    
                    pack_text = f"{i+1}. 📦 {pack_name} ({sticker_count} stiker) - {created_date}"
                    msg += pack_text + "\n"
                    
                    row = []
                    if sticker_set_name:
                        row.append(InlineKeyboardButton(f"➕ Add", url=f"https://t.me/addstickers/{sticker_set_name}"))
                    row.append(InlineKeyboardButton(f"🗑️", callback_data=f"delpack_{i}"))
                    keyboard.append(row)
                
                keyboard.append([InlineKeyboardButton(f"📦 Official SafeRobot Pack", url=SAFEROBOT_STICKER_PACK)])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await query.answer("❌ Error deleting pack", show_alert=True)
        return
    
    if query.data == "buy_premium":
        lang = get_user_language(update)
        
        title = "SafeRobot Premium - 1 Month"
        description = "Unlimited stickers, custom name, 250MB download, WhatsApp export"
        payload = f"premium_1month_{query.from_user.id}"
        currency = "XTR"
        
        prices = [LabeledPrice("Premium 1 Month", PREMIUM_PRICE_STARS)]
        
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency=currency,
            prices=prices
        )
        return
    
    if query.data == "refresh_stats":
        user_id = query.from_user.id
        
        if not is_owner(user_id):
            await query.answer("❌ Hanya owner!", show_alert=True)
            return
        
        stats = db.get_stats()
        top_users = db.get_top_users(5)
        
        stats_msg = f"""
📊 *SAFEROBOT STATISTICS*
━━━━━━━━━━━━━━━━━━━━

👥 *USER STATISTICS*
├ Total Users: `{stats['total_users']}`
├ Active Users (7d): `{stats['active_users']}`
├ 👑 Premium Users: `{stats['premium_users']}`

🔥 *DOWNLOADS*
├ Total: `{stats['total_downloads']}`
├ 🎥 Video: `{stats['video_downloads']}`
└ 🎵 Audio: `{stats['audio_downloads']}`

🎨 *STICKERS*
└ Total: `{stats['total_stickers']}`

🏆 *TOP 5 USERS*
"""
        
        for i, user in enumerate(top_users, 1):
            username = f"@{user['username']}" if user['username'] else user['first_name']
            premium = "👑" if user.get('is_premium') else ""
            stats_msg += f"{i}. {username} {premium}- `{user['download_count']}`\n"
        
        stats_msg += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_msg,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Handle download buttons
    data = query.data.split('|')
    format_code = data[0]
    url_id = data[1]
    lang = data[2] if len(data) > 2 else 'en'
    
    url = context.user_data.get(url_id)
    
    if not url:
        await query.message.reply_text(
            "❌ Link expired! Please send again." if lang == 'en' else "❌ Link kadaluarsa!"
        )
        return
    
    if format_code == 'v':
        format_type = 'video'
    elif format_code == 'a':
        format_type = 'audio'
    elif format_code == 'p':
        format_type = 'photo'
    else:
        format_type = 'video'
    
    downloading_msg = LANGUAGES[lang]['downloading'].format(
        LANGUAGES[lang].get(format_type, format_type)
    )
    status_msg = await query.message.reply_text(downloading_msg)
    
    try:
        is_premium = db.is_premium(query.from_user.id)
        max_size = PREMIUM_VIDEO_SIZE_LIMIT if is_premium else FREE_VIDEO_SIZE_LIMIT
        
        result = await bot.download_media(url, format_type, max_size)
        
        if result['success']:
            await status_msg.edit_text(LANGUAGES[lang]['sending'])
            
            filepath = result['filepath']
            
            if not os.path.exists(filepath):
                await status_msg.edit_text(LANGUAGES[lang]['download_failed'].format("File not found"))
                return
            
            file_size = os.path.getsize(filepath)
            file_size_mb = file_size / (1024 * 1024)
            max_telegram_size = 50 * 1024 * 1024  # 50MB Telegram limit
            
            # Check file size limits
            if file_size > max_size:
                limit_msg = LANGUAGES[lang]['file_too_large_premium'] if is_premium else LANGUAGES[lang]['file_too_large_free']
                hint = LANGUAGES[lang]['try_smaller'] if is_premium else LANGUAGES[lang]['upgrade_hint']
                await status_msg.edit_text(
                    LANGUAGES[lang]['file_too_large'].format(file_size_mb, limit_msg, hint)
                )
                if os.path.exists(filepath):
                    os.remove(filepath)
                return
            
            if format_type == 'photo':
                caption = LANGUAGES[lang]['photo_caption'].format(result['title'])
                try:
                    with open(filepath, 'rb') as photo:
                        await query.message.reply_photo(
                            photo=photo,
                            caption=caption,
                            parse_mode='Markdown'
                        )
                except Exception:
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
                
                if file_size > max_telegram_size:
                    with open(filepath, 'rb') as document:
                        await query.message.reply_document(
                            document=document,
                            caption=caption + "\n\n⚠️ Sent as document (file too large for video)",
                            parse_mode='Markdown'
                        )
                else:
                    try:
                        with open(filepath, 'rb') as video:
                            await query.message.reply_video(
                                video=video,
                                duration=int(result['duration']) if result['duration'] else None,
                                caption=caption,
                                parse_mode='Markdown',
                                supports_streaming=True
                            )
                    except Exception:
                        with open(filepath, 'rb') as document:
                            await query.message.reply_document(
                                document=document,
                                caption=caption,
                                parse_mode='Markdown'
                            )
            
            db.increment_download(query.from_user.id, format_type)
            await status_msg.delete()
            
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

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk pre-checkout query"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk pembayaran sukses"""
    user = update.effective_user
    lang = get_user_language(update)
    
    premium_until = db.set_premium(user.id, months=1)
    
    success_msg = LANGUAGES[lang]['payment_success'].format(
        premium_until.strftime('%Y-%m-%d %H:%M')
    )
    
    await update.message.reply_text(
        success_msg,
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk error"""
    print(f"Error: {context.error}")
    import traceback
    traceback.print_exc()

def main():
    """Fungsi utama untuk menjalankan bot"""
    print("🤖 SafeRobot v5.0 Starting...")
    print("🎨 Features: Multi-platform Download + WhatsApp Sticker Export")
    print("📦 Default Pack Name:", DEFAULT_STICKER_PACK_TITLE)
    print("👑 Premium: 250MB download, custom name, unlimited stickers")
    print("✅ Supported: YouTube, TikTok, Instagram, Pinterest, Facebook, X/Twitter")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"💾 Database: {DATABASE_PATH}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler untuk newpack
    newpack_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("newpack", newpack_command)],
        states={
            WAITING_PACK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pack_name)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_newpack, pattern="^cancel_newpack$"),
            CommandHandler("cancel", lambda u, c: ConversationHandler.END)
        ],
    )
    
    # Conversation handler untuk customname (premium only)
    customname_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("customname", customname_command)],
        states={
            WAITING_CUSTOM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_name)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_customname, pattern="^cancel_customname$"),
            CommandHandler("cancel", lambda u, c: ConversationHandler.END)
        ],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("mystatus", mystatus_command))
    application.add_handler(CommandHandler("mypacks", mypacks_command))
    application.add_handler(newpack_conv_handler)
    application.add_handler(customname_conv_handler)
    
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    application.add_error_handler(error_handler)
    
    print("✅ SafeRobot is running!")
    print("\n📋 Owner commands:")
    print("   /stats - View statistics")
    print("   /broadcast <message> - Send to all users")
    print("\n👤 User commands:")
    print("   /start - Start bot")
    print("   /newpack - Create new sticker pack")
    print("   /mypacks - View saved packs")
    print("   /customname - Custom pack name (Premium)")
    print("   /mystatus - Check status")
    print("   /premium - Premium info")
    print(f"\n📦 Official Pack: {SAFEROBOT_STICKER_PACK}")
    print("\nPress Ctrl+C to stop")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
