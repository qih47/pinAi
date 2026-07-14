from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
import logging

from backend.app.services.training.synthetic_service import synthetic_training_service
from backend.app.services.training.job_manager import job_manager

router = APIRouter()
logger = logging.getLogger("CAKRA_SYNTHETIC_API")

class SyntheticSubmitRequest(BaseModel):
    dokumen_id: int

@router.get("/source-docs")
async def get_source_docs():
    """
    Fetches documents from qa_peraturan_db (berita) and cross-checks with rag_document_questions.
    """
    try:
        docs = await synthetic_training_service.get_source_docs()
        return {"status": "success", "data": docs}
    except Exception as e:
        logger.error(f"Failed to fetch synthetic source docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit")
async def submit_synthetic_job(
    request: Request,
    body: SyntheticSubmitRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a single document for synthetic training.
    """
    try:
        job_id = await job_manager.submit_job(body.dokumen_id, "SYNTHETIC_QA")
        
        background_tasks.add_task(
            synthetic_training_service.run_synthetic_pipeline, 
            job_id, 
            body.dokumen_id,
            request
        )

        return {
            "status": "success", 
            "message": "Synthetic job submitted successfully", 
            "job_id": job_id
        }
    except Exception as e:
        logger.error(f"Failed to submit synthetic job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit-batch")
async def submit_batch_synthetic_job(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Submits a SINGLE background job to process ALL unenrolled documents for synthetic Q&A training.
    """
    try:
        # We use 0 as a special ID for batch jobs
        job_id = await job_manager.submit_job(0, "SYNTHETIC_BATCH")
        
        background_tasks.add_task(
            synthetic_training_service.run_batch_synthetic_pipeline, 
            job_id,
            request
        )
                
        return {
            "status": "success", 
            "message": "Successfully submitted a batch job for ALL missing documents.",
            "job_id": job_id
        }
    except Exception as e:
        logger.error(f"Failed to submit batch synthetic jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
