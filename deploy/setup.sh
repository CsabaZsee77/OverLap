#!/bin/bash
# OverLAP – Hetzner VPS setup script
# Futtatás: bash setup.sh <GITHUB_REPO_URL>
# Pl.:       bash setup.sh https://github.com/CsabaZsee77/OverLap.git
#
# Ubuntu 22.04 LTS

set -e

REPO_URL="${1:-https://github.com/CsabaZsee77/OverLap.git}"
APP_USER="overlap"
APP_DIR="/home/${APP_USER}/OverLap"

echo "=== OverLAP deployment: ${REPO_URL} ==="

# ─── Rendszer frissítés ──────────────────────────��────────────────────────────
apt update && apt upgrade -y
apt install -y git nginx python3 python3-pip python3-venv curl

# ─── Node.js 20 LTS ─────────────────────────────────────────────────────���────
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

echo "Node: $(node -v)  NPM: $(npm -v)  Python: $(python3 -V)"

# ─── Felhasználó ────────────────────────────────��────────────────────────────
if ! id "${APP_USER}" &>/dev/null; then
    adduser --disabled-password --gecos "" "${APP_USER}"
    usermod -aG sudo "${APP_USER}"
fi

# ─── Repo klónozás ─────────────────────────────────────────────────��─────────
if [ -d "${APP_DIR}" ]; then
    echo "Repo már létezik → git pull"
    sudo -u "${APP_USER}" git -C "${APP_DIR}" pull
else
    sudo -u "${APP_USER}" git clone "${REPO_URL}" "${APP_DIR}"
fi

# ─── Frontend build ────────────────────��──────────────────────────────────────
echo "=== Frontend build ==="
cd "${APP_DIR}/frontend"
sudo -u "${APP_USER}" npm ci
sudo -u "${APP_USER}" npm run build
echo "Frontend build kész → ${APP_DIR}/frontend/dist/"

# ─── Backend Python env ────────────────────────────────��──────────────────────
echo "=== Backend setup ==="
cd "${APP_DIR}/backend"
sudo -u "${APP_USER}" python3 -m venv venv
sudo -u "${APP_USER}" "${APP_DIR}/backend/venv/bin/pip" install -r requirements.txt

# ─── Pályák feltöltése (seed) ──────────────────────────────────────────────────
echo "=== Track seed ==="
sudo -u "${APP_USER}" "${APP_DIR}/backend/venv/bin/python3" "${APP_DIR}/deploy/seed_tracks.py"

# ─── Systemd service ──────────────────────────────��────────────────────────���─
cp "${APP_DIR}/deploy/overlap-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable overlap-api
systemctl restart overlap-api
systemctl status overlap-api --no-pager

# ─── Nginx konfig ──────────────────────────��─────────────────────────────────
cp "${APP_DIR}/deploy/nginx.conf" /etc/nginx/sites-available/overlap
ln -sf /etc/nginx/sites-available/overlap /etc/nginx/sites-enabled/overlap
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "=== KÉSZ ==="
SERVER_IP=$(curl -s https://api.ipify.org)
echo "Elérhető: http://${SERVER_IP}"
echo "API docs: http://${SERVER_IP}/api/docs"
