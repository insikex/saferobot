#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     🛡️ SAFEGUARD BOT - TELEGRAM SECURITY                     ║
║                         Multi-Language Group Protection                        ║
║                                                                                ║
║  Author: SafeGuard Team                                                        ║
║  Version: 2.0.0                                                                ║
║  License: MIT                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Fitur Utama / Main Features:
- 🌐 Multi-Language (Indonesia & English auto-detection)
- ✅ Member Verification (Button, Math, Emoji CAPTCHA)
- 🚫 Anti-Spam & Anti-Flood Protection
- 🔗 Anti-Link & Anti-Forward
- 🛡️ Anti-Raid Detection
- ⚠️ Warning System
- 🔨 Admin Tools (Kick, Ban, Mute)
- 📊 Statistics & Logging
- ⚙️ Customizable Settings per Group
"""

import logging
import asyncio
import sqlite3
import random
import re
import time
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import json

# Telegram imports
from telegram import (
    Update, 
    ChatPermissions, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ChatMember,
    User,
    Chat,
    Message
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ChatMemberHandler,
    ContextTypes, 
    filters,
    JobQueue
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, BadRequest, Forbidden

# ═══════════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Bot Token - Ganti dengan token bot Anda
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Database file
DATABASE_FILE = "safeguard.db"

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('safeguard.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#                           MULTI-LANGUAGE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class Language(Enum):
    """Supported languages"""
    ID = "id"  # Indonesian
    EN = "en"  # English

# Indonesian translations
LANG_ID = {
    # General
    "welcome_bot": """
🛡️ <b>SafeGuard Bot - Pelindung Grup Telegram</b>

Halo! Saya adalah bot pelindung grup yang akan membantu menjaga keamanan grup Anda dari spam, bot, dan serangan berbahaya.

<b>🔥 Fitur Utama:</b>
├ ✅ Verifikasi member baru (CAPTCHA)
├ 🚫 Anti-Spam & Anti-Flood
├ 🔗 Anti-Link & Anti-Forward
├ 🛡️ Anti-Raid (Serangan Massal)
├ ⚠️ Sistem Peringatan
├ 🔨 Tools Admin Lengkap
└ 📊 Statistik & Log

<b>📝 Perintah Admin:</b>
/settings - Pengaturan bot
/setwelcome - Atur pesan selamat datang
/warn - Beri peringatan ke user
/unwarn - Hapus peringatan
/kick - Kick user dari grup
/ban - Ban user dari grup
/mute - Bisukan user
/unmute - Batalkan bisu
/purge - Hapus pesan massal
/stats - Statistik grup

<b>📝 Perintah Umum:</b>
/help - Bantuan
/rules - Aturan grup
/ping - Cek bot online

<i>Tambahkan saya ke grup dan jadikan admin untuk mulai!</i>
""",
    "welcome_group": "🛡️ Bot SafeGuard aktif! Gunakan /help untuk melihat perintah.",
    "help_text": """
📖 <b>Bantuan SafeGuard Bot</b>

<b>🔧 Perintah Admin:</b>
├ /settings - Menu pengaturan lengkap
├ /setwelcome [teks] - Atur pesan welcome
├ /warn @user [alasan] - Beri peringatan
├ /unwarn @user - Hapus peringatan
├ /warns @user - Lihat jumlah warn
├ /kick @user [alasan] - Kick user
├ /ban @user [alasan] - Ban user
├ /unban @user - Unban user
├ /mute @user [durasi] - Bisukan user
├ /unmute @user - Batalkan bisu
├ /purge [jumlah] - Hapus pesan
├ /setlang - Ubah bahasa
└ /stats - Statistik grup

<b>📝 Perintah Umum:</b>
├ /help - Tampilkan bantuan ini
├ /rules - Lihat aturan grup
├ /ping - Cek status bot
└ /mywarns - Lihat peringatan saya

<b>💡 Tips:</b>
• Reply pesan user untuk aksi cepat
• Gunakan @username atau user_id
• Durasi: 1m, 1h, 1d (menit/jam/hari)
""",
    
    # Verification
    "verify_welcome": "👋 Selamat datang <b>{name}</b>!\n\n🔐 Untuk membuktikan Anda bukan bot, silakan {verify_instruction}\n\n⏱️ Waktu: <b>{timeout} detik</b>",
    "verify_button_instruction": "klik tombol di bawah",
    "verify_math_instruction": "jawab soal matematika berikut:\n\n<code>{question}</code>",
    "verify_emoji_instruction": "pilih emoji yang sesuai:\n\n{question}",
    "verify_button_text": "✅ Saya Manusia",
    "verify_success": "✅ Verifikasi berhasil! Selamat datang di grup, <b>{name}</b>!",
    "verify_failed": "❌ Verifikasi gagal! User <b>{name}</b> telah di-kick.",
    "verify_timeout": "⏰ Waktu verifikasi habis! User <b>{name}</b> telah di-kick.",
    "verify_wrong": "❌ Jawaban salah! Coba lagi. Sisa percobaan: <b>{attempts}</b>",
    "verify_not_your": "⚠️ Ini bukan verifikasi untuk Anda!",
    
    # Anti-Spam
    "spam_detected": "🚫 <b>Spam terdeteksi!</b>\n\nUser: {user}\nAlasan: {reason}",
    "flood_warning": "⚠️ {user}, Anda mengirim pesan terlalu cepat! Pelanggaran: {count}/{limit}",
    "flood_muted": "🔇 {user} dibisukan selama {duration} karena spam!",
    "link_deleted": "🔗 {user}, link tidak diizinkan di grup ini!",
    "forward_deleted": "📤 {user}, forward pesan tidak diizinkan!",
    "media_deleted": "📸 {user}, media tidak diizinkan untuk akun baru!",
    
    # Anti-Raid
    "raid_detected": "🚨 <b>PERINGATAN RAID!</b>\n\nTerdeteksi {count} member baru dalam {time} detik.\nMode perlindungan diaktifkan!",
    "raid_mode_on": "🛡️ Mode anti-raid AKTIF! Member baru akan ditolak sementara.",
    "raid_mode_off": "✅ Mode anti-raid dinonaktifkan.",
    
    # Warning System
    "warn_given": "⚠️ <b>Peringatan!</b>\n\nUser: {user}\nAlasan: {reason}\nTotal: <b>{current}/{max}</b>",
    "warn_kicked": "❌ {user} telah di-kick karena mencapai batas peringatan!",
    "warn_removed": "✅ Peringatan untuk {user} telah dihapus. Total: {current}/{max}",
    "warn_list": "📋 <b>Daftar Peringatan {user}:</b>\n\nTotal: {current}/{max}\n{list}",
    "no_warns": "✅ {user} tidak memiliki peringatan.",
    
    # Admin Actions
    "user_kicked": "👢 {user} telah di-kick!\nAlasan: {reason}\nOleh: {admin}",
    "user_banned": "🔨 {user} telah di-ban!\nAlasan: {reason}\nOleh: {admin}",
    "user_unbanned": "✅ {user} telah di-unban oleh {admin}",
    "user_muted": "🔇 {user} dibisukan!\nDurasi: {duration}\nAlasan: {reason}\nOleh: {admin}",
    "user_unmuted": "🔊 {user} sudah bisa berbicara lagi!",
    "purge_done": "🗑️ Berhasil menghapus {count} pesan!",
    
    # Settings
    "settings_title": "⚙️ <b>Pengaturan Grup</b>\n\nKlik tombol untuk mengubah pengaturan:",
    "settings_verification": "Verifikasi Member",
    "settings_antispam": "Anti-Spam",
    "settings_antilink": "Anti-Link",
    "settings_antiforward": "Anti-Forward",
    "settings_antiraid": "Anti-Raid",
    "settings_welcome": "Pesan Welcome",
    "settings_captcha_type": "Tipe CAPTCHA",
    "settings_language": "Bahasa",
    "settings_updated": "✅ Pengaturan berhasil diperbarui!",
    
    # CAPTCHA Types
    "captcha_button": "🔘 Tombol",
    "captcha_math": "🔢 Matematika",
    "captcha_emoji": "😀 Emoji",
    
    # Errors
    "error_admin_only": "❌ Perintah ini hanya untuk admin!",
    "error_reply_user": "❌ Reply ke pesan user yang ingin ditindak!",
    "error_not_found": "❌ User tidak ditemukan!",
    "error_cant_admin": "❌ Tidak bisa menindak admin lain!",
    "error_bot_not_admin": "❌ Saya bukan admin! Jadikan saya admin terlebih dahulu.",
    "error_no_permission": "❌ Saya tidak memiliki izin untuk melakukan ini!",
    "error_private_only": "❌ Perintah ini hanya bisa digunakan di private chat!",
    "error_group_only": "❌ Perintah ini hanya bisa digunakan di grup!",
    
    # Stats
    "stats_title": """
