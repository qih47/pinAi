import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_RAG_SERVICE")

# Stopwords Indonesia yang sering merusak tsquery jika ikut di-AND-kan
_STOPWORDS_ID = {
    "yang", "di", "ke", "dari", "dan", "atau", "untuk", "with", "dengan", "pada",
    "adalah", "ini", "itu", "dalam", "oleh", "juga", "sudah", "akan", "tidak",
    "ada", "saya", "anda", "bisa", "lebih", "seperti", "sebagai", "saat", "jika",
    "maka", "telas", "telah", "harus", "dapat", "agar", "bahwa", "karena", "namun",
    "namanya", "setiap", "serta", "tentang", "antara",
}

# ── THRESHOLD KONFIGURASI RE-RANKER ──────────────────────────────────────────
# BGE cross-encoder menghasilkan score 0.0 - 1.0 (setelah sigmoid)
_RERANK_RATIO = 0.15
_RERANK_FLOOR = 0.40


class RagService:
    """
    Orkestrator Advanced RAG — Hybrid Search PostgreSQL (pgvector + Full-Text Search)
    menggunakan Reciprocal Rank Fusion (RRF), ekspansi Parent-Child sesuai ERD,
    dan filtrasi via Cross-Encoder Re-ranker.
    """

    def __init__(self):
        logger.info(
            "[RAG_SERVICE_INIT] Hybrid RRF + Re-ranker Engine initialized."
        )

    def _prepare_tsquery(self, query: str) -> str:
        """
        Bersihkan query → format kompatibel to_tsquery Postgres.
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

        # AND operator: dokumen WAJIB mengandung semua token agar relevan secara keyword
        return " & ".join(f"{t}:*" for t in tokens)

    async def assemble_powerful_context(
        self, query: str, limit: int = 5, min_score: float = 0.005
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Pipeline RAG 3 fase terpadu - Mengembalikan tuple (context_string, sources_metadata)
        Memperbaiki kebocoran data dengan structural grouping per dokumen.
        """
        logger.debug(f'[RAG_SERVICE] Extracting RRF for query: "{query}"')

        # ======================================================================
        # FASE 0: LAZY IMPORT — anti-mismatch
        # ======================================================================
        try:
            from backend.app.services.rag.vector_service import vector_service
        except ImportError:
            try:
                from backend.app.services.rag.vector_service import VectorService
                vector_service = VectorService()
            except ImportError as e:
                logger.error(f"[RAG_CRITICAL_ERROR] vector_service cannot be imported: {str(e)}")
                return (
                    "[PERINGATAN SISTEM]: Terjadi kerusakan internal pada modul vector_service. "
                    "Katakan kepada user bahwa sistem sedang mengalami kendala teknis pada komponen pencarian.",
                    []
                )

        try:
            query_embedding = await vector_service.get_query_embedding(query)
        except AttributeError as ae:
            logger.error(f"[RAG_CRITICAL_ERROR] Method get_query_embedding not found: {str(ae)}")
            return "[PERINGATAN SISTEM]: Method pencarian embedding absen di backend.", []

        if not query_embedding:
            logger.error("[RAG_CRITICAL_ERROR] Failed to generate embedding from query!")
            return "", []

        if len(query.split()) < 3:
            logger.warning(f"[RAG_QUERY_WARNING] Short query: '{query}'. Tsquery might be ineffective.")

        formatted_tsquery = self._prepare_tsquery(query)
        query_vector_str = str(query_embedding)

        document_candidates: Dict[int, Dict[str, Any]] = {}

        # ======================================================================
        # FASE 1: HYBRID SEARCH + RRF di PostgreSQL (Menggabungkan pgvector + FTS)
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
                    LIMIT $3 * 4;
                """

                raw_chunks = await conn.fetch(hybrid_sql, query_vector_str, formatted_tsquery, limit)

                if not raw_chunks:
                    logger.warning("[RAG_HYBRID_WARNING] Zero match hybrid. Fallback to vector search.")
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
                        LIMIT $2 * 4;
                    """
                    raw_chunks = await conn.fetch(vector_only_sql, query_vector_str, limit)

                if not raw_chunks:
                    logger.warning("[RAG_SERVICE] Zero matches in hybrid search")
                    return "", []

                for row in raw_chunks:
                    if row["dokumen_id"] is None:
                        continue

                    doc_id = int(row["dokumen_id"])
                    rrf_score = float(row["rrf_score"])
                    chunk_seq = row["chunk_seq"] or 0
                    page_str = row["page_str"] or "1"

                    if doc_id not in document_candidates:
                        document_candidates[doc_id] = {
                            "best_chunk_seq": chunk_seq,
                            "rrf_score": rrf_score,
                            "pages": {page_str},
                            "target_seqs": {chunk_seq}
                        }
                    else:
                        document_candidates[doc_id]["pages"].add(page_str)
                        document_candidates[doc_id]["target_seqs"].add(chunk_seq)
                        if rrf_score > document_candidates[doc_id]["rrf_score"]:
                            document_candidates[doc_id]["rrf_score"] = rrf_score

            except Exception as sql_err:
                logger.error(f"[RAG_SQL_ERROR] Failed to execute Hybrid Search RRF: {str(sql_err)}")
                return "", []

        candidate_doc_ids = list(document_candidates.keys())
        if not candidate_doc_ids:
            return "", []

        # ======================================================================
        # FASE 2: PARENT-CHILD HIERARCHICAL STRUCTURE ASSEMBLY (Sesuai ERD)
        # ======================================================================
        expanded_blocks = []

        async with get_db() as conn:
            try:
                parent_sql = """
                    SELECT d.id, d.judul, d.nomor, j.nama AS nama_jenis
                    FROM dokumen d
                    LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                    WHERE d.id = ANY($1);
                """
                parent_rows = await conn.fetch(parent_sql, candidate_doc_ids)
                parent_map = {r["id"]: r for r in parent_rows}

                for doc_id, doc_info in document_candidates.items():
                    parent = parent_map.get(doc_id)
                    if not parent:
                        continue

                    seq_to_fetch = set()
                    for seq in doc_info["target_seqs"]:
                        seq_to_fetch.add(max(0, seq - 1))
                        seq_to_fetch.add(seq)
                        seq_to_fetch.add(seq + 1)

                    chunk_fetch_sql = """
                        SELECT dc.content, dc.chunk_id, ds.section_title, ds.section_type
                        FROM dokumen_chunk dc
                        LEFT JOIN dokumen_section ds ON dc.dokumen_id = ds.dokumen_id 
                            AND (dc.section_id = ds.id OR ds.id::text = dc.parent_id)
                        WHERE dc.dokumen_id = $1 AND dc.chunk_id = ANY($2)
                        ORDER BY dc.chunk_id ASC;
                    """
                    chunk_rows = await conn.fetch(chunk_fetch_sql, doc_id, list(seq_to_fetch))

                    seen_seqs = set()
                    text_segments = []
                    sections_found = set()

                    for crow in chunk_rows:
                        c_seq = crow["chunk_id"]
                        if c_seq in seen_seqs:
                            continue
                        seen_seqs.add(c_seq)

                        segment_text = ""
                        if crow["section_title"]:
                            sections_found.add(f"{crow['section_type'] or 'Bagian'} {crow['section_title']}")
                            segment_text += f"\n[Bagian: {crow['section_title']} ({crow['section_type'] or 'Regulasi'})]\n"
                        content_safe = crow["content"][:3000]
                        segment_text += content_safe
                        text_segments.append(segment_text)

                    combined_text = "\n\n".join(text_segments).strip()
                    sorted_pages = sorted(list(doc_info["pages"]))
                    sorted_sections = sorted(list(sections_found))

                    expanded_blocks.append({
                        "id": doc_id,
                        "jenis": parent["nama_jenis"] or "Regulasi Resmi",
                        "judul": parent["judul"] or "Dokumen Internal Pindad",
                        "nomor": parent["nomor"] or "N/A",
                        "halaman": ", ".join(sorted_pages),
                        "sections": sorted_sections,
                        "rrf_score": doc_info["rrf_score"],
                        "text": combined_text,
                    })

            except Exception as e:
                logger.error(f"[RAG_DB_ERROR] Failed parent-child assembly: {str(e)}")
                return "", []

        if not expanded_blocks:
            return "", []

        # ======================================================================
        # FASE 3: CROSS-ENCODER RE-RANKER FILTRATION
        # ======================================================================
        logger.debug(f"[RAG_SERVICE] Processing {len(expanded_blocks)} document blocks...")

        try:
            from backend.app.services.rag.reranker_service import reranker_service

            corpus_texts = [b["text"] for b in expanded_blocks]
            rerank_scores = await reranker_service.compute_scores(query, corpus_texts)

            for idx, score in enumerate(rerank_scores):
                expanded_blocks[idx]["final_score"] = float(score)

            logger.debug("[RAG_SERVICE] Re-ranking complete, filtering results...")

        except Exception as ren_err:
            logger.warning(
                f"[RAG_RERANK_WARNING] Re-ranker error: {str(ren_err)}. Fallback to RRF."
            )
            expanded_blocks = expanded_blocks[:2]
            for b in expanded_blocks:
                b["final_score"] = b["rrf_score"]

        # Urutkan berdasarkan skor tertinggi
        expanded_blocks.sort(key=lambda x: x["final_score"], reverse=True)

        best_score = expanded_blocks[0].get("final_score", 0.0) if expanded_blocks else 0.0
        effective_min_score = max(best_score * _RERANK_RATIO, _RERANK_FLOOR)

        logger.info(
            f"🎯 [RAG THRESHOLD] best_score={best_score:.4f} | "
            f"effective_min_score={effective_min_score:.4f} "
            f"(ratio={_RERANK_RATIO}, floor={_RERANK_FLOOR})"
        )

        # ======================================================================
        # ASSEMBLY KONTEKS FINAL + METADATA SUMBER UNTUK GEMMA & FE
        # ======================================================================
        final_contexts = []
        sources_metadata = []
        inserted_count = 0

        for b in expanded_blocks:
            if inserted_count >= limit:
                break

            f_score = b.get("final_score", 0.0)

            if f_score < effective_min_score:
                logger.debug(
                    f"[RAG_SERVICE] Dropped '{b['judul']}' (score {f_score:.4f} < {effective_min_score:.4f})"
                )
                continue

            block_str = (
                f"--- DOKUMEN RUJUKAN [{inserted_count + 1}] ---\n"
                f"• Jenis Regulasi  : {b['jenis']}\n"
                f"• Judul           : {b['judul']}\n"
                f"• No. Regulasi    : {b['nomor']}\n"
                f"• Estimasi Halaman: {b['halaman']}\n"
                f"• Skor Relevansi  : {f_score:.4f}\n"
                f"• Isi Kandungan Dokumen:\n{b['text']}\n"
            )
            final_contexts.append(block_str)

            sources_metadata.append({
                "id": b["id"],
                "dokumen_id": b["id"],
                "title": b["judul"],
                "filename": b["judul"],
                "nomor": b["nomor"],
                "page": b["halaman"],
                "page_number": b["halaman"],
                "jenis": b["jenis"],
                "sections": b.get("sections", []),
                "score": f_score,
            })

            inserted_count += 1

        if not final_contexts:
            logger.warning("[RAG_SERVICE] No documents passed threshold")
            return (
                "[PERINGATAN SISTEM]: Dokumen regulasi mengenai kueri ini TIDAK DITEMUKAN di basis data internal Pindad. "
                "Asisten WAJIB menyampaikan secara langsung bahwa data regulasi resmi tidak tersedia di RAGDB. "
                "DILARANG keras mengarang bebas atau berasumsi dari pengetahuan umum!",
                []
            )

        logger.info(
            f"[RAG_SERVICE] {len(final_contexts)} documents passed threshold (from {len(expanded_blocks)} candidates)"
        )
        return "\n".join(final_contexts), sources_metadata


rag_service = RagService()
