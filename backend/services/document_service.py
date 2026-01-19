import logging
from typing import Dict, List, Any
from backend.database.connection import db_manager
from backend.utils.embedding_utils import embedding_manager
from backend.config.settings import settings


class DocumentService:
    @staticmethod
    async def search_documents(query: str, limit: int = None) -> Dict[str, Any]:
        """Search documents in the database using Hybrid Search (Vector + Full-Text) with threshold filtering."""
        if limit is None:
            limit = settings.LIMIT
            
        logging.info(f"🔍 [search_documents] Mencari (Hybrid): '{query}'")
        try:
            # Generate embedding for the query using bge-m3
            query_embedding = embedding_manager.model.encode([query], normalize_embeddings=True)[0].tolist()
            query_vector_str = embedding_manager.embedding_to_pgvector_str(query_embedding)

            conn = await db_manager.get_rag_connection()

            # --- 1. Full-Text Search ---
            logging.info("🔍 [search_documents] Menjalankan Full-Text Search...")
            fts_sql = """
            SELECT
                dc.id,
                dc.dokumen_id,
                d.judul,
                d.nomor,
                d.tanggal,
                d.tempat,
                d.filename,
                d.id_jenis,
                dc.content,
                dc.chunk_id,
                ts_rank_cd(to_tsvector('indonesian', dc.content), plainto_tsquery('indonesian', $1), 1) as fts_score -- Gunakan ts_rank_cd untuk efisiensi
            FROM dokumen_chunk dc
            JOIN dokumen d ON dc.dokumen_id = d.id
            WHERE to_tsvector('indonesian', dc.content) @@ plainto_tsquery('indonesian', $1)
              AND d.status_ocr = 'rag_ready'
            ORDER BY fts_score DESC
            LIMIT $2;
            """
            fts_chunks = await conn.fetch(fts_sql, query, limit)
            logging.info(f"✅ [search_documents] FTS menemukan {len(fts_chunks)} chunk.")

            # --- 2. Vector Search ---
            logging.info("🔍 [search_documents] Menjalankan Vector Search...")
            # Gunakan <-> untuk cosine distance (1 - cosine_similarity) di pgvector
            # Jadi, (dc.embedding <-> $1) = 1 - cosine_similarity
            # cosine_similarity = 1 - (dc.embedding <-> $1)
            vector_sql = """
            SELECT
                dc.id,
                dc.dokumen_id,
                d.judul,
                d.nomor,
                d.tanggal,
                d.tempat,
                d.filename,
                d.id_jenis,
                dc.content,
                dc.chunk_id,
                (dc.embedding <-> $1::vector) as cosine_distance
            FROM dokumen_chunk dc
            JOIN dokumen d ON dc.dokumen_id = d.id
            WHERE d.status_ocr = 'rag_ready'
            ORDER BY (dc.embedding <-> $1::vector)
            LIMIT $2;
            """
            vector_chunks = await conn.fetch(vector_sql, query_vector_str, limit)
            logging.info(
                f"✅ [search_documents] Vector Search menemukan {len(vector_chunks)} chunk."
            )

            # --- 3. Gabungkan Hasil (Hybrid) ---
            combined_scores = {}
            id_to_chunk = {}

            # Tambahkan skor FTS
            for chunk in fts_chunks:
                chunk_id = chunk["id"]
                combined_scores[chunk_id] = {
                    "fts_score": float(chunk["fts_score"]),
                    "vector_score": 0.0,
                    "similarity": 0.0,
                    "chunk_data": dict(chunk),
                }
                id_to_chunk[chunk_id] = dict(chunk)
                # Hapus kolom sementara dari chunk_data
                del combined_scores[chunk_id]["chunk_data"]["fts_score"]

            # Tambahkan skor Vector dan perbarui similarity
            for chunk in vector_chunks:
                chunk_id = chunk["id"]
                cosine_distance = float(chunk["cosine_distance"])
                # cosine_similarity = 1 - cosine_distance
                cosine_similarity = 1.0 - cosine_distance

                if chunk_id in combined_scores:
                    # Jika chunk muncul di FTS, update skor vector-nya
                    combined_scores[chunk_id]["vector_score"] = cosine_similarity
                    combined_scores[chunk_id]["similarity"] = (
                        cosine_similarity  # Gunakan similarity vector untuk filtering
                    )
                else:
                    # Jika chunk hanya ada di Vector Search
                    combined_scores[chunk_id] = {
                        "fts_score": 0.0,
                        "vector_score": cosine_similarity,
                        "similarity": cosine_similarity,
                        "chunk_data": dict(chunk),
                    }
                    id_to_chunk[chunk_id] = dict(chunk)

            # --- 4. Hitung Skor Gabungan dan Urutkan ---
            # Bobot untuk hybrid search (FTS vs Vector)
            WEIGHT_FTS = 0.4
            WEIGHT_VECTOR = 0.6

            def calculate_hybrid_score(scores):
                fts_norm = scores["fts_score"]  # Skor FTS biasanya 0-1
                vector_norm = scores["vector_score"]  # Sudah dalam bentuk similarity 0-1
                return (WEIGHT_FTS * fts_norm) + (WEIGHT_VECTOR * vector_norm)

            # Buat list tuple (chunk_id, hybrid_score) untuk diurutkan
            scored_chunks = [
                (cid, calculate_hybrid_score(scores))
                for cid, scores in combined_scores.items()
            ]

            # Urutkan berdasarkan skor gabungan, tertinggi dulu
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            # Ambil chunk yang sudah diurutkan
            sorted_chunk_ids = [cid for cid, score in scored_chunks]
            sorted_chunks = [
                id_to_chunk[cid] for cid in sorted_chunk_ids if cid in id_to_chunk
            ]

            # --- 5. Filter berdasarkan SIMILARITY_THRESHOLD ---
            # Gunakan similarity dari vector search (karena itu representasi semantik utama)
            filtered_chunks = []
            for chunk in sorted_chunks:
                vector_similarity = combined_scores[chunk["id"]]["vector_score"]
                if vector_similarity >= settings.SIMILARITY_THRESHOLD:
                    chunk["similarity"] = (
                        vector_similarity  # Pastikan kolom similarity ada dan benar
                    )
                    filtered_chunks.append(chunk)

            # Ambil limit
            final_chunks = filtered_chunks[:limit]

            # Ambil info dokumen untuk hasil final
            document_ids = list(set(chunk["dokumen_id"] for chunk in final_chunks))
            documents = []
            if document_ids:
                doc_sql = """
                SELECT id, judul, nomor, tanggal, tempat, filename, status, id_jenis
                FROM dokumen
                WHERE id = ANY($1)
                """
                documents = await conn.fetch(doc_sql, document_ids)

            logging.info(
                f"✅ [search_documents] Ditemukan {len(final_chunks)} chunk yang melewati filter Hybrid Search (threshold={settings.SIMILARITY_THRESHOLD})."
            )
            await db_manager.release_rag_connection(conn)

            # Log hasil hybrid (opsional, untuk debugging)
            for i, chunk in enumerate(final_chunks):
                logging.info(
                    f"[search_documents][Hybrid] Chunk-{i} dokumen_id={chunk['dokumen_id']} judul={chunk['judul']} content: {chunk['content'][:100]}... similarity: {chunk['similarity']:.4f}"
                )

            return {
                "documents": [dict(row) for row in documents],
                "chunks": [dict(row) for row in final_chunks],
            }

        except Exception as e:
            logging.error(f"Error searching documents (Hybrid): {e}")
            # Fallback ke vector search original jika hybrid gagal
            try:
                conn = await db_manager.get_rag_connection()

                # Gunakan kode vector search original kamu di sini
                # Pastikan query_vector_str dan threshold sudah didefinisikan
                # Gunakan <-> untuk cosine similarity
                chunk_sql = """
                SELECT
                    dc.id,
                    dc.dokumen_id,
                    d.judul,
                    d.nomor,
                    d.tanggal,
                    d.tempat,
                    d.filename,
                    d.id_jenis,
                    dc.content,
                    dc.chunk_id,
                    (dc.embedding <-> $1::vector) as cosine_distance
                FROM dokumen_chunk dc
                JOIN dokumen d ON dc.dokumen_id = d.id
                WHERE d.status_ocr = 'rag_ready'
                ORDER BY (dc.embedding <-> $1::vector)
                LIMIT $2;
                """

                chunks = await conn.fetch(chunk_sql, query_vector_str, limit)

                # Filter berdasarkan threshold setelah mengambil semua
                filtered_chunks = []
                for chunk in chunks:
                    cosine_similarity = 1.0 - float(chunk["cosine_distance"])
                    if cosine_similarity >= settings.SIMILARITY_THRESHOLD:
                        chunk["similarity"] = cosine_similarity
                        filtered_chunks.append(dict(chunk))
                    # Hapus kolom distance setelah digunakan
                    del chunk["cosine_distance"]

                # Ambil limit setelah filtering
                final_chunks = filtered_chunks[:limit]

                document_ids = list(set(chunk["dokumen_id"] for chunk in final_chunks))
                documents = []
                if document_ids:
                    doc_sql = """
                    SELECT id, judul, nomor, tanggal, tempat, filename, status, id_jenis
                    FROM dokumen
                    WHERE id = ANY($1)
                    """
                    documents = await conn.fetch(doc_sql, document_ids)

                logging.info(
                    f"✅ [search_documents] Fallback Vector Search menemukan {len(final_chunks)} chunk."
                )
                await db_manager.release_rag_connection(conn)

                return {
                    "documents": [dict(row) for row in documents],
                    "chunks": [dict(row) for row in final_chunks],
                }
            except Exception as fallback_e:
                logging.error(f"Fallback search also failed: {fallback_e}")
                return {"documents": [], "chunks": []}