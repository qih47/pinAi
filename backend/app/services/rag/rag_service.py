"""
RAG Service — Sprint 3
================================

Perubahan dari Sprint 2:
  1. HARD_FLOOR dinaikkan dari 0.05 → 0.55
     (BGE sigmoid output: 0.5 = tidak yakin, bukan relevan)
  2. MAX_DOCS_TO_LLM = 3 — cap maksimum dokumen ke LLM
  3. Score Exposure tetap ada: TINGGI/SEDANG/RENDAH
  4. Threshold SEDANG redefined: >= 0.55 (bukan 0.3)

Model: mxbai-embed-large (1024d) + BGE Cross-Encoder Re-ranker
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from backend.app.core.database import get_db, get_peraturan_db

logger = logging.getLogger("CAKRA_RAG_SERVICE")

_STOPWORDS_ID = {
    "yang", "di", "ke", "dari", "dan", "atau", "untuk", "with", "dengan", "pada",
    "adalah", "ini", "itu", "dalam", "oleh", "juga", "sudah", "akan", "tidak",
    "ada", "saya", "anda", "bisa", "lebih", "seperti", "sebagai", "saat", "jika",
    "maka", "telas", "telah", "harus", "dapat", "agar", "bahwa", "karena", "namun",
    "namanya", "setiap", "serta", "tentang", "antara",
}

# ── SPRINT 3: THRESHOLD REALISTIS UNTUK BGE SIGMOID OUTPUT ───────────────────
# BGE CrossEncoder pakai sigmoid → output 0.0-1.0
# 0.5 = model tidak yakin (netral), BUKAN relevan
# Dokumen dianggap relevan hanya jika BGE cukup yakin: >= 0.51
HARD_FLOOR = 0.45

# Cap maksimum dokumen yang dikirim ke LLM — 10 optimal untuk akurasi dan performa TTFT
MAX_DOCS_TO_LLM = 10


def _get_score_label(score: float) -> str:
    """Konversi skor BGE sigmoid ke label human-readable."""
    if score >= 0.75:
        return "TINGGI"
    elif score >= 0.55:
        return "SEDANG"
    else:
        return "RENDAH"


# Kata-kata prosedural regulasi dan boilerplate yang sering menjadi noise pencarian FTS/Dense
_PROCEDURAL_NOISE = {
    "pasal", "ayat", "huruf", "angka", "nomor", "no", "tentang", "ketentuan",
    "aturan", "peraturan", "berapa", "bagaimana", "apakah", "jatah", "terkait",
    "mengenai", "berdasarkan", "menurut", "dalam", "pada", "oleh", "bagi",
    "untuk", "syarat", "tata", "cara", "pedoman", "standar", "adalah", "yaitu",
    "pindad", "pt", "persero", "pkb", "skep", "sop", "ik", "se", "dokumen"
}


class RagService:
    """
    Orkestrator Advanced RAG — Hybrid Search PostgreSQL (pgvector + FTS)
    menggunakan RRF, Parent-Child expansion, dan Cross-Encoder Re-ranker.

    Sprint 3: Hard Floor 0.55 + MAX_DOCS_TO_LLM cap
    """

    def __init__(self):
        logger.info("[RAG_SERVICE_INIT] Hybrid RRF + Re-ranker Engine initialized (Sprint 3).")

    def _prepare_tsquery(self, query: str) -> str:
        cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in query)
        raw_tokens = [
            t.lower()
            for t in cleaned.split()
            if t and t.lower() not in _STOPWORDS_ID and len(t) > 1
        ]

        if not raw_tokens:
            return "pindad"

        # Prioritaskan kata substantif (buang procedural noise)
        substantive_tokens = [t for t in raw_tokens if t not in _PROCEDURAL_NOISE]
        tokens = substantive_tokens if substantive_tokens else raw_tokens

        # Ambil hingga 10 kata kunci substantif tanpa memotong secara sembrono
        tokens = tokens[:10]
        return " | ".join(f"{t}:*" for t in tokens)

    async def assemble_powerful_context(
        self, query: str, limit: int = 5, min_score: float = HARD_FLOOR,
        allowed_access_tiers: Optional[List[str]] = None,
        target_doc_ids: Optional[List[int]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Pipeline RAG 3 fase terpadu dengan dukungan tiering akses (INTERNAL vs EXTERNAL)
        serta anchoring dokumen target (target_doc_ids).
        Sprint 3: min_score default = HARD_FLOOR (0.45), cap MAX_DOCS_TO_LLM=10.
        """
        logger.debug(f'[RAG_SERVICE] Extracting RRF for query: "{query}" | Tiers: {allowed_access_tiers}')

        # ======================================================================
        # FASE 0: LAZY IMPORT
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

        # Bersihkan noise korporat/boilerplate agar embedding berfokus pada topik substantif
        embed_tokens = [
            w for w in query.split()
            if w.lower() not in _PROCEDURAL_NOISE and len(w) > 1
        ]
        effective_embed_query = " ".join(embed_tokens) if len(embed_tokens) >= 2 else query

        try:
            query_embedding = await vector_service.get_query_embedding(effective_embed_query)
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
        # FASE 0: Q2Q SEMANTIC MATCHING (Pencocokan Pertanyaan Alami via rag_document_questions)
        # ======================================================================
        synt_qa_matches = []
        synt_target_doc_ids = set()

        async with get_db() as conn_qa:
            try:
                qa_sql = """
                    SELECT
                        q.id,
                        q.source_id AS dokumen_id,
                        q.generated_question,
                        q.answer,
                        q.page_range,
                        d.judul,
                        d.nomor,
                        1.0 - (q.embedding <=> $1::vector) AS similarity
                    FROM rag_document_questions q
                    JOIN dokumen d ON q.source_id = d.id
                    WHERE ($2::int[] IS NULL OR q.source_id = ANY($2))
                    ORDER BY q.embedding <=> $1::vector
                    LIMIT 4;
                """
                qa_rows = await conn_qa.fetch(qa_sql, query_vector_str, target_doc_ids)
                for qr in qa_rows:
                    sim = float(qr["similarity"]) if qr["similarity"] is not None else 0.0
                    if sim >= 0.82:
                        synt_qa_matches.append(dict(qr))
                        synt_target_doc_ids.add(int(qr["dokumen_id"]))
                if synt_qa_matches:
                    logger.info(
                        f"[RAG_SERVICE] 🎯 [Q2Q HIT] Menemukan {len(synt_qa_matches)} QA cocok dari 183k pertanyaan "
                        f"(Top Score: {synt_qa_matches[0]['similarity']:.4f} | Dokumen {synt_qa_matches[0]['dokumen_id']}: '{synt_qa_matches[0]['judul'][:30]}...')"
                    )
            except Exception as e_qa:
                logger.warning(f"[RAG_SERVICE] ⚠️ Q2Q pre-matching pass skipped: {e_qa}")

        # ======================================================================
        # FASE 1: HYBRID SEARCH + RRF (Perluasan pool kandidat ke 150)
        # ======================================================================
        async with get_db() as conn:
            try:
                hybrid_sql = """
                    WITH vector_search AS (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS rank
                        FROM dokumen_chunk
                        WHERE ($4::text[] IS NULL OR access_tier = ANY($4))
                          AND ($5::int[] IS NULL OR dokumen_id = ANY($5))
                        ORDER BY embedding <=> $1::vector
                        LIMIT $3 * 30
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
                          AND ($4::text[] IS NULL OR access_tier = ANY($4))
                          AND ($5::int[] IS NULL OR dokumen_id = ANY($5))
                        ORDER BY ts_rank_cd(
                            to_tsvector('indonesian', content),
                            to_tsquery('indonesian', $2)
                        ) DESC
                        LIMIT $3 * 30
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
                        COALESCE(NULLIF(NULLIF(dc.page_number, '0'), ''), '1') AS page_str
                    FROM ranked_candidates rc
                    INNER JOIN dokumen_chunk dc ON rc.chunk_id = dc.id
                    WHERE ($4::text[] IS NULL OR dc.access_tier = ANY($4))
                      AND ($5::int[] IS NULL OR dc.dokumen_id = ANY($5))
                    ORDER BY rc.rrf_score DESC
                    LIMIT $3 * 8;
                """

                raw_chunks = await conn.fetch(hybrid_sql, query_vector_str, formatted_tsquery, limit, allowed_access_tiers, target_doc_ids)

                if not raw_chunks:
                    logger.warning("[RAG_HYBRID_WARNING] Zero match hybrid. Fallback to vector search.")
                    vector_only_sql = """
                        SELECT
                            dc.id AS chunk_id,
                            1.0 / (60.0 + ROW_NUMBER() OVER (ORDER BY dc.embedding <=> $1::vector)) AS rrf_score,
                            dc.dokumen_id,
                            dc.content AS chunk_content,
                            dc.chunk_id AS chunk_seq,
                            COALESCE(NULLIF(NULLIF(dc.page_number, '0'), ''), '1') AS page_str
                        FROM dokumen_chunk dc
                        WHERE ($3::text[] IS NULL OR dc.access_tier = ANY($3))
                          AND ($4::int[] IS NULL OR dc.dokumen_id = ANY($4))
                        ORDER BY dc.embedding <=> $1::vector
                        LIMIT $2 * 4;
                    """
                    raw_chunks = await conn.fetch(vector_only_sql, query_vector_str, limit, allowed_access_tiers, target_doc_ids)

                if not raw_chunks:
                    logger.warning("[RAG_SERVICE] Zero matches in hybrid search")
                    return "", []

                for row in raw_chunks:
                    if row["dokumen_id"] is None:
                        continue

                    doc_id = int(row["dokumen_id"])
                    rrf_score = float(row["rrf_score"])
                    chunk_db_id = int(row["chunk_id"])
                    page_str = row["page_str"] or "1"

                    # Q2Q Boost: jika dokumen ini juga terverifikasi di rag_document_questions, berikan boost
                    q2q_boost = 0.015 if doc_id in synt_target_doc_ids else 0.0
                    boosted_score = rrf_score + q2q_boost

                    if doc_id not in document_candidates:
                        document_candidates[doc_id] = {
                            "best_chunk_seq": chunk_db_id,
                            "rrf_score": boosted_score,
                            "pages": {page_str},
                            "target_chunk_ids": {chunk_db_id}
                        }
                    else:
                        document_candidates[doc_id]["pages"].add(page_str)
                        document_candidates[doc_id]["target_chunk_ids"].add(chunk_db_id)
                        if boosted_score > document_candidates[doc_id]["rrf_score"]:
                            document_candidates[doc_id]["rrf_score"] = boosted_score

            except Exception as sql_err:
                logger.error(f"[RAG_SQL_ERROR] Failed to execute Hybrid Search RRF: {str(sql_err)}")
                return "", []

        candidate_doc_ids = list(document_candidates.keys())
        if not candidate_doc_ids:
            return "", []

        # ======================================================================
        # FASE 2: PARENT-CHILD HIERARCHICAL STRUCTURE ASSEMBLY
        # ======================================================================
        expanded_blocks = []

        async with get_db() as conn:
            try:
                parent_sql = """
                    SELECT d.id, d.judul, d.nomor, d.filename, d.tanggal, j.nama AS nama_jenis
                    FROM dokumen d
                    LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                    WHERE d.id = ANY($1);
                """
                parent_rows = await conn.fetch(parent_sql, candidate_doc_ids)
                parent_map = {r["id"]: dict(r) for r in parent_rows}
                
                # Fetch status berlaku dan filename asli dari MySQL berdasarkan NOMOR
                try:
                    nomors = [r["nomor"] for r in parent_rows if r["nomor"]]
                    if nomors:
                        async with get_peraturan_db() as p_conn:
                            async with p_conn.cursor() as p_cur:
                                format_strings = ','.join(['%s'] * len(nomors))
                                await p_cur.execute(
                                    f"SELECT noper, gambar, gambar2, gambar3, stataktif, mencabut "
                                    f"FROM berita WHERE noper IN ({format_strings})", 
                                    tuple(nomors)
                                )
                                peraturan_rows = await p_cur.fetchall()
                                
                                import os
                                PERATURAN_DIR = "/home/qisthi/pinAi/file_peraturan"
                                
                                mysql_map = {}
                                for prow in peraturan_rows:
                                    noper = prow[0]
                                    gambar1 = prow[1]
                                    gambar2 = prow[2]
                                    gambar3 = prow[3]
                                    stataktif = prow[4]
                                    mencabut = prow[5]
                                    
                                    total_pages = 0
                                    valid_file = None
                                    for file_name in [gambar1, gambar2, gambar3]:
                                        if file_name and isinstance(file_name, str) and file_name.lower().endswith(".pdf"):
                                            abs_path = os.path.join(PERATURAN_DIR, file_name)
                                            if os.path.exists(abs_path):
                                                valid_file = file_name
                                                # NOTE: fitz.open() dihapus dari sini karena membuka PDF secara sinkron
                                                # untuk menghitung jumlah halaman di dalam loop pencarian RAG sangat lambat
                                                # dan memblokir event loop.
                                                break
                                                
                                    if noper:
                                        # Use lower() for case-insensitive matching between MySQL and Postgres
                                        mysql_map[noper.lower()] = (valid_file, stataktif, mencabut, total_pages)
                                
                                for pid, pdata in parent_map.items():
                                    nomor = pdata.get("nomor")
                                    if nomor and nomor.lower() in mysql_map:
                                        mysql_fname, stataktif, mencabut, total_pages = mysql_map[nomor.lower()]
                                        pdata["mysql_filename"] = mysql_fname
                                        pdata["total_pages"] = total_pages
                                        if stataktif == "batal":
                                            pdata["status_berlaku"] = "Dicabut"
                                        elif stataktif == "obsolete":
                                            pdata["status_berlaku"] = "Tidak Berlaku"
                                        else:
                                            pdata["status_berlaku"] = "Berlaku"
                                        pdata["mencabut"] = mencabut
                                    else:
                                        pdata["mysql_filename"] = None
                                        pdata["status_berlaku"] = "Berlaku"
                                        pdata["mencabut"] = None
                except Exception as e:
                    logger.error(f"[RAG_SERVICE] Failed fetching stataktif from MySQL: {e}")


                for doc_id, doc_info in document_candidates.items():
                    parent = parent_map.get(doc_id)
                    if not parent:
                        continue

                    chunk_ids_to_fetch = set()
                    cids = sorted(list(doc_info.get("target_chunk_ids", [])))
                    if cids:
                        for cid in cids:
                            # Setiap target chunk diperluas secara kontinu (-3 sampai +8)
                            # agar mencakup seluruh klausul dalam bab terkait (misal: pasal cuti 22 s/d 27)
                            for offset in range(-3, 8):
                                if cid + offset >= 1:
                                    chunk_ids_to_fetch.add(cid + offset)

                    chunk_fetch_sql = """
                        SELECT dc.id, dc.content, dc.chunk_id, dc.page_number, ds.section_title, ds.section_type
                        FROM dokumen_chunk dc
                        LEFT JOIN dokumen_section ds ON dc.dokumen_id = ds.dokumen_id
                            AND (dc.section_id = ds.id OR ds.id::text = dc.parent_id)
                        WHERE dc.dokumen_id = $1 AND dc.id = ANY($2)
                        ORDER BY dc.id ASC;
                    """
                    chunk_rows = await conn.fetch(chunk_fetch_sql, doc_id, list(chunk_ids_to_fetch))

                    seen_ids = set()
                    text_segments = []
                    sections_found = set()

                    for crow in chunk_rows:
                        c_id = crow["id"]
                        if c_id in seen_ids:
                            continue
                        seen_ids.add(c_id)

                        cp_str = str(crow["page_number"] or "").strip()
                        if cp_str and cp_str not in ["0", "0.0", "null", "None"]:
                            doc_info["pages"].add(cp_str)

                        segment_text = ""
                        if crow["section_title"]:
                            sections_found.add(f"{crow['section_type'] or 'Bagian'} {crow['section_title']}")
                            segment_text += f"\n[Bagian: {crow['section_title']} ({crow['section_type'] or 'Regulasi'})]\n"
                        content_safe = crow["content"][:3000]
                        segment_text += content_safe
                        text_segments.append(segment_text)

                    combined_text = "\n\n".join(text_segments).strip()
                    
                    cleaned_pages = []
                    for p in doc_info["pages"]:
                        p_str = str(p).strip()
                        if not p_str or p_str in ["0", "0.0", "null", "None", ""]:
                            cleaned_pages.append("1")
                        else:
                            cleaned_pages.append(p_str)
                    
                    sorted_pages = sorted(list(set(cleaned_pages)))
                    sorted_sections = sorted(list(sections_found))

                    expanded_blocks.append({
                        "id": doc_id,
                        "jenis": parent["nama_jenis"] or "Regulasi Resmi",
                        "judul": parent["judul"] or "Dokumen Internal Pindad",
                        "nomor": parent["nomor"] or "N/A",
                        "mysql_filename": parent.get("mysql_filename"),
                        "total_pages": parent.get("total_pages", ""),
                        "halaman": ", ".join(sorted_pages),
                        "sections": sorted_sections,
                        "rrf_score": doc_info["rrf_score"],
                        "text": combined_text,
                        "status_berlaku": parent.get("status_berlaku", "Berlaku"),
                        "tanggal": str(parent.get("tanggal")) if parent.get("tanggal") else "Tidak diketahui",
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
                base_score = float(score)
                doc_status = expanded_blocks[idx].get("status_berlaku", "Berlaku")
                if doc_status == "Berlaku":
                    final_score = min(1.0, base_score + 0.05)
                elif doc_status in ["Tidak Berlaku", "Dicabut"]:
                    final_score = max(0.0, base_score - 0.15)
                else:
                    final_score = base_score
                expanded_blocks[idx]["final_score"] = final_score
                expanded_blocks[idx]["raw_bge_score"] = base_score

            logger.debug("[RAG_SERVICE] Re-ranking complete, applying hard floor filter...")

        except Exception as ren_err:
            logger.warning(
                f"[RAG_RERANK_WARNING] Re-ranker error: {str(ren_err)}. Fallback to RRF."
            )
            expanded_blocks = expanded_blocks[:2]
            for b in expanded_blocks:
                base_score = float(b["rrf_score"])
                doc_status = b.get("status_berlaku", "Berlaku")
                if doc_status in ["Tidak Berlaku", "Dicabut"]:
                    b["final_score"] = max(0.0, base_score - 0.15)
                else:
                    b["final_score"] = base_score

        # Urutkan berdasarkan skor tertinggi
        expanded_blocks.sort(key=lambda x: x["final_score"], reverse=True)

        # ── SPRINT 3: LOG SEMUA SKOR KANDIDAT (buat tuning) ──────────────────
        logger.info(
            f"🎯 [RAG THRESHOLD] hard_floor={HARD_FLOOR} | "
            f"candidates={len(expanded_blocks)} | "
            f"best_score={expanded_blocks[0]['final_score']:.4f}"
        )
        for idx, b in enumerate(expanded_blocks):
            passed = "✅ PASS" if b["final_score"] >= HARD_FLOOR else "❌ DROP"
            status_tag = b.get("status_berlaku", "Berlaku")
            logger.info(
                f"   [{passed}] #{idx+1} '{b['nomor']}' ({status_tag}) | Score={b['final_score']:.4f} (raw={b.get('raw_bge_score', b['final_score']):.4f})"
            )

        # ======================================================================
        # ASSEMBLY KONTEKS FINAL + SCORE EXPOSURE
        # ======================================================================
        final_contexts = []
        sources_metadata = []
        inserted_count = 0

        for b in expanded_blocks:
            # Cap maksimum dokumen ke LLM
            if inserted_count >= MAX_DOCS_TO_LLM:
                logger.debug(
                    f"[RAG_SERVICE] Cap reached ({MAX_DOCS_TO_LLM}), "
                    f"dropping '{b['judul']}' (score {b['final_score']:.4f})"
                )
                break

            f_score = b.get("final_score", 0.0)
            best_score = expanded_blocks[0].get("final_score", 0.0) if expanded_blocks else 0.0
            # Dynamic Margin Pruning: jika dokumen teratas kuat (>= 0.55),
            # pangkas dokumen yang skornya drop > 0.003 dari best_score agar dokumen marjinal/asing tidak menyusup
            dynamic_floor = max(HARD_FLOOR, best_score - 0.003) if best_score >= 0.55 else HARD_FLOOR

            if f_score < dynamic_floor:
                logger.debug(
                    f"[RAG_SERVICE] Dropped '{b['judul']}' "
                    f"(score {f_score:.4f} < dynamic floor {dynamic_floor:.4f})"
                )
                continue

            score_label = _get_score_label(f_score)
            status_berlaku = b.get("status_berlaku", "Berlaku")
            tanggal = b.get("tanggal", "Tidak diketahui")

            block_str = (
                f"[DOKUMEN {inserted_count + 1}] Tingkat Relevansi: {score_label} (Skor: {f_score:.2f})\n"
                f"ID Dokumen: {b['id']}\n"
                f"Status Berlaku: {status_berlaku}\n"
                f"Tanggal Terbit: {tanggal}\n"
                f"Jenis Regulasi: {b['jenis']}\n"
                f"Judul: {b['judul']}\n"
                f"No. Regulasi: {b['nomor']}\n"
                f"Estimasi Halaman: {b['halaman']}\n"
                f"Isi Kandungan Dokumen:\n{b['text']}\n"
            )
            final_contexts.append(block_str)

            # Ambil filename hanya jika ada kecocokan di MySQL
            filename_val = b.get("mysql_filename")
            if filename_val:
                file_path_val = f"file_peraturan/{filename_val}"
            else:
                filename_val = None
                file_path_val = None

            sources_metadata.append({
                "id": b["id"],
                "dokumen_id": b["id"],
                "title": b["judul"],
                "filename": filename_val,
                "file_path": file_path_val,
                "nomor": b["nomor"],
                "page": b["halaman"],
                "page_number": b["halaman"],
                "total_pages": b.get("total_pages", ""),
                "jenis": b["jenis"],
                "sections": b.get("sections", []),
                "score": f_score,
                "score_label": score_label,
                "stataktif": b.get("status_berlaku", "Berlaku"),
            })

            inserted_count += 1

        if not final_contexts:
            logger.warning(
                f"[RAG_SERVICE] No documents passed hard floor {HARD_FLOOR}. "
                f"Top score was {expanded_blocks[0]['final_score']:.4f} — "
                f"consider lowering HARD_FLOOR if this is expected."
            )
            return (
                "[PERINGATAN SISTEM]: Dokumen regulasi mengenai kueri ini TIDAK DITEMUKAN di basis data internal Pindad. "
                "Asisten WAJIB menyampaikan secara langsung bahwa data regulasi resmi tidak tersedia di RAGDB. "
                "DILARANG keras mengarang bebas atau berasumsi dari pengetahuan umum!",
                []
            )

        qa_summary_block = ""
        if synt_qa_matches:
            qa_lines = ["[RINGKASAN INTISARI REGULASI TERKAIT (TANYA-JAWAB RESMI)]"]
            for m in synt_qa_matches[:2]:
                q_text = m.get("generated_question", "")
                a_text = m.get("answer", "")
                p_text = m.get("page_range", "")
                j_text = m.get("judul", "")
                qa_lines.append(f"• Dokumen: {j_text} (Estimasi Halaman: {p_text})")
                qa_lines.append(f"  Tanya: {q_text}")
                qa_lines.append(f"  Intisari: {a_text}")
            qa_summary_block = "\n".join(qa_lines) + "\n\n"

        # ======================================================================
        # FASE 4: KNOWLEDGE GRAPH CONTEXT ENRICHMENT (GRAPH RAG)
        # ======================================================================
        graph_summary_block = ""
        try:
            from backend.app.services.rag.graph_retriever import graph_retriever
            passed_doc_ids = [s["id"] for s in sources_metadata if "id" in s]
            if passed_doc_ids:
                graph_summary_block = await graph_retriever.retrieve_graph_context(
                    doc_ids=passed_doc_ids,
                    query=query,
                    max_relations=6
                )
        except Exception as e_graph:
            logger.warning(f"[RAG_SERVICE] ⚠️ Graph context extraction skipped: {e_graph}")

        logger.info(
            f"[RAG_SERVICE] {len(final_contexts)} documents passed "
            f"(hard_floor={HARD_FLOOR}, cap={MAX_DOCS_TO_LLM}, "
            f"from {len(expanded_blocks)} candidates)"
        )
        prefix_blocks = []
        if qa_summary_block:
            prefix_blocks.append(qa_summary_block.strip())
        if graph_summary_block:
            prefix_blocks.append(graph_summary_block.strip())

        full_prefix = ("\n\n".join(prefix_blocks) + "\n\n") if prefix_blocks else ""
        full_context_text = full_prefix + "\n".join(final_contexts)
        return full_context_text, sources_metadata


rag_service = RagService()