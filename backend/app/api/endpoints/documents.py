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
import aiomysql

from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    Query,
    HTTPException,
    Form,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.paths import get_account_dir
from backend.app.core.database import get_db, get_peraturan_db
from backend.app.api.schemas.document import (
    DocumentSchema,
    DocumentListSchema,
    DocumentIngestSchema,
    DocumentReindexSchema,
    DocumentStatsSchema,
)
from backend.app.api.schemas.document_schemas import DocumentLineageSchema, DocumentLineageItemSchema
from backend.app.services.rag.rag_service import rag_service
from backend.app.services.documents.document_manager import document_manager
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
    search: Optional[str] = Query(None, description="Kata kunci pencarian"),
    status: Optional[str] = Query(None, description="Filter status aktif (berlaku/batal/obsolete)"),
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
        async with get_peraturan_db() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                conditions = []
                params_count = []
                params_data = []
                
                if search:
                    search_term = f"%{search}%"
                    conditions.append("(b.judul LIKE %s OR b.noper LIKE %s OR b.isi_berita LIKE %s)")
                    params_count.extend([search_term, search_term, search_term])
                    params_data.extend([search_term, search_term, search_term])
                
                if status:
                    if status.lower() == "berlaku":
                        conditions.append("b.stataktif = ''")
                    elif status.lower() in ["batal", "obsolete"]:
                        conditions.append("b.stataktif = %s")
                        params_count.append(status.lower())
                        params_data.append(status.lower())
                
                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                
                # Count total
                await cursor.execute(f"SELECT COUNT(*) AS total FROM berita b {where_clause}", params_count)
                total_result = await cursor.fetchone()
                total = total_result['total'] if total_result else 0
                
                # Fetch dengan pagination
                await cursor.execute(
                    f"""
                    SELECT 
                        b.id_berita AS id, 
                        b.judul AS title, 
                        b.noper AS nomor, 
                        b.tanggal AS created_at, 
                        COALESCE(NULLIF(b.gambar, ''), NULLIF(b.gambar2, ''), NULLIF(b.gambar3, '')) AS filename, 
                        k.nama_kategori AS jenis_dokumen,
                        b.stataktif AS stataktif,
                        b.isi_berita AS isi_berita,
                        0 AS chunk_count
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    {where_clause}
                    ORDER BY b.id_berita DESC
                    LIMIT {limit} OFFSET {offset}
                    """,
                    params_data
                )
                rows = await cursor.fetchall()
            
            import re
            
            def extract_snippet(text, keyword, window=100):
                if not text or not keyword: return None
                # Strip HTML
                clean_text = re.sub('<[^<]+>', ' ', text)
                clean_text = ' '.join(clean_text.split())
                
                idx = clean_text.lower().find(keyword.lower())
                if idx == -1: return None
                
                start = max(0, idx - window)
                end = min(len(clean_text), idx + len(keyword) + window)
                
                snippet = clean_text[start:end]
                if start > 0: snippet = "..." + snippet
                if end < len(clean_text): snippet = snippet + "..."
                
                # Highlight keyword
                # Case insensitive highlight
                pattern = re.compile(f'({re.escape(keyword)})', re.IGNORECASE)
                snippet = pattern.sub(r'<b>\1</b>', snippet)
                return snippet

            documents = []
            for row in rows:
                raw_date = row["created_at"]
                if isinstance(raw_date, str) and ("0000-00-00" in raw_date):
                    valid_date = None
                else:
                    valid_date = raw_date
                
                snip = None
                if search:
                    snip = extract_snippet(row.get("isi_berita", ""), search)
                    
                documents.append(DocumentSchema(
                    id=row["id"],
                    title=row["title"] or "Tanpa Judul",
                    description=None,
                    source_type="internal",
                    file_path=row["filename"],
                    file_size=0,
                    file_type="application/pdf",
                    created_at=valid_date or datetime.utcnow(),
                    updated_at=None,
                    chunk_count=row["chunk_count"] or 0,
                    embedding_status="completed",
                    nomor=row["nomor"],
                    tanggal=valid_date,
                    filename=row["filename"],
                    jenis_dokumen=row["jenis_dokumen"],
                    stataktif=row.get("stataktif"),
                    snippet=snip
                ))
            
            logger.info(f"📋 [DOCUMENTS] Listed {len(documents)}/{total} dokumen (offset={offset}, limit={limit})")
            
            return DocumentListSchema(
                items=documents,
                total=total,
                offset=offset,
                limit=limit
            )
            
    except Exception as e:
        logger.error(f"❌ [DOCUMENTS] Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengambil daftar dokumen")


