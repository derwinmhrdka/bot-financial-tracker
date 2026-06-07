#!/usr/bin/env bash
# Build & restart container — dipanggil setelah git-sync (GitHub Actions atau manual).
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

mkdir -p data secrets

if [[ ! -f .env.local ]]; then
  if [[ -f deploy/env.local.example ]]; then
    cp deploy/env.local.example .env.local
    echo "WARN: .env.local dibuat dari deploy/env.local.example — edit dulu" >&2
  else
    echo "ERROR: .env.local tidak ada di $APP_DIR" >&2
    exit 1
  fi
fi

if ! command -v docker >/dev/null; then
  echo "ERROR: docker tidak terpasang — install Docker di VPS dulu" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin tidak ditemukan" >&2
  exit 1
fi

chmod +x deploy/docker-deploy.sh 2>/dev/null || true

_has_token() {
  grep -qE '^TELEGRAM_BOT_TOKEN=.+[^[:space:]]' .env.local 2>/dev/null
}

docker compose build

if ! _has_token; then
  echo "SKIP docker compose up: isi TELEGRAM_BOT_TOKEN di .env.local lalu: bash deploy/docker-deploy.sh"
  exit 0
fi

docker compose up -d --remove-orphans
echo "OK: fintracker-bot container running"
docker compose ps
