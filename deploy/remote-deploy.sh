#!/usr/bin/env bash
# Dipanggil setelah git pull (GitHub Actions atau manual).
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

if [[ ! -f .env.local ]]; then
  echo "ERROR: .env.local tidak ada di $APP_DIR" >&2
  exit 1
fi

if ! command -v python3 >/dev/null; then
  echo "ERROR: python3 tidak terpasang" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

chmod +x deploy/start-bot.sh deploy/remote-deploy.sh 2>/dev/null || true

if systemctl is-active --quiet fintracker-bot 2>/dev/null; then
  sudo systemctl restart fintracker-bot
  echo "OK: fintracker-bot restarted"
elif systemctl list-unit-files fintracker-bot.service >/dev/null 2>&1; then
  sudo systemctl enable --now fintracker-bot
  echo "OK: fintracker-bot started"
else
  echo "WARN: systemd fintracker-bot belum dipasang — jalankan deploy/vps-install.sh sekali"
fi
