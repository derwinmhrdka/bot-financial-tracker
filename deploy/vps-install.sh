#!/usr/bin/env bash
# Setup sekali di VPS (Ubuntu/Debian). Jalankan sebagai user dengan sudo.
# Contoh: GITHUB_REPO=https://github.com/USER/bot-financial-tracker.git bash deploy/vps-install.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bot-financial-tracker}"
GITHUB_REPO="${GITHUB_REPO:-}"

if [[ $EUID -eq 0 ]]; then
  echo "Jangan jalankan sebagai root. Pakai user biasa + sudo (mis. ubuntu)."
  exit 1
fi

echo "==> Paket sistem"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3 python3-venv python3-pip git ca-certificates

DEPLOY_USER="${DEPLOY_USER:-$USER}"

echo "==> Direktori $APP_DIR (owner: $DEPLOY_USER)"
sudo mkdir -p "$APP_DIR"
sudo chown "$DEPLOY_USER":"$DEPLOY_USER" "$APP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  if [[ -z "$GITHUB_REPO" ]]; then
    echo "Set GITHUB_REPO=https://github.com/ORG/bot-financial-tracker.git lalu jalankan lagi."
    exit 1
  fi
  git clone "$GITHUB_REPO" "$APP_DIR"
fi

cd "$APP_DIR"
git pull --ff-only || true

echo "==> Python venv + dependensi"
bash deploy/remote-deploy.sh

echo "==> systemd (User=$DEPLOY_USER)"
sudo cp deploy/fintracker-bot.service /etc/systemd/system/
sudo sed -i "s|/opt/bot-financial-tracker|$APP_DIR|g" /etc/systemd/system/fintracker-bot.service
sudo sed -i "s|^User=.*|User=$DEPLOY_USER|" /etc/systemd/system/fintracker-bot.service
sudo sed -i "s|^Group=.*|Group=$DEPLOY_USER|" /etc/systemd/system/fintracker-bot.service
sudo chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$APP_DIR"
sudo chmod +x "$APP_DIR/deploy/start-bot.sh" "$APP_DIR/deploy/remote-deploy.sh"

if [[ ! -f .env.local ]]; then
  cp deploy/env.local.example .env.local
  echo ""
  echo "PENTING: edit $APP_DIR/.env.local (token, sheets, path absolut)"
  echo "  nano $APP_DIR/.env.local"
  echo "Upload service account JSON ke: $APP_DIR/secrets/"
fi

sudo mkdir -p "$APP_DIR/data" "$APP_DIR/secrets"
sudo chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$APP_DIR/data" "$APP_DIR/secrets"

SUDOERS="/etc/sudoers.d/fintracker-bot"
echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart fintracker-bot, /bin/systemctl start fintracker-bot, /bin/systemctl stop fintracker-bot, /bin/systemctl enable fintracker-bot, /bin/systemctl daemon-reload" | sudo tee "$SUDOERS" >/dev/null
sudo chmod 440 "$SUDOERS"

sudo systemctl daemon-reload
sudo systemctl enable fintracker-bot

echo ""
echo "Selesai setup. Sebelum start:"
echo "  1. Lengkapi .env.local (FINTRACKER_DB_PATH=$APP_DIR/data/expenses.db)"
echo "  2. secrets/*.json untuk Google Sheets"
echo "  3. sudo systemctl start fintracker-bot"
echo "  4. journalctl -u fintracker-bot -f"
