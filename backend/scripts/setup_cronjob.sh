#!/usr/bin/env bash
# ==============================================================================
# CAKRA AI — Setup Cronjob Otomatis untuk Nightly & Weekend Marathon Training
# ==============================================================================
# Jadwal:
# 1. Hari Kerja (Senin - Kamis malam): 18:00 WIB s/d 07:30/08:00 WIB
# 2. Weekend Marathon: Mulai Jumat 18:00 WIB s/d Senin 08:00 WIB Non-Stop (Sabtu & Minggu 24 jam)
# ==============================================================================

set -e

mkdir -p /home/qisthi/pinAi/backend/storage/logs
mkdir -p /home/qisthi/pinAi/backend/storage/locks

PYTHON_BIN="/home/qisthi/pinAi/rag_env/bin/python"
SCRIPT_PATH="/home/qisthi/pinAi/backend/scripts/run_nightly_training.py"
LOG_PATH="/home/qisthi/pinAi/backend/storage/logs/nightly_training.log"

# Cron entries:
# - 0 18 * * *     : Trigger harian pukul 18:00 WIB (Senin-Minggu)
# - 0 19-23 * * 5  : Watchdog Jumat malam tiap jam (19:00 - 23:00)
# - 0 * * * 6,0    : Watchdog Sabtu & Minggu 24 jam tiap jam non-stop
# - 0 1-7 * * 1    : Watchdog Senin dini hari tiap jam (01:00 - 07:00) sebelum jam 08:00

CRON_CONTENT="# CAKRA AI NIGHTLY & WEEKEND MARATHON TRAINING
0 18 * * * $PYTHON_BIN $SCRIPT_PATH >> $LOG_PATH 2>&1
0 19-23 * * 5 $PYTHON_BIN $SCRIPT_PATH >> $LOG_PATH 2>&1
0 * * * 6,0 $PYTHON_BIN $SCRIPT_PATH >> $LOG_PATH 2>&1
0 1-7 * * 1 $PYTHON_BIN $SCRIPT_PATH >> $LOG_PATH 2>&1"

# Bersihkan entri lama run_nightly_training.py dan pasang konfigurasi baru
(crontab -l 2>/dev/null | grep -v "run_nightly_training.py" | grep -v "CAKRA AI NIGHTLY & WEEKEND MARATHON TRAINING" || true; echo "$CRON_CONTENT") | crontab -

echo "================================================================="
echo "✅ Cronjob Nightly & Weekend Marathon Berhasil Didaftarkan!"
echo "Jadwal:"
echo "  - Hari Kerja: 18:00 - 07:30 WIB (Toleransi Hard Stop 08:00 WIB)"
echo "  - Weekend Marathon: Jumat 18:00 WIB s/d Senin 08:00 WIB Non-Stop (Sabtu & Minggu 24 Jam)"
echo "Log: $LOG_PATH"
echo "================================================================="
crontab -l | grep "run_nightly_training.py"
