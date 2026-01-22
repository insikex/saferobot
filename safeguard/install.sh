#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════════
#                     🛡️ SAFEGUARD BOT - INSTALLATION SCRIPT
#                         Untuk VPS Debian 12/13 atau Ubuntu
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Warna untuk output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logo
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                     🛡️ SAFEGUARD BOT - INSTALLER                             ║"
echo "║                         Telegram Group Protection                             ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Fungsi untuk log
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cek root
if [ "$EUID" -ne 0 ]; then
    log_error "Script ini harus dijalankan sebagai root!"
    echo "Gunakan: sudo bash install.sh"
    exit 1
fi

# Direktori instalasi
INSTALL_DIR="/opt/safeguard"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1: Update sistem
log_info "Updating system packages..."
apt update && apt upgrade -y

# Step 2: Install dependencies
log_info "Installing Python and dependencies..."
apt install -y python3 python3-pip python3-venv git curl

# Step 3: Buat direktori instalasi
log_info "Creating installation directory..."
mkdir -p $INSTALL_DIR

# Step 4: Copy file bot
log_info "Copying bot files..."
cp "$SCRIPT_DIR/safeguard_bot.py" $INSTALL_DIR/
cp "$SCRIPT_DIR/requirements.txt" $INSTALL_DIR/ 2>/dev/null || true
cp "$SCRIPT_DIR/README.md" $INSTALL_DIR/ 2>/dev/null || true

# Step 5: Setup virtual environment
log_info "Setting up Python virtual environment..."
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install python-telegram-bot[job-queue]==21.3

# Step 6: Minta token bot
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}                         KONFIGURASI BOT TOKEN                                  ${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Untuk mendapatkan token:"
echo "1. Buka @BotFather di Telegram"
echo "2. Kirim /newbot"
echo "3. Ikuti instruksi untuk membuat bot"
echo "4. Copy token yang diberikan"
echo ""
read -p "Masukkan Bot Token: " BOT_TOKEN

if [ -z "$BOT_TOKEN" ]; then
    log_error "Token tidak boleh kosong!"
    exit 1
fi

# Step 7: Buat systemd service
log_info "Creating systemd service..."
cat > /etc/systemd/system/safeguard.service << EOF
[Unit]
Description=SafeGuard Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="BOT_TOKEN=$BOT_TOKEN"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/safeguard_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 8: Reload dan aktifkan service
log_info "Enabling and starting service..."
systemctl daemon-reload
systemctl enable safeguard
systemctl start safeguard

# Step 9: Cek status
sleep 3
if systemctl is-active --quiet safeguard; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}                    ✅ INSTALASI BERHASIL!                                      ${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "Bot sudah berjalan! Berikut beberapa perintah berguna:"
    echo ""
    echo -e "  ${BLUE}Lihat status:${NC}    sudo systemctl status safeguard"
    echo -e "  ${BLUE}Lihat log:${NC}       sudo journalctl -u safeguard -f"
    echo -e "  ${BLUE}Restart bot:${NC}     sudo systemctl restart safeguard"
    echo -e "  ${BLUE}Stop bot:${NC}        sudo systemctl stop safeguard"
    echo ""
    echo -e "Langkah selanjutnya:"
    echo "1. Buka bot di Telegram"
    echo "2. Kirim /start untuk memulai"
    echo "3. Tambahkan bot ke grup dan jadikan admin"
    echo ""
else
    log_error "Bot gagal dijalankan! Cek log dengan:"
    echo "sudo journalctl -u safeguard -n 50"
fi
