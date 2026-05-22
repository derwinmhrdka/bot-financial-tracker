#!/usr/bin/env bash
# Pasang skill + template Hermes (Linux / VPS)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

if [[ ! -d "$HERMES_HOME" ]]; then
  echo "Hermes belum terpasang. Jalankan: hermes setup"
  exit 1
fi

echo "Hermes home: $HERMES_HOME"
echo "Repo: $REPO"

mkdir -p "$HERMES_HOME/skills"
rm -rf "$HERMES_HOME/skills/financial-tracker"
cp -r "$REPO/skills/financial-tracker" "$HERMES_HOME/skills/"

cp "$REPO/deploy/AGENTS.md" "$HERMES_HOME/AGENTS.md"
cp "$REPO/deploy/SOUL.md" "$HERMES_HOME/SOUL.md"

# gateway.json minimal
cat > "$HERMES_HOME/gateway.json" <<'EOF'
{"platforms":{"telegram":{"enabled":true}}}
EOF

if command -v python3 >/dev/null 2>&1; then
  python3 "$REPO/deploy/patch_hermes_config.py" "$REPO"
else
  echo "WARN: python3 tidak ada — set manual tool_progress=off dan disabled_toolsets: [skills]"
fi

echo ""
echo "Selesai. Langkah manual:"
echo "  1. cp deploy/env.local.example .env.local && edit"
echo "  2. export vars dari .env.local atau sync ke $HERMES_HOME/.env"
echo "  3. hermes gateway (atau scripts/start-gateway.ps1 di Windows)"
