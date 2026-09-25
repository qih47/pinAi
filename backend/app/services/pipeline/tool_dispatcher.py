"""
CAKRA AI — Universal Tool Dispatcher (MCP-Ready Architecture)
============================================================
Pusat eksekusi tools otonom Call 2 yang modular, aman, dan non-destruktif.
Mendukung tool internal native (web_search, doc_search, python_calc) dan
siap dihubungkan ke remote MCP Server di masa depan via adapter.
"""

import os
import re
import sys
import json
import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, AsyncGenerator, Union

from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_TOOL_DISPATCHER")


@dataclass
class ToolResult:
    """Standardized MCP-Ready Tool Execution Result."""
    tool_name: str
    status: str  # "success" | "error" | "timeout"
    intent: str
    display_data: Dict[str, Any]
    llm_context: str
    error_message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TOOL: WEB SEARCH & LIVE SCRAPING
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_web_search_tool_stream(query: str, reason: str = "") -> AsyncGenerator[Union[Tuple[str, str], ToolResult], None]:
    """Eksekusi pencarian web SearXNG + Reranking + Scraping 2 tautan teratas dengan status progresif."""
    from backend.app.services.web_tools.web_search import (
        perform_web_search,
        format_search_results_for_llm,
        sanitize_web_query,
    )
    from backend.app.services.web_tools.url_reader import fetch_webpage_content

    clean_query = sanitize_web_query(query.strip()) or query.strip()
    intent_desc = reason.strip() if reason.strip() else f"Menelusuri informasi web: '{clean_query}'"
    logger.info(f"[TOOL_DISPATCHER] 🌐 Executing web_search for query: '{clean_query}'")

    yield ("Mencari di mesin pencari", "TOOL_WEBSEARCH_SEARCHING")

    try:
        raw_results = await perform_web_search(clean_query, num_results=6)
        if not raw_results:
            from backend.app.services.web_tools.web_search import simplify_search_query
            simplified_q = simplify_search_query(clean_query)
            if simplified_q and simplified_q != clean_query:
                logger.info(f"[TOOL_DISPATCHER] 🔄 Retrying web search with simplified query: '{simplified_q}'")
                yield ("Menajamkan pencarian web", "TOOL_WEBSEARCH_SIMPLIFYING")
                raw_results = await perform_web_search(simplified_q, num_results=6)

        if not raw_results:
            yield ToolResult(
                tool_name="websearch",
                status="success",
                intent=intent_desc,
                display_data={
                    "tool": "websearch",
                    "intent": intent_desc,
                    "query": clean_query,
                    "results": [],
                    "stage": "done",
                },
                llm_context=f"Tidak ditemukan hasil pencarian web yang valid untuk query: '{clean_query}'.",
            )
            return

        # Reranking jika tersedia
        yield ("Menyaring rujukan web", "TOOL_WEBSEARCH_RERANKING")
        search_results = raw_results
        try:
            from backend.app.services.rag.reranker_service import reranker_service
            corpus_texts = [f"{r.get('title', '')} {r.get('content', '')}".strip() for r in raw_results]
            scores = await reranker_service.compute_scores(clean_query, corpus_texts)
            ranked = sorted(zip(scores, raw_results), key=lambda x: x[0], reverse=True)
            search_results = [r for _, r in ranked[:4]]
        except Exception as e:
            logger.warning(f"[TOOL_DISPATCHER] Rerank fallback for websearch: {e}")
            search_results = raw_results[:4]

        # ── REALTIME PREVIEW EMISSION ──
        # Langsung emit preview hasil pencarian (URL & judul) agar widget langsung muncul di UI secara realtime!
        yield ("TOOL_PREVIEW", {
            "tool": "websearch",
            "intent": intent_desc,
            "query": clean_query,
            "results": search_results,
            "stage": "searching",
        })

        # Format teks konteks awal untuk LLM
        web_context = format_search_results_for_llm(search_results)

        # Quick scrape 2 URL teratas untuk detail mendalam
        top_urls = [r["url"] for r in search_results[:2] if r.get("url")]
        if top_urls:
            yield ("Membaca isi tautan web", "TOOL_WEBSEARCH_SCRAPING")
            async def _scrape_one(u: str) -> str:
                try:
                    c = await fetch_webpage_content(u)
                    return c[:3000] if c else ""
                except Exception:
                    return ""

            scraped_contents = await asyncio.gather(*[_scrape_one(u) for u in top_urls])
            extra_text = "\n\n".join(
                [f"--- KONTEN SITUS ({top_urls[i]}) ---\n{scraped_contents[i]}"
                 for i in range(len(top_urls)) if scraped_contents[i]]
            )
            if extra_text:
                web_context += f"\n\n=== DETAIL KONTEN WEB TERBARU ===\n{extra_text}"

        safe_web_context = (web_context[:7500] + "\n(dipotong)") if len(web_context) > 7500 else web_context

        yield ToolResult(
            tool_name="websearch",
            status="success",
            intent=intent_desc,
            display_data={
                "tool": "websearch",
                "intent": intent_desc,
                "query": clean_query,
                "results": search_results,
                "stage": "done",
            },
            llm_context=safe_web_context,
        )

    except Exception as e:
        logger.error(f"[TOOL_DISPATCHER] Error in web_search_tool: {e}", exc_info=True)
        yield ToolResult(
            tool_name="websearch",
            status="error",
            intent=intent_desc,
            display_data={"tool": "websearch", "intent": intent_desc, "query": clean_query, "results": [], "stage": "error"},
            llm_context=f"Kendala teknis saat menelusuri web: {str(e)}",
            error_message=str(e),
        )


async def execute_web_search_tool(query: str, reason: str = "") -> ToolResult:
    """Wrapper sinkronisasi tool web search untuk backward-compatibility."""
    last_res = None
    async for item in execute_web_search_tool_stream(query, reason=reason):
        if isinstance(item, ToolResult):
            last_res = item
    return last_res or ToolResult("websearch", "error", reason, {}, "Gagal mengeksekusi websearch")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TOOL: DOC SEARCH & REGULASI INTERNAL (RAG LOOKUP)
# ═══════════════════════════════════════════════════════════════════════════════

