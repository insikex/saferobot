# 🛡️ SafeGuard Bot - Telegram Group Protection

Bot keamanan grup Telegram dengan fitur lengkap dan multi-bahasa (Indonesia & English).

## ✨ Fitur Utama

### 🔐 Verifikasi Member Baru (CAPTCHA)
- **Button CAPTCHA** - Klik tombol untuk verifikasi
- **Math CAPTCHA** - Jawab soal matematika sederhana
- **Emoji CAPTCHA** - Pilih emoji yang benar
- Auto-kick jika tidak verifikasi dalam waktu yang ditentukan

### 🚫 Anti-Spam Protection
- **Anti-Flood** - Batasi spam pesan beruntun
- **Anti-Link** - Blokir link/URL otomatis
- **Anti-Forward** - Blokir pesan forward
- **Auto-mute** - Bisukan pelanggar spam otomatis

### 🛡️ Anti-Raid Detection
- Deteksi serangan massal (banyak member join sekaligus)
- Mode perlindungan otomatis saat raid terdeteksi
- Konfigurasi batas join per waktu

### ⚠️ Warning System
- Sistem peringatan dengan batas kustom
- Auto-kick saat mencapai batas peringatan
- Log peringatan dengan alasan

### 🔨 Admin Tools
- `/warn` - Beri peringatan ke user
- `/unwarn` - Hapus peringatan
- `/kick` - Kick user dari grup
- `/ban` - Ban user dari grup
- `/unban` - Unban user
- `/mute` - Bisukan user (dengan durasi)
- `/unmute` - Batalkan bisu
- `/purge` - Hapus pesan massal
- `/stats` - Statistik grup

### 🌐 Multi-Language
- **Otomatis** - Bot mendeteksi bahasa user dari pengaturan Telegram
- **Indonesia** - Untuk user dengan bahasa Indonesia
- **English** - Untuk user lainnya
- Admin dapat mengatur bahasa default grup

### ⚙️ Pengaturan Lengkap
- Menu pengaturan interaktif dengan tombol
- Konfigurasi per-grup
- Pesan welcome kustom
- Aturan grup kustom

## 📋 Daftar Perintah

### Perintah Admin
| Perintah | Deskripsi |
|----------|-----------|
| `/settings` | Buka menu pengaturan |
| `/setwelcome <teks>` | Atur pesan selamat datang |
| `/warn @user [alasan]` | Beri peringatan |
| `/unwarn @user` | Hapus peringatan |
| `/warns @user` | Lihat peringatan user |
| `/kick @user [alasan]` | Kick user |
| `/ban @user [alasan]` | Ban user |
| `/unban <user_id>` | Unban user |
| `/mute @user [durasi] [alasan]` | Bisukan user |
| `/unmute @user` | Batalkan bisu |
| `/purge [jumlah]` | Hapus pesan |
| `/stats` | Statistik grup |
| `/rules [aturan]` | Lihat/atur aturan |
| `/setlang` | Ubah bahasa grup |

### Perintah Umum
| Perintah | Deskripsi |
|----------|-----------|
| `/start` | Mulai bot |
| `/help` | Bantuan |
| `/ping` | Cek status bot |
| `/mywarns` | Lihat peringatan saya |
| `/rules` | Lihat aturan grup |

### Format Durasi Mute
- `1m` - 1 menit
- `1h` - 1 jam
- `1d` - 1 hari
- Contoh: `/mute @user 30m spam`

## 🚀 Instalasi di VPS Debian 13

### 1. Update Sistem
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Python dan Dependencies
```bash
sudo apt install -y python3 python3-pip python3-venv git
```

