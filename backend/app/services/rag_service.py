import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_RAG_SERVICE")

# Stopwords Indonesia yang sering merusak tsquery jika ikut di-AND-kan
_STOPWORDS_ID = {
    "yang",
    "di",
    "ke",
    "dari",
    "dan",
    "atau",
    "untuk",
    "dengan",
    "pada",
    "adalah",
    "ini",
    "itu",
    "dalam",
    "oleh",
    "juga",
    "sudah",
    "akan",
    "tidak",
    "ada",
    "saya",
    "anda",
    "bisa",
    "lebih",
    "seperti",
    "sebagai",
    "saat",
    "jika",
    "maka",
    "telah",
    "harus",
    "dapat",
    "agar",
    "bahwa",
    "karena",
    "namun",
    "namanya",
    "setiap",
    "serta",
    "tentang",
    "antara",
}


class RagService:
    """
    Orkestrator Advanced RAG — Hybrid Search PostgreSQL (pgvector + Full-Text Search)
    menggunakan Reciprocal Rank Fusion (RRF), ekspansi Parent-Child sesuai ERD,
    dan filtrasi via Cross-Encoder Re-ranker.

    Diselaraskan dengan:
    - mxbai-embed-large (1024 dim, native)
    - 179 chunk saat ini (seq scan, HNSW aktif otomatis saat data bertambah)
    - min_score dikalibrasi ulang ke range RRF aktual
    """

    def __init__(self):
        print(
            "🛡️  [RAG SERVICE] Orkestrator Hybrid RRF + Re-ranker Engine siap tempur, bolo!"
        )

    def _prepare_tsquery(self, query: str) -> str:
        """
        Bersihkan query → format kompatibel to_tsquery Postgres.

        Perubahan dari versi lama:
        - Operator OR (|) bukan AND (&) → recall lebih tinggi, tidak zero-result
        - Stopwords Indonesia difilter → tidak merusak tsquery
        - Prefix matching (:*) tetap dipertahankan
        - Maksimal 6 token untuk efisiensi
        """
        cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in query)
        tokens = [
            t.lower()
            for t in cleaned.split()
            if t and t.lower() not in _STOPWORDS_ID and len(t) > 1
        ]

        if not tokens:
            return "pindad"

        # Ambil maks 6 token paling bermakna, hindari overfitting query
        tokens = tokens[:6]

        # OR operator: dokumen yang punya SALAH SATU kata sudah masuk kandidat
        # Lebih baik re-ranker yang menyaring, bukan tsquery yang membunuh recall
        return " | ".join(f"{t}:*" for t in tokens)

    async def assemble_powerful_context(
        self, query: str, limit: int = 5, min_score: float = 0.005
    ) -> tuple[str, list[dict]]:
        """
        Pipeline RAG 3 fase - sekarang return tuple (context_string, sources_metadata)
        """
        print(f'🔍 [RAG HYBRID] Memulai ekstraksi RRF untuk kueri: "{query}"')

        # ======================================================================
        # FASE 0: LAZY IMPORT — anti-mismatch
        # ======================================================================
        try:
            from backend.app.services.vector_service import vector_service
        except ImportError:
            try:
                from backend.app.services.vector_service import VectorService

                vector_service = VectorService()
            except ImportError as e:
                logger.error(
                    f"💥 [RAG CRITICAL] vector_service tidak bisa di-import: {str(e)}"
                )
                return (
                    "[PERINGATAN SISTEM]: Terjadi kerusakan internal pada modul vector_service. "
                    "Katakan kepada user bahwa sistem sedang mengalami kendala teknis pada komponen pencarian."
                )

        # Generate embedding — mxbai pakai prefixed query untuk retrieval
        try:
            query_embedding = await vector_service.get_query_embedding(query)
        except AttributeError as ae:
            logger.error(
                f"💥 [RAG CRITICAL] Method get_query_embedding tidak ditemukan: {str(ae)}"
            )
            return "[PERINGATAN SISTEM]: Method pencarian embedding absen di backend."

        if not query_embedding:
            logger.error("💥 [RAG CRITICAL] Gagal generate embedding dari kueri user!")
            return ""

        # Validasi fallback: jika query terlalu pendek, perkaya sebelum tsquery
        if len(query.split()) < 3:
            logger.warning(
                f"⚠️  [RAG] Query pendek: '{query}'. Tsquery mungkin kurang efektif."
            )

        formatted_tsquery = self._prepare_tsquery(query)
        query_vector_str = str(query_embedding)

        candidate_chunks = []  # List of (chunk_id, doc_id, page, rrf_score)
        chunk_score_map = {}  # doc_id → best chunk info

        # ======================================================================
        # FASE 1: HYBRID SEARCH + RRF di PostgreSQL
        # ======================================================================
        async with get_db() as conn:
            try:
                hybrid_sql = """
                    WITH vector_search AS (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS rank
                        FROM dokumen_chunk
                        ORDER BY embedding <=> $1::vector
                        LIMIT $3 * 10
                    ),
                    text_search AS (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (
                                ORDER BY ts_rank_cd(
                                    to_tsvector('indonesian', content),
                                    to_tsquery('indonesian', $2)
                                ) DESC
                            ) AS rank
                        FROM dokumen_chunk
                        WHERE to_tsvector('indonesian', content) @@ to_tsquery('indonesian', $2)
                        ORDER BY ts_rank_cd(
                            to_tsvector('indonesian', content),
                            to_tsquery('indonesian', $2)
                        ) DESC
                        LIMIT $3 * 10
                    ),
                    ranked_candidates AS (
                        SELECT
                            COALESCE(v.id, t.id) AS chunk_id,
                            (
                                COALESCE(1.0 / (60.0 + v.rank), 0.0) +
                                COALESCE(1.0 / (60.0 + t.rank), 0.0)
                            ) AS rrf_score
                        FROM vector_search v
                        FULL OUTER JOIN text_search t ON v.id = t.id
                    )
                    SELECT
                        rc.chunk_id,
                        rc.rrf_score,
                        dc.dokumen_id,
                        dc.content AS chunk_content,
                        dc.chunk_id AS chunk_seq,
                        COALESCE(NULLIF(dc.page_number, ''), '1') AS page_str
                    FROM ranked_candidates rc
                    INNER JOIN dokumen_chunk dc ON rc.chunk_id = dc.id
                    ORDER BY rc.rrf_score DESC
                    LIMIT $3;
                """

                raw_chunks = await conn.fetch(
                    hybrid_sql, query_vector_str, formatted_tsquery, limit
                )

                if not raw_chunks:
                    # Fallback: jika text search zero result, coba pure vector only
                    logger.warning(
                        "⚠️  [RAG] Zero match hybrid. Fallback ke pure vector search..."
                    )
                    vector_only_sql = """
                        SELECT
                            dc.id AS chunk_id,
                            1.0 / (60.0 + ROW_NUMBER() OVER (ORDER BY dc.embedding <=> $1::vector)) AS rrf_score,
                            dc.dokumen_id,
                            dc.content AS chunk_content,
                            dc.chunk_id AS chunk_seq,
                            COALESCE(NULLIF(dc.page_number, ''), '1') AS page_str
                        FROM dokumen_chunk dc
                        ORDER BY dc.embedding <=> $1::vector
                        LIMIT $2;
                    """
                    raw_chunks = await conn.fetch(
                        vector_only_sql, query_vector_str, limit
                    )

                if not raw_chunks:
                    print("⚠️  [RAG CORE] Zero match bahkan di pure vector search!")
                    return ""

                for row in raw_chunks:
                    if row["dokumen_id"] is None:
                        continue

                    doc_id = int(row["dokumen_id"])
                    chunk_seq = row["chunk_seq"] or 0
                    clean_page = row["page_str"] or "1"

                    candidate_chunks.append(
                        {
                            "chunk_id": row["chunk_id"],
                            "doc_id": doc_id,
                            "chunk_seq": chunk_seq,
                            "page": clean_page,
                            "rrf_score": float(row["rrf_score"]),
                            "chunk_content": row["chunk_content"] or "",
                        }
                    )

                    # Simpan best chunk per dokumen untuk sibling expansion
                    if (
                        doc_id not in chunk_score_map
                        or row["rrf_score"] > chunk_score_map[doc_id]["rrf_score"]
                    ):
                        chunk_score_map[doc_id] = {
                            "page": clean_page,
                            "rrf_score": float(row["rrf_score"]),
                            "best_chunk_seq": chunk_seq,
                        }

            except Exception as sql_err:
                logger.error(
                    f"💥 [RAG SQL ERROR] Gagal eksekusi Hybrid Search RRF: {str(sql_err)}"
                )
                return ""

        candidate_doc_ids = list(chunk_score_map.keys())
        if not candidate_doc_ids:
            return ""

        # ======================================================================
        # FASE 2: PARENT EXPANSION + SIBLING CHUNKS
        # Ambil chunk relevan ± 1 sibling untuk konteks lebih kaya
        # Jauh lebih presisi dari ambil clean_text seluruh dokumen
        # ======================================================================
        expanded_blocks = []

        async with get_db() as conn:
            try:
                # Ambil metadata dokumen parent
                parent_sql = """
                    SELECT
                        d.id,
                        d.judul,
                        d.nomor,
                        j.nama AS nama_jenis
                    FROM dokumen d
                    LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                    WHERE d.id = ANY($1);
                """
                parent_rows = await conn.fetch(parent_sql, candidate_doc_ids)
                parent_map = {r["id"]: r for r in parent_rows}

                # Ambil sibling chunks (chunk best ± 1) per dokumen
                for cand in candidate_chunks:
                    doc_id = cand["doc_id"]
                    best_seq = cand["chunk_seq"]
                    parent = parent_map.get(doc_id)
                    if not parent:
                        continue

                    # Ambil chunk target + 1 sebelum + 1 sesudah untuk konteks sekitar
                    sibling_sql = """
                        SELECT content, chunk_id
                        FROM dokumen_chunk
                        WHERE dokumen_id = $1
                          AND chunk_id BETWEEN $2 AND $3
                        ORDER BY chunk_id ASC;
                    """
                    sibling_rows = await conn.fetch(
                        sibling_sql, doc_id, max(0, best_seq - 1), best_seq + 1
                    )

                    # Gabungkan sibling content
                    combined_text = "\n\n".join(
                        r["content"] for r in sibling_rows if r["content"]
                    )

                    # Fallback ke chunk tunggal jika sibling kosong
                    if not combined_text:
                        combined_text = cand["chunk_content"]

                    meta = chunk_score_map.get(doc_id, {})

                    expanded_blocks.append(
                        {
                            "id": doc_id,
                            "jenis": parent["nama_jenis"] or "N/A",
                            "judul": parent["judul"] or "Dokumen Resmi Pindad",
                            "nomor": parent["nomor"] or "N/A",
                            "halaman": cand["page"],
                            "rrf_score": cand["rrf_score"],
                            "text": combined_text,
                        }
                    )

            except Exception as e:
                logger.error(
                    f"💥 [RAG DB ERROR] Gagal ekspansi parent+sibling: {str(e)}"
                )
                return ""

        if not expanded_blocks:
            return ""

        # Deduplikasi: jika satu dokumen muncul lebih dari sekali, ambil yang rrf_score tertinggi
        seen_doc_ids = {}
        deduped_blocks = []
        for b in expanded_blocks:
            doc_id = b["id"]
            if doc_id not in seen_doc_ids or b["rrf_score"] > seen_doc_ids[doc_id]:
                seen_doc_ids[doc_id] = b["rrf_score"]
                deduped_blocks.append(b)
        expanded_blocks = deduped_blocks

        # ======================================================================
        # FASE 3: CROSS-ENCODER RE-RANKER
        # ======================================================================
        print(f"🔮 [RAG RE-RANKER] Memproses {len(expanded_blocks)} blok kandidat...")

        try:
            from backend.app.services.reranker_service import reranker_service

            corpus_texts = [b["text"] for b in expanded_blocks]
            rerank_scores = await reranker_service.compute_scores(query, corpus_texts)

            for idx, score in enumerate(rerank_scores):
                expanded_blocks[idx]["final_score"] = float(score)

            print("📈 [RAG RE-RANKER] Selesai. Menyaring passing grade...")

        except Exception as ren_err:
            logger.warning(
                f"⚠️  [RAG RERANK] Re-ranker absen atau error: {str(ren_err)}. "
                f"Fallback ke skor RRF."
            )
            for b in expanded_blocks:
                b["final_score"] = b["rrf_score"]

        expanded_blocks.sort(key=lambda x: x["final_score"], reverse=True)

        # ========================================================================
        # ASSEMBLY KONTEKS FINAL + METADATA SUMBER
        # ========================================================================
        final_contexts = []
        sources_metadata = []  # 🔥 NEW: Kumpulkan metadata untuk frontend
        inserted_count = 0

        for b in expanded_blocks:
            if inserted_count >= limit:
                break

            f_score = b.get("final_score", 0.0)

            if f_score < min_score:
                print(
                    f"🗑️  [RAG DROPPED] '{b['judul']}' dibuang "
                    f"(skor {f_score:.6f} < threshold {min_score})"
                )
                continue

            block_str = (
                f"--- DOKUMEN RUJUKAN [{inserted_count + 1}] ---\n"
                f"• Jenis Regulasi  : {b['jenis']}\n"
                f"• Judul           : {b['judul']}\n"
                f"• No. Regulasi    : {b['nomor']}\n"
                f"• Estimasi Halaman: {b['halaman']}\n"
                f"• Skor Akurasi    : {f_score:.6f}\n"
                f"• Isi Dokumen:\n{b['text']}\n"
            )
            final_contexts.append(block_str)

            # 🔥 NEW: Simpan metadata sumber untuk frontend
            sources_metadata.append({
            "id": b["id"],
            "dokumen_id": b["id"],
            "title": b["judul"],
            "filename": b["judul"],
            "nomor": b["nomor"],
            "page": b["halaman"],
            "page_number": b["halaman"],
            "jenis": b["jenis"],
            "score": f_score,
            # 🔥 Tambahkan file_path jika ada di database
            # "file_path": b.get("file_path", ""),
            # "url": f"/uploads/{b.get('file_path', '')}"
        })
        
        inserted_count += 1

        if not final_contexts:
            print("⚠️  [RAG EMPTY] Tidak ada dokumen yang lolos threshold.")
            return (
                "[PERINGATAN SISTEM]: Dokumen regulasi mengenai kueri ini TIDAK DITEMUKAN "
                "di basis data internal Pindad. "
                "Asisten WAJIB menyampaikan bahwa data tidak tersedia di RAGDB. "
                "DILARANG mengarang atau berasumsi dari pengetahuan umum!",
                []  # 🔥 Return empty sources
            )

        print(
            f"✅ [RAG COMPLETE] {len(final_contexts)} dokumen rujukan berhasil dirakit "
            f"untuk DeepSeek R1."
        )
        return "\n".join(final_contexts), sources_metadata  # 🔥 Return tuple


rag_service = RagService()