def sanitize_doc_search_query(q: str) -> str:
    """Membersihkan stop words regulasi umum yang merusak pencarian vector/BM25."""
    noise_pattern = re.compile(
        r"\b(?:sop|skep|direksi|regulasi\s+internal|dokumen\s+regulasi|aturan\s+terkait|peraturan|kebijakan|pt\s+pindad|pindad|persero)\b",
        re.IGNORECASE
    )
    cleaned = noise_pattern.sub(" ", q)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= 4 else q.strip()


async def execute_doc_search_tool_stream(
    query: str, 
    reason: str = "", 
    doc_type: str = "",
    query_judul: Optional[Union[List[str], str]] = None,
    search_tags: Optional[Union[List[str], str]] = None,
    session_uuid: Optional[str] = None,
    current_user_npp: Optional[str] = None,
    request: Optional[Any] = None,
) -> AsyncGenerator[Union[Tuple[str, str], ToolResult], None]:
    """
    Eksekusi alur RAG lengkap untuk tool docsearch:
    0. Brain-First Check: Cek ketersediaan dokumen di Memori Sesi (Brain)
    1. Call 1.1 CRAG Verifier untuk mengevaluasi Brain kandidat atau fallback ke MySQL
    2. Seleksi dokumen utama (full read PDF, max 2 jika komparatif) vs dokumen histori
    3. Ekstraksi teks fisik PDF per halaman atau gunakan cache Brain jika tersedia
    4. Simpan dokumen baru yang berhasil diekstrak ke SessionBrain
    5. BGE Cross-Encoder Reranking per halaman & Integrasi Halaman Eksplisit
    6. Tri-Window connected context expansion (±1 halaman)
    7. Perakitan konteks pasal/klausul asli untuk disuntikkan ke Call 2
    """
    from backend.app.core.paths import FILE_PERATURAN_DIR
    from backend.app.services.peraturan_service import get_candidate_documents_metadata
    from backend.app.services.pipeline.call1_crag_verifier import verify_retrieved_documents_crag, ENABLE_CALL1_1_CRAG
    from backend.app.services.rag.reranker_service import reranker_service
    from backend.app.services.pipeline.document_intelligence import (
        extract_and_ocr_document_async,
        expand_tri_window_context,
        extract_explicit_pages_from_query,
    )

    clean_query = query.strip() if query else ""
    effective_query = sanitize_doc_search_query(clean_query)
    intent_desc = reason.strip() if reason.strip() else f"Menelaah regulasi internal terkait: '{clean_query}'"

    # 1. Parsing query_judul
    query_judul_list: List[str] = []
    if isinstance(query_judul, list):
        query_judul_list = [str(x).strip() for x in query_judul if str(x).strip()]
    elif isinstance(query_judul, str) and query_judul.strip():
        if "," in query_judul:
            query_judul_list = [x.strip() for x in query_judul.split(",") if x.strip()]
        else:
            query_judul_list = [query_judul.strip()]

    if not query_judul_list:
        query_judul_list = [w for w in effective_query.split() if len(w) >= 3]
        if not query_judul_list:
            query_judul_list = [effective_query]

    # 2. Parsing search_tags
    search_tags_list: List[str] = []
    if isinstance(search_tags, list):
        search_tags_list = [str(x).strip().lower() for x in search_tags if str(x).strip()]
    elif isinstance(search_tags, str) and search_tags.strip():
        search_tags_list = [x.strip().lower() for x in search_tags.split(",") if x.strip()]

    logger.info(
        f"[TOOL_DISPATCHER] 📑 Executing full RAG doc_search: "
        f"query='{clean_query}', query_judul={query_judul_list}, search_tags={search_tags_list}, session={session_uuid}, npp={current_user_npp}"
    )

    yield ("Membuka arsip regulasi", "TOOL_DOCSEARCH_OPENING")

    try:
        # ── STEP 0: Brain-First Check (Cek Memori Sesi) ──
        brain = None
        session_brain_docs = []
        if session_uuid and current_user_npp:
            try:
                from backend.app.services.session.session_brain_service import SessionBrainService
                brain = SessionBrainService(current_user_npp, session_uuid)
                session_brain_docs = brain.list_documents()
            except Exception as e_b:
                logger.warning(f"[TOOL_DISPATCHER] Gagal inisialisasi SessionBrainService: {e_b}")

        is_brain_relevant = False
        candidate_docs = []

        if session_brain_docs and brain:
            manifest_data_preview = brain.get_manifest().get("documents", {})
            brain_tokens = []
            for b_item in session_brain_docs:
                b_id = str(b_item.get("id") or b_item.get("doc_id")) if isinstance(b_item, dict) else str(b_item)
                m_info = manifest_data_preview.get(b_id, {}) if isinstance(manifest_data_preview, dict) else {}
                if isinstance(m_info, dict):
                    brain_tokens.append(f"{m_info.get('title', '')} {m_info.get('nomor', '')}".lower())
                else:
                    brain_tokens.append(str(m_info).lower())
            brain_combined_text = " ".join(brain_tokens)

            target_keywords = set()
            for qj in query_judul_list:
                for word in str(qj or "").lower().split():
                    if len(word) >= 3 and word not in ["dokumen", "peraturan", "terkait", "surat", "tentang", "mengenai", "nomor"]:
                        target_keywords.add(word)
            for tag in search_tags_list:
                for word in str(tag or "").lower().split():
                    if len(word) >= 3:
                        target_keywords.add(word)

            if target_keywords:
                is_brain_relevant = any(kw in brain_combined_text for kw in target_keywords)
            else:
                for word in clean_query.lower().split():
                    if len(word) >= 4 and word in brain_combined_text:
                        is_brain_relevant = True
                        break

            if is_brain_relevant:
                manifest_data = brain.get_manifest().get("documents", {})
                for b_item in reversed(session_brain_docs[:2]):
                    b_id = str(b_item.get("id") or b_item.get("doc_id")) if isinstance(b_item, dict) else str(b_item)
                    m_info = manifest_data.get(b_id, {})
                    full_b_doc = brain.get_document(b_id)
                    doc_title = m_info.get("title") or (full_b_doc.get("title") if full_b_doc else "") or f"Dokumen {b_id}"
                    doc_nomor = m_info.get("nomor") or (full_b_doc.get("nomor") if full_b_doc else "")
                    doc_jenis = m_info.get("jenis") or (full_b_doc.get("jenis") if full_b_doc else "Regulasi")
                    doc_tanggal = m_info.get("tanggal") or (full_b_doc.get("tanggal") if full_b_doc else "")
                    clean_file_path = m_info.get("file_path") or (full_b_doc.get("file_path") if full_b_doc else "")

                    if (not doc_nomor or not clean_file_path) and str(b_id).isdigit():
                        try:
                            from backend.app.core.database import get_peraturan_db
                            from backend.app.services.tools.document_resolver import find_valid_pdf_file
                            async with get_peraturan_db() as conn_my:
                                async with conn_my.cursor() as cur:
                                    await cur.execute(
                                        "SELECT b.noper, k.nama_kategori, b.tanggal, b.gambar, b.gambar2, b.gambar3, b.judul "
                                        "FROM berita b "
                                        "LEFT JOIN kategori k ON b.id_kategori = k.id_kategori "
                                        "WHERE b.id_berita = %s LIMIT 1",
                                        (int(b_id),)
                                    )
                                    row = await cur.fetchone()
                                    if row:
                                        doc_nomor = row[0] or doc_nomor or ""
                                        doc_jenis = row[1] or doc_jenis or "SKEP"
                                        doc_tanggal = str(row[2]) if row[2] else (doc_tanggal or "")
                                        if not clean_file_path:
                                            clean_file_path = find_valid_pdf_file(row[3], row[4], row[5]) or ""
                                        if not doc_title or doc_title == f"Dokumen {b_id}":
                                            doc_title = row[6] or doc_title
                        except Exception as _e:
                            logger.warning(f"[TOOL_DISPATCHER] Gagal lookup noper untuk id {b_id}: {_e}")

                    # 🎯 Filter relevansi spesifik dokumen di Brain jika target_keywords ada
                    doc_ident = f"{doc_title} {doc_nomor} {b_id}".lower()
                    if target_keywords and not any(kw in doc_ident for kw in target_keywords):
                        continue

                    candidate_docs.append({
                        "id": b_id,
                        "judul": doc_title or f"Dokumen {b_id}",
                        "noper": doc_nomor or "",
                        "nomor": doc_nomor or "",
                        "score": 1.0,
                        "status_berlaku": "Berlaku",
                        "valid_file": clean_file_path,
                        "file_path": clean_file_path,
                        "filename": os.path.basename(clean_file_path) if clean_file_path else "",
                        "tanggal": doc_tanggal or "",
                        "mencabut": "",
                        "jenis": doc_jenis or "Regulasi",
                        "total_pages": m_info.get("total_pages") or (full_b_doc.get("total_pages", 1) if full_b_doc else 1),
                        "is_supplementary": False,
                        "_from_session_brain": True
                    })
                    logger.info(f"[TOOL_DISPATCHER] 🧠 [BRAIN-HIT] Dokumen aktif sesi {b_id} ('{doc_title}') disiapkan dari Brain.")

        # ── STEP 1: Call 1.1 CRAG QC Verifier (Brain Validasi / Fallback ke MySQL) ──
        crag_primary_id = None
        if candidate_docs and is_brain_relevant:
            yield ("🧠 Mengakses dokumen dari memori sesi", "BRAIN_HIT")
            # ⚡ DIRECT BRAIN HIT: Jika judul dokumen Brain sudah pasti cocok dengan keyword target,
            # lewati panggilan LLM CRAG (hemat ~4.7 detik) dan lanjut instan ke ekstraksi halaman!
            is_direct_title_hit = any(
                target_keywords and any(kw in (d.get("judul", "") + " " + d.get("noper", "")).lower() for kw in target_keywords)
                for d in candidate_docs
            )
            if is_direct_title_hit:
                crag_primary_id = candidate_docs[0]["id"]
                logger.info(f"[TOOL_DISPATCHER] ⚡ Brain Direct Hit untuk {crag_primary_id}: Relevansi judul pasti, lewati re-evaluasi CRAG LLM.")
            elif ENABLE_CALL1_1_CRAG:
                crag_eval = await verify_retrieved_documents_crag(
                    user_query=clean_query,
                    target_judul_list=query_judul_list,
                    target_tags=search_tags_list,
                    candidate_docs=candidate_docs,
                    request=request,
                    turn=1
                )
                if not crag_eval.get("is_relevant"):
                    logger.warning(
                        f"[TOOL_DISPATCHER] ⚠️ Dokumen di Brain tidak relevan menurut CRAG ({crag_eval.get('reason')}). "
                        f"Fallback otomatis ke Database MySQL..."
                    )
                    yield ("Menajamkan pencarian regulasi", "CRAG_RETRY")
                    candidate_docs = []
                else:
                    crag_primary_id = crag_eval.get("primary_doc_id")

        if not candidate_docs:
            yield ("Menelusuri regulasi", "SEARCHING_REGULATIONS")
            candidate_docs = await get_candidate_documents_metadata(
                user_message=clean_query,
                query_judul_list=query_judul_list,
                rag_queries=[clean_query],
                search_tags=search_tags_list
            ) or []

            if candidate_docs and ENABLE_CALL1_1_CRAG:
                yield ("Menilai relevansi dokumen", "TOOL_DOCSEARCH_SCORING")
                crag_eval = await verify_retrieved_documents_crag(
                    user_query=clean_query,
                    target_judul_list=query_judul_list,
                    target_tags=search_tags_list,
                    candidate_docs=candidate_docs,
                    request=request,
                    turn=1
                )
                crag_primary_id = crag_eval.get("primary_doc_id")

                if not crag_eval.get("is_relevant"):
                    suggested_qj = crag_eval.get("suggested_query_judul") or query_judul_list
                    suggested_queries = crag_eval.get("suggested_queries") or [clean_query]
                    suggested_tags = crag_eval.get("suggested_tags") or search_tags_list

                    logger.warning(
                        f"[TOOL_DISPATCHER] ⚠️ Turn 1 Call 1.1 CRAG flagged candidates as NOT RELEVANT "
                        f"({crag_eval.get('reason')}). Retrying with suggested: qj={suggested_qj}"
                    )
                    yield ("Menajamkan pencarian regulasi", "CRAG_RETRY")
                    retry_docs = await get_candidate_documents_metadata(
                        user_message=clean_query,
                        query_judul_list=suggested_qj,
                        rag_queries=suggested_queries,
                        search_tags=suggested_tags
                    )
                    if retry_docs:
                        crag_eval_t2 = await verify_retrieved_documents_crag(
                            user_query=clean_query,
                            target_judul_list=suggested_qj,
                            target_tags=suggested_tags,
                            candidate_docs=retry_docs,
                            request=request,
                            turn=2
                        )
                        candidate_docs = retry_docs
                        crag_primary_id = crag_eval_t2.get("primary_doc_id")
                        query_judul_list = suggested_qj

        if not candidate_docs:
            logger.info(f"[TOOL_DISPATCHER] ℹ️ Tidak ada kandidat dokumen untuk query: '{clean_query}'")
            yield ToolResult(
                tool_name="docsearch",
                status="success",
                intent=intent_desc,
                display_data={
                    "tool": "docsearch",
                    "intent": intent_desc,
                    "query": clean_query,
                    "documents": [],
                    "stage": "done",
                },
                llm_context=f"Tidak ditemukan dokumen atau arsip regulasi internal yang cocok dengan kata kunci: '{clean_query}'. Evaluasi apakah perlu mencari dengan kata kunci lain atau mencari informasi publik via websearch.",
            )
            return

        # ── STEP 2: Sort Candidates & Mode Komparatif (Baca Maks 2 Dokumen) ──
        is_comparative = any(k in clean_query.lower() for k in ["bandingkan", "perbandingan", "komparasi", "bedanya", "perbedaan"])
        max_full_read = 2 if (is_comparative and len(candidate_docs) > 1) else 1

        def candidate_rank_key(d):
            doc_id_str = str(d.get("id"))
            is_crag_primary = 1 if (crag_primary_id and doc_id_str == str(crag_primary_id)) else 0
            berlaku_score = 1 if d.get("status_berlaku") == "Berlaku" else 0
            target_match_score = 0.0
            d_title = (str(d.get("judul", "")) + " " + str(d.get("noper", ""))).lower()
            if query_judul_list:
                for qj in query_judul_list:
                    qj_str = str(qj or "").lower().strip()
                    if qj_str and qj_str in d_title:
                        target_match_score += 1.0
            base_score = float(d.get("score") or 0.0)
            return (is_crag_primary, berlaku_score, target_match_score, base_score)

        candidate_docs.sort(key=candidate_rank_key, reverse=True)

        full_read_docs = []
        historical_docs = []
        for doc in candidate_docs:
            is_supp = doc.get("is_supplementary", False)
            if is_supp:
                historical_docs.append(doc)
            elif len(full_read_docs) < max_full_read:
                full_read_docs.append(doc)
            else:
                historical_docs.append(doc)

        if not full_read_docs and candidate_docs:
            full_read_docs = candidate_docs[:max_full_read]
            historical_docs = candidate_docs[max_full_read:]

        # ── STEP 2.5: Emit Real-time Preview Candidates untuk UI Card ──
        preview_docs = []
        for doc in (full_read_docs + historical_docs)[:4]:
            d_id = doc.get("id") or doc.get("id_berita")
            is_brain_doc = bool(doc.get("_from_session_brain"))
            preview_docs.append({
                "id": d_id,
                "doc_id": d_id,
                "title": doc.get("title") or doc.get("judul") or "Dokumen Internal Pindad",
                "nomor": doc.get("noper") or doc.get("nomor"),
                "jenis": doc.get("jenis") or "Regulasi",
                "stataktif": doc.get("status_berlaku") or doc.get("stataktif") or "Berlaku",
                "total_pages": str(doc.get("total_pages", "")),
                "page": "",
                "page_number": "",
                "filename": doc.get("filename"),
                "file_path": doc.get("file_path") or (f"file_peraturan/{doc.get('filename')}" if doc.get("filename") else ""),
                "tanggal": doc.get("tanggal"),
                "mencabut": doc.get("mencabut", ""),
                "score": doc.get("score"),
                "cache_hit": is_brain_doc,
                "_from_session_brain": is_brain_doc,
            })

        yield ("TOOL_PREVIEW", {
            "tool": "docsearch",
            "query": clean_query,
            "intent": intent_desc or "Pencarian regulasi internal",
            "documents": preview_docs,
            "total_found": len(candidate_docs)
        })

        # ── STEP 3: PDF Extraction per Halaman & Session Brain Caching ──
        cached_docs = {}
        uncached_docs = []
        for doc in full_read_docs:
            d_key = str(doc.get("id"))
            if brain and brain.has_document(d_key):
                cached_item = brain.get_document(d_key)
                if cached_item and "text_map" in cached_item:
                    cached_docs[doc.get("id")] = cached_item
                    continue
            uncached_docs.append(doc)

        if cached_docs and not uncached_docs:
            yield ("🧠 Dari memori sesi", "BRAIN_HIT")
        elif cached_docs and uncached_docs:
            yield ("🧠 Dari memori sesi", "BRAIN_HIT")
            yield ("Memuat dokumen", "DOC_LOADING")
        else:
            yield ("Memuat dokumen", "DOC_LOADING")

        global_page_pool = []
        doc_text_maps = {}
        newly_saved_count = 0

        for doc in full_read_docs:
            doc_id = doc.get("id")
            doc_id_key = str(doc_id)
            if doc_id in cached_docs:
                text_map = cached_docs[doc_id]["text_map"]
                page_count = cached_docs[doc_id].get("total_pages", len(text_map))
                valid_file = cached_docs[doc_id].get("file_path") or doc.get("valid_file") or ""
                doc["_from_session_brain"] = True
            else:
                valid_file = doc.get("valid_file") or ""
                if not valid_file or not os.path.exists(valid_file):
                    fn = doc.get("filename")
                    if fn:
                        cand_path = os.path.join(FILE_PERATURAN_DIR, fn)
                        if os.path.exists(cand_path):
                            valid_file = cand_path
                            doc["valid_file"] = valid_file

                if not valid_file or not os.path.exists(valid_file):
                    logger.warning(f"[TOOL_DISPATCHER] ⚠️ File fisik PDF tidak ditemukan untuk Doc ID {doc_id} ('{valid_file}')")
                    continue

                cache_key = f"doc_{doc_id}"
                text_map, _, page_count = await extract_and_ocr_document_async(valid_file, cache_key=cache_key, render_images=False)
                if brain:
                    await brain.save_document(doc_id_key, {
                        "title": doc.get("judul", ""),
                        "nomor": doc.get("noper", doc.get("nomor", "")),
                        "jenis": doc.get("jenis", "Regulasi"),
                        "tanggal": doc.get("tanggal", ""),
                        "file_path": valid_file,
                        "text_map": text_map,
                        "total_pages": page_count,
                    })
                    newly_saved_count += 1

            final_pages = page_count or len(text_map) or 1
            doc["total_pages"] = final_pages
            doc_text_maps[doc_id] = text_map

            for idx, item in enumerate(text_map):
                p_val = item.get("page_num", 0)
                p_num = (p_val + 1) if p_val > 0 else (idx + 1)
                p_text = item.get("text", "")
                global_page_pool.append({
                    "page_num": p_num,
                    "page_index": idx,
                    "text": p_text,
                    "doc_id": doc_id,
                    "doc_title": doc.get("judul", ""),
                    "doc_noper": doc.get("noper", ""),
                    "doc_status": doc.get("status_berlaku", "Berlaku"),
                    "doc_tanggal": doc.get("tanggal", ""),
                    "doc_mencabut": doc.get("mencabut", ""),
                    "valid_file": valid_file,
                    "filename": doc.get("filename", ""),
                    "file_path": valid_file,
                    "jenis": doc.get("jenis", "Regulasi")
                })

        if newly_saved_count > 0:
            yield ("💾 Menyimpan ke memori", "BRAIN_SAVE")

        # ── STEP 4: Page-Level BGE Reranker & Explicit Page Extraction ──
        connected_pages_per_doc = {}
        if global_page_pool:
            yield ("Menyaring pasal relevan", "FILTERING_RELEVANT_ARTICLES")

            # Ekstrak nomor halaman eksplisit jika user menyebutkan "halaman 15" atau "hal 3"
            explicit_pages_by_doc = {}
            for d_id, t_map in doc_text_maps.items():
                exp_p = extract_explicit_pages_from_query(clean_query, total_pages=len(t_map))
                if exp_p:
                    explicit_pages_by_doc[d_id] = [p - 1 for p in exp_p if 0 <= p - 1 < len(t_map)]

            effective_page_query = f"{' '.join(query_judul_list)} {clean_query}".strip()
            page_corpus = [p["text"] if p["text"] else f"Dokumen {p['doc_title']} halaman {p['page_num']}" for p in global_page_pool]
            scores = await reranker_service.compute_scores(effective_page_query, page_corpus)

            focus_keywords = set()
            for token in effective_page_query.lower().split():
                clean_tok = re.sub(r"[^\w]", "", token)
                if len(clean_tok) >= 4 and clean_tok not in [
                    "dokumen", "peraturan", "terkait", "dalam", "surat", "nomor",
                    "tentang", "mengenai", "pindad", "apakah", "bagaimana", "adalah"
                ]:
                    focus_keywords.add(clean_tok)

            for idx, score in enumerate(scores):
                p_obj = global_page_pool[idx]
                final_score = float(score)
                p_text_lower = p_obj.get("text", "").lower()
                if focus_keywords and any(kw in p_text_lower for kw in focus_keywords):
                    final_score += 0.4
                p_obj["score"] = final_score

            global_page_pool.sort(key=lambda x: x["score"], reverse=True)
            max_seeds = 6 if is_comparative else 4
            top_seeds = [p for p in global_page_pool if p["score"] > 0.35][:max_seeds]
            if not top_seeds:
                top_seeds = global_page_pool[:min(max_seeds, len(global_page_pool))]

            seeds_by_doc = {}
            for seed in top_seeds:
                d_id = seed["doc_id"]
                if d_id not in seeds_by_doc:
                    seeds_by_doc[d_id] = []
                seeds_by_doc[d_id].append(seed["page_index"])

            # Dahulukan halaman eksplisit hasil parsing query
            for d_id, exp_indices in explicit_pages_by_doc.items():
                if exp_indices:
                    if d_id not in seeds_by_doc:
                        seeds_by_doc[d_id] = []
                    for ep in exp_indices:
                        if ep not in seeds_by_doc[d_id]:
                            seeds_by_doc[d_id].insert(0, ep)

            for d_id, seed_indices in seeds_by_doc.items():
                t_map = doc_text_maps.get(d_id, [])
                expanded_indices = expand_tri_window_context(seed_indices, t_map, total_pages=len(t_map))
                max_exp = 16 if is_comparative else 12
                if len(expanded_indices) > max_exp:
                    expanded_indices = expanded_indices[:max_exp]
                connected_pages_per_doc[d_id] = expanded_indices

            yield ("Membaca pasal terpilih", "READING_SELECTED_ARTICLES")

        # ── STEP 5: Assembling Rich Context (Klausul & Pasal Asli) ──
        context_blocks = []
        for doc in full_read_docs:
            d_id = doc.get("id")
            p_indices = connected_pages_per_doc.get(d_id, [])
            t_map = doc_text_maps.get(d_id, [])

            if p_indices and t_map:
                doc_page_texts = []
                for p_idx in p_indices:
                    page_text = t_map[p_idx]["text"] if p_idx < len(t_map) else ""
                    doc_page_texts.append(f"[HALAMAN {p_idx + 1}]\n{page_text}")

                meta_header = (
                    f"--- DOKUMEN: {doc.get('judul', '')} (HALAMAN TERHUBUNG: {', '.join(str(p+1) for p in p_indices)}) ---\n"
                    f"Status Berlaku: {doc.get('status_berlaku', 'Berlaku')}\n"
                    f"Tanggal Terbit: {doc.get('tanggal', '-')}\n"
                    f"Nomor Regulasi: {doc.get('noper', doc.get('nomor', '-'))}\n"
                    f"Mencabut: {doc.get('mencabut', '-')}\n"
                )
                full_doc_content = "\n\n".join(doc_page_texts)
                context_blocks.append(f"{meta_header}Isi Klausul/Pasal:\n{full_doc_content}\n-------------------")
            else:
                isi_fallback = (doc.get("raw_isi") or doc.get("isi_snippet") or "").strip()
                context_blocks.append(
                    f"--- DOKUMEN: {doc.get('judul', '')} ---\n"
                    f"Nomor: {doc.get('noper', doc.get('nomor', '-'))}\n"
                    f"Status: {doc.get('status_berlaku', 'Berlaku')}\n"
                    f"Ringkasan:\n{isi_fallback or 'Dokumen terverifikasi di arsip Pindad.'}\n-------------------"
                )

        if historical_docs:
            hist_lines = []
            for doc in historical_docs[:10]:
                status_label = doc.get("status_berlaku", "Tidak Diketahui")
                tgl_main = doc.get("tanggal", "-")[:10] if doc.get("tanggal") else "-"
                hist_lines.append(f"• [{doc.get('noper', 'N/A')}] {doc.get('judul', '')} (Tanggal: {tgl_main} | Status: {status_label})")

            context_blocks.append(
                "--- DOKUMEN REFERENSI / RIWAYAT SEJARAH ---\n" + "\n".join(hist_lines)
            )

        rag_context = "\n\n".join(context_blocks)

        # ── STEP 6: Format Dokumen untuk Card UI Frontend ──
        formatted_docs = []
        for doc in (full_read_docs + historical_docs)[:4]:
            d_id = doc.get("id") or doc.get("id_berita")
            p_indices = connected_pages_per_doc.get(d_id, [])
            page_str = ", ".join(str(p + 1) for p in p_indices) if p_indices else (doc.get("page") or doc.get("page_number") or "")
            is_brain_doc = bool(doc.get("_from_session_brain") or (d_id in cached_docs))
            formatted_docs.append({
                "id": d_id,
                "doc_id": d_id,
                "title": doc.get("title") or doc.get("judul") or "Dokumen Internal Pindad",
                "nomor": doc.get("noper") or doc.get("nomor"),
                "jenis": doc.get("jenis") or "Regulasi",
                "stataktif": doc.get("status_berlaku") or doc.get("stataktif") or "Berlaku",
                "total_pages": str(doc.get("total_pages", "")),
                "page": page_str,
                "page_number": page_str,
                "filename": doc.get("filename"),
                "file_path": doc.get("file_path") or (f"file_peraturan/{doc.get('filename')}" if doc.get("filename") else None),
                "score": round(float(doc.get("score", 0.0)), 3) if doc.get("score") else None,
                "cache_hit": is_brain_doc,
                "_from_session_brain": is_brain_doc,
            })

        # Batas kapasitas konteks LLM aman (~8.750 - 9.000 token, di bawah 10k token)
        safe_rag_context = (rag_context[:35000] + "\n(dipotong demi efisiensi context)") if len(rag_context) > 35000 else (rag_context or f"Tidak ditemukan rincian klausul untuk topik: '{clean_query}'.")

        yield ToolResult(
            tool_name="docsearch",
            status="success",
            intent=intent_desc,
            display_data={
                "tool": "docsearch",
                "intent": intent_desc,
                "query": clean_query,
                "documents": formatted_docs,
                "stage": "done",
            },
            llm_context=safe_rag_context,
        )

    except Exception as e:
        logger.error(f"[TOOL_DISPATCHER] Error in full doc_search_tool pipeline: {e}", exc_info=True)
        yield ToolResult(
            tool_name="docsearch",
            status="error",
            intent=intent_desc,
            display_data={"tool": "docsearch", "intent": intent_desc, "query": clean_query, "documents": [], "stage": "error"},
            llm_context=f"Kendala saat menelaah dokumen regulasi internal: {str(e)}",
            error_message=str(e),
        )