### 3. Buat Bot di Telegram
1. Buka [@BotFather](https://t.me/BotFather) di Telegram
2. Kirim `/newbot`
3. Ikuti instruksi untuk membuat bot
4. Simpan **token** yang diberikan

### 4. Clone/Upload Bot
```bash
# Buat direktori
mkdir -p /opt/safeguard
cd /opt/safeguard

# Upload file safeguard_bot.py ke folder ini
# Atau copy dari lokasi lain
```

### 5. Setup Virtual Environment
```bash
cd /opt/safeguard
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install python-telegram-bot[job-queue]==21.3
```

### 6. Konfigurasi Token
```bash
# Set environment variable
export BOT_TOKEN="YOUR_BOT_TOKEN_HERE"

# Atau edit langsung di file safeguard_bot.py
# Cari baris: BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
# Ganti dengan token Anda
```

### 7. Test Jalankan Bot
```bash
cd /opt/safeguard
source venv/bin/activate
python3 safeguard_bot.py
```

### 8. Setup Systemd Service (Agar berjalan otomatis)

Buat file service:
```bash
sudo nano /etc/systemd/system/safeguard.service
```

Isi dengan:
```ini
[Unit]
Description=SafeGuard Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/safeguard
Environment="BOT_TOKEN=YOUR_BOT_TOKEN_HERE"
ExecStart=/opt/safeguard/venv/bin/python3 /opt/safeguard/safeguard_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**PENTING**: Ganti `YOUR_BOT_TOKEN_HERE` dengan token bot Anda!

### 9. Aktifkan dan Jalankan Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Aktifkan service agar start saat boot
sudo systemctl enable safeguard

# Jalankan service
sudo systemctl start safeguard

# Cek status
sudo systemctl status safeguard
```

### 10. Perintah Berguna
```bash
# Lihat log bot
sudo journalctl -u safeguard -f

# Restart bot
sudo systemctl restart safeguard

# Stop bot
sudo systemctl stop safeguard

# Lihat status
sudo systemctl status safeguard
```

## 📁 Struktur File

```
/opt/safeguard/
├── safeguard_bot.py    # File utama bot
├── safeguard.db        # Database SQLite (otomatis dibuat)
├── safeguard.log       # File log (otomatis dibuat)
├── requirements.txt    # Dependencies
├── README.md           # Dokumentasi ini
└── venv/               # Virtual environment
```

## ⚙️ Konfigurasi Bot di Telegram

### Mengatur Bot Commands di BotFather
1. Buka [@BotFather](https://t.me/BotFather)
2. Kirim `/setcommands`
3. Pilih bot Anda
4. Kirim daftar perintah berikut:

```
start - Mulai bot
help - Bantuan
ping - Cek status bot
settings - Pengaturan grup (admin)
warn - Beri peringatan (admin)
unwarn - Hapus peringatan (admin)
warns - Lihat peringatan user
mywarns - Lihat peringatan saya
kick - Kick user (admin)
ban - Ban user (admin)
unban - Unban user (admin)
mute - Bisukan user (admin)
unmute - Batalkan bisu (admin)
purge - Hapus pesan (admin)
stats - Statistik grup
rules - Aturan grup
setwelcome - Atur pesan welcome (admin)
setlang - Ubah bahasa (admin)
```

### Menambahkan Bot ke Grup
1. Buka grup Anda di Telegram
2. Klik nama grup → Edit → Administrators
3. Add Administrator → Cari bot Anda
4. Berikan izin:
   - ✅ Delete messages
   - ✅ Ban users
   - ✅ Invite users via link
   - ✅ Pin messages
   - ✅ Manage video chats
   - ✅ Remain anonymous (opsional)

## 🔧 Troubleshooting

### Bot tidak merespon
1. Pastikan token sudah benar
2. Cek apakah bot sudah jadi admin
3. Lihat log: `sudo journalctl -u safeguard -f`

### Error permission
1. Pastikan bot punya izin admin yang cukup
2. Bot tidak bisa menindak admin lain

### Database error
1. Hapus file `safeguard.db` untuk reset
2. Restart bot

### Bot crash terus-menerus
1. Cek log untuk detail error
2. Pastikan Python dan dependencies ter-update
3. Cek koneksi internet VPS

## 📝 Changelog

### v2.0.0
- Multi-language support (ID & EN)
- Multiple CAPTCHA types (Button, Math, Emoji)
- Anti-raid protection
- Improved database with SQLite
- Better error handling
- Comprehensive statistics

## 📄 License

MIT License - Bebas digunakan dan dimodifikasi.

## 🤝 Support

Jika ada pertanyaan atau masalah, silakan buat issue di repository ini.

---

Made with ❤️ for Telegram Community
