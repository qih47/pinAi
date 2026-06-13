"""
CAKRA AI — Background Task Scheduler
====================================
Tugas berkala: Memory consolidation nightly, cleanup sesi expired, dll.
Menggunakan APScheduler untuk scheduling yang reliable.
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.services.memory_service import memory_service

logger = logging.getLogger("CAKRA_BACKGROUND_TASKS")

scheduler: AsyncIOScheduler = None


async def start_background_scheduler(app):
    """
    Inisialisasi dan jalankan scheduler background tasks saat startup FastAPI.
    """
    global scheduler
    
    try:
        scheduler = AsyncIOScheduler()
        
        # Job 1: Konsolidasi Memori Pegawai (Setiap hari jam 02:00 WIB)
        # WIB adalah UTC+7, jadi jam 02:00 WIB = 19:00 UTC hari sebelumnya
        scheduler.add_job(
            _run_nightly_memory_consolidation,
            CronTrigger(hour=19, minute=0, second=0, timezone="UTC"),
            id="memory_consolidation",
            name="Nightly Memory Consolidation (02:00 WIB)",
            replace_existing=True,
            coalesce=True,
        )
        
        # Job 2: Pembersihan Token Sesi Expired (Setiap 30 menit)
        from backend.app.utils.token_expiry import cleanup_expired_sessions
        scheduler.add_job(
            cleanup_expired_sessions,
            CronTrigger(minute="*/30"),
            id="session_cleanup",
            name="Session Token Expiry Cleanup (30m)",
            replace_existing=True,
            coalesce=True,
        )
        
        # Mulai scheduler
        scheduler.start()
        logger.info("✅ [SCHEDULER] Background task scheduler berhasil dimulai.")
        logger.info("📅 [SCHEDULER] Job terjadwal: Memory Consolidation daily @ 02:00 WIB, Session Cleanup every 30m")
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Gagal memulai background scheduler: {e}")
        raise e


async def stop_background_scheduler():
    """
    Hentikan scheduler saat FastAPI shutdown.
    """
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("🛑 [SCHEDULER] Background scheduler dihentikan dengan aman.")


async def _run_nightly_memory_consolidation():
    """
    Task wrapper untuk konsolidasi memori malam hari.
    Dipanggil secara otomatis oleh APScheduler sesuai jadwal.
    """
    logger.info("🌙 [NIGHTLY JOB] Memulai siklus konsolidasi memori pegawai...")
    try:
        result = await memory_service.consolidate_nightly_memory()
        
        if result.get("status") == "success":
            logger.info(
                f"✅ [NIGHTLY JOB] Konsolidasi memori berhasil! "
                f"({result.get('employees_processed')} pegawai diproses, "
                f"{result.get('memories_saved')} memori tersimpan)"
            )
        elif result.get("status") == "skipped":
            logger.info(f"⏭️  [NIGHTLY JOB] Konsolidasi dilewati: {result.get('message')}")
        else:
            logger.warning(f"⚠️  [NIGHTLY JOB] Konsolidasi gagal: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"💥 [NIGHTLY JOB] Eksekusi konsolidasi memori error: {e}", exc_info=True)


# ============================================================================
# ENDPOINT ADMIN: Manual Trigger Memory Consolidation
# ============================================================================

async def trigger_manual_memory_consolidation():
    """
    Endpoint untuk trigger manual konsolidasi memori (untuk admin testing/maintenance).
    Bisa dipanggil via: POST /api/admin/run-memory-consolidation
    """
    logger.info("🔧 [MANUAL TRIGGER] Admin memicu konsolidasi memori manual...")
    try:
        result = await memory_service.consolidate_nightly_memory()
        logger.info(f"✅ [MANUAL TRIGGER] Konsolidasi selesai: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ [MANUAL TRIGGER] Konsolidasi manual error: {e}", exc_info=True)
        raise e
