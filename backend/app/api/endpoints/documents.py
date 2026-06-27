"""
CAKRA AI — Document Management Endpoints
==========================================
CRUD operations untuk dokumen RAG:
  - GET /api/documents (list dengan pagination)
  - POST /api/documents/ingest (upload + chunk + embed)
  - DELETE /api/documents/{id} (delete + cleanup)
  - POST /api/documents/{id}/reindex (re-embed)
  - GET /api/documents/stats (statistik dokumen)
"""

import os
import logging
import asyncio
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    Query,
    HTTPException,
    Form,
)
from fastapi.responses import JSONResponse

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.paths import get_account_dir
from backend.app.core.database import get_db
from backend.app.api.schemas.document import (
    DocumentSchema,
    DocumentListSchema,
    DocumentIngestSchema,
    DocumentReindexSchema,
    DocumentStatsSchema,
)
from backend.app.services.rag_service import rag_service
from backend.app.utils.upload_validator import (
    validate_uploaded_file,
    UploadValidationError,
)

logger = logging.getLogger("CAKRA_DOCUMENTS")

router = APIRouter(tags=["documents"])

# ══════════════════════════════════════════════════════════════════════════════
# GET /api/documents — List dokumen dengan pagination
# ══════════════════════════════════════════════════════════════════════════════


