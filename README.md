# 🤖 SafeRobot v6.0 - Universal Video Downloader Bot

Bot Telegram UNIVERSAL untuk mendownload video dari **WEBSITE APAPUN** - seperti 9xbuddy.site!

## 🔥 Apa yang Baru di v6.0?

### Universal Video Extraction (Enhanced)
Bot ini sekarang dapat mendownload video dari **hampir semua website** menggunakan teknologi yang sama seperti 9xbuddy.site dan aplikasi browser download di PlayStore:

1. **Network Interception** - Menangkap SEMUA request video/audio dari browser
2. **Playwright Browser Automation** - Render halaman JavaScript secara penuh
3. **Multi-Pattern Detection** - Deteksi 60+ pola URL video
4. **External API Fallback** - Multiple API (Cobalt, SaveFrom, Y2Mate, dll)
5. **Specialized Videy/Videq Extractor** - Extractor khusus untuk platform Videy family
6. **Improved Error Handling** - Retry logic dan better fallbacks

## ✨ Fitur

### 🔥 Universal Download (BARU!)
- **Download dari WEBSITE APAPUN** yang memiliki video
- Network interception (seperti browser app di PlayStore)
- Deteksi otomatis video player (JWPlayer, Video.js, Plyr, dll)
- Ekstraksi video dari JavaScript yang ter-obfuscate
- Fallback ke external API (cobalt, dll)

### 📱 Platform Sosial Media
- TikTok
- Instagram (Post, Reels, Stories)
- Twitter/X
- YouTube
- Facebook
- Pinterest

### 🎬 Platform Streaming (100+ Platform)
- **DoodStream Family**: doodstream.com, dood.to, dood-hd.com, dll
- **TeraBox Family**: terabox.com, 1024terabox.com, dll
- **Videy/Videq Family**: vidoy.com, videq.io, videypro.live, dll
- **LuluStream**: lulustream.com, lulu.st, lixstream.com
- **MyVidPlay, Filemoon, StreamWish, VidHide**
- **Dan 100+ platform lainnya!**

### 🔥 Fitur Lainnya
- Multi-language (Indonesia/English)
- Button menu interface
- Download video, audio, dan foto
- Auto-zip untuk link folder/playlist (limit ukuran)
- Statistik pengguna (untuk owner)
- Broadcast message ke semua user

---

## 🧠 Bagaimana Universal Extraction Bekerja?

### Mengapa 9xbuddy.site dan Browser App Bisa Download dari Mana Saja?

1. **Network Interception**: Mereka menangkap SEMUA request HTTP/HTTPS dari browser, termasuk video stream
2. **JavaScript Rendering**: Mereka merender halaman secara penuh termasuk JavaScript
3. **Player Detection**: Mereka mendeteksi video player seperti JWPlayer, Video.js, Plyr

### Teknologi yang Digunakan SafeRobot v5.0:

1. **Playwright Browser Automation** - Menjalankan browser Chromium secara headless
2. **Network Response Interception** - Menangkap semua URL video/audio dari network requests
3. **JavaScript Extraction** - Mengekstrak URL dari JavaScript context
4. **Pattern Matching** - 40+ regex pattern untuk mendeteksi URL video
5. **External API Fallback** - Menggunakan API seperti Cobalt jika metode lain gagal

---

## 🚀 CARA MENJALANKAN DI VPS DEBIAN 13

### Langkah 1: Update Sistem

```bash
# Login ke VPS sebagai root atau gunakan sudo
sudo apt update && sudo apt upgrade -y
```

### Langkah 2: Install Dependencies

```bash
# Install Python dan pip
sudo apt install -y python3 python3-pip python3-venv

# Install FFmpeg (untuk konversi audio/video)
sudo apt install -y ffmpeg

# Install dependencies tambahan
sudo apt install -y git curl wget
```

### Langkah 3: Clone Repository atau Upload File

**Opsi A: Upload file langsung**
```bash
# Buat direktori untuk bot
mkdir -p /opt/saferobot
cd /opt/saferobot

# Upload file saferobot.py ke direktori ini menggunakan SFTP atau SCP
```

**Opsi B: Clone dari repository**
```bash
cd /opt
git clone <YOUR_REPOSITORY_URL> saferobot
cd saferobot
```

### Langkah 4: Buat Virtual Environment

```bash
cd /opt/saferobot

# Buat virtual environment
python3 -m venv venv

# Aktifkan virtual environment
source venv/bin/activate
```

### Langkah 5: Install Python Dependencies

```bash
# Pastikan virtual environment aktif
source /opt/saferobot/venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install python-telegram-bot[all]
pip install yt-dlp
pip install beautifulsoup4
pip install requests
pip install lxml
pip install playwright

# PENTING: Install browser untuk Playwright
python -m playwright install chromium
```

Atau gunakan requirements.txt:

```bash
# Install dari requirements.txt
pip install -r requirements.txt

# PENTING: Install browser untuk Playwright (Universal Extraction)
python -m playwright install chromium
```

> **Note**: Playwright digunakan untuk Network Interception yang membuat bot bisa download dari website apapun seperti 9xbuddy.site

### Langkah 6: Konfigurasi Bot

Edit file `saferobot.py` dan ganti konfigurasi:

```bash
nano /opt/saferobot/saferobot.py
```