@router.get("/{document_id}/lineage", response_model=DocumentLineageSchema)
async def get_document_lineage(document_id: int):
    """
    Mengambil silsilah dokumen (siapa yang dicabut dan siapa yang mencabut)
    """
    from backend.app.core.database import get_peraturan_db
    
    try:
        async with get_peraturan_db() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 1. Ambil dokumen saat ini
                await cursor.execute(
                    "SELECT id_berita, noper, judul, stataktif, tanggal, mencabut FROM berita WHERE id_berita = %s",
                    (document_id,)
                )
                row_current = await cursor.fetchone()
                
                if not row_current:
                    raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
                
                current_item = DocumentLineageItemSchema(
                    id=row_current["id_berita"],
                    noper=row_current["noper"],
                    judul=row_current["judul"],
                    stataktif=row_current["stataktif"],
                    tanggal=row_current["tanggal"] if not isinstance(row_current["tanggal"], str) else None,
                    relation_type="Saat ini"
                )
                
                # 2. Cari dokumen yang dicabut oleh dokumen ini (revokes)
                revokes = []
                mencabut_str = row_current.get("mencabut", "")
                if mencabut_str:
                    ids_to_revoke = [x for x in mencabut_str.split("|") if x.strip().isdigit()]
                    if ids_to_revoke:
                        format_strings = ','.join(['%s'] * len(ids_to_revoke))
                        await cursor.execute(
                            f"SELECT id_berita, noper, judul, stataktif, tanggal FROM berita WHERE id_berita IN ({format_strings})",
                            tuple(ids_to_revoke)
                        )
                        rows_revokes = await cursor.fetchall()
                        for r in rows_revokes:
                            revokes.append(DocumentLineageItemSchema(
                                id=r["id_berita"],
                                noper=r["noper"],
                                judul=r["judul"],
                                stataktif=r["stataktif"],
                                tanggal=r["tanggal"] if not isinstance(r["tanggal"], str) else None,
                                relation_type="Dicabut oleh dokumen ini"
                            ))
                
                # 3. Cari dokumen yang mencabut dokumen ini (revoked_by)
                revoked_by = []
                doc_id_str = str(document_id)
                await cursor.execute(
                    """
                    SELECT id_berita, noper, judul, stataktif, tanggal 
                    FROM berita 
                    WHERE mencabut = %s 
                       OR mencabut LIKE %s 
                       OR mencabut LIKE %s 
                       OR mencabut LIKE %s
                    """,
                    (doc_id_str, f"{doc_id_str}|%", f"%|{doc_id_str}|%", f"%|{doc_id_str}")
                )
                rows_revoked_by = await cursor.fetchall()
                for r in rows_revoked_by:
                    revoked_by.append(DocumentLineageItemSchema(
                        id=r["id_berita"],
                        noper=r["noper"],
                        judul=r["judul"],
                        stataktif=r["stataktif"],
                        tanggal=r["tanggal"] if not isinstance(r["tanggal"], str) else None,
                        relation_type="Mencabut dokumen ini"
                    ))
                
                return DocumentLineageSchema(
                    current=current_item,
                    revokes=revokes,
                    revoked_by=revoked_by
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [DOCUMENTS] Error getting lineage: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengambil silsilah dokumen")

from pydantic import BaseModel
from fastapi import Request

class DocumentInsightResponse(BaseModel):
    insight: str

@router.get("/{document_id}/insight", response_model=DocumentInsightResponse)
async def get_document_insight(document_id: int, request: Request):
    """
    Menghasilkan rangkuman cerdas (AI Insight) poin penting dari isi dokumen
    """
    from backend.app.services.pipeline.mode_hub import ModeHub
    import json
    import re
    
    try:
        mode_hub = ModeHub()
        gen = mode_hub.execute(
            user_message="",
            chat_history=[],
            chat_mode="insight",
            is_thinking=False,
            context_isolation={"isolated_doc_id": document_id},
            request=request
        )
        
        full_response = ""
        async for chunk_str in gen:
            try:
                data_json = chunk_str.strip()
                if data_json:
                    data = json.loads(data_json)
                    if data.get("event_type") == "chunk":
                        chunk_text = data.get("chunk")
                        if chunk_text:
                            full_response += chunk_text
            except Exception as e:
                logger.error(f"Error parsing insight chunk: {e}")

        # Bersihkan tag internal LLM jika ada (misal <|channel>thought)
        clean_response = re.sub(r'<\|channel>thought.*?<channel\|>', '', full_response, flags=re.DOTALL)
        clean_response = clean_response.replace("<|channel>thought", "").replace("<channel|>", "").strip()
        
        return DocumentInsightResponse(insight=clean_response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [DOCUMENTS] Error generating insight: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal membuat rangkuman dokumen: {str(e)}")


@router.get("/preview_b64/{encoded_filename}")
async def preview_document_b64(encoded_filename: str):
    """
    Preview dokumen PDF dengan base64 filename untuk bypass IDM
    """
    from fastapi import Response
    from backend.app.core.paths import BASE_DIR
    import os
    import base64
    
    try:
        filename = base64.b64decode(encoded_filename).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename encoding")
        
    file_path = os.path.join(BASE_DIR, "file_peraturan", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
        
    with open(file_path, "rb") as f:
        content = f.read()
        
    return Response(
        content=content,
        media_type="application/octet-stream"
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/documents/ingest — Upload + Chunk + Embed
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/ingest", response_model=DocumentSchema)
async def ingest_document(
    background_tasks: BackgroundTasks,
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
        background_tasks.add_task(
            document_manager.process_document_background,
            doc_id=doc_id,
            file_path=str(file_path),
        )
        
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
    background_tasks: BackgroundTasks,
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
        background_tasks.add_task(
            document_manager.reindex_document_background,
            doc_id=doc_id,
            force_rechunk=force_rechunk
        )
        
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


# Background tasks extracted to document_manager.py