@router.get("", response_model=DocumentListSchema)
async def list_documents(
    current_user_npp: str = Depends(get_current_user_npp),
    offset: int = Query(0, ge=0, description="Offset untuk pagination"),
    limit: int = Query(20, ge=1, le=100, description="Limit items per halaman"),
):
    """
    List semua dokumen dengan pagination.
    
    Query Parameters:
    - offset: Mulai dari item ke berapa (default 0)
    - limit: Berapa item per halaman (default 20, max 100)
    
    Returns:
    - items: Daftar DocumentSchema
    - total: Total dokumen di database
    - offset: Offset yang digunakan
    - limit: Limit yang digunakan
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa akses dokumen")
    
    try:
        async with get_db() as conn:
            # Count total
            total_result = await conn.fetchval("SELECT COUNT(*) FROM dokumen")
            total = total_result or 0
            
            # Fetch dengan pagination
            rows = await conn.fetch(
                """
                SELECT 
                    d.id, d.judul AS title, 
                    d.nomor, d.tanggal AS created_at, d.filename, j.nama AS jenis_dokumen,
                    (SELECT COUNT(*) FROM dokumen_chunk WHERE dokumen_id = d.id) AS chunk_count
                FROM dokumen d
                LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                ORDER BY d.id DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            
            documents = []
            for row in rows:
                documents.append(DocumentSchema(
                    id=row["id"],
                    title=row["title"] or "Tanpa Judul",
                    description=None,
                    source_type="internal",
                    file_path=row["filename"],
                    file_size=0,
                    file_type="application/pdf",
                    created_at=row["created_at"] or datetime.utcnow(),
                    updated_at=None,
                    chunk_count=row["chunk_count"] or 0,
                    embedding_status="completed",
                    nomor=row["nomor"],
                    tanggal=row["created_at"],
                    filename=row["filename"],
                    jenis_dokumen=row["jenis_dokumen"]
                ))
            
            logger.info(f"📋 [DOCUMENTS] Listed {len(documents)}/{total} dokumen (offset={offset}, limit={limit})")
            
            return DocumentListSchema(
                items=documents,
                total=total,
                offset=offset,
                limit=limit,
            )
    
    except Exception as e:
        logger.error(f"❌ [DOCUMENTS] Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/documents/ingest — Upload + Chunk + Embed
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/ingest", response_model=DocumentSchema)
async def ingest_document(
    title: str = Form(..., min_length=1, max_length=255),
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user_npp: str = Depends(get_current_user_npp),
):
    """
    Upload dokumen baru, chunk, dan embed ke vector database.
    
    Parameters:
    - title: Judul dokumen (required)
    - file: File upload (PDF, TXT, DOCX, etc.)
    - description: Deskripsi opsional
    
    Returns:
    - DocumentSchema dengan status embedding=pending (akan di-process background)
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa upload dokumen")
    
    try:
        # 1. Validate file
        logger.info(f"📤 [INGEST] Validating file: {file.filename}")
        
        file_content = await file.read()
        await validate_uploaded_file(file_content, file.filename or "")
        
        # 2. Get account directory
        account_docs_dir = get_account_dir(current_user_npp, "documents")
        
        # 3. Save file
        file_path = account_docs_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"✅ [INGEST] File saved: {file_path}")
        
        # 4. Insert dokumen record into database
        async with get_db() as conn:
            async with conn.transaction():
                doc_id = await conn.fetchval(
                    """
                    INSERT INTO dokumen (title, description, source_type, file_path, file_size, file_type, created_at, updated_at, embedding_status)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW(), $7)
                    RETURNING id
                    """,
                    title,
                    description or "",
                    "upload",
                    str(file_path),
                    len(file_content),
                    file.content_type or "application/octet-stream",
                    "pending",
                )
                
                logger.info(f"💾 [INGEST] Document record created: ID={doc_id}")
        
        # 5. Queue background task untuk chunk + embed
        # (Bisa trigger via Celery atau APScheduler, untuk sekarang cukup status=pending)
        asyncio.create_task(_process_document_background(doc_id, str(file_path)))
        
        # 6. Return dokumen info
        return DocumentSchema(
            id=doc_id,
            title=title,
            description=description or "",
            source_type="upload",
            file_path=str(file_path),
            file_size=len(file_content),
            file_type=file.content_type or "application/octet-stream",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            chunk_count=0,
            embedding_status="pending",
        )
    
    except UploadValidationError as e:
        logger.warning(f"⚠️ [INGEST] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ [INGEST] Error ingesting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/documents/{id} — Delete dokumen + chunks + embeddings
# ══════════════════════════════════════════════════════════════════════════════


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    delete_file: bool = Query(True, description="Hapus file fisik juga"),
    current_user_npp: str = Depends(get_current_user_npp),
):
    """
    Delete dokumen dan cascade ke chunks + embeddings.
    
    Parameters:
    - doc_id: Document ID yang akan didelete
    - delete_file: Apakah hapus file fisik juga (default True)
    
    Returns:
    - {"message": "Document deleted", "doc_id": N, "chunks_deleted": N}
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa delete dokumen")
    
    try:
        async with get_db() as conn:
            async with conn.transaction():
                # Get dokumen info
                doc_info = await conn.fetchrow(
                    "SELECT id, file_path FROM dokumen WHERE id = $1",
                    doc_id,
                )
                
                if not doc_info:
                    raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
                
                file_path = doc_info["file_path"]
                
                # Delete chunks (cascade via FK)
                chunks_deleted = await conn.fetchval(
                    "DELETE FROM dokumen_chunk WHERE dokumen_id = $1",
                    doc_id,
                )
                
                # Delete dokumen
                await conn.execute(
                    "DELETE FROM dokumen WHERE id = $1",
                    doc_id,
                )
                
                logger.info(f"🗑️ [DELETE] Document {doc_id} deleted, {chunks_deleted} chunks removed")
        
        # Delete file if requested
        if delete_file and file_path:
            try:
                Path(file_path).unlink()
                logger.info(f"🗑️ [DELETE] File deleted: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ [DELETE] Could not delete file {file_path}: {e}")
        
        return {
            "message": "Document deleted",
            "doc_id": doc_id,
            "chunks_deleted": chunks_deleted or 0,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [DELETE] Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/documents/{id}/reindex — Re-embed dokumen
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/{doc_id}/reindex")
async def reindex_document(
    doc_id: int,
    force_rechunk: bool = Query(False, description="Re-chunk ulang atau gunakan chunks lama"),
    current_user_npp: str = Depends(get_current_user_npp),
):
    """
    Re-index dokumen (re-embed ke vector database).
    
    Parameters:
    - doc_id: Document ID
    - force_rechunk: Apakah perlu re-chunk ulang dari file
    
    Returns:
    - {"message": "Reindexing started", "doc_id": N, "status": "processing"}
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa reindex dokumen")
    
    try:
        async with get_db() as conn:
            # Check dokumen exists
            doc_exists = await conn.fetchval(
                "SELECT id FROM dokumen WHERE id = $1",
                doc_id,
            )
            
            if not doc_exists:
                raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
            
            # Update status ke processing
            await conn.execute(
                "UPDATE dokumen SET embedding_status = $1, updated_at = NOW() WHERE id = $2",
                "processing",
                doc_id,
            )
            
            logger.info(f"🔄 [REINDEX] Document {doc_id} marked for reindexing")
        
        # Queue background task
        asyncio.create_task(_reindex_document_background(doc_id, force_rechunk))
        
        return {
            "message": "Reindexing started",
            "doc_id": doc_id,
            "status": "processing",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [REINDEX] Error reindexing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/documents/stats — Statistik dokumen
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/stats", response_model=DocumentStatsSchema)
async def get_document_stats(
    current_user_npp: str = Depends(get_current_user_npp),
):
    """
    Get statistik dokumen (total, chunks, file size, status).
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa akses stats")
    
    try:
        async with get_db() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT d.id) as total_documents,
                    COALESCE(COUNT(c.id), 0) as total_chunks,
                    COALESCE(SUM(d.file_size), 0) as total_file_size,
                    COALESCE(SUM(CASE WHEN d.embedding_status = 'pending' THEN 1 ELSE 0 END), 0) as documents_pending,
                    COALESCE(SUM(CASE WHEN d.embedding_status = 'completed' THEN 1 ELSE 0 END), 0) as documents_completed,
                    COALESCE(SUM(CASE WHEN d.embedding_status = 'failed' THEN 1 ELSE 0 END), 0) as documents_failed
                FROM dokumen d
                LEFT JOIN dokumen_chunk c ON d.id = c.dokumen_id
                """
            )
            
            return DocumentStatsSchema(
                total_documents=stats["total_documents"] or 0,
                total_chunks=stats["total_chunks"] or 0,
                total_file_size=stats["total_file_size"] or 0,
                documents_pending=stats["documents_pending"] or 0,
                documents_completed=stats["documents_completed"] or 0,
                documents_failed=stats["documents_failed"] or 0,
            )
    
    except Exception as e:
        logger.error(f"❌ [STATS] Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# Background Tasks
# ══════════════════════════════════════════════════════════════════════════════


async def _process_document_background(doc_id: int, file_path: str):
    """
    Background task: chunk dokumen + embed chunks.
    Dijalankan async tanpa menunggu response endpoint.
    """
    try:
        logger.info(f"🔄 [BG] Starting document processing: {doc_id}")
        
        # 1. Extract text dari file
        from backend.app.services.pipeline import extract_pdf_text
        text_content = await extract_pdf_text(file_path)
        
        if not text_content:
            logger.warning(f"⚠️ [BG] No text extracted from {file_path}")
            async with get_db() as conn:
                await conn.execute(
                    "UPDATE dokumen SET embedding_status = $1 WHERE id = $2",
                    "failed",
                    doc_id,
                )
            return
        
        # 2. Chunk dokumen
        from backend.app.services.document_chunking.manager import chunk_text
        chunks = await chunk_text(text_content)
        
        logger.info(f"✂️ [BG] Created {len(chunks)} chunks for document {doc_id}")
        
        # 3. Embed chunks
        async with get_db() as conn:
            async with conn.transaction():
                for idx, chunk_text_content in enumerate(chunks):
                    # Get embedding dari rag_service
                    embedding = await rag_service.embed_text(chunk_text_content)
                    
                    # Insert chunk
                    await conn.execute(
                        """
                        INSERT INTO dokumen_chunk (dokumen_id, chunk_index, content, embedding)
                        VALUES ($1, $2, $3, $4)
                        """,
                        doc_id,
                        idx,
                        chunk_text_content,
                        embedding,  # pgvector format
                    )
                
                # Update dokumen status to completed
                await conn.execute(
                    "UPDATE dokumen SET embedding_status = $1, updated_at = NOW() WHERE id = $2",
                    "completed",
                    doc_id,
                )
        
        logger.info(f"✅ [BG] Document {doc_id} processing completed")
    
    except Exception as e:
        logger.error(f"❌ [BG] Document processing failed: {e}")
        async with get_db() as conn:
            await conn.execute(
                "UPDATE dokumen SET embedding_status = $1 WHERE id = $2",
                "failed",
                doc_id,
            )


async def _reindex_document_background(doc_id: int, force_rechunk: bool):
    """
    Background task: re-embed existing dokumen chunks.
    """
    try:
        logger.info(f"🔄 [BG] Starting reindex: {doc_id} (force_rechunk={force_rechunk})")
        
        async with get_db() as conn:
            if force_rechunk:
                # Delete old chunks
                await conn.execute(
                    "DELETE FROM dokumen_chunk WHERE dokumen_id = $1",
                    doc_id,
                )
                
                # Get file path dan re-process
                file_path = await conn.fetchval(
                    "SELECT file_path FROM dokumen WHERE id = $1",
                    doc_id,
                )
                
                # Trigger full processing
                await _process_document_background(doc_id, file_path)
            else:
                # Just re-embed existing chunks
                chunks = await conn.fetch(
                    "SELECT id, content FROM dokumen_chunk WHERE dokumen_id = $1 ORDER BY chunk_index",
                    doc_id,
                )
                
                for chunk in chunks:
                    embedding = await rag_service.embed_text(chunk["content"])
                    await conn.execute(
                        "UPDATE dokumen_chunk SET embedding = $1 WHERE id = $2",
                        embedding,
                        chunk["id"],
                    )
                
                # Mark as completed
                await conn.execute(
                    "UPDATE dokumen SET embedding_status = $1, updated_at = NOW() WHERE id = $2",
                    "completed",
                    doc_id,
                )
        
        logger.info(f"✅ [BG] Reindex completed for document {doc_id}")
    
    except Exception as e:
        logger.error(f"❌ [BG] Reindex failed: {e}")
        async with get_db() as conn:
            await conn.execute(
                "UPDATE dokumen SET embedding_status = $1 WHERE id = $2",
                "failed",
                doc_id,
            )
