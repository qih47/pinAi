#!/usr/bin/env bash
# ============================================================
# CAKRA AI - Frontend Launcher (Chat + Analytics)
# ============================================================
set -uo pipefail
cd "$(dirname "$0")"

echo "🧹 Membersihkan proses Vite lama & cache..."
# Matikan semua proses vite yang mungkin masih nyangkut
pkill -9 -f "vite" 2>/dev/null || true

# Bersihkan port yang biasa dipakai frontend (5173-5176)
fuser -k -9 5173/tcp 5174/tcp 5175/tcp 5176/tcp 2>/dev/null || true

echo "🚀 Starting Chat Frontend (5173)..."
npm run dev:chat -- --host --force &
CHAT_PID=$!

echo "🚀 Starting Analytics Frontend (5174)..."
npm run dev:analytics -- --host --force &
ANALYTICS_PID=$!

# Pastikan kedua proses ikut mati kalau script ini di-kill (SIGTERM/SIGINT)
trap "echo '🛑 Stopping frontends...'; kill $CHAT_PID $ANALYTICS_PID 2>/dev/null" EXIT INT TERM

wait $CHAT_PID $ANALYTICS_PID