async def execute_doc_search_tool(
    query: str, 
    reason: str = "", 
    doc_type: str = "",
    query_judul: Optional[Union[List[str], str]] = None,
    search_tags: Optional[Union[List[str], str]] = None,
    session_uuid: Optional[str] = None,
    current_user_npp: Optional[str] = None,
    request: Optional[Any] = None,
) -> ToolResult:
    """Wrapper sinkronisasi tool doc search untuk backward-compatibility."""
    last_res = None
    async for item in execute_doc_search_tool_stream(
        query, 
        reason=reason, 
        doc_type=doc_type,
        query_judul=query_judul,
        search_tags=search_tags,
        session_uuid=session_uuid,
        current_user_npp=current_user_npp,
        request=request,
    ):
        if isinstance(item, ToolResult):
            last_res = item
    return last_res or ToolResult("docsearch", "error", reason, {}, "Gagal mengeksekusi docsearch")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TOOL: PYTHON CALCULATOR (ISOLATED SANDBOX)
# ═══════════════════════════════════════════════════════════════════════════════

_FORBIDDEN_PYTHON_TOKENS = {
    "import os", "import sys", "import subprocess", "import socket", "import shutil",
    "import pty", "import requests", "import urllib", "__import__", "eval(", "exec(",
    "open(", "compile(", "globals()", "locals()", "builtins", "rmtree", "system("
}

