#!/usr/bin/env python3
"""
CAKRA AI — Master Nightly Training & Fine-Tuning CLI Runner
===========================================================
Skrip eksekusi mandiri (standalone) yang dapat dijalankan langsung atau via crontab.
TIDAK mengganggu atau mengubah alur kerja chat/inference yang sedang berjalan (Call 1 & Call 2).
HANYA menggunakan PostgreSQL (ragdb) di localhost.

Usage:
    # 1. Jalankan training malam (otomatis mengikuti jadwal 18:00 - 07:30):
    python backend/scripts/run_nightly_training.py

    # 2. Uji coba / Force run sekarang (tanpa menunggu jam 18:00):
    python backend/scripts/run_nightly_training.py --force-now

    # 3. Test 1 dokumen tertentu sebanyak 2 halaman pertama saja:
    python backend/scripts/run_nightly_training.py --force-now --doc-id 1 --limit-pages 2

    # 4. Batasi maksimal 5 dokumen:
    python backend/scripts/run_nightly_training.py --force-now --max-docs 5
"""

import sys
import os
import argparse
import asyncio
import logging
import fcntl

# Pastikan path root masuk ke sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.services.training.nightly.orchestrator import NightlyTrainingOrchestrator
from backend.app.services.training.nightly.db_setup import close_ragdb_pool

LOCK_FILE = os.path.join(BASE_DIR, "backend/storage/locks/nightly_training.lock")

# Setup logging terminal yang rapi
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("CAKRA_NIGHTLY_RUNNER")

def acquire_process_lock():
    """Memastikan hanya 1 instance run_nightly_training yang berjalan pada satu waktu."""
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(f"{os.getpid()}\n")
        lock_fd.flush()
        return lock_fd
    except (BlockingIOError, IOError):
        logger.info("🔒 [INSTANCE_LOCK] Sesi training lain sedang aktif berjalan. Instance ini keluar dengan aman untuk mencegah bentrok/duplikasi.")
        return None

def parse_args():
    parser = argparse.ArgumentParser(description="CAKRA AI Nightly Training & Fine-Tuning Engine")
    parser.add_argument("--force-now", action="store_true", help="Paksa jalan sekarang (lewati validasi jam 18:00)")
    parser.add_argument("--doc-id", type=int, default=None, help="Proses ID dokumen tertentu saja")
    parser.add_argument("--max-docs", type=int, default=None, help="Batas maksimal dokumen yang diproses")
    parser.add_argument("--limit-pages", type=int, default=None, help="Batas maksimal halaman per dokumen (untuk testing)")
    parser.add_argument("--model", type=str, default="gemma4:31b", help="Model LLM Ollama yang digunakan (default: gemma4:31b)")
    return parser.parse_args()

async def main():
    args = parse_args()

    # 1. Pastikan single instance dengan process lock file
    lock_fd = acquire_process_lock()
    if not lock_fd:
        return

    orchestrator = NightlyTrainingOrchestrator(
        model_name=args.model
    )

    # 2. Cek apakah berada dalam jendela waktu jika bukan force-now
    if not args.force_now and not orchestrator.is_within_training_window():
        logger.info("⏰ [OUTSIDE_WINDOW] Saat ini di luar jadwal training (Hari Kerja 18:00 - 07:30 WIB / Weekend Marathon Jumat 18:00 s.d. Senin 08:00 WIB). Standby.")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass
        return

    try:
        await orchestrator.run_nightly_loop(
            force_run=args.force_now,
            max_docs=args.max_docs,
            page_limit=args.limit_pages,
            specific_doc_id=args.doc_id
        )
    except KeyboardInterrupt:
        logger.warning("\n🛑 [INTERRUPTED] Sinyal Ctrl+C diterima. Menghentikan proses secara aman...")
    except Exception as e:
        logger.error(f"❌ [CRITICAL_ERROR] Eksekusi terhenti: {e}", exc_info=True)
    finally:
        await close_ragdb_pool()
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass
        logger.info("👋 [EXIT] Resource DB, Lock, & koneksi bersih.")

if __name__ == "__main__":
    asyncio.run(main())
