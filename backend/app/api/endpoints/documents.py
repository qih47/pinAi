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
from typing import Optional
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
    BackgroundTasks,
)
from fastapi.responses import JSONResponse

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.paths import get_account_dir
from backend.app.api.schemas.document import (
    DocumentSchema,
    DocumentListSchema,
    DocumentStatsSchema,
)
from backend.app.api.schemas.document_schemas import DocumentLineageSchema
from backend.app.services.documents.document_manager import document_manager
from backend.app.services.documents.documents_service import documents_service
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
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa akses dokumen")
    
    try:
        result = await documents_service.list_documents(offset, limit, search, status)
        return DocumentListSchema(**result)
            
    except Exception as e:
        logger.error(f"❌ [DOCUMENTS] Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengambil daftar dokumen")


@router.get("/{document_id}/lineage", response_model=DocumentLineageSchema)
async def get_document_lineage(document_id: int):
    """
    Mengambil silsilah dokumen (siapa yang dicabut dan siapa yang mencabut)
    """
    try:
        lineage = await documents_service.get_document_lineage(document_id)
        if not lineage:
            raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
        return DocumentLineageSchema(**lineage)
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
        
        # 4. Insert dokumen record into database via service
        doc_id = await documents_service.create_document_record(
            title=title,
            description=description or "",
            file_path=str(file_path),
            file_size=len(file_content),
            file_type=file.content_type or "application/octet-stream",
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
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa delete dokumen")
    
    try:
        success, file_path, chunks_deleted = await documents_service.delete_document(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
            
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
    """
    
    if current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Guest tidak bisa reindex dokumen")
    
    try:
        success = await documents_service.mark_document_processing(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
            
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
        stats = await documents_service.get_document_stats()
        return DocumentStatsSchema(**stats)
    
    except Exception as e:
        logger.error(f"❌ [STATS] Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
