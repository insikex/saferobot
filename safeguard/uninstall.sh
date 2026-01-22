#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════════
#                     🛡️ SAFEGUARD BOT - UNINSTALL SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Cek root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} Script ini harus dijalankan sebagai root!"
    exit 1
fi

echo -e "${YELLOW}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                     🛡️ SAFEGUARD BOT - UNINSTALLER                           ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

read -p "Apakah Anda yakin ingin menghapus SafeGuard Bot? (y/n): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Uninstall dibatalkan."
    exit 0
fi

echo ""
echo -e "${YELLOW}[INFO]${NC} Menghentikan service..."
systemctl stop safeguard 2>/dev/null || true
systemctl disable safeguard 2>/dev/null || true

echo -e "${YELLOW}[INFO]${NC} Menghapus service file..."
rm -f /etc/systemd/system/safeguard.service
systemctl daemon-reload

echo -e "${YELLOW}[INFO]${NC} Menghapus file instalasi..."
rm -rf /opt/safeguard

echo ""
echo -e "${GREEN}✅ SafeGuard Bot berhasil dihapus!${NC}"
