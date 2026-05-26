from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
import os
import logging
from ..config import settings
from ..database import get_db  # Tetap import get_db yang pakai decorator

router = APIRouter()
logger = logging.getLogger(__name__)


# Fungsi pembantu supaya Depends bisa baca get_db yang punya decorator
async def get_db_conn():
    async with get_db() as conn:
        yield conn


@router.get("/documents")
async def list_documents(conn=Depends(get_db_conn)):  # Pakai wrapper di sini
    """Get list of documents from database"""
    try:
        documents = await conn.fetch("""
            SELECT d.id, d.judul, d.nomor, d.tanggal, d.filename, d.status, d.created_at
            FROM dokumen d
            ORDER BY d.created_at DESC
            LIMIT 20
        """)

        return {"documents": [dict(d) for d in documents], "count": len(documents)}
    except Exception as e:
        logger.error(f"Error fetching documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/document/{doc_id}")
async def get_document(doc_id: int, conn=Depends(get_db_conn)):  # Pakai wrapper di sini
    """Get specific document details"""
    try:
        document = await conn.fetchrow(
            """
            SELECT d.id, d.judul, d.nomor, d.tanggal, d.tempat, d.filename, d.status, 
                   d.created_at, d.status_ocr, d.source_file_type
            FROM dokumen d
            WHERE d.id = $1
        """,
            doc_id,
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        chunks = await conn.fetch(
            """
            SELECT id, content, created_at
            FROM dokumen_chunk
            WHERE dokumen_id = $1
            ORDER BY chunk_id
        """,
            doc_id,
        )

        return {"document": dict(document), "chunks": [dict(c) for c in chunks]}
    except Exception as e:
        logger.error(f"Error fetching document {doc_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
