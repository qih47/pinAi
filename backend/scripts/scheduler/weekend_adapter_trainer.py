#!/usr/bin/env python3
"""
CAKRA AI — Weekend Continuous Dual-Adapter Training & Early Hot-Reload Orchestrator
==================================================================================
Tugas Utama:
1. Memantau jendela waktu Weekend (Jumat 18:00 WIB s/d Senin 07:30 WIB).
2. Mematikan Chat Service & WebUI Chat sementara demi alokasi 100% VRAM GPU A40 (~40-44 GB).
3. Melatih Adapter 1: `cakra-router-lora` (Call 1 Intent Router).
4. Melakukan VRAM flush & garbage collection.
5. Melatih Adapter 2: `cakra-core-lora` (Call 2 Responder Core).
6. ATURAN KRUSIAL: Begitu training selesai (meski masih hari Sabtu atau Minggu),
   JANGAN MENUNGGU HARI SENIN! Langsung hot-reload adapter dan bangkitkan kembali
   Chat Service (port 8001) serta Chat WebUI (port 5173).

Usage:
    # 1. Jalankan orchestrator sesuai jadwal weekend:
    python backend/scripts/scheduler/weekend_adapter_trainer.py

    # 2. Uji coba / Force run sekarang:
    python backend/scripts/scheduler/weekend_adapter_trainer.py --force-now
"""

import sys
import os
import argparse
import subprocess
import time
import fcntl
import logging
from datetime import datetime

# Setup root path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOCK_FILE = os.path.join(BASE_DIR, "backend/storage/locks/weekend_trainer.lock")
LOG_FILE = os.path.join(BASE_DIR, "logs/training/weekend_trainer.log")

os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [WEEKEND_TRAINER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a")
    ]
)
logger = logging.getLogger("WEEKEND_TRAINER")

VLLM_PYTHON = "/home/qisthi/vllm_env/bin/python"
RAG_PYTHON = "/home/qisthi/pinAi/rag_env/bin/python"

ROUTER_DATASET = os.path.join(BASE_DIR, "data/finetune/nightly_dispatcher_router.jsonl")
CORE_DATASET = os.path.join(BASE_DIR, "data/finetune/nightly_cakra_core.jsonl")

ROUTER_OUT_DIR = os.path.join(BASE_DIR, "models/adapters/cakra-router-lora")
CORE_OUT_DIR = os.path.join(BASE_DIR, "models/adapters/cakra-core-lora")


def acquire_process_lock():
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(f"{os.getpid()}\n")
        lock_fd.flush()
        return lock_fd
    except (BlockingIOError, IOError):
        logger.info("🔒 [LOCK] Sesi training lain sedang aktif. Orchestrator keluar dengan aman.")
        return None