📊 <b>Statistik Grup</b>

👥 Total Member: <b>{members}</b>
✅ Terverifikasi: <b>{verified}</b>
❌ Ditolak: <b>{rejected}</b>
🚫 Spam Diblokir: <b>{spam_blocked}</b>
⚠️ Total Peringatan: <b>{warnings}</b>
🔨 Total Ban: <b>{bans}</b>

📅 Sejak: {since}
""",
    
    # Misc
    "ping_response": "🏓 Pong! Latensi: <b>{latency}ms</b>",
    "rules_not_set": "📜 Aturan grup belum diatur.",
    "rules_text": "📜 <b>Aturan Grup:</b>\n\n{rules}",
    "lang_changed": "✅ Bahasa berhasil diubah ke Indonesia!",
    "welcome_custom": "Pesan selamat datang berhasil diatur!",
    
    # Buttons
    "btn_back": "◀️ Kembali",
    "btn_close": "❌ Tutup",
    "btn_enable": "✅ Aktif",
    "btn_disable": "❌ Nonaktif",
}

# English translations
LANG_EN = {
    # General
    "welcome_bot": """
🛡️ <b>SafeGuard Bot - Telegram Group Protection</b>

Hello! I am a group protection bot that will help keep your group safe from spam, bots, and malicious attacks.

<b>🔥 Main Features:</b>
├ ✅ New Member Verification (CAPTCHA)
├ 🚫 Anti-Spam & Anti-Flood
├ 🔗 Anti-Link & Anti-Forward
├ 🛡️ Anti-Raid Detection
├ ⚠️ Warning System
├ 🔨 Complete Admin Tools
└ 📊 Statistics & Logging

<b>📝 Admin Commands:</b>
/settings - Bot settings
/setwelcome - Set welcome message
/warn - Warn a user
/unwarn - Remove warning
/kick - Kick user from group
/ban - Ban user from group
/mute - Mute user
/unmute - Unmute user
/purge - Mass delete messages
/stats - Group statistics

<b>📝 General Commands:</b>
/help - Help
/rules - Group rules
/ping - Check bot status

<i>Add me to your group and make me admin to start!</i>
""",
    "welcome_group": "🛡️ SafeGuard Bot is active! Use /help to see commands.",
    "help_text": """
📖 <b>SafeGuard Bot Help</b>

<b>🔧 Admin Commands:</b>
├ /settings - Complete settings menu
├ /setwelcome [text] - Set welcome message
├ /warn @user [reason] - Warn user
├ /unwarn @user - Remove warning
├ /warns @user - Check warnings
├ /kick @user [reason] - Kick user
├ /ban @user [reason] - Ban user
├ /unban @user - Unban user
├ /mute @user [duration] - Mute user
├ /unmute @user - Unmute user
├ /purge [count] - Delete messages
├ /setlang - Change language
└ /stats - Group statistics

<b>📝 General Commands:</b>
├ /help - Show this help
├ /rules - View group rules
├ /ping - Check bot status
└ /mywarns - View my warnings

<b>💡 Tips:</b>
• Reply to user message for quick action
• Use @username or user_id
• Duration: 1m, 1h, 1d (minute/hour/day)
""",
    
    # Verification
    "verify_welcome": "👋 Welcome <b>{name}</b>!\n\n🔐 To prove you're not a bot, please {verify_instruction}\n\n⏱️ Time: <b>{timeout} seconds</b>",
    "verify_button_instruction": "click the button below",
    "verify_math_instruction": "answer the following math question:\n\n<code>{question}</code>",
    "verify_emoji_instruction": "select the correct emoji:\n\n{question}",
    "verify_button_text": "✅ I'm Human",
    "verify_success": "✅ Verification successful! Welcome to the group, <b>{name}</b>!",
    "verify_failed": "❌ Verification failed! User <b>{name}</b> has been kicked.",
    "verify_timeout": "⏰ Verification timeout! User <b>{name}</b> has been kicked.",
    "verify_wrong": "❌ Wrong answer! Try again. Attempts left: <b>{attempts}</b>",
    "verify_not_your": "⚠️ This is not your verification!",
    
    # Anti-Spam
    "spam_detected": "🚫 <b>Spam detected!</b>\n\nUser: {user}\nReason: {reason}",
    "flood_warning": "⚠️ {user}, you're sending messages too fast! Violations: {count}/{limit}",
    "flood_muted": "🔇 {user} has been muted for {duration} due to spam!",
    "link_deleted": "🔗 {user}, links are not allowed in this group!",
    "forward_deleted": "📤 {user}, forwarded messages are not allowed!",
    "media_deleted": "📸 {user}, media is not allowed for new accounts!",
    
    # Anti-Raid
    "raid_detected": "🚨 <b>RAID WARNING!</b>\n\nDetected {count} new members in {time} seconds.\nProtection mode activated!",
    "raid_mode_on": "🛡️ Anti-raid mode is ON! New members will be temporarily rejected.",
    "raid_mode_off": "✅ Anti-raid mode has been disabled.",
    
    # Warning System
    "warn_given": "⚠️ <b>Warning!</b>\n\nUser: {user}\nReason: {reason}\nTotal: <b>{current}/{max}</b>",
    "warn_kicked": "❌ {user} has been kicked for reaching warning limit!",
    "warn_removed": "✅ Warning removed for {user}. Total: {current}/{max}",
    "warn_list": "📋 <b>Warnings for {user}:</b>\n\nTotal: {current}/{max}\n{list}",
    "no_warns": "✅ {user} has no warnings.",
    
    # Admin Actions
    "user_kicked": "👢 {user} has been kicked!\nReason: {reason}\nBy: {admin}",
    "user_banned": "🔨 {user} has been banned!\nReason: {reason}\nBy: {admin}",
    "user_unbanned": "✅ {user} has been unbanned by {admin}",
    "user_muted": "🔇 {user} has been muted!\nDuration: {duration}\nReason: {reason}\nBy: {admin}",
    "user_unmuted": "🔊 {user} can speak again!",
    "purge_done": "🗑️ Successfully deleted {count} messages!",
    
    # Settings
    "settings_title": "⚙️ <b>Group Settings</b>\n\nClick buttons to change settings:",
    "settings_verification": "Member Verification",
    "settings_antispam": "Anti-Spam",
    "settings_antilink": "Anti-Link",
    "settings_antiforward": "Anti-Forward",
    "settings_antiraid": "Anti-Raid",
    "settings_welcome": "Welcome Message",
    "settings_captcha_type": "CAPTCHA Type",
    "settings_language": "Language",
    "settings_updated": "✅ Settings updated successfully!",
    
    # CAPTCHA Types
    "captcha_button": "🔘 Button",
    "captcha_math": "🔢 Math",
    "captcha_emoji": "😀 Emoji",
    
    # Errors
    "error_admin_only": "❌ This command is for admins only!",
    "error_reply_user": "❌ Reply to the user's message you want to take action on!",
    "error_not_found": "❌ User not found!",
    "error_cant_admin": "❌ Cannot take action on other admins!",
    "error_bot_not_admin": "❌ I'm not an admin! Make me admin first.",
    "error_no_permission": "❌ I don't have permission to do this!",
    "error_private_only": "❌ This command can only be used in private chat!",
    "error_group_only": "❌ This command can only be used in groups!",
    
    # Stats
    "stats_title": """
📊 <b>Group Statistics</b>

