#!/usr/bin/env bash
pkill -f 'cloudflared tunnel --url' 2>/dev/null && echo "tunnel stopped" || echo "no tunnel running"