Cari bagian KONFIGURASI dan ganti:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Dapatkan dari @BotFather
OWNER_ID = YOUR_TELEGRAM_USER_ID   # Ganti dengan User ID Anda
```

**Cara mendapatkan BOT_TOKEN:**
1. Buka Telegram, cari @BotFather
2. Kirim `/newbot`
3. Ikuti instruksi untuk membuat bot baru
4. Copy token yang diberikan

**Cara mendapatkan User ID:**
1. Buka Telegram, cari @userinfobot
2. Kirim `/start`
3. Copy ID yang ditampilkan

### Langkah 7: Test Menjalankan Bot

```bash
cd /opt/saferobot
source venv/bin/activate
python3 saferobot.py
```

Jika berhasil, Anda akan melihat:
```
============================================================
🤖 SafeRobot v4.0 - Multi-Platform Video Downloader
============================================================
...
✅ SafeRobot is running!
```

### Langkah 8: Menjalankan Bot sebagai Service (Background)

Buat systemd service agar bot berjalan terus menerus:

```bash
sudo nano /etc/systemd/system/saferobot.service
```

Paste konfigurasi berikut:

```ini
[Unit]
Description=SafeRobot Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/saferobot
Environment=PATH=/opt/saferobot/venv/bin
ExecStart=/opt/saferobot/venv/bin/python3 /opt/saferobot/saferobot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Simpan dan keluar (Ctrl+X, Y, Enter).

### Langkah 9: Aktifkan dan Jalankan Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service agar berjalan saat boot
sudo systemctl enable saferobot

# Start service
sudo systemctl start saferobot

# Cek status
sudo systemctl status saferobot
```

### Langkah 10: Perintah Pengelolaan Service

```bash
# Melihat status bot
sudo systemctl status saferobot

# Melihat log real-time
sudo journalctl -u saferobot -f

# Restart bot
sudo systemctl restart saferobot

# Stop bot
sudo systemctl stop saferobot

# Start bot
sudo systemctl start saferobot
```

---

## 📝 Perintah Bot

### Untuk Semua User
- `/start` - Menu utama
- `/platforms` - Daftar platform yang didukung
- Kirim link untuk download

### Untuk Owner
- `/stats` - Statistik pengguna dan download
- `/broadcast <pesan>` - Kirim pesan ke semua user

---

## 🛠️ Troubleshooting

### Bot tidak bisa download video

1. **Update yt-dlp ke versi terbaru:**
```bash
source /opt/saferobot/venv/bin/activate
pip install --upgrade yt-dlp
sudo systemctl restart saferobot
```

2. **Cek apakah FFmpeg terinstall:**
```bash
ffmpeg -version
```

3. **Cek log error:**
```bash
sudo journalctl -u saferobot -n 50
```

### Bot tidak merespons

1. **Cek status service:**
```bash
sudo systemctl status saferobot
```

2. **Cek koneksi internet VPS:**
```bash
ping api.telegram.org
```

3. **Restart bot:**
```bash
sudo systemctl restart saferobot
```

### Error "Permission denied"

```bash
# Berikan permission ke folder downloads
chmod -R 755 /opt/saferobot
chown -R root:root /opt/saferobot
```

### Memory/CPU tinggi

1. **Limit file size di konfigurasi** (sudah diatur 50MB default)
2. **Restart service secara berkala:**
```bash
# Buat cron job untuk restart setiap hari jam 3 pagi
sudo crontab -e
# Tambahkan baris:
0 3 * * * /bin/systemctl restart saferobot
```

---

## 📁 Struktur File

```
/opt/saferobot/
├── saferobot.py          # File utama bot
├── venv/                  # Virtual environment
├── downloads/             # Folder temporary download
├── users_database.json    # Database pengguna
├── requirements.txt       # Python dependencies
└── README.md             # Dokumentasi
```

---

## 🔄 Update Bot

```bash
cd /opt/saferobot
source venv/bin/activate

# Update yt-dlp
pip install --upgrade yt-dlp

# Update dependencies lain
pip install --upgrade python-telegram-bot beautifulsoup4 requests

# Restart bot
sudo systemctl restart saferobot
```

---

## ⚙️ Konfigurasi Tambahan

### Mengatur Timeout Download

Dalam file `saferobot.py`, cari bagian `ydl_opts` dan sesuaikan:

```python
ydl_opts = {
    ...
    'socket_timeout': 60,  # Timeout dalam detik
    'retries': 3,          # Jumlah retry jika gagal
    ...
}
```

### Mengatur Limit Ukuran File

```python
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB (limit Telegram)
```

### Auto-zip Folder/Playlist

Jika link terdeteksi sebagai folder/playlist, bot akan menggabungkan hasil download menjadi file .zip. Anda dapat mengatur batasnya lewat environment variable:

```bash
# 1 = aktif, 0 = nonaktif
export ALLOW_PLAYLIST_ZIP=1

# Batas jumlah item yang diambil dari playlist/folder
export MAX_ARCHIVE_ITEMS=10

# Batas ukuran arsip (dalam byte)
export MAX_ARCHIVE_SIZE=52428800
```

---

## 📞 Support

Jika ada pertanyaan atau masalah, hubungi owner bot melalui Telegram.

---

## ⚠️ Disclaimer

Bot ini dibuat untuk keperluan edukasi. Gunakan dengan bijak dan patuhi Terms of Service dari masing-masing platform.

---

**Made with ❤️ by SafeRobot Team**
