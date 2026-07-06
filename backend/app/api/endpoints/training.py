from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
import logging
from typing import Optional, List, Dict, Any
from backend.app.core.database import get_db, get_peraturan_db
from backend.app.services.training.job_manager import job_manager

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
        # 1. Fetch source documents from MySQL
        mysql_docs = []
        async with get_peraturan_db() as conn_mysql:
            async with conn_mysql.cursor() as cur:
                # We fetch a subset or everything (e.g., top 100 for now, ordered by date)
                await cur.execute("""
                    SELECT id_berita, judul, noper, tanggal, gambar, id_kategori
                    FROM berita
                    ORDER BY id_berita DESC
                    LIMIT 200
                """)
                columns = [col[0] for col in cur.description]
                rows = await cur.fetchall()
                for row in rows:
                    mysql_docs.append(dict(zip(columns, row)))

        # 2. Cross-check with PostgreSQL to see which are already embedded
        embedded_ids = set()
        async with get_db() as conn_pg:
            # We assume dokumen.id maps to berita.id_berita
            pg_rows = await conn_pg.fetch("SELECT id FROM dokumen")
            embedded_ids = {row['id'] for row in pg_rows}

        # 3. Assemble response
        result = []
        for doc in mysql_docs:
            doc_id = doc['id_berita']
            result.append({
                "id": doc_id,
                "judul": doc['judul'],
                "noper": doc['noper'],
                "tanggal": doc['tanggal'].isoformat() if doc['tanggal'] else None,
                "kategori_id": doc['id_kategori'],
                "file_name": doc['gambar'],
                "is_embedded": doc_id in embedded_ids
            })

        return {"status": "success", "data": result}

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
        async with get_db() as conn:
            rows = await conn.fetch("""
                SELECT job_id, dokumen_id, tipe_training, status, progress, logs, updated_at
                FROM training_jobs
                ORDER BY updated_at DESC
                LIMIT 50
            """)
            
            return {
                "status": "success",
                "data": [dict(r) for r in rows]
            }
    except Exception as e:
        logger.error(f"Failed to fetch job statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))
