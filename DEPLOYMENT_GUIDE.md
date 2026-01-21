# SafeRobot v6.0 - Panduan Deployment di VPS Debian 13

## Daftar Isi
1. [Persiapan VPS](#1-persiapan-vps)
2. [Install Dependencies](#2-install-dependencies)
3. [Setup Bot](#3-setup-bot)
4. [Konfigurasi Systemd](#4-konfigurasi-systemd-service)
5. [Menjalankan Bot](#5-menjalankan-bot)
6. [Maintenance](#6-maintenance)

---

## 1. Persiapan VPS

### Login ke VPS
```bash
ssh root@IP_VPS_ANDA
```

### Update sistem
```bash
apt update && apt upgrade -y
```

### Install dependencies sistem
```bash
apt install -y python3 python3-pip python3-venv git ffmpeg
```

---

## 2. Install Dependencies

### Buat user baru untuk bot (rekomendasi keamanan)
```bash
# Buat user baru
adduser saferobot

# Masuk ke user tersebut
su - saferobot
```

### Clone repository atau upload file
```bash
# Opsi 1: Clone dari GitHub (jika ada)
cd ~
git clone https://github.com/insikex/saferobot.git
cd saferobot

# Opsi 2: Upload manual menggunakan SCP (dari komputer lokal)
# scp saferobot.py saferobot@IP_VPS:~/saferobot/
```

### Buat virtual environment
```bash
cd ~/saferobot
python3 -m venv venv
source venv/bin/activate
```

### Install Python dependencies
```bash
pip install --upgrade pip
pip install python-telegram-bot[job-queue] yt-dlp Pillow
```

### Buat file requirements.txt (opsional, untuk dokumentasi)
```bash
cat > requirements.txt << 'EOF'
python-telegram-bot[job-queue]>=20.0
yt-dlp>=2024.1.0
Pillow>=10.0.0
EOF
```

---

## 3. Setup Bot

### Edit konfigurasi bot
```bash
nano saferobot.py
```

**Ubah bagian ini dengan data Anda:**
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Dari @BotFather
OWNER_ID = YOUR_TELEGRAM_ID        # ID Telegram Anda (number)
```

**Cara mendapatkan BOT_TOKEN:**
1. Buka Telegram, cari @BotFather
2. Ketik /newbot
3. Ikuti instruksi, copy token yang diberikan

**Cara mendapatkan OWNER_ID:**
1. Buka Telegram, cari @userinfobot
2. Start bot tersebut
3. Copy ID yang ditampilkan

### Simpan dan keluar dari nano
```
Ctrl + X, lalu Y, lalu Enter
```

### Test jalankan bot
```bash
python saferobot.py
```

Jika berhasil, akan muncul:
```
🤖 SafeRobot v6.0 Starting...
🎨 Features: Multi-platform Download + WhatsApp Sticker Export
🔘 NEW: Button-based menu (no commands needed!)
...
✅ SafeRobot is running!
```

Tekan `Ctrl + C` untuk menghentikan sementara.

---

## 4. Konfigurasi Systemd Service

### Keluar dari virtual environment
```bash
deactivate
```

### Buat service file (sebagai root)
```bash
exit  # Keluar dari user saferobot, kembali ke root
```

```bash
cat > /etc/systemd/system/saferobot.service << 'EOF'
[Unit]
Description=SafeRobot Telegram Bot
After=network.target

[Service]
Type=simple
User=saferobot
Group=saferobot
WorkingDirectory=/home/saferobot/saferobot
Environment="PATH=/home/saferobot/saferobot/venv/bin:/usr/bin"
ExecStart=/home/saferobot/saferobot/venv/bin/python saferobot.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=saferobot

[Install]
WantedBy=multi-user.target
EOF
```

### Reload systemd daemon
```bash
systemctl daemon-reload
```

### Aktifkan service agar jalan otomatis saat boot
```bash
systemctl enable saferobot
```

---

## 5. Menjalankan Bot

### Start bot
```bash
systemctl start saferobot
```

### Cek status bot
```bash
systemctl status saferobot
```

Output yang diharapkan:
```
● saferobot.service - SafeRobot Telegram Bot
     Loaded: loaded (/etc/systemd/system/saferobot.service; enabled)
     Active: active (running) since ...
```

### Lihat log bot
```bash
# Log real-time
journalctl -u saferobot -f

# Log 100 baris terakhir
journalctl -u saferobot -n 100
```

### Perintah kontrol lainnya
```bash
# Stop bot
systemctl stop saferobot

# Restart bot
systemctl restart saferobot

# Disable autostart
systemctl disable saferobot
```

---

## 6. Maintenance

### Update bot
```bash
# Login sebagai user saferobot
su - saferobot
cd ~/saferobot

# Pull perubahan terbaru (jika dari git)
git pull

# Atau upload file baru manual

# Keluar dari user
exit

# Restart service
systemctl restart saferobot
```

### Update yt-dlp (jika download gagal)
```bash
su - saferobot
source ~/saferobot/venv/bin/activate
pip install --upgrade yt-dlp
deactivate
exit
systemctl restart saferobot
```

### Backup database
```bash
# Sebagai root
cp /home/saferobot/saferobot/users_database.json /root/backup_users_database_$(date +%Y%m%d).json
```

### Cek disk usage
```bash
# Cek ukuran folder downloads
du -sh /home/saferobot/saferobot/downloads/

# Bersihkan file lama jika perlu
rm -rf /home/saferobot/saferobot/downloads/*
rm -rf /home/saferobot/saferobot/stickers/*
```

---

## Troubleshooting

### Bot tidak jalan
```bash
# Cek log error
journalctl -u saferobot -n 50 --no-pager

# Cek apakah service aktif
systemctl is-active saferobot
```

### Download gagal
1. Update yt-dlp:
```bash
su - saferobot
source ~/saferobot/venv/bin/activate
pip install --upgrade yt-dlp
```

2. Pastikan ffmpeg terinstall:
```bash
ffmpeg -version
```

### Bot restart terus menerus
Cek log untuk error:
```bash
journalctl -u saferobot -n 100
```

### Permission denied
```bash
# Pastikan ownership benar
chown -R saferobot:saferobot /home/saferobot/saferobot
chmod +x /home/saferobot/saferobot/saferobot.py
```

---

## Catatan Keamanan

1. **Jangan bagikan BOT_TOKEN** - Token adalah kunci akses ke bot Anda
2. **Gunakan firewall**:
```bash
apt install ufw
ufw allow ssh
ufw enable
```

3. **Update sistem secara berkala**:
```bash
apt update && apt upgrade -y
```

4. **Backup database secara berkala**

---

## Struktur Folder

```
/home/saferobot/saferobot/
├── saferobot.py           # File utama bot
├── venv/                  # Virtual environment Python
├── downloads/             # Folder temporary downloads
├── stickers/              # Folder temporary stickers
├── users_database.json    # Database user
└── requirements.txt       # Dependencies
```

---

## Perintah Ringkas

| Aksi | Perintah |
|------|----------|
| Start bot | `systemctl start saferobot` |
| Stop bot | `systemctl stop saferobot` |
| Restart bot | `systemctl restart saferobot` |
| Cek status | `systemctl status saferobot` |
| Lihat log | `journalctl -u saferobot -f` |
| Update yt-dlp | `pip install --upgrade yt-dlp` |

---

## Kontak & Dukungan

- Bot Official: @SafeRobot
- Sticker Pack: https://t.me/addstickers/saferobot

Selamat menggunakan SafeRobot! 🤖