def execute_python_calc_sync(code: str) -> Tuple[bool, str]:
    """Menjalankan kode kalkulator di subprocess terisolasi dengan timeout 3 detik."""
    # 1. Validasi keamanan sintaks
    code_lower = code.lower()
    for forbidden in _FORBIDDEN_PYTHON_TOKENS:
        if forbidden in code_lower:
            return False, f"Akses ke modul berbahaya '{forbidden}' diblokir oleh Security Firewall demi keselamatan sistem."

    # 2. Siapkan wrapper kode dengan batas memori dan output terarah
    runner_script = (
        "import math, statistics\n"
        "try:\n"
        + "\n".join("    " + line for line in code.splitlines())
        + "\nexcept Exception as e:\n"
        "    print(f'Error Eksekusi: {e}')\n"
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", runner_script],
            capture_output=True,
            text=True,
            timeout=3.5,
        )
        output = proc.stdout.strip()
        if not output and proc.stderr.strip():
            output = proc.stderr.strip()
        return True, output if output else "Eksekusi berhasil tanpa output cetak (print)."
    except subprocess.TimeoutExpired:
        return False, "Eksekusi kode melebihi batas waktu (timeout 3 detik)."
    except Exception as e:
        return False, f"Gagal mengeksekusi kalkulasi: {str(e)}"


