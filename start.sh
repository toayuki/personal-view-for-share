#!/bin/bash
cd "$(dirname "$0")"

caffeinate -i &
CAFFEINATE_PID=$!

cloudflared tunnel --config ~/.cloudflared/config.yml run my-tunnel &
TUNNEL_PID=$!

(cd api && source venv/bin/activate && uvicorn src.main:app --reload --host 192.168.0.7 --port 8000) &
API_PID=$!

(cd web && source ../venv/bin/activate && uvicorn src.main:app --reload --host 192.168.0.7 --port 3000) &
WEB_PID=$!

trap "kill $CAFFEINATE_PID $TUNNEL_PID $API_PID $WEB_PID 2>/dev/null" EXIT INT TERM
wait $API_PID $WEB_PID