👥 Total Members: <b>{members}</b>
✅ Verified: <b>{verified}</b>
❌ Rejected: <b>{rejected}</b>
🚫 Spam Blocked: <b>{spam_blocked}</b>
⚠️ Total Warnings: <b>{warnings}</b>
🔨 Total Bans: <b>{bans}</b>

📅 Since: {since}
""",
    
    # Misc
    "ping_response": "🏓 Pong! Latency: <b>{latency}ms</b>",
    "rules_not_set": "📜 Group rules have not been set.",
    "rules_text": "📜 <b>Group Rules:</b>\n\n{rules}",
    "lang_changed": "✅ Language changed to English!",
    "welcome_custom": "Welcome message has been set!",
    
    # Buttons
    "btn_back": "◀️ Back",
    "btn_close": "❌ Close",
    "btn_enable": "✅ Enabled",
    "btn_disable": "❌ Disabled",
}

# Language mappings
LANGUAGES = {
    Language.ID: LANG_ID,
    Language.EN: LANG_EN,
}

# Indonesian language codes
INDONESIAN_CODES = ['id', 'id-ID', 'jv', 'su', 'ms']

def get_user_language(user: User) -> Language:
    """Detect user language based on their Telegram language code"""
    if user and user.language_code:
        if user.language_code.lower() in INDONESIAN_CODES or user.language_code.lower().startswith('id'):
            return Language.ID
    return Language.EN

def get_text(lang: Language, key: str, **kwargs) -> str:
    """Get translated text with optional formatting"""
    texts = LANGUAGES.get(lang, LANG_EN)
    text = texts.get(key, LANG_EN.get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text

# ═══════════════════════════════════════════════════════════════════════════════
#                             DATABASE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class Database:
    """SQLite database handler for storing group configurations and statistics"""
    
    def __init__(self, db_file: str = DATABASE_FILE):
        self.db_file = db_file
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize database and create tables"""
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        
        # Groups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                language TEXT DEFAULT 'en',
                verification_enabled INTEGER DEFAULT 1,
                captcha_type TEXT DEFAULT 'button',
                verification_timeout INTEGER DEFAULT 120,
                antispam_enabled INTEGER DEFAULT 1,
                antiflood_enabled INTEGER DEFAULT 1,
                antiflood_limit INTEGER DEFAULT 5,
                antiflood_time INTEGER DEFAULT 10,
                antilink_enabled INTEGER DEFAULT 0,
                antiforward_enabled INTEGER DEFAULT 0,
                antiraid_enabled INTEGER DEFAULT 1,
                antiraid_limit INTEGER DEFAULT 10,
                antiraid_time INTEGER DEFAULT 60,
                welcome_enabled INTEGER DEFAULT 1,
                welcome_message TEXT,
                rules TEXT,
                warn_limit INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                chat_id INTEGER,
                username TEXT,
                first_name TEXT,
                warnings INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                mute_until TIMESTAMP,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # Warnings log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                admin_id INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                chat_id INTEGER PRIMARY KEY,
                verified_count INTEGER DEFAULT 0,
                rejected_count INTEGER DEFAULT 0,
                spam_blocked INTEGER DEFAULT 0,
                warnings_count INTEGER DEFAULT 0,
                bans_count INTEGER DEFAULT 0,
                kicks_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Pending verifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_verifications (
                user_id INTEGER,
                chat_id INTEGER,
                message_id INTEGER,
                captcha_answer TEXT,
                attempts INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # Flood tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flood_tracking (
                user_id INTEGER,
                chat_id INTEGER,
                message_count INTEGER DEFAULT 0,
                last_message TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                violations INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # Raid tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raid_tracking (
                chat_id INTEGER PRIMARY KEY,
                join_count INTEGER DEFAULT 0,
                first_join TIMESTAMP,
                raid_mode INTEGER DEFAULT 0,
                raid_until TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def get_group(self, chat_id: int) -> dict:
        """Get group configuration"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM groups WHERE chat_id = ?', (chat_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def create_group(self, chat_id: int, title: str = None) -> dict:
        """Create new group configuration"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO groups (chat_id, title) VALUES (?, ?)
        ''', (chat_id, title))
        cursor.execute('''
            INSERT OR IGNORE INTO statistics (chat_id) VALUES (?)
        ''', (chat_id,))
        self.conn.commit()
        return self.get_group(chat_id)
    
    def update_group(self, chat_id: int, **kwargs):
        """Update group configuration"""
        if not kwargs:
            return
        
        set_clause = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [chat_id]
        
        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE groups SET {set_clause}, updated_at = CURRENT_TIMESTAMP 
            WHERE chat_id = ?
        ''', values)
        self.conn.commit()
    
    def get_or_create_group(self, chat_id: int, title: str = None) -> dict:
        """Get group or create if not exists"""
        group = self.get_group(chat_id)
        if not group:
            group = self.create_group(chat_id, title)
            group = self.get_group(chat_id)
        return group
    
    def get_user(self, user_id: int, chat_id: int) -> dict:
        """Get user in a specific chat"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def create_user(self, user_id: int, chat_id: int, username: str = None, first_name: str = None):
        """Create user record"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, chat_id, username, first_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, chat_id, username, first_name))
        self.conn.commit()
    
    def update_user(self, user_id: int, chat_id: int, **kwargs):
        """Update user record"""
        if not kwargs:
            return
        
        set_clause = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id, chat_id]
        
        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE users SET {set_clause} WHERE user_id = ? AND chat_id = ?
        ''', values)
        self.conn.commit()
    
    def get_or_create_user(self, user_id: int, chat_id: int, username: str = None, first_name: str = None) -> dict:
        """Get user or create if not exists"""
        user = self.get_user(user_id, chat_id)
        if not user:
            self.create_user(user_id, chat_id, username, first_name)
            user = self.get_user(user_id, chat_id)
        return user
    
    def add_warning(self, user_id: int, chat_id: int, admin_id: int, reason: str) -> int:
        """Add warning to user and return new warning count"""
        cursor = self.conn.cursor()
        
        # Add to warnings log
        cursor.execute('''
            INSERT INTO warnings (user_id, chat_id, admin_id, reason)
            VALUES (?, ?, ?, ?)
        ''', (user_id, chat_id, admin_id, reason))
        
        # Update user warnings count
        cursor.execute('''
            UPDATE users SET warnings = warnings + 1 WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        
        # Update statistics
        cursor.execute('''
            UPDATE statistics SET warnings_count = warnings_count + 1 WHERE chat_id = ?
        ''', (chat_id,))
        
        self.conn.commit()
        
        user = self.get_user(user_id, chat_id)
        return user['warnings'] if user else 0
    
    def remove_warning(self, user_id: int, chat_id: int) -> int:
        """Remove one warning from user"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            UPDATE users SET warnings = MAX(0, warnings - 1) WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        
        self.conn.commit()
        
        user = self.get_user(user_id, chat_id)
        return user['warnings'] if user else 0
    
    def reset_warnings(self, user_id: int, chat_id: int):
        """Reset all warnings for user"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET warnings = 0 WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        self.conn.commit()
    
    def get_warnings_list(self, user_id: int, chat_id: int) -> List[dict]:
        """Get list of warnings for user"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM warnings WHERE user_id = ? AND chat_id = ? ORDER BY created_at DESC
        ''', (user_id, chat_id))
        return [dict(row) for row in cursor.fetchall()]
    
    def add_pending_verification(self, user_id: int, chat_id: int, message_id: int, 
                                  answer: str, timeout: int):
        """Add pending verification"""
        cursor = self.conn.cursor()
        expires_at = datetime.now() + timedelta(seconds=timeout)
        cursor.execute('''
            INSERT OR REPLACE INTO pending_verifications 
            (user_id, chat_id, message_id, captcha_answer, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, chat_id, message_id, answer, expires_at))
        self.conn.commit()
    
    def get_pending_verification(self, user_id: int, chat_id: int) -> dict:
        """Get pending verification"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM pending_verifications WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def remove_pending_verification(self, user_id: int, chat_id: int):
        """Remove pending verification"""
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM pending_verifications WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        self.conn.commit()
    
    def update_verification_attempts(self, user_id: int, chat_id: int) -> int:
        """Decrease verification attempts and return remaining"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE pending_verifications SET attempts = attempts - 1 
            WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        self.conn.commit()
        
        verification = self.get_pending_verification(user_id, chat_id)
        return verification['attempts'] if verification else 0
    
    def update_flood_tracking(self, user_id: int, chat_id: int) -> Tuple[int, int]:
        """Update flood tracking and return (message_count, violations)"""
        cursor = self.conn.cursor()
        now = datetime.now()
        
        cursor.execute('''
            SELECT * FROM flood_tracking WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        row = cursor.fetchone()
        
        if row:
            row = dict(row)
            last_message = datetime.fromisoformat(row['last_message']) if row['last_message'] else now
            time_diff = (now - last_message).total_seconds()
            
            if time_diff < 10:  # Within flood window
                message_count = row['message_count'] + 1
            else:
                message_count = 1
            
            cursor.execute('''
                UPDATE flood_tracking SET message_count = ?, last_message = ? 
                WHERE user_id = ? AND chat_id = ?
            ''', (message_count, now, user_id, chat_id))
            self.conn.commit()
            
            return message_count, row['violations']
        else:
            cursor.execute('''
                INSERT INTO flood_tracking (user_id, chat_id, message_count, last_message)
                VALUES (?, ?, 1, ?)
            ''', (user_id, chat_id, now))
            self.conn.commit()
            return 1, 0
    
    def add_flood_violation(self, user_id: int, chat_id: int) -> int:
        """Add flood violation and return total violations"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE flood_tracking SET violations = violations + 1 
            WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        self.conn.commit()
        
        cursor.execute('''
            SELECT violations FROM flood_tracking WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        row = cursor.fetchone()
        return row['violations'] if row else 0
    
    def reset_flood_tracking(self, user_id: int, chat_id: int):
        """Reset flood tracking for user"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE flood_tracking SET message_count = 0, violations = 0 
            WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        self.conn.commit()
    
    def track_join(self, chat_id: int) -> Tuple[int, bool]:
        """Track new member join for raid detection, returns (join_count, is_raid)"""
        cursor = self.conn.cursor()
        now = datetime.now()
        
        cursor.execute('''
            SELECT * FROM raid_tracking WHERE chat_id = ?
        ''', (chat_id,))
        row = cursor.fetchone()
        
        group = self.get_group(chat_id)
        raid_limit = group['antiraid_limit'] if group else 10
        raid_time = group['antiraid_time'] if group else 60
        
        if row:
            row = dict(row)
            first_join = datetime.fromisoformat(row['first_join']) if row['first_join'] else now
            time_diff = (now - first_join).total_seconds()
            
            if time_diff < raid_time:
                join_count = row['join_count'] + 1
                is_raid = join_count >= raid_limit
                
                cursor.execute('''
                    UPDATE raid_tracking SET join_count = ?, raid_mode = ?
                    WHERE chat_id = ?
                ''', (join_count, 1 if is_raid else row['raid_mode'], chat_id))
            else:
                join_count = 1
                cursor.execute('''
                    UPDATE raid_tracking SET join_count = 1, first_join = ?, raid_mode = 0
                    WHERE chat_id = ?
                ''', (now, chat_id))
                is_raid = False
            
            self.conn.commit()
            return join_count, is_raid
        else:
            cursor.execute('''
                INSERT INTO raid_tracking (chat_id, join_count, first_join)
                VALUES (?, 1, ?)
            ''', (chat_id, now))
            self.conn.commit()
            return 1, False
    
    def is_raid_mode(self, chat_id: int) -> bool:
        """Check if raid mode is active"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT raid_mode FROM raid_tracking WHERE chat_id = ?
        ''', (chat_id,))
        row = cursor.fetchone()
        return bool(row['raid_mode']) if row else False
    
    def set_raid_mode(self, chat_id: int, enabled: bool):
        """Set raid mode status"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO raid_tracking (chat_id, raid_mode, join_count, first_join)
            VALUES (?, ?, 0, CURRENT_TIMESTAMP)
        ''', (chat_id, 1 if enabled else 0))
        self.conn.commit()
    
    def update_statistics(self, chat_id: int, **kwargs):
        """Update group statistics"""
        if not kwargs:
            return
        
        set_clause = ', '.join([f'{k} = {k} + ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [chat_id]
        
        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE statistics SET {set_clause} WHERE chat_id = ?
        ''', values)
        self.conn.commit()
    
    def get_statistics(self, chat_id: int) -> dict:
        """Get group statistics"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM statistics WHERE chat_id = ?
        ''', (chat_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# Global database instance
db = Database()

# ═══════════════════════════════════════════════════════════════════════════════
#                             CAPTCHA SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class CaptchaGenerator:
    """Generate different types of CAPTCHA challenges"""
    
    EMOJI_SETS = {
        'animals': ['🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮'],
        'fruits': ['🍎', '🍐', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍑', '🍒', '🥝', '🍍'],
        'sports': ['⚽', '🏀', '🏈', '⚾', '🥎', '🎾', '🏐', '🏉', '🎱', '🏓', '🏸', '🥊'],
        'weather': ['☀️', '🌙', '⭐', '🌧️', '⛈️', '🌈', '❄️', '💨', '🌊', '🔥', '💧', '🌪️'],
    }
    
    EMOJI_NAMES_ID = {
        '🐶': 'anjing', '🐱': 'kucing', '🐭': 'tikus', '🐹': 'hamster',
        '🐰': 'kelinci', '🦊': 'rubah', '🐻': 'beruang', '🐼': 'panda',
        '🐨': 'koala', '🐯': 'harimau', '🦁': 'singa', '🐮': 'sapi',
        '🍎': 'apel', '🍐': 'pir', '🍊': 'jeruk', '🍋': 'lemon',
        '🍌': 'pisang', '🍉': 'semangka', '🍇': 'anggur', '🍓': 'stroberi',
        '🍑': 'persik', '🍒': 'ceri', '🥝': 'kiwi', '🍍': 'nanas',
        '⚽': 'sepak bola', '🏀': 'basket', '🏈': 'american football', '⚾': 'baseball',
    }
    
    EMOJI_NAMES_EN = {
        '🐶': 'dog', '🐱': 'cat', '🐭': 'mouse', '🐹': 'hamster',
        '🐰': 'rabbit', '🦊': 'fox', '🐻': 'bear', '🐼': 'panda',
        '🐨': 'koala', '🐯': 'tiger', '🦁': 'lion', '🐮': 'cow',
        '🍎': 'apple', '🍐': 'pear', '🍊': 'orange', '🍋': 'lemon',
        '🍌': 'banana', '🍉': 'watermelon', '🍇': 'grapes', '🍓': 'strawberry',
        '🍑': 'peach', '🍒': 'cherry', '🥝': 'kiwi', '🍍': 'pineapple',
        '⚽': 'soccer', '🏀': 'basketball', '🏈': 'football', '⚾': 'baseball',
    }
    
    @staticmethod
    def generate_button() -> Tuple[str, str]:
        """Generate simple button CAPTCHA"""
        answer = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
        return "button", answer
    
    @staticmethod
    def generate_math() -> Tuple[str, str]:
        """Generate math CAPTCHA"""
        operations = [
            ('+', lambda a, b: a + b),
            ('-', lambda a, b: a - b),
            ('×', lambda a, b: a * b),
        ]
        
        op_symbol, op_func = random.choice(operations)
        
        if op_symbol == '×':
            a = random.randint(1, 10)
            b = random.randint(1, 10)
        elif op_symbol == '-':
            a = random.randint(10, 50)
            b = random.randint(1, a)
        else:
            a = random.randint(1, 50)
            b = random.randint(1, 50)
        
        answer = str(op_func(a, b))
        question = f"{a} {op_symbol} {b} = ?"
        
        return question, answer
    
    @classmethod
    def generate_emoji(cls, lang: Language) -> Tuple[str, str, List[str]]:
        """Generate emoji CAPTCHA with options"""
        category = random.choice(list(cls.EMOJI_SETS.keys()))
        emojis = cls.EMOJI_SETS[category]
        
        # Select correct answer
        correct_emoji = random.choice(emojis)
        
        # Get emoji name based on language
        names = cls.EMOJI_NAMES_ID if lang == Language.ID else cls.EMOJI_NAMES_EN
        emoji_name = names.get(correct_emoji, correct_emoji)
        
        # Generate options (3 wrong + 1 correct)
        wrong_emojis = [e for e in emojis if e != correct_emoji]
        options = random.sample(wrong_emojis, min(3, len(wrong_emojis))) + [correct_emoji]
        random.shuffle(options)
        
        if lang == Language.ID:
            question = f"Pilih emoji <b>{emoji_name}</b>:"
        else:
            question = f"Select the <b>{emoji_name}</b> emoji:"
        
        return question, correct_emoji, options

# ═══════════════════════════════════════════════════════════════════════════════
#                              DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════

def admin_only(func):
    """Decorator to check if user is admin"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        
        if chat.type == 'private':
            lang = get_user_language(user)
            await update.message.reply_text(get_text(lang, "error_group_only"))
            return
        
        member = await chat.get_member(user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            lang = get_user_language(user)
            await update.message.reply_text(get_text(lang, "error_admin_only"))
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

def group_only(func):
    """Decorator to ensure command is used in group"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type == 'private':
            lang = get_user_language(update.effective_user)
            await update.message.reply_text(get_text(lang, "error_group_only"))
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def is_bot_admin(chat: Chat, bot_id: int) -> bool:
    """Check if bot is admin in chat"""
    try:
        member = await chat.get_member(bot_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[User]:
    """Get target user from reply or arguments"""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    
    if context.args:
        try:
            # Try to get user by ID
            user_id = int(context.args[0].replace('@', ''))
            member = await update.effective_chat.get_member(user_id)
            return member.user
        except (ValueError, BadRequest):
            # Try to get by username
            try:
                username = context.args[0].replace('@', '')
                # This won't work directly, need to use reply or ID
                return None
            except:
                return None
    return None

# ═══════════════════════════════════════════════════════════════════════════════
#                             COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    if chat.type == 'private':
        # Private chat - show full welcome message
        keyboard = [
            [InlineKeyboardButton("➕ Tambahkan ke Grup" if lang == Language.ID else "➕ Add to Group", 
                                  url=f"https://t.me/{context.bot.username}?startgroup=true")],
            [InlineKeyboardButton("📖 Bantuan" if lang == Language.ID else "📖 Help", 
                                  callback_data="help")]
        ]
        await update.message.reply_text(
            get_text(lang, "welcome_bot"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        # Group chat - short message
        db.get_or_create_group(chat.id, chat.title)
        await update.message.reply_text(
            get_text(lang, "welcome_group"),
            parse_mode=ParseMode.HTML
        )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    user = update.effective_user
    lang = get_user_language(user)
    
    await update.message.reply_text(
        get_text(lang, "help_text"),
        parse_mode=ParseMode.HTML
    )

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command"""
    user = update.effective_user
    lang = get_user_language(user)
    
    start_time = time.time()
    message = await update.message.reply_text("🏓 Pinging...")
    latency = round((time.time() - start_time) * 1000)
    
    await message.edit_text(
        get_text(lang, "ping_response", latency=latency),
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command"""
    chat = update.effective_chat
    user = update.effective_user
    lang = get_user_language(user)
    
    group = db.get_or_create_group(chat.id, chat.title)
    
    keyboard = build_settings_keyboard(group, lang)
    
    await update.message.reply_text(
        get_text(lang, "settings_title"),
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

def build_settings_keyboard(group: dict, lang: Language) -> InlineKeyboardMarkup:
    """Build settings inline keyboard"""
    on = get_text(lang, "btn_enable")
    off = get_text(lang, "btn_disable")
    
    captcha_types = {
        'button': get_text(lang, "captcha_button"),
        'math': get_text(lang, "captcha_math"),
        'emoji': get_text(lang, "captcha_emoji"),
    }
    
    keyboard = [
        [InlineKeyboardButton(
            f"{on if group['verification_enabled'] else off} {get_text(lang, 'settings_verification')}",
            callback_data="toggle_verification"
        )],
        [InlineKeyboardButton(
            f"🔐 {get_text(lang, 'settings_captcha_type')}: {captcha_types.get(group['captcha_type'], 'Button')}",
            callback_data="change_captcha"
        )],
        [InlineKeyboardButton(
            f"{on if group['antispam_enabled'] else off} {get_text(lang, 'settings_antispam')}",
            callback_data="toggle_antispam"
        )],
        [InlineKeyboardButton(
            f"{on if group['antilink_enabled'] else off} {get_text(lang, 'settings_antilink')}",
            callback_data="toggle_antilink"
        )],
        [InlineKeyboardButton(
            f"{on if group['antiforward_enabled'] else off} {get_text(lang, 'settings_antiforward')}",
            callback_data="toggle_antiforward"
        )],
        [InlineKeyboardButton(
            f"{on if group['antiraid_enabled'] else off} {get_text(lang, 'settings_antiraid')}",
            callback_data="toggle_antiraid"
        )],
        [InlineKeyboardButton(
            f"{on if group['welcome_enabled'] else off} {get_text(lang, 'settings_welcome')}",
            callback_data="toggle_welcome"
        )],
        [InlineKeyboardButton(
            f"🌐 {get_text(lang, 'settings_language')}",
            callback_data="change_language"
        )],
        [InlineKeyboardButton(get_text(lang, "btn_close"), callback_data="close_settings")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

@admin_only
async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warn command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text(get_text(lang, "error_reply_user"))
        return
    
    # Can't warn admins
    member = await chat.get_member(target.id)
    if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(get_text(lang, "error_cant_admin"))
        return
    
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason"
    if update.message.reply_to_message:
        reason = ' '.join(context.args) if context.args else "No reason"
    
    # Add user to database if not exists
    db.get_or_create_user(target.id, chat.id, target.username, target.first_name)
    
    # Add warning
    warn_count = db.add_warning(target.id, chat.id, user.id, reason)
    group = db.get_group(chat.id)
    warn_limit = group['warn_limit'] if group else 3
    
    if warn_count >= warn_limit:
        # Kick user
        try:
            await chat.ban_member(target.id)
            await chat.unban_member(target.id)  # Unban so they can rejoin
            db.reset_warnings(target.id, chat.id)
            db.update_statistics(chat.id, kicks_count=1)
            
            await update.message.reply_text(
                get_text(lang, "warn_kicked", user=target.mention_html()),
                parse_mode=ParseMode.HTML
            )
        except TelegramError as e:
            logger.error(f"Error kicking user: {e}")
    else:
        await update.message.reply_text(
            get_text(lang, "warn_given", 
                    user=target.mention_html(),
                    reason=reason,
                    current=warn_count,
                    max=warn_limit),
            parse_mode=ParseMode.HTML
        )

@admin_only
async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unwarn command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text(get_text(lang, "error_reply_user"))
        return
    
    warn_count = db.remove_warning(target.id, chat.id)
    group = db.get_group(chat.id)
    warn_limit = group['warn_limit'] if group else 3
    
    await update.message.reply_text(
        get_text(lang, "warn_removed",
                user=target.mention_html(),
                current=warn_count,
                max=warn_limit),
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warns command to check user warnings"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    target = await get_target_user(update, context)
    if not target:
        target = user
    
    db_user = db.get_or_create_user(target.id, chat.id, target.username, target.first_name)
    group = db.get_group(chat.id)
    warn_limit = group['warn_limit'] if group else 3
    
    if db_user['warnings'] == 0:
        await update.message.reply_text(
            get_text(lang, "no_warns", user=target.mention_html()),
            parse_mode=ParseMode.HTML
        )
    else:
        warnings = db.get_warnings_list(target.id, chat.id)
        warn_list = "\n".join([f"• {w['reason']} ({w['created_at']})" for w in warnings[:5]])
        
        await update.message.reply_text(
            get_text(lang, "warn_list",
                    user=target.mention_html(),
                    current=db_user['warnings'],
                    max=warn_limit,
                    list=warn_list),
            parse_mode=ParseMode.HTML
        )

async def cmd_mywarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mywarns command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    if chat.type == 'private':
        await update.message.reply_text(get_text(lang, "error_group_only"))
        return
    
    db_user = db.get_or_create_user(user.id, chat.id, user.username, user.first_name)
    group = db.get_group(chat.id)
    warn_limit = group['warn_limit'] if group else 3
    
    if db_user['warnings'] == 0:
        await update.message.reply_text(
            get_text(lang, "no_warns", user=user.mention_html()),
            parse_mode=ParseMode.HTML
        )
    else:
        warnings = db.get_warnings_list(user.id, chat.id)
        warn_list = "\n".join([f"• {w['reason']}" for w in warnings[:5]])
        
        await update.message.reply_text(
            get_text(lang, "warn_list",
                    user=user.mention_html(),
                    current=db_user['warnings'],
                    max=warn_limit,
                    list=warn_list),
            parse_mode=ParseMode.HTML
        )

@admin_only
async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kick command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text(get_text(lang, "error_reply_user"))
        return
    
    # Can't kick admins
    member = await chat.get_member(target.id)
    if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(get_text(lang, "error_cant_admin"))
        return
    
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason"
    if update.message.reply_to_message:
        reason = ' '.join(context.args) if context.args else "No reason"
    
    try:
        await chat.ban_member(target.id)
        await chat.unban_member(target.id)
        db.update_statistics(chat.id, kicks_count=1)
        
        await update.message.reply_text(
            get_text(lang, "user_kicked",
                    user=target.mention_html(),
                    reason=reason,
                    admin=user.mention_html()),
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Error kicking user: {e}")
        await update.message.reply_text(get_text(lang, "error_no_permission"))

@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text(get_text(lang, "error_reply_user"))
        return
    
    # Can't ban admins
    member = await chat.get_member(target.id)
    if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(get_text(lang, "error_cant_admin"))
        return
    
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason"
    if update.message.reply_to_message:
        reason = ' '.join(context.args) if context.args else "No reason"
    
    try:
        await chat.ban_member(target.id)
        db.update_user(target.id, chat.id, is_banned=1)
        db.update_statistics(chat.id, bans_count=1)
        
        await update.message.reply_text(
            get_text(lang, "user_banned",
                    user=target.mention_html(),
                    reason=reason,
                    admin=user.mention_html()),
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Error banning user: {e}")
        await update.message.reply_text(get_text(lang, "error_no_permission"))

@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /unban <user_id>" if lang == Language.EN else "Penggunaan: /unban <user_id>"
        )
        return
    
    try:
        target_id = int(context.args[0])
        await chat.unban_member(target_id)
        db.update_user(target_id, chat.id, is_banned=0)
        
        await update.message.reply_text(
            get_text(lang, "user_unbanned",
                    user=f"<code>{target_id}</code>",
                    admin=user.mention_html()),
            parse_mode=ParseMode.HTML
        )
    except (ValueError, TelegramError) as e:
        logger.error(f"Error unbanning user: {e}")
        await update.message.reply_text(get_text(lang, "error_not_found"))

@admin_only
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mute command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text(get_text(lang, "error_reply_user"))
        return
    
    # Can't mute admins
    member = await chat.get_member(target.id)
    if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(get_text(lang, "error_cant_admin"))
        return
    
    # Parse duration
    duration_str = "forever"
    until_date = None
    reason = "No reason"
    
    if context.args:
        duration_arg = context.args[0] if update.message.reply_to_message else (context.args[1] if len(context.args) > 1 else None)
        if duration_arg:
            duration_match = re.match(r'(\d+)([mhd])', duration_arg)
            if duration_match:
                amount = int(duration_match.group(1))
                unit = duration_match.group(2)
                
                if unit == 'm':
                    until_date = datetime.now() + timedelta(minutes=amount)
                    duration_str = f"{amount} {'menit' if lang == Language.ID else 'minutes'}"
                elif unit == 'h':
                    until_date = datetime.now() + timedelta(hours=amount)
                    duration_str = f"{amount} {'jam' if lang == Language.ID else 'hours'}"
                elif unit == 'd':
                    until_date = datetime.now() + timedelta(days=amount)
                    duration_str = f"{amount} {'hari' if lang == Language.ID else 'days'}"
        
        # Get reason
        if update.message.reply_to_message:
            reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason"
        else:
            reason = ' '.join(context.args[2:]) if len(context.args) > 2 else "No reason"
    
    try:
        await chat.restrict_member(
            target.id,
            ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        db.update_user(target.id, chat.id, is_muted=1, mute_until=until_date)
        
        await update.message.reply_text(
            get_text(lang, "user_muted",
                    user=target.mention_html(),
                    duration=duration_str,
                    reason=reason,
                    admin=user.mention_html()),
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Error muting user: {e}")
        await update.message.reply_text(get_text(lang, "error_no_permission"))

@admin_only
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmute command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text(get_text(lang, "error_reply_user"))
        return
    
    try:
        await chat.restrict_member(
            target.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        db.update_user(target.id, chat.id, is_muted=0, mute_until=None)
        
        await update.message.reply_text(
            get_text(lang, "user_unmuted", user=target.mention_html()),
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Error unmuting user: {e}")
        await update.message.reply_text(get_text(lang, "error_no_permission"))

@admin_only
async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /purge command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    if not update.message.reply_to_message:
        # Purge by count
        count = int(context.args[0]) if context.args else 10
        count = min(count, 100)  # Max 100 messages
    else:
        # Purge from reply to current message
        reply_id = update.message.reply_to_message.message_id
        current_id = update.message.message_id
        count = current_id - reply_id
    
    deleted = 0
    try:
        message_ids = list(range(update.message.message_id - count, update.message.message_id + 1))
        for i in range(0, len(message_ids), 100):
            batch = message_ids[i:i+100]
            try:
                await chat.delete_messages(batch)
                deleted += len(batch)
            except:
                pass
        
        confirm = await chat.send_message(
            get_text(lang, "purge_done", count=deleted),
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(3)
        await confirm.delete()
    except TelegramError as e:
        logger.error(f"Error purging: {e}")

@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    stats = db.get_statistics(chat.id)
    if not stats:
        db.get_or_create_group(chat.id, chat.title)
        stats = db.get_statistics(chat.id)
    
    try:
        member_count = await chat.get_member_count()
    except:
        member_count = "N/A"
    
    await update.message.reply_text(
        get_text(lang, "stats_title",
                members=member_count,
                verified=stats['verified_count'] if stats else 0,
                rejected=stats['rejected_count'] if stats else 0,
                spam_blocked=stats['spam_blocked'] if stats else 0,
                warnings=stats['warnings_count'] if stats else 0,
                bans=stats['bans_count'] if stats else 0,
                since=stats['created_at'] if stats else 'N/A'),
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setwelcome command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /setwelcome <message>\n\nVariables:\n{name} - User name\n{username} - Username\n{chat} - Group name"
            if lang == Language.EN else
            "Penggunaan: /setwelcome <pesan>\n\nVariabel:\n{name} - Nama user\n{username} - Username\n{chat} - Nama grup"
        )
        return
    
    welcome_msg = ' '.join(context.args)
    db.update_group(chat.id, welcome_message=welcome_msg)
    
    await update.message.reply_text(get_text(lang, "welcome_custom"))

@admin_only
async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rules command"""
    user = update.effective_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    if chat.type == 'private':
        await update.message.reply_text(get_text(lang, "error_group_only"))
        return
    
    group = db.get_or_create_group(chat.id, chat.title)
    
    if context.args and (await chat.get_member(user.id)).status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        # Set rules
        rules = ' '.join(context.args)
        db.update_group(chat.id, rules=rules)
        await update.message.reply_text("✅ Rules updated!" if lang == Language.EN else "✅ Aturan diperbarui!")
    else:
        # Show rules
        if group and group['rules']:
            await update.message.reply_text(
                get_text(lang, "rules_text", rules=group['rules']),
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(get_text(lang, "rules_not_set"))

@admin_only
async def cmd_setlang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setlang command"""
    chat = update.effective_chat
    user = update.effective_user
    lang = get_user_language(user)
    
    keyboard = [
        [
            InlineKeyboardButton("🇮🇩 Indonesia", callback_data="setlang_id"),
            InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")
        ]
    ]
    
    await update.message.reply_text(
        "🌐 Choose language / Pilih bahasa:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#                            CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    user = query.from_user
    chat = update.effective_chat
    lang = get_user_language(user)
    data = query.data
    
    await query.answer()
    
    # Help callback
    if data == "help":
        await query.message.edit_text(
            get_text(lang, "help_text"),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Close settings
    if data == "close_settings":
        await query.message.delete()
        return
    
    # Language change callbacks
    if data.startswith("setlang_"):
        new_lang = data.split("_")[1]
        db.update_group(chat.id, language=new_lang)
        
        if new_lang == "id":
            await query.message.edit_text("✅ Bahasa berhasil diubah ke Indonesia!")
        else:
            await query.message.edit_text("✅ Language changed to English!")
        return
    
    # Verification callbacks
    if data.startswith("verify_"):
        await handle_verification_callback(update, context)
        return
    
    # Math answer callbacks
    if data.startswith("math_"):
        await handle_math_callback(update, context)
        return
    
    # Emoji answer callbacks
    if data.startswith("emoji_"):
        await handle_emoji_callback(update, context)
        return
    
    # Settings callbacks - check admin
    if chat.type != 'private':
        member = await chat.get_member(user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await query.answer("Only admins can change settings!", show_alert=True)
            return
    
    group = db.get_or_create_group(chat.id, chat.title)
    
    # Toggle settings
    if data == "toggle_verification":
        db.update_group(chat.id, verification_enabled=0 if group['verification_enabled'] else 1)
    elif data == "toggle_antispam":
        db.update_group(chat.id, antispam_enabled=0 if group['antispam_enabled'] else 1)
    elif data == "toggle_antilink":
        db.update_group(chat.id, antilink_enabled=0 if group['antilink_enabled'] else 1)
    elif data == "toggle_antiforward":
        db.update_group(chat.id, antiforward_enabled=0 if group['antiforward_enabled'] else 1)
    elif data == "toggle_antiraid":
        db.update_group(chat.id, antiraid_enabled=0 if group['antiraid_enabled'] else 1)
    elif data == "toggle_welcome":
        db.update_group(chat.id, welcome_enabled=0 if group['welcome_enabled'] else 1)
    elif data == "change_captcha":
        # Cycle through captcha types
        types = ['button', 'math', 'emoji']
        current_idx = types.index(group['captcha_type']) if group['captcha_type'] in types else 0
        next_type = types[(current_idx + 1) % len(types)]
        db.update_group(chat.id, captcha_type=next_type)
    elif data == "change_language":
        keyboard = [
            [
                InlineKeyboardButton("🇮🇩 Indonesia", callback_data="setlang_id"),
                InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")
            ],
            [InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_settings")]
        ]
        await query.message.edit_text(
            "🌐 Choose language / Pilih bahasa:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif data == "back_settings":
        pass  # Just refresh settings
    
    # Refresh settings menu
    group = db.get_group(chat.id)
    keyboard = build_settings_keyboard(group, lang)
    
    await query.message.edit_text(
        get_text(lang, "settings_title"),
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

async def handle_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button CAPTCHA verification"""
    query = update.callback_query
    user = query.from_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    data = query.data
    parts = data.split("_")
    target_user_id = int(parts[1])
    
    if user.id != target_user_id:
        await query.answer(get_text(lang, "verify_not_your"), show_alert=True)
        return
    
    verification = db.get_pending_verification(user.id, chat.id)
    if not verification:
        await query.answer("Verification expired!", show_alert=True)
        return
    
    # Verification successful
    try:
        await chat.restrict_member(
            user.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        
        db.remove_pending_verification(user.id, chat.id)
        db.update_user(user.id, chat.id, is_verified=1)
        db.update_statistics(chat.id, verified_count=1)
        
        await query.message.edit_text(
            get_text(lang, "verify_success", name=user.first_name),
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Error verifying user: {e}")

async def handle_math_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle math CAPTCHA answer"""
    query = update.callback_query
    user = query.from_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    data = query.data
    parts = data.split("_")
    target_user_id = int(parts[1])
    answer = parts[2]
    
    if user.id != target_user_id:
        await query.answer(get_text(lang, "verify_not_your"), show_alert=True)
        return
    
    verification = db.get_pending_verification(user.id, chat.id)
    if not verification:
        await query.answer("Verification expired!", show_alert=True)
        return
    
    if answer == verification['captcha_answer']:
        # Correct answer
        try:
            await chat.restrict_member(
                user.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            
            db.remove_pending_verification(user.id, chat.id)
            db.update_user(user.id, chat.id, is_verified=1)
            db.update_statistics(chat.id, verified_count=1)
            
            await query.message.edit_text(
                get_text(lang, "verify_success", name=user.first_name),
                parse_mode=ParseMode.HTML
            )
        except TelegramError as e:
            logger.error(f"Error verifying user: {e}")
    else:
        # Wrong answer
        attempts = db.update_verification_attempts(user.id, chat.id)
        
        if attempts <= 0:
            # No more attempts - kick user
            try:
                await chat.ban_member(user.id)
                await chat.unban_member(user.id)
                db.remove_pending_verification(user.id, chat.id)
                db.update_statistics(chat.id, rejected_count=1)
                
                await query.message.edit_text(
                    get_text(lang, "verify_failed", name=user.first_name),
                    parse_mode=ParseMode.HTML
                )
            except TelegramError as e:
                logger.error(f"Error kicking user: {e}")
        else:
            await query.answer(
                get_text(lang, "verify_wrong", attempts=attempts),
                show_alert=True
            )

async def handle_emoji_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle emoji CAPTCHA answer"""
    query = update.callback_query
    user = query.from_user
    chat = update.effective_chat
    lang = get_user_language(user)
    
    data = query.data
    parts = data.split("_")
    target_user_id = int(parts[1])
    answer = parts[2]
    
    if user.id != target_user_id:
        await query.answer(get_text(lang, "verify_not_your"), show_alert=True)
        return
    
    verification = db.get_pending_verification(user.id, chat.id)
    if not verification:
        await query.answer("Verification expired!", show_alert=True)
        return
    
    if answer == verification['captcha_answer']:
        # Correct answer
        try:
            await chat.restrict_member(
                user.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            
            db.remove_pending_verification(user.id, chat.id)
            db.update_user(user.id, chat.id, is_verified=1)
            db.update_statistics(chat.id, verified_count=1)
            
            await query.message.edit_text(
                get_text(lang, "verify_success", name=user.first_name),
                parse_mode=ParseMode.HTML
            )
        except TelegramError as e:
            logger.error(f"Error verifying user: {e}")
    else:
        # Wrong answer
        attempts = db.update_verification_attempts(user.id, chat.id)
        
        if attempts <= 0:
            # No more attempts - kick user
            try:
                await chat.ban_member(user.id)
                await chat.unban_member(user.id)
                db.remove_pending_verification(user.id, chat.id)
                db.update_statistics(chat.id, rejected_count=1)
                
                await query.message.edit_text(
                    get_text(lang, "verify_failed", name=user.first_name),
                    parse_mode=ParseMode.HTML
                )
            except TelegramError as e:
                logger.error(f"Error kicking user: {e}")
        else:
            await query.answer(
                get_text(lang, "verify_wrong", attempts=attempts),
                show_alert=True
            )

# ═══════════════════════════════════════════════════════════════════════════════
#                           NEW MEMBER HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining the group"""
    chat = update.effective_chat
    
    if not update.message or not update.message.new_chat_members:
        return
    
    group = db.get_or_create_group(chat.id, chat.title)
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        lang = get_user_language(member)
        
        # Anti-raid check
        if group['antiraid_enabled']:
            join_count, is_raid = db.track_join(chat.id)
            
            if is_raid or db.is_raid_mode(chat.id):
                # Raid detected - kick new member
                try:
                    await chat.ban_member(member.id)
                    await chat.unban_member(member.id)
                    
                    if is_raid and join_count == group['antiraid_limit']:
                        await chat.send_message(
                            get_text(lang, "raid_detected",
                                    count=join_count,
                                    time=group['antiraid_time']),
                            parse_mode=ParseMode.HTML
                        )
                except:
                    pass
                continue
        
        # Create user record
        db.get_or_create_user(member.id, chat.id, member.username, member.first_name)
        
        # Verification
        if group['verification_enabled']:
            await send_verification(update, context, member, group, lang)
        elif group['welcome_enabled']:
            # Just send welcome message
            await send_welcome_message(update, context, member, group, lang)

async def send_verification(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           member: User, group: dict, lang: Language):
    """Send verification challenge to new member"""
    chat = update.effective_chat
    captcha_type = group['captcha_type']
    timeout = group['verification_timeout']
    
    # Mute user until verification
    try:
        await chat.restrict_member(
            member.id,
            ChatPermissions(can_send_messages=False)
        )
    except TelegramError as e:
        logger.error(f"Error muting new member: {e}")
        return
    
    # Generate CAPTCHA based on type
    if captcha_type == 'button':
        _, answer = CaptchaGenerator.generate_button()
        instruction = get_text(lang, "verify_button_instruction")
        
        keyboard = [[InlineKeyboardButton(
            get_text(lang, "verify_button_text"),
            callback_data=f"verify_{member.id}"
        )]]
        
    elif captcha_type == 'math':
        question, answer = CaptchaGenerator.generate_math()
        instruction = get_text(lang, "verify_math_instruction", question=question)
        
        # Generate answer options
        correct = int(answer)
        wrong_answers = [correct + random.randint(-10, 10) for _ in range(3)]
        wrong_answers = [w for w in wrong_answers if w != correct and w >= 0][:3]
        
        options = wrong_answers + [correct]
        random.shuffle(options)
        
        keyboard = [[
            InlineKeyboardButton(str(opt), callback_data=f"math_{member.id}_{opt}")
            for opt in options
        ]]
        
    elif captcha_type == 'emoji':
        question, answer, options = CaptchaGenerator.generate_emoji(lang)
        instruction = get_text(lang, "verify_emoji_instruction", question=question)
        
        keyboard = [[
            InlineKeyboardButton(opt, callback_data=f"emoji_{member.id}_{opt}")
            for opt in options
        ]]
    else:
        # Default to button
        _, answer = CaptchaGenerator.generate_button()
        instruction = get_text(lang, "verify_button_instruction")
        keyboard = [[InlineKeyboardButton(
            get_text(lang, "verify_button_text"),
            callback_data=f"verify_{member.id}"
        )]]
    
    # Send verification message
    message = await update.message.reply_text(
        get_text(lang, "verify_welcome",
                name=member.first_name,
                verify_instruction=instruction,
                timeout=timeout),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    # Store pending verification
    db.add_pending_verification(member.id, chat.id, message.message_id, str(answer), timeout)
    
    # Schedule timeout job
    context.job_queue.run_once(
        verification_timeout_job,
        timeout,
        data={
            'chat_id': chat.id,
            'user_id': member.id,
            'message_id': message.message_id
        },
        name=f"verify_timeout_{chat.id}_{member.id}"
    )

async def send_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE,
                               member: User, group: dict, lang: Language):
    """Send welcome message to new member"""
    chat = update.effective_chat
    
    if group['welcome_message']:
        message = group['welcome_message'].format(
            name=member.first_name,
            username=f"@{member.username}" if member.username else member.first_name,
            chat=chat.title
        )
    else:
        message = f"👋 Welcome {member.mention_html()} to {chat.title}!"
    
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

async def verification_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to handle verification timeout"""
    data = context.job.data
    chat_id = data['chat_id']
    user_id = data['user_id']
    message_id = data['message_id']
    
    # Check if still pending
    verification = db.get_pending_verification(user_id, chat_id)
    if not verification:
        return  # Already verified or removed
    
    try:
        # Kick user
        await context.bot.ban_chat_member(chat_id, user_id)
        await context.bot.unban_chat_member(chat_id, user_id)
        
        # Update message
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⏰ Verification timeout! User has been kicked.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        # Cleanup
        db.remove_pending_verification(user_id, chat_id)
        db.update_statistics(chat_id, rejected_count=1)
        
    except TelegramError as e:
        logger.error(f"Error in verification timeout: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#                           MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all messages for anti-spam protection"""
    if not update.message or not update.effective_chat:
        return
    
    chat = update.effective_chat
    user = update.effective_user
    message = update.message
    
    if chat.type == 'private':
        return
    
    # Check if user is admin
    try:
        member = await chat.get_member(user.id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
    except:
        pass
    
    group = db.get_or_create_group(chat.id, chat.title)
    lang = get_user_language(user)
    
    # Anti-spam checks
    if group['antispam_enabled']:
        # Anti-flood
        if group['antiflood_enabled']:
            msg_count, violations = db.update_flood_tracking(user.id, chat.id)
            
            if msg_count > group['antiflood_limit']:
                violations = db.add_flood_violation(user.id, chat.id)
                
                try:
                    await message.delete()
                except:
                    pass
                
                if violations >= 3:
                    # Mute user for 5 minutes
                    try:
                        await chat.restrict_member(
                            user.id,
                            ChatPermissions(can_send_messages=False),
                            until_date=datetime.now() + timedelta(minutes=5)
                        )
                        db.reset_flood_tracking(user.id, chat.id)
                        db.update_statistics(chat.id, spam_blocked=1)
                        
                        await chat.send_message(
                            get_text(lang, "flood_muted",
                                    user=user.mention_html(),
                                    duration="5 min"),
                            parse_mode=ParseMode.HTML
                        )
                    except:
                        pass
                else:
                    await chat.send_message(
                        get_text(lang, "flood_warning",
                                user=user.mention_html(),
                                count=violations,
                                limit=3),
                        parse_mode=ParseMode.HTML
                    )
                return
    
    # Anti-link
    if group['antilink_enabled'] and message.text:
        link_pattern = r'(https?://|t\.me/|telegram\.me/|@\w+)'
        if re.search(link_pattern, message.text, re.IGNORECASE):
            try:
                await message.delete()
                db.update_statistics(chat.id, spam_blocked=1)
                
                warn_msg = await chat.send_message(
                    get_text(lang, "link_deleted", user=user.mention_html()),
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(5)
                await warn_msg.delete()
            except:
                pass
            return
    
    # Anti-forward
    if group['antiforward_enabled'] and message.forward_date:
        try:
            await message.delete()
            db.update_statistics(chat.id, spam_blocked=1)
            
            warn_msg = await chat.send_message(
                get_text(lang, "forward_deleted", user=user.mention_html()),
                parse_mode=ParseMode.HTML
            )
            await asyncio.sleep(5)
            await warn_msg.delete()
        except:
            pass
        return

# ═══════════════════════════════════════════════════════════════════════════════
#                              ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Exception while handling update: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
#                               MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main function to run the bot"""
    print("""
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                     🛡️ SAFEGUARD BOT - TELEGRAM SECURITY                     ║
    ║                         Multi-Language Group Protection                        ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: Please set your bot token!")
        print("   Set BOT_TOKEN environment variable or edit the script.")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("ping", cmd_ping))
    application.add_handler(CommandHandler("settings", cmd_settings))
    application.add_handler(CommandHandler("warn", cmd_warn))
    application.add_handler(CommandHandler("unwarn", cmd_unwarn))
    application.add_handler(CommandHandler("warns", cmd_warns))
    application.add_handler(CommandHandler("mywarns", cmd_mywarns))
    application.add_handler(CommandHandler("kick", cmd_kick))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("mute", cmd_mute))
    application.add_handler(CommandHandler("unmute", cmd_unmute))
    application.add_handler(CommandHandler("purge", cmd_purge))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    application.add_handler(CommandHandler("rules", cmd_rules))
    application.add_handler(CommandHandler("setlang", cmd_setlang))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # New member handler
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        new_member_handler
    ))
    
    # Message handler for anti-spam
    application.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
        message_handler
    ))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🚀 SafeGuard Bot is starting...")
    print("✅ Bot is running! Press Ctrl+C to stop.")
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
