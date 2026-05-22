#!/usr/bin/env bash
# Sinkron repo dari GitHub — buang perubahan lokal pada file yang di-track.
# AMAN: .env.local, secrets/, data/, .venv tidak dihapus (gitignore / untracked).
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
BRANCH="${DEPLOY_BRANCH:-main}"

if [[ ! -d .git ]]; then
  echo "ERROR: bukan git repo: $APP_DIR" >&2
  exit 1
fi

echo "==> git fetch origin $BRANCH"
git fetch origin "$BRANCH"
echo "==> git reset --hard origin/$BRANCH"
git reset --hard "origin/$BRANCH"
echo "OK: repo sync (file secret lokal tetap)"
