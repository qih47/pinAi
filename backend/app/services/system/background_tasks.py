import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.services.memory.memory_service import memory_service

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
        
        # Job 3: Auditor Knowledge Decay (Setiap Senin Jam 03:00 WIB)
        from backend.app.services.pipeline.background_auditor import scan_knowledge_decay
        scheduler.add_job(
            scan_knowledge_decay,
            CronTrigger(day_of_week="sun", hour=20, minute=0, second=0, timezone="UTC"), # Sunday 20:00 UTC = Monday 03:00 WIB
            id="knowledge_decay_auditor",
            name="Weekly Knowledge Decay Audit (03:00 WIB)",
            replace_existing=True,
            coalesce=True,
        )
        
        # Mulai scheduler
        scheduler.start()
        logger.info("[SCHEDULER_INIT_SUCCESS] Background task scheduler started successfully.")
        logger.info("[SCHEDULER_JOBS_SCHEDULED] Jobs scheduled: Memory Consolidation daily @ 02:00 WIB, Session Cleanup every 30m, Decay Auditor weekly @ 03:00 WIB.")
        
    except Exception as e:
        logger.error(f"[SCHEDULER_INIT_ERROR] Failed to start background scheduler: {e}")
        raise e


async def stop_background_scheduler():
    """
    Hentikan scheduler saat FastAPI shutdown.
    """
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("[SCHEDULER_SHUTDOWN_SUCCESS] Background scheduler stopped successfully.")


async def _run_nightly_memory_consolidation():
    """
    Task wrapper untuk konsolidasi memori malam hari.
    Dipanggil secara otomatis oleh APScheduler sesuai jadwal.
    """
    logger.info("[NIGHTLY_JOB_START] Starting memory consolidation cycle.")
    try:
        result = await memory_service.consolidate_nightly_memory()
        
        if result.get("status") == "success":
            logger.info(f"[NIGHTLY_JOB_SUCCESS] Memory consolidation completed successfully: {result}")
        elif result.get("status") == "skipped":
            logger.info(f"[NIGHTLY_JOB_SKIPPED] Consolidation skipped: {result.get('message')}")
        else:
            logger.warning(f"[NIGHTLY_JOB_FAILED] Consolidation failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"[NIGHTLY_JOB_ERROR] Consolidation error: {e}", exc_info=True)


# ============================================================================
# ENDPOINT ADMIN: Manual Trigger Memory Consolidation
# ============================================================================

async def trigger_manual_memory_consolidation():
    """
    Endpoint untuk trigger manual konsolidasi memori (untuk admin testing/maintenance).
    Bisa dipanggil via: POST /api/admin/run-memory-consolidation
    """
    logger.info("[MANUAL_TRIGGER_START] Admin triggered manual memory consolidation.")
    try:
        result = await memory_service.consolidate_nightly_memory()
        logger.info(f"[MANUAL_TRIGGER_SUCCESS] Consolidation completed successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"[MANUAL_TRIGGER_ERROR] Manual consolidation error: {e}", exc_info=True)
        raise e