async def execute_python_calc_tool_stream(code: str, reason: str = "") -> AsyncGenerator[Union[Tuple[str, str], ToolResult], None]:
    """Eksekusi kalkulasi matematis presisi via Python Sandbox dengan status progresif."""
    clean_code = code.strip()
    intent_desc = reason.strip() if reason.strip() else "Melakukan kalkulasi matematis presisi via Python Sandbox"
    logger.info(f"[TOOL_DISPATCHER] ⚡ Executing python_calc (len: {len(clean_code)})")

    yield ("Menjalankan komputasi", "TOOL_CALC_RUNNING")
    success, output = await asyncio.to_thread(execute_python_calc_sync, clean_code)

    yield ToolResult(
        tool_name="python_calc",
        status="success" if success else "error",
        intent=intent_desc,
        display_data={
            "tool": "python_calc",
            "intent": intent_desc,
            "code": clean_code,
            "output": output,
            "error": None if success else output,
            "stage": "done" if success else "error",
        },
        llm_context=f"--- HASIL EKSEKUSI PYTHON SANDBOX ---\nOutput:\n{output}",
        error_message=None if success else output,
    )


async def execute_python_calc_tool(code: str, reason: str = "") -> ToolResult:
    """Wrapper asinkron untuk tool kalkulator Python."""
    last_res = None
    async for item in execute_python_calc_tool_stream(code, reason=reason):
        if isinstance(item, ToolResult):
            last_res = item
    return last_res or ToolResult("python_calc", "error", reason, {}, "Gagal mengeksekusi python_calc")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TOOL: URL READER & SUB-LINK DISCOVERY (URLFETCH)
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_url_fetch_tool_stream(urls: Any, reason: str = "", user_query: str = "") -> AsyncGenerator[Union[Tuple[str, str], ToolResult], None]:
    """Eksekusi pembacaan konten halaman web langsung via url_reader dengan status progresif."""
    from backend.app.services.web_tools.url_reader import (
        extract_url_display_info,
        fetch_webpage_with_discovery,
        extract_urls_from_text,
    )

    target_urls: List[str] = []
    if isinstance(urls, list):
        for item in urls:
            if isinstance(item, str):
                target_urls.extend(extract_urls_from_text(item) if "http" in item else [item])
    elif isinstance(urls, str):
        if urls.strip().startswith("[") and urls.strip().endswith("]"):
            try:
                raw_list = json.loads(urls)
                if isinstance(raw_list, list):
                    for item in raw_list:
                        target_urls.extend(extract_urls_from_text(str(item)))
            except Exception:
                target_urls = extract_urls_from_text(urls)
        else:
            target_urls = extract_urls_from_text(urls)

    # Filter URL valid
    target_urls = [u.strip() for u in target_urls if u.startswith("http://") or u.startswith("https://")]
    # Deduplicate
    seen_urls = set()
    clean_target_urls = []
    for u in target_urls:
        if u not in seen_urls:
            seen_urls.add(u)
            clean_target_urls.append(u)

    intent_desc = reason.strip() if reason.strip() else f"Membaca konten dari {len(clean_target_urls)} tautan web"
    logger.info(f"[TOOL_DISPATCHER] 🔗 Executing urlfetch for URLs: {clean_target_urls}")

    if not clean_target_urls:
        yield ToolResult(
            tool_name="urlfetch",
            status="error",
            intent=intent_desc,
            display_data={
                "tool": "urlfetch",
                "nodes": [],
                "fetching": None,
                "activity": intent_desc,
            },
            llm_context="Tidak ditemukan URL web yang valid dalam pemanggilan alat urlfetch.",
            error_message="No valid URLs provided",
        )
        return

    # ── REALTIME PREVIEW EMISSION ──
    # Langsung emit preview target URLs agar widget timeline langsung muncul di UI secara realtime!
    initial_nodes = []
    for u in clean_target_urls:
        d_info = extract_url_display_info(u)
        initial_nodes.append({
            "title": d_info.get("title") or u,
            "domain": d_info.get("domain") or "",
            "url": u
        })

    yield ("TOOL_PREVIEW", {
        "tool": "urlfetch",
        "nodes": initial_nodes,
        "fetching": clean_target_urls[0] if clean_target_urls else None,
        "activity": intent_desc,
        "stage": "fetching",
    })

    yield ("Mengunduh konten tautan", "TOOL_URLFETCH_DOWNLOADING")

    collected_nodes = []
    url_contexts = ""
    for u in clean_target_urls:
        display_info = extract_url_display_info(u)
        content, sub_nodes = await fetch_webpage_with_discovery(u, user_query=user_query or reason)
        if content:
            url_contexts += f"\n\n==== ISI WEB: {u} ====\n\n{content}\n\n========================\n"
        if sub_nodes:
            collected_nodes.extend(sub_nodes)
        else:
            collected_nodes.append({
                "title": display_info["title"],
                "domain": display_info["domain"],
                "url": u
            })

    yield ("Mengekstrak isi halaman", "TOOL_URLFETCH_PARSING")

    activity_text = intent_desc or "Menelaah referensi tautan web"
    safe_url_context = (url_contexts[:7500] + "\n(dipotong demi efisiensi)") if len(url_contexts) > 7500 else url_contexts
    has_content = bool(url_contexts and url_contexts.strip())

    yield ToolResult(
        tool_name="urlfetch",
        status="success" if has_content else "error",
        intent=intent_desc,
        display_data={
            "tool": "urlfetch",
            "nodes": collected_nodes,
            "fetching": None,
            "activity": activity_text
        },
        llm_context=f"=== KONTEN DARI TAUTAN WEB ===\n{safe_url_context}" if has_content else f"Gagal mengunduh atau konten kosong untuk tautan: {clean_target_urls}",
        error_message=None if has_content else "Halaman web kosong atau tidak dapat diakses",
    )


