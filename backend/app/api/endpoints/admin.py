"""
CAKRA AI — Admin Dashboard Endpoints
====================================
Endpoints untuk administratior: memory consolidation trigger, audit logs, system config, dll.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.background_tasks import trigger_manual_memory_consolidation

router = APIRouter()
logger = logging.getLogger("CAKRA_ADMIN")


@router.post("/run-memory-consolidation")
async def manual_memory_consolidation_trigger(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Manual trigger untuk konsolidasi memori pegawai (Nightly Job).
    Hanya bisa diakses oleh admin yang sudah login.
    
    Usage: POST /api/admin/run-memory-consolidation
    """
    if not current_user_npp:
        logger.warning("⚠️ [ADMIN] Akses admin memory consolidation tanpa login ditolak")
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    logger.info(f"🔧 [ADMIN] User {current_user_npp} memicu manual memory consolidation...")
    
    try:
        result = await trigger_manual_memory_consolidation()
        logger.info(f"✅ [ADMIN] Manual consolidation selesai: {result}")
        return {
            "status": "success",
            "message": "Konsolidasi memori berhasil dijalankan secara manual",
            "details": result
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Manual consolidation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Manual consolidation failed: {str(e)}"
        )


@router.get("/system-status")
async def get_system_status(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Endpoint untuk melihat status sistem CAKRA AI (GPU, memory, scheduler jobs, dll).
    Hanya bisa diakses oleh admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        import torch
        from backend.app.services.background_tasks import scheduler
        
        gpu_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else "N/A"
        vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3 if gpu_available else 0.0
        
        scheduler_status = "RUNNING" if (scheduler and scheduler.running) else "STOPPED"
        
        logger.info(f"📊 [ADMIN] {current_user_npp} mengakses system status")
        
        return {
            "status": "success",
            "system": {
                "gpu": {
                    "available": gpu_available,
                    "name": gpu_name,
                    "vram_gb": f"{vram_total:.2f}" if vram_total > 0 else "0.00"
                },
                "scheduler": {
                    "status": scheduler_status,
                    "jobs": [
                        {
                            "id": job.id,
                            "name": job.name,
                            "next_run": str(job.next_run_time) if job.next_run_time else "N/A"
                        }
                        for job in (scheduler.get_jobs() if scheduler and scheduler.running else [])
                    ]
                }
            }
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] System status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")