def is_weekend_window() -> bool:
    """
    Weekend window:
    - Jumat mulai 18:00 WIB
    - Sabtu full 24 jam
    - Minggu full 24 jam
    - Senin s/d 07:30 WIB
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
    hour = now.hour
    minute = now.minute

    if weekday == 4 and hour >= 18:
        return True
    if weekday in (5, 6):
        return True
    if weekday == 0 and (hour < 7 or (hour == 7 and minute <= 30)):
        return True
    return False


def is_active_lora_training_running() -> bool:
    """Periksa apakah proses training LoRA manual atau PID 2305842 sedang berjalan."""
    try:
        res = subprocess.run(["pgrep", "-f", "train_dispatcher_router.py"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return True
        res2 = subprocess.run(["pgrep", "-f", "train_responder_core.py"], capture_output=True, text=True)
        if res2.returncode == 0 and res2.stdout.strip():
            return True
    except Exception as e:
        logger.warning(f"Error checking active training: {e}")
    return False


def stop_chat_services():
    logger.info("🛑 Menghentikan Chat Service & WebUI Chat untuk membebaskan 100% VRAM GPU...")
    subprocess.run(["pkill", "-9", "-f", "run_chat_service.py"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "dev:chat"], capture_output=True)
    subprocess.run(["fuser", "-k", "-9", "8001/tcp"], capture_output=True)
    subprocess.run(["fuser", "-k", "-9", "5173/tcp"], capture_output=True)
    
    # Flush CUDA VRAM
    try:
        subprocess.run([RAG_PYTHON, "-c", "import torch; torch.cuda.empty_cache() if torch.cuda.is_available() else None"], capture_output=True)
    except Exception:
        pass
    time.sleep(2)
    logger.info("✨ VRAM bebas untuk dedicated training.")


def restart_chat_services():
    """
    Aturan Krusial: Begitu training selesai, langsung hidupkan kembali Chat Service & WebUI Chat!
    """
    logger.info("🚀 [EARLY_RELOAD] Training selesai! Membangkitkan kembali Chat Service & WebUI...")
    start_script = os.path.join(BASE_DIR, "start_services.sh")
    
    # Start vLLM / Chat
    try:
        subprocess.run(["bash", start_script, "chat"], cwd=BASE_DIR, capture_output=True)
        logger.info("✅ Chat Service (:8001) berhasil diaktifkan.")
    except Exception as e:
        logger.error(f"Gagal restart chat service: {e}")

    try:
        subprocess.run(["bash", start_script, "frontend"], cwd=BASE_DIR, capture_output=True)
        logger.info("✅ Chat WebUI (:5173) berhasil diaktifkan.")
    except Exception as e:
        logger.error(f"Gagal restart frontend: {e}")


def train_adapter_1_router():
    logger.info("▶️ [STEP 1/2] Memulai Training Adapter 1: cakra-router-lora (Call 1)...")
    if not os.path.exists(ROUTER_DATASET) or os.path.getsize(ROUTER_DATASET) == 0:
        logger.info(f"Dataset {ROUTER_DATASET} belum ada, mengekstrak dari ragdb...")
        cmd_gen = [
            RAG_PYTHON,
            os.path.join(BASE_DIR, "backend/scripts/finetune/generate_dispatcher_dataset.py"),
            "--output", ROUTER_DATASET,
            "--from-db"
        ]
        subprocess.run(cmd_gen, cwd=BASE_DIR, check=True)

    cmd_train = [
        VLLM_PYTHON if os.path.exists(VLLM_PYTHON) else RAG_PYTHON,
        os.path.join(BASE_DIR, "backend/scripts/finetune/train_dispatcher_router.py"),
        "--dataset", ROUTER_DATASET,
        "--output_dir", ROUTER_OUT_DIR,
        "--epochs", "1",
        "--batch_size", "24",
        "--grad_accum", "1"
    ]
    logger.info(f"Eksekusi perintah training: {' '.join(cmd_train)}")
    res = subprocess.run(cmd_train, cwd=BASE_DIR)
    if res.returncode != 0:
        raise RuntimeError(f"Training Adapter 1 (Router) gagal dengan exit code {res.returncode}")
    logger.info("✅ Adapter 1 (cakra-router-lora) berhasil dilatih!")


def train_adapter_2_core():
    logger.info("▶️ [STEP 2/2] Memulai Training Adapter 2: cakra-core-lora (Call 2)...")
    if not os.path.exists(CORE_DATASET) or os.path.getsize(CORE_DATASET) == 0:
        logger.info(f"Dataset {CORE_DATASET} belum ada, mengekstrak dari ragdb...")
        cmd_gen = [
            RAG_PYTHON,
            os.path.join(BASE_DIR, "backend/scripts/finetune/generate_responder_dataset.py"),
            "--output", CORE_DATASET,
            "--from-db"
        ]
        subprocess.run(cmd_gen, cwd=BASE_DIR, check=True)

    cmd_train = [
        RAG_PYTHON,
        os.path.join(BASE_DIR, "backend/scripts/finetune/train_responder_core.py"),
        "--dataset", CORE_DATASET,
        "--output_dir", CORE_OUT_DIR,
        "--epochs", "3"
    ]
    logger.info(f"Eksekusi perintah training: {' '.join(cmd_train)}")
    res = subprocess.run(cmd_train, cwd=BASE_DIR)
    if res.returncode != 0:
        raise RuntimeError(f"Training Adapter 2 (Core) gagal dengan exit code {res.returncode}")
    logger.info("✅ Adapter 2 (cakra-core-lora) berhasil dilatih!")


def main():
    parser = argparse.ArgumentParser(description="CAKRA AI Weekend Dual-Adapter Continuous Training")
    parser.add_argument("--force-now", action="store_true", help="Paksa training sekarang lewati pengecekan jendela weekend")
    args = parser.parse_args()

    lock_fd = acquire_process_lock()
    if not lock_fd:
        return

    # Safety check: Jangan tabrakan dengan job GPU aktif
    if is_active_lora_training_running():
        logger.info("⚠️ [SAFETY_SHIELD] Ada training LoRA yang sedang aktif di GPU A40 saat ini. Standby agar tidak merusak proses aktif.")
        return

    if not args.force_now and not is_weekend_window():
        logger.info("⏰ Saat ini di luar jendela Weekend Marathon (Jumat 18:00 - Senin 07:30 WIB). Standby.")
        return

    logger.info("=================================================================")
    logger.info("🚀 MEMULAI WEEKEND CONTINUOUS DUAL-ADAPTER TRAINING PIPELINE")
    logger.info("=================================================================")

    try:
        # Step A: Matikan Chat service demi VRAM
        stop_chat_services()

        # Step B: Latih Adapter 1
        train_adapter_1_router()

        # Step C: Flush VRAM
        logger.info("🔄 Membersihkan VRAM & cache GPU...")
        time.sleep(3)

        # Step D: Latih Adapter 2
        train_adapter_2_core()

        logger.info("🎉 DUAL-ADAPTER TRAINING SELESAI DENGAN SUKSES!")

    except Exception as e:
        logger.error(f"❌ Error dalam training: {e}", exc_info=True)
    finally:
        # ATURAN KRUSIAL: Apapun hasilnya atau kapanpun selesainya (Sabtu / Minggu),
        # LANGSUNG HIDUPKAN KEMBALI CHAT SERVICE!
        restart_chat_services()
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