async def execute_url_fetch_tool(urls: Any, reason: str = "", user_query: str = "") -> ToolResult:
    """Wrapper sinkronisasi tool urlfetch untuk backward-compatibility."""
    last_res = None
    async for item in execute_url_fetch_tool_stream(urls, reason=reason, user_query=user_query):
        if isinstance(item, ToolResult):
            last_res = item
    return last_res or ToolResult("urlfetch", "error", reason, {}, "Gagal mengeksekusi urlfetch")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TOOL: GEOCODING & MAP SEARCH (OPENSTREETMAP NOMINATIM)
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_map_search_tool(location: str, reason: str = "") -> ToolResult:
    """Eksekusi pencarian titik koordinat dan fasilitas via geocode_osm."""
    from backend.app.services.tools.geocoding import geocode_osm

async def execute_map_search_tool_stream(location: str, reason: str = "") -> AsyncGenerator[Union[Tuple[str, str], ToolResult], None]:
    """Eksekusi pencarian geocoding OpenStreetMap Nominatim dengan status progresif."""
    from backend.app.services.web_tools.geocoding import geocode_osm

    clean_loc = location.strip()
    intent_desc = reason.strip() if reason.strip() else f"Mencari titik lokasi / fasilitas: '{clean_loc}'"
    logger.info(f"[TOOL_DISPATCHER] 🌍 Executing map_search for location: '{clean_loc}'")

    yield ("Menelusuri koordinat peta", "TOOL_MAP_SEARCHING")

    try:
        coords = await geocode_osm(clean_loc)
        if coords:
            division_info = f"\nDivisi/Fasilitas: {coords['division']}" if coords.get("division") else ""
            map_info = (
                f"Hasil pencarian lokasi untuk '{clean_loc}':\n"
                f"Latitude: {coords['lat']}\n"
                f"Longitude: {coords['lng']}\n"
                f"Alamat Terdaftar: {coords['name']}{division_info}\n"
            )
            yield ToolResult(
                tool_name="map_search",
                status="success",
                intent=intent_desc,
                display_data={
                    "tool": "map_search",
                    "intent": intent_desc,
                    "location": clean_loc,
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                    "name": coords["name"],
                    "division": coords.get("division"),
                    "stage": "done"
                },
                llm_context=f"[TOOL: GEOCODING_RESULT]\n{map_info}",
            )
        else:
            yield ToolResult(
                tool_name="map_search",
                status="error",
                intent=intent_desc,
                display_data={"tool": "map_search", "intent": intent_desc, "location": clean_loc, "stage": "not_found"},
                llm_context=f"Lokasi atau fasilitas '{clean_loc}' tidak ditemukan dalam peta OpenStreetMap.",
                error_message="Location not found"
            )
    except Exception as e:
        logger.error(f"[TOOL_DISPATCHER] Error in map_search_tool: {e}", exc_info=True)
        yield ToolResult(
            tool_name="map_search",
            status="error",
            intent=intent_desc,
            display_data={"tool": "map_search", "intent": intent_desc, "location": clean_loc, "stage": "error"},
            llm_context=f"Kendala teknis saat mencari lokasi: {str(e)}",
            error_message=str(e)
        )


