from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import logging

from backend.app.services.training.job_manager import job_manager
from backend.app.services.training.training_service import training_service

router = APIRouter()
logger = logging.getLogger("CAKRA_TRAINING_API")

class TrainingSubmitRequest(BaseModel):
    dokumen_id: int
    tipe_training: str

@router.get("/source-docs")
async def get_source_docs():
    """
    Fetches documents from qa_peraturan_db (berita) and cross-checks with ragdb (dokumen).
    Returns list with is_embedded flag.
    """
    try:
        docs = await training_service.get_source_docs()
        return {"status": "success", "data": docs}
    except Exception as e:
        logger.error(f"Failed to fetch source docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit")
async def submit_training_job(
    request: TrainingSubmitRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a document for training (ingestion). 
    Fires off a background task so the API returns immediately.
    """
    try:
        # Submit to queue (DB)
        job_id = await job_manager.submit_job(request.dokumen_id, request.tipe_training)
        
        # Trigger background execution
        background_tasks.add_task(
            job_manager.run_job_background, 
            job_id, 
            request.dokumen_id, 
            request.tipe_training
        )

        return {
            "status": "success", 
            "message": "Job submitted successfully", 
            "job_id": job_id
        }
    except Exception as e:
        logger.error(f"Failed to submit training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_active_jobs():
    """
    Fetches all currently running or recently finished jobs.
    """
    try:
        jobs = await job_manager.get_active_jobs()
        return {
            "status": "success",
            "data": jobs
        }
    except Exception as e:
        logger.error(f"Failed to fetch job statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── NIGHTLY 5-WORKER TRAINING ENDPOINTS (RAGDB ONLY) ────────────────────────
from backend.app.services.training.nightly.orchestrator import (
    trigger_nightly_training,
    stop_nightly_training,
    get_nightly_dashboard_status,
    get_live_monitor_data
)

@router.get("/nightly/live-monitor")
async def get_nightly_live_monitor():
    """Mengambil payload data realtime bentangan 2 halaman, status worker, log terminal, dan training artifacts"""
    try:
        data = await get_live_monitor_data()
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Failed to fetch live monitor data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nightly/status")
async def get_nightly_status():
    """Mengambil status live eksekusi training malam & ringkasan statistik ragdb"""
    try:
        data = await get_nightly_dashboard_status()
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Failed to fetch nightly status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from typing import Optional

class NightlyTriggerRequest(BaseModel):
    max_docs: Optional[int] = None
    page_limit: Optional[int] = None
    doc_id: Optional[int] = None

@router.post("/nightly/start")
async def start_nightly_manual(req: NightlyTriggerRequest = None):
    """Memicu training malam secara manual dari tombol Dashboard Analytics"""
    try:
        max_docs = req.max_docs if req else None
        page_limit = req.page_limit if req else None
        doc_id = req.doc_id if req else None
        res = await trigger_nightly_training(
            force_now=True,
            max_docs=max_docs,
            page_limit=page_limit,
            specific_doc_id=doc_id
        )
        return res
    except Exception as e:
        logger.error(f"Failed to trigger nightly training: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/nightly/stop")
async def stop_nightly_manual():
    """Menghentikan training malam dengan aman & simpan checkpoint ke ragdb"""
    try:
        res = await stop_nightly_training()
        return res
    except Exception as e:
        logger.error(f"Failed to stop nightly training: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from backend.app.services.training.nightly.peraturan_sync import PeraturanLineageSyncService
from backend.app.services.training.nightly.checkpoint_manager import CheckpointManager

@router.post("/nightly/sync-catalog")
async def sync_peraturan_catalog():
    """Sinkronisasi katalog dan silsilah hukum dari MySQL berita ke ragdb (100% Read-Only ke MySQL)"""
    try:
        res = await PeraturanLineageSyncService.sync_catalog_and_lineage()
        return {"status": "success", "data": res}
    except Exception as e:
        logger.error(f"Failed to sync catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nightly/stats")
async def get_nightly_stats():
    """Mengambil rincian statistik Tier 1 (Berlaku Aktif) vs Tier 2 (Dicabut/Usang)"""
    try:
        stats = await CheckpointManager.get_training_statistics()
        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Failed to fetch training statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nightly/reset")
async def reset_nightly_training_from_zero(clean_artifacts: bool = True):
    """
    Mereset seluruh progres training ke titik awal (Dokumen 1, Halaman 1):
    1. Menghentikan orchestrator jika sedang berjalan
    2. Mereset checkpoint status 2.245 dokumen ke PENDING (last_completed_page = 0)
    3. Mengosongkan & mengarsipkan dataset JSONL Call 1 Router e4b dan Call 2 Core
    4. Membersihkan chunks testing di ragdb
    """
    try:
        await stop_nightly_training()
        res = await CheckpointManager.reset_all_training_checkpoints(clean_artifacts=clean_artifacts)
        return res
    except Exception as e:
        logger.error(f"Failed to reset nightly training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


