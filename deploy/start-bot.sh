#!/usr/bin/env bash
# Dipanggil systemd — muat .env.local lalu jalankan bot Telegram.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

if [[ ! -f .env.local ]]; then
  echo "Missing $APP_DIR/.env.local — buat manual di VPS (lihat deploy/DEPLOY.md)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env.local
set +a

exec "$APP_DIR/.venv/bin/python" -m tracker.telegram_bot
