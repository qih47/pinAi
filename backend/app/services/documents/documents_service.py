import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import aiomysql

from backend.app.core.database import get_db, get_peraturan_db

logger = logging.getLogger("CAKRA_DOCUMENTS_SERVICE")

def extract_snippet(text: str, keyword: str, window: int = 100) -> Optional[str]:
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
    pattern = re.compile(f'({re.escape(keyword)})', re.IGNORECASE)
    snippet = pattern.sub(r'<b>\1</b>', snippet)
    return snippet

class DocumentsService:
    async def list_documents(
        self, offset: int, limit: int, search: Optional[str], status: Optional[str]
    ) -> Dict[str, Any]:
        """List documents with pagination and filtering from peraturan_db (MySQL)."""
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
                
                # Fetch with pagination
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
                    
                documents.append({
                    "id": row["id"],
                    "title": row["title"] or "Tanpa Judul",
                    "description": None,
                    "source_type": "internal",
                    "file_path": row["filename"],
                    "file_size": 0,
                    "file_type": "application/pdf",
                    "created_at": valid_date or datetime.utcnow(),
                    "updated_at": None,
                    "chunk_count": row["chunk_count"] or 0,
                    "embedding_status": "completed",
                    "nomor": row["nomor"],
                    "tanggal": valid_date,
                    "filename": row["filename"],
                    "jenis_dokumen": row["jenis_dokumen"],
                    "stataktif": row.get("stataktif"),
                    "snippet": snip
                })
            
            logger.info(f"📋 [DOCUMENTS] Listed {len(documents)}/{total} dokumen (offset={offset}, limit={limit})")
            
            return {
                "items": documents,
                "total": total,
                "offset": offset,
                "limit": limit
            }

    async def get_document_lineage(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get document lineage from MySQL."""
        async with get_peraturan_db() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id_berita, noper, judul, stataktif, tanggal, mencabut FROM berita WHERE id_berita = %s",
                    (document_id,)
                )
                row_current = await cursor.fetchone()
                
                if not row_current:
                    return None
                
                current_item = {
                    "id": row_current["id_berita"],
                    "noper": row_current["noper"],
                    "judul": row_current["judul"],
                    "stataktif": row_current["stataktif"],
                    "tanggal": row_current["tanggal"] if not isinstance(row_current["tanggal"], str) else None,
                    "relation_type": "Saat ini"
                }
                
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
                            revokes.append({
                                "id": r["id_berita"],
                                "noper": r["noper"],
                                "judul": r["judul"],
                                "stataktif": r["stataktif"],
                                "tanggal": r["tanggal"] if not isinstance(r["tanggal"], str) else None,
                                "relation_type": "Dicabut oleh dokumen ini"
                            })
                
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
                    revoked_by.append({
                        "id": r["id_berita"],
                        "noper": r["noper"],
                        "judul": r["judul"],
                        "stataktif": r["stataktif"],
                        "tanggal": r["tanggal"] if not isinstance(r["tanggal"], str) else None,
                        "relation_type": "Mencabut dokumen ini"
                    })
                
                return {
                    "current": current_item,
                    "revokes": revokes,
                    "revoked_by": revoked_by
                }

    async def create_document_record(
        self, title: str, description: str, file_path: str, file_size: int, file_type: str
    ) -> int:
        """Create a new document record in PostgreSQL with status 'pending'."""
        async with get_db() as conn:
            async with conn.transaction():
                doc_id = await conn.fetchval(
                    """
                    INSERT INTO dokumen (title, description, source_type, file_path, file_size, file_type, created_at, updated_at, embedding_status)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW(), $7)
                    RETURNING id
                    """,
                    title,
                    description,
                    "upload",
                    str(file_path),
                    file_size,
                    file_type,
                    "pending",
                )
                return doc_id

    async def delete_document(self, doc_id: int) -> Tuple[bool, Optional[str], int]:
        """Delete document from PostgreSQL. Returns (success, file_path, chunks_deleted)."""
        async with get_db() as conn:
            async with conn.transaction():
                doc_info = await conn.fetchrow(
                    "SELECT id, file_path FROM dokumen WHERE id = $1",
                    doc_id,
                )
                
                if not doc_info:
                    return False, None, 0
                
                file_path = doc_info["file_path"]
                
                chunks_deleted = await conn.fetchval(
                    "DELETE FROM dokumen_chunk WHERE dokumen_id = $1",
                    doc_id,
                )
                
                await conn.execute(
                    "DELETE FROM dokumen WHERE id = $1",
                    doc_id,
                )
                
                return True, file_path, chunks_deleted or 0

    async def mark_document_processing(self, doc_id: int) -> bool:
        """Set document status to 'processing'."""
        async with get_db() as conn:
            doc_exists = await conn.fetchval(
                "SELECT id FROM dokumen WHERE id = $1",
                doc_id,
            )
            
            if not doc_exists:
                return False
            
            await conn.execute(
                "UPDATE dokumen SET embedding_status = $1, updated_at = NOW() WHERE id = $2",
                "processing",
                doc_id,
            )
            return True

    async def get_document_stats(self) -> Dict[str, int]:
        """Get document statistics from PostgreSQL."""
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
            
            return {
                "total_documents": stats["total_documents"] or 0,
                "total_chunks": stats["total_chunks"] or 0,
                "total_file_size": stats["total_file_size"] or 0,
                "documents_pending": stats["documents_pending"] or 0,
                "documents_completed": stats["documents_completed"] or 0,
                "documents_failed": stats["documents_failed"] or 0,
            }

documents_service = DocumentsService()
