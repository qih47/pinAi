#!/usr/bin/env bash
# =============================================================================
#   🚀 CAKRA AI - Quick Monitoring Launcher
# =============================================================================
# Jalankan script ini kapan saja dengan: ./monitor.sh
# Atau: ./monitor.sh --chat (khusus Chat Service Call 1 & 2)
# Atau: ./monitor.sh --status (cek kesehatan port & PID)

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f "./rag_env/bin/python" ]; then
    ./rag_env/bin/python monitor_services.py "$@"
else
    python3 monitor_services.py "$@"
fi
