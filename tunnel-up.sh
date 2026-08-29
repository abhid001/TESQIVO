#!/usr/bin/env bash
# Start a Cloudflare quick tunnel to the local TESQIVO stack and point
# TESQIVO_PUBLIC_URL at it. Re-run after a reboot or if the tunnel drops.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .tunnel
PORT=$(grep -E '^TESQIVO_HTTP_PORT=' .env | cut -d= -f2)
PORT=${PORT:-8080}
pkill -f 'cloudflared tunnel --url' 2>/dev/null || true
sleep 1
nohup cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate > .tunnel/cloudflared.log 2>&1 &
echo $! > .tunnel/pid
for i in $(seq 1 20); do
  URL=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' .tunnel/cloudflared.log | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
[ -z "${URL:-}" ] && { echo "tunnel did not come up; see .tunnel/cloudflared.log"; exit 1; }
sed -i '' "s#^TESQIVO_PUBLIC_URL=.*#TESQIVO_PUBLIC_URL=${URL}#" .env
docker compose up -d >/dev/null
echo "$URL" > .tunnel/url
echo "TESQIVO is live at: $URL"
