#!/usr/bin/env bash
# ==============================================================================
# CAKRA AI — Setup Cronjob Otomatis untuk Nightly Training
# ==============================================================================
# Menjadwalkan eksekusi otomatis setiap hari pukul 18:00 WIB s/d 07:30/08:00 WIB.
# ==============================================================================

set -e

mkdir -p /home/qisthi/pinAi/backend/storage/logs

CRON_LINE="0 18 * * * /home/qisthi/pinAi/rag_env/bin/python /home/qisthi/pinAi/backend/scripts/run_nightly_training.py >> /home/qisthi/pinAi/backend/storage/logs/nightly_training.log 2>&1"

# Cek & pasang ke crontab user aktif tanpa duplikasi
(crontab -l 2>/dev/null | grep -v "run_nightly_training.py" || true; echo "$CRON_LINE") | crontab -

echo "================================================================="
echo "✅ Cronjob Berhasil Didaftarkan ke Sistem!"
echo "Jadwal: Setiap hari tepat pukul 18:00 WIB"
echo "Log: /home/qisthi/pinAi/backend/storage/logs/nightly_training.log"
echo "================================================================="
crontab -l | grep "run_nightly_training.py"
