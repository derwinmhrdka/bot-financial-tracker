#!/usr/bin/env bash
# Dipanggil setelah git pull (GitHub Actions atau manual).
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

if [[ ! -f .env.local ]]; then
  if [[ -f deploy/env.local.example ]]; then
    cp deploy/env.local.example .env.local
    echo "WARN: .env.local dibuat dari deploy/env.local.example — edit dulu" >&2
  else
    echo "ERROR: .env.local tidak ada di $APP_DIR" >&2
    exit 1
  fi
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

_has_token() {
  grep -qE '^TELEGRAM_BOT_TOKEN=.+[^[:space:]]' .env.local 2>/dev/null
}

if ! _has_token; then
  echo "SKIP systemctl: isi TELEGRAM_BOT_TOKEN di .env.local lalu: bash deploy/remote-deploy.sh"
  exit 0
fi

if systemctl is-active --quiet fintracker-bot 2>/dev/null; then
  sudo systemctl restart fintracker-bot
  echo "OK: fintracker-bot restarted"
elif systemctl list-unit-files fintracker-bot.service >/dev/null 2>&1; then
  sudo systemctl enable --now fintracker-bot
  echo "OK: fintracker-bot started"
else
  echo "WARN: systemd fintracker-bot belum dipasang — jalankan deploy/vps-install.sh sekali"
fi
