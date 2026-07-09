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