async def execute_map_search_tool(location: str, reason: str = "") -> ToolResult:
    """Wrapper sinkronisasi tool map search untuk backward-compatibility."""
    last_res = None
    async for item in execute_map_search_tool_stream(location, reason=reason):
        if isinstance(item, ToolResult):
            last_res = item
    return last_res or ToolResult("map_search", "error", reason, {}, "Gagal mengeksekusi map_search")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. MASTER DISPATCHER (MCP-READY HUB)
# ═══════════════════════════════════════════════════════════════════════════════

async def dispatch_agentic_tool_stream(
    tool_name: str, 
    payload_str: Union[str, Dict[str, Any]],
    session_uuid: Optional[str] = None,
    current_user_npp: Optional[str] = None,
    request: Optional[Any] = None,
) -> AsyncGenerator[Union[Tuple[str, Any], ToolResult], None]:
    """
    Pusat parsing dan delegasi panggilan tool bertahap (progressive status streaming).
    Menerima nama tool dan payload, memancarkan (status_text, status_key) secara dinamis,
    lalu diakhiri dengan yield ToolResult.
    """
    tool_clean = tool_name.strip().lower()
    if isinstance(payload_str, dict):
        parsed_json = payload_str
        raw_str = json.dumps(payload_str)
    else:
        raw_str = (payload_str or "").strip()
        parsed_json: Dict[str, Any] = {}
        try:
            parsed_json = json.loads(raw_str)
        except Exception:
            q_match = re.search(r'["\'](?:query|location|url|urls|q)["\']\s*:\s*(?:\[([^\]]+)\]|["\']([^"\']+)["\'])', raw_str)
            if q_match:
                parsed_json["query"] = q_match.group(1) or q_match.group(2)
            r_match = re.search(r'["\'](?:reason|intent)["\']\s*:\s*["\']([^"\']+)["\']', raw_str)
            if r_match:
                parsed_json["reason"] = r_match.group(1)

    query_val = parsed_json.get("query") or parsed_json.get("q") or raw_str.replace("{", "").replace("}", "").strip()
    reason_val = parsed_json.get("reason") or parsed_json.get("intent") or ""

    if tool_clean in ("websearch", "web_search"):
        async for item in execute_web_search_tool_stream(query_val, reason=reason_val):
            yield item

    elif tool_clean in ("docsearch", "doc_search", "rag_search", "rag"):
        doc_type_val = parsed_json.get("doc_type") or ""
        q_judul_val = parsed_json.get("query_judul")
        s_tags_val = parsed_json.get("search_tags") or parsed_json.get("tags")
        async for item in execute_doc_search_tool_stream(
            query_val, 
            reason=reason_val, 
            doc_type=doc_type_val,
            query_judul=q_judul_val,
            search_tags=s_tags_val,
            session_uuid=session_uuid,
            current_user_npp=current_user_npp,
            request=request,
        ):
            yield item

    elif tool_clean in ("urlfetch", "url_fetch", "read_url", "fetch_url"):
        urls_val = parsed_json.get("urls") or parsed_json.get("url") or query_val
        async for item in execute_url_fetch_tool_stream(urls_val, reason=reason_val):
            yield item

    elif tool_clean in ("map_search", "map", "geocode", "geocoding"):
        loc_val = parsed_json.get("location") or parsed_json.get("lokasi") or query_val
        async for item in execute_map_search_tool_stream(loc_val, reason=reason_val):
            yield item

    elif tool_clean in ("python_calc", "python", "calc", "calculator"):
        code_val = parsed_json.get("code") or raw_str
        async for item in execute_python_calc_tool_stream(code_val, reason=reason_val):
            yield item

    else:
        logger.warning(f"[TOOL_DISPATCHER] Unknown tool requested: '{tool_clean}'")
        yield ToolResult(
            tool_name=tool_clean,
            status="error",
            intent=f"Percobaan memanggil tool tidak dikenal '{tool_clean}'",
            display_data={"tool": tool_clean, "stage": "error"},
            llm_context=f"Tool '{tool_clean}' tidak tersedia dalam sistem CAKRA AI.",
            error_message=f"Tool '{tool_clean}' not found",
        )


async def dispatch_agentic_tool(tool_name: str, payload_str: Union[str, Dict[str, Any]]) -> ToolResult:
    """Wrapper asinkron untuk tool dispatcher langsung (backward-compatible)."""
    last_res = None
    async for item in dispatch_agentic_tool_stream(tool_name, payload_str):
        if isinstance(item, ToolResult):
            last_res = item
    return last_res or ToolResult(tool_name, "error", "", {}, f"Tool '{tool_name}' execution failed")
