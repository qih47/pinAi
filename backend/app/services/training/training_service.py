import logging
from typing import List, Dict, Any
from backend.app.core.database import get_db, get_peraturan_db

logger = logging.getLogger("CAKRA_TRAINING_SERVICE")

class TrainingService:
    @staticmethod
    async def get_source_docs() -> List[Dict[str, Any]]:
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

            return result

        except Exception as e:
            logger.error(f"Failed to fetch source docs: {e}")
            raise RuntimeError(f"Database error when fetching source docs: {e}")

training_service = TrainingService()
