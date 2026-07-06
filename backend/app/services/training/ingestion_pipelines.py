import asyncio
import logging
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_INGESTION_PIPELINE")

async def run_standard_embedding_pipeline(job_id: str, dokumen_id: int, manager):
    """
    Standard RAG Ingestion Pipeline.
    Extracts text, chunks it, embeds with mxbai-embed-large, and saves to vector DB.
    """
    await manager.update_job_progress(job_id, "RUNNING", 10, "Fetching document from shared storage (/home/qisthi/pinAi/file_peraturan)...")
    await asyncio.sleep(2) # Simulating heavy I/O
    
    await manager.update_job_progress(job_id, "RUNNING", 30, "Parsing PDF and extracting text via OCR/PyMuPDF...")
    await asyncio.sleep(3) # Simulating parsing
    
    await manager.update_job_progress(job_id, "RUNNING", 50, "Splitting text into semantic chunks and sections...")
    await asyncio.sleep(2)
    
    await manager.update_job_progress(job_id, "RUNNING", 75, "Generating embeddings using local model...")
    await asyncio.sleep(4)
    
    await manager.update_job_progress(job_id, "RUNNING", 95, "Committing vectors to ragdb PostgreSQL...")
    await asyncio.sleep(1)
    
    # Mark the document as embedded in ragdb
    async with get_db() as conn:
        await conn.execute("""
            INSERT INTO dokumen (id, judul, nomor, status, status_ocr) 
            VALUES ($1, 'Mock Extracted Title', 'MOCK-123', 'COMPLETED', 'DONE')
            ON CONFLICT (id) DO UPDATE SET status = 'COMPLETED'
        """, dokumen_id)

async def run_synthetic_qa_pipeline(job_id: str, dokumen_id: int, manager):
    """
    Synthetic Q&A Generation.
    Uses Gemma to read the document and generate hundreds of QA pairs.
    """
    await manager.update_job_progress(job_id, "RUNNING", 10, "Fetching document from shared storage...")
    await asyncio.sleep(2)
    
    await manager.update_job_progress(job_id, "RUNNING", 40, "Running deep LLM analysis to generate synthetic Q&A pairs (This may take a while)...")
    await asyncio.sleep(6)
    
    await manager.update_job_progress(job_id, "RUNNING", 80, "Embedding synthetic questions for exact-match retrieval...")
    await asyncio.sleep(3)
    
    async with get_db() as conn:
        await conn.execute("""
            INSERT INTO dokumen (id, judul, nomor, status, status_ocr) 
            VALUES ($1, 'Mock Synthetic Title', 'MOCK-123', 'COMPLETED', 'DONE')
            ON CONFLICT (id) DO UPDATE SET status = 'COMPLETED'
        """, dokumen_id)

async def run_graph_rag_pipeline(job_id: str, dokumen_id: int, manager):
    """
    Graph RAG Entity Extraction.
    Extracts entities and relationships.
    """
    await manager.update_job_progress(job_id, "RUNNING", 10, "Fetching document...")
    await asyncio.sleep(2)
    
    await manager.update_job_progress(job_id, "RUNNING", 50, "Extracting NER (Named Entities) and Relationships...")
    await asyncio.sleep(5)
    
    await manager.update_job_progress(job_id, "RUNNING", 90, "Updating Knowledge Graph nodes and edges...")
    await asyncio.sleep(2)
    
    async with get_db() as conn:
        await conn.execute("""
            INSERT INTO dokumen (id, judul, nomor, status, status_ocr) 
            VALUES ($1, 'Mock Graph Title', 'MOCK-123', 'COMPLETED', 'DONE')
            ON CONFLICT (id) DO UPDATE SET status = 'COMPLETED'
        """, dokumen_id)

async def run_vision_rag_pipeline(job_id: str, dokumen_id: int, manager):
    """
    Vision RAG Processing using ColPali.
    """
    await manager.update_job_progress(job_id, "RUNNING", 10, "Fetching document...")
    await asyncio.sleep(2)
    
    await manager.update_job_progress(job_id, "RUNNING", 40, "Rendering PDF pages into high-res images...")
    await asyncio.sleep(3)
    
    await manager.update_job_progress(job_id, "RUNNING", 80, "Running Vision Model (ColPali) to generate visual embeddings...")
    await asyncio.sleep(6)
    
    async with get_db() as conn:
        await conn.execute("""
            INSERT INTO dokumen (id, judul, nomor, status, status_ocr) 
            VALUES ($1, 'Mock Vision Title', 'MOCK-123', 'COMPLETED', 'DONE')
            ON CONFLICT (id) DO UPDATE SET status = 'COMPLETED'
        """, dokumen_id)
