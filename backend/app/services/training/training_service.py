import logging
from typing import List, Dict, Any
from backend.app.core.database import get_db, get_peraturan_db

logger = logging.getLogger("CAKRA_TRAINING_SERVICE")

class TrainingService:
    @staticmethod
    async def get_source_docs() -> List[Dict[str, Any]]:
        """
        Fetches all documents from qa_peraturan_db (berita) and cross-checks with ragdb (dokumen_chunk).
        Returns list with accurate is_embedded flag based on whether vector embeddings actually exist.
        """
        try:
            # 1. Fetch all source documents from MySQL (tanpa limit 200)
            mysql_docs = []
            async with get_peraturan_db() as conn_mysql:
                async with conn_mysql.cursor() as cur:
                    await cur.execute("""
                        SELECT id_berita, judul, noper, tanggal, gambar, id_kategori
                        FROM berita
                        ORDER BY id_berita DESC
                    """)
                    columns = [col[0] for col in cur.description]
                    rows = await cur.fetchall()
                    for row in rows:
                        mysql_docs.append(dict(zip(columns, row)))

            # 2. Cross-check dengan PostgreSQL ragdb:
            # Dokumen dianggap tuntas (is_embedded = True) jika:
            # a) Memiliki embedding vektor di dokumen_chunk, ATAU
            # b) Telah selesai diproses 100% oleh Nightly 6-Worker Training (nightly_training_checkpoints)
            embedded_ids = set()
            nightly_completed_ids = set()
            async with get_db() as conn_pg:
                pg_rows = await conn_pg.fetch("""
                    SELECT DISTINCT dokumen_id 
                    FROM dokumen_chunk 
                    WHERE embedding IS NOT NULL
                """)
                embedded_ids = {row['dokumen_id'] for row in pg_rows}

                chk_rows = await conn_pg.fetch("""
                    SELECT DISTINCT dokumen_id
                    FROM nightly_training_checkpoints
                    WHERE status = 'COMPLETED'
                """)
                nightly_completed_ids = {row['dokumen_id'] for row in chk_rows}

            # 3. Assemble response
            result = []
            for doc in mysql_docs:
                doc_id = doc['id_berita']
                tgl = doc.get('tanggal')
                tgl_str = tgl.isoformat() if hasattr(tgl, 'isoformat') else str(tgl) if tgl else None
                is_done = (doc_id in embedded_ids) or (doc_id in nightly_completed_ids)
                result.append({
                    "id": doc_id,
                    "judul": doc['judul'],
                    "noper": doc['noper'],
                    "tanggal": tgl_str,
                    "kategori_id": doc['id_kategori'],
                    "file_name": doc['gambar'],
                    "is_embedded": is_done,
                    "has_vector_chunks": doc_id in embedded_ids,
                    "is_nightly_completed": doc_id in nightly_completed_ids
                })

            return result

        except Exception as e:
            logger.error(f"Failed to fetch source docs: {e}")
            raise RuntimeError(f"Database error when fetching source docs: {e}")

training_service = TrainingService()
