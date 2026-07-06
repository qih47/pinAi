import asyncio
import logging
from typing import Optional
from datetime import datetime
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_JOB_MANAGER")

class TrainingJobManager:
    """
    Manages the lifecycle of asynchronous training jobs.
    In the future, this can be swapped out with Celery or a Redis Queue.
    """
    def __init__(self):
        pass

    async def submit_job(self, dokumen_id: int, tipe_training: str) -> str:
        """
        Submits a new job to the database queue.
        """
        async with get_db() as conn:
            job_id = await conn.fetchval("""
                INSERT INTO training_jobs (dokumen_id, tipe_training, status, progress, logs)
                VALUES ($1, $2, 'PENDING', 0, 'Job submitted to queue.')
                RETURNING job_id
            """, dokumen_id, tipe_training)
            
            logger.info(f"🚀 [JOB_MANAGER] Job {job_id} submitted for Dokumen {dokumen_id} via {tipe_training}")
            return str(job_id)

    async def update_job_progress(self, job_id: str, status: str, progress: int, log_message: str):
        """
        Updates the progress and status of a running job.
        """
        async with get_db() as conn:
            await conn.execute("""
                UPDATE training_jobs 
                SET status = $1, progress = $2, logs = CONCAT(logs, '\n[', NOW()::text, '] ', $3::text), updated_at = NOW()
                WHERE job_id = $4::uuid
            """, status, progress, log_message, job_id)
            logger.debug(f"[JOB_MANAGER] Job {job_id}: {progress}% - {log_message}")

    async def run_job_background(self, job_id: str, dokumen_id: int, tipe_training: str):
        """
        The background worker that routes the job to the correct pipeline.
        This runs asynchronously outside the request lifecycle.
        """
        try:
            await self.update_job_progress(job_id, "RUNNING", 5, "Initializing ingestion pipeline...")
            
            from backend.app.services.training.ingestion_pipelines import (
                run_standard_embedding_pipeline,
                run_synthetic_qa_pipeline,
                run_graph_rag_pipeline,
                run_vision_rag_pipeline
            )
            
            if tipe_training == "STANDARD":
                await run_standard_embedding_pipeline(job_id, dokumen_id, self)
            elif tipe_training == "SYNTHETIC_QA":
                await run_synthetic_qa_pipeline(job_id, dokumen_id, self)
            elif tipe_training == "GRAPH_RAG":
                await run_graph_rag_pipeline(job_id, dokumen_id, self)
            elif tipe_training == "VISION_RAG":
                await run_vision_rag_pipeline(job_id, dokumen_id, self)
            else:
                raise ValueError(f"Unknown training type: {tipe_training}")

            await self.update_job_progress(job_id, "DONE", 100, "Pipeline completed successfully.")
            logger.info(f"✅ [JOB_MANAGER] Job {job_id} completed.")
            
        except Exception as e:
            logger.error(f"❌ [JOB_MANAGER] Job {job_id} failed: {str(e)}")
            await self.update_job_progress(job_id, "FAILED", 0, f"Error: {str(e)}")

job_manager = TrainingJobManager()
