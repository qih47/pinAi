#!/usr/bin/env bash
# ============================================================
# CAKRA AI - Frontend Launcher (Chat + Analytics)
# ============================================================
set -uo pipefail
cd "$(dirname "$0")"

echo "🧹 Membersihkan proses Chat Vite (port 5173)..."
# Matikan hanya frontend chat (5173)
fuser -k -9 5173/tcp 2>/dev/null || true

echo "🚀 Starting Chat Frontend (5173)..."
npm run dev:chat -- --host --force &
CHAT_PID=$!

ANALYTICS_PID=""
if ! fuser 5174/tcp >/dev/null 2>&1; then
    echo "🚀 Starting Analytics Frontend (5174)..."
    npm run dev:analytics -- --host --force &
    ANALYTICS_PID=$!
else
    echo "⚡ Analytics Frontend (5174) is already active, preserving running instance."
fi

# Pastikan proses chat ikut mati kalau script ini di-kill
trap "echo '🛑 Stopping frontends...'; kill $CHAT_PID $ANALYTICS_PID 2>/dev/null" EXIT INT TERM

if [ -n "$ANALYTICS_PID" ]; then
    wait $CHAT_PID $ANALYTICS_PID
else
    wait $CHAT_PID
fi