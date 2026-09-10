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

# Pastikan path root masuk ke sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.services.training.nightly.orchestrator import NightlyTrainingOrchestrator
from backend.app.services.training.nightly.db_setup import close_ragdb_pool

# Setup logging terminal yang rapi
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("CAKRA_NIGHTLY_RUNNER")

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

    orchestrator = NightlyTrainingOrchestrator(
        model_name=args.model
    )

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
        logger.info("👋 [EXIT] Resource DB & koneksi bersih.")

if __name__ == "__main__":
    asyncio.run(main())
