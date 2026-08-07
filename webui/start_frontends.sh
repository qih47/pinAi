#!/bin/bash
cd /home/qisthi/pinAi/webui
echo "Starting Chat Frontend (5173)..."
npm run dev:chat -- --host &
CHAT_PID=$!

echo "Starting Analytics Frontend (5174)..."
npm run dev:analytics -- --host &
ANALYTICS_PID=$!

trap "kill $CHAT_PID $ANALYTICS_PID" EXIT
wait $CHAT_PID $ANALYTICS_PID
