import logging
import json
import asyncio
import os
import re
import time
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.paths import FILE_PERATURAN_DIR
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.peraturan_service import _find_valid_pdf_file
from backend.app.services.pipeline.modes.mode_utils import (
    select_call2_module, 
    get_module_config, 
    build_call2_system_prompt,
    sanitize_history_for_rag,
    sanitize_history_for_pronoun
)

logger = logging.getLogger("MODE_DOCUMENTS")


class ModeDocuments:
    """
    Mode Documents: Deep RAG Executor.
    """
    async def execute(
        self,
        user_message: str,
        chat_history: List[ChatMessageSchema],
        is_thinking: bool,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_isolation: Optional[Dict[str, Any]] = None,
        routing_data: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        employee_name: str = "Pegawai",
        current_user_npp: Optional[str] = None,
        session_uuid: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        logger.info("[MODE_DOCUMENTS] Starting execution")
        t_mode_docs_start = time.perf_counter()
        
        # ── Step 1: Query Generation via Call 1 (Sudah dieksekusi di mode_hub) ────
        # Kita hanya perlu membaca hasil dari routing_data yang sudah diisi oleh ModeHub
        if not routing_data:
            routing_data = {}
            
        # Ambil hasil rumusan query cerdas, kalau gagal fallback ke user_message
        rag_queries = routing_data.get("queries") 
        if not rag_queries:
            rag_queries = [user_message]
            
        # (Dihapus: Logika penggabungan enrichment_str ke rag_queries[0] karena merusak natural language untuk pgvector/BGE reranker)
        
        query_judul_list = routing_data.get("query_judul", [])
        
        rag_context = None
        rag_sources = None

        # ── Step 2: Tiered Cascade Search (Sequential Waterfall) ────────────────────
        should_run_rag = routing_data.get("need_rag", True)
        is_chitchat_msg = routing_data.get("is_chitchat", False) or routing_data.get("is_greeting", False)

        rag_context = None
        rag_sources = []
        judul_context = ""
        ocr_attachments = []
        judul_sources = []
        community_context = ""
        query_judul_str = ""

        if not should_run_rag:
            logger.info("[MODE_DOCUMENTS] 💬 need_rag=False terdeteksi di mode documents -> Lewati pencarian RAG & FTS!")
        else:
            from backend.app.services.peraturan_service import get_candidate_documents_metadata
            from backend.app.services.rag.reranker_service import reranker_service
            from backend.app.services.pipeline.document_intelligence import (
                extract_and_ocr_document_async,
                expand_tri_window_context,
                extract_explicit_pages_from_query
            )
            
            query_judul_list = routing_data.get("query_judul") or []
            query_judul_str = " ".join(query_judul_list) if isinstance(query_judul_list, list) else str(query_judul_list)
            
            # ─────────────────────────────────────────────────────────────────
            # TIER 1: Progressive Document Stepper & Global Page-Level Reranking
            # ─────────────────────────────────────────────────────────────────
            # 1A. Brain-First Check: Cek ketersediaan dokumen di Memori Sesi (Brain)
            brain = None
            session_brain_docs = []
            if session_uuid and current_user_npp:
                from backend.app.services.session.session_brain_service import SessionBrainService
                brain = SessionBrainService(current_user_npp, session_uuid)
                session_brain_docs = brain.list_documents()

            # 🧠 SMART RELEVANCE GATEKEEPER UNTUK SESSION BRAIN:
            # Periksa apakah dokumen di Brain masih cocok dengan yang dicari pengguna saat ini.
            # Jika user menanyakan regulasi baru (Topic Shift, misal di Brain ada PKB tapi user ganti fokus ke Urusan Dalam),
            # JANGAN biarkan Brain membajak sesi, langsung turun ke Global Database RAG!
            is_brain_relevant = True
            iso_id = ""
            iso_title = ""
            iso_nomor = ""
            if context_isolation and isinstance(context_isolation, dict):
                iso_id = str(context_isolation.get("isolated_doc_id") or context_isolation.get("id_dokumen") or "")
                iso_title = str(context_isolation.get("title") or context_isolation.get("doc_title") or "").strip().lower()
                iso_nomor = str(context_isolation.get("nomor") or "").strip().lower()

            if session_brain_docs:
                manifest_data_preview = brain.get_manifest().get("documents", {}) if brain else {}
                brain_tokens = []
                brain_ids = set()
                for b_item in session_brain_docs:
                    b_id = str(b_item.get("id") or b_item.get("doc_id")) if isinstance(b_item, dict) else str(b_item)
                    brain_ids.add(b_id)
                    m_info = manifest_data_preview.get(b_id, {}) if isinstance(manifest_data_preview, dict) else {}
                    if isinstance(m_info, dict):
                        brain_tokens.append(f"{m_info.get('title', '')} {m_info.get('nomor', '')}".lower())
                    else:
                        brain_tokens.append(str(m_info).lower())
                brain_combined_text = " ".join(brain_tokens)

                # Jika ada context isolation eksplisit, verifikasi apakah dokumen di Brain cocok dengan target isolasi
                if iso_id or iso_title or iso_nomor:
                    matched_iso = False
                    if iso_id and iso_id in brain_ids:
                        matched_iso = True
                    elif iso_nomor and any(iso_nomor in bt for bt in brain_tokens):
                        matched_iso = True
                    elif iso_title and any(iso_title in bt for bt in brain_tokens):
                        matched_iso = True

                    if not matched_iso:
                        is_brain_relevant = False
                        logger.info(
                            f"[MODE_DOCUMENTS] 🔄 Context isolation doc mismatch: Brain has {brain_ids} ('{brain_combined_text[:60]}') "
                            f"but user isolated doc is id='{iso_id}', title='{iso_title}', nomor='{iso_nomor}'. Bypassing Brain -> Global RAG."
                        )
                else:
                    target_keywords = set()
                    for qj in query_judul_list:
                        for word in str(qj or "").lower().split():
                            if len(word) >= 3 and word not in ["dokumen", "peraturan", "terkait", "surat", "tentang", "mengenai", "nomor"]:
                                target_keywords.add(word)
                    active_search_tags = routing_data.get("search_tags", [])
                    for tag in active_search_tags:
                        for word in str(tag or "").lower().split():
                            if len(word) >= 3:
                                target_keywords.add(word)

                    if target_keywords:
                        is_brain_relevant = any(kw in brain_combined_text for kw in target_keywords)
                        if not is_brain_relevant:
                            logger.info(
                                f"[MODE_DOCUMENTS] 🔄 Brain docs mismatch: Brain has '{brain_combined_text[:80]}' "
                                f"but user targets '{target_keywords}'. Falling back to Global RAG."
                            )

            candidate_docs = []

            if session_brain_docs and is_brain_relevant:
                yield format_sse(status="🧠 Mengakses dokumen dari memori sesi", event_type=SSEEventType.STATUS)
                manifest_data = brain.get_manifest().get("documents", {}) if brain else {}
                
                selected_b_items = []
                for b_item in reversed(session_brain_docs):
                    b_id = str(b_item.get("id") or b_item.get("doc_id")) if isinstance(b_item, dict) else str(b_item)
                    if iso_id:
                        if b_id == iso_id:
                            selected_b_items = [b_item]
                            break
                    else:
                        selected_b_items.append(b_item)
                        if len(selected_b_items) >= 2:  # Maksimal 2 dokumen aktif sesi jika tanpa isolasi
                            break

                if not selected_b_items and session_brain_docs:
                    selected_b_items = [session_brain_docs[-1]]

                for b_item in selected_b_items:
                    b_id = str(b_item.get("id") or b_item.get("doc_id")) if isinstance(b_item, dict) else str(b_item)
                    m_info = manifest_data.get(b_id, {})
                    full_b_doc = brain.get_document(b_id) if brain else None
                    doc_title = m_info.get("title") or (full_b_doc.get("title") if full_b_doc else "") or f"Dokumen {b_id}"
                    doc_nomor = m_info.get("nomor") or (full_b_doc.get("nomor") if full_b_doc else "")
                    doc_jenis = m_info.get("jenis") or (full_b_doc.get("jenis") if full_b_doc else "")
                    doc_tanggal = m_info.get("tanggal") or (full_b_doc.get("tanggal") if full_b_doc else "")
                    clean_file_path = m_info.get("file_path") or (full_b_doc.get("file_path") if full_b_doc else "")
                    if clean_file_path and not os.path.exists(clean_file_path):
                        clean_file_path = ""

                    # Lookup MySQL berita jika nomor, jenis, atau file_path belum tersimpan di Brain
                    if (not doc_nomor or not doc_jenis or doc_jenis == "Regulasi" or not clean_file_path) and str(b_id).isdigit():
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
                            logger.warning(f"[MODE_DOCUMENTS] Gagal lookup noper/jenis untuk id {b_id}: {_e}")

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
                        "jenis": doc_jenis or "SKEP",
                        "total_pages": m_info.get("total_pages") or (full_b_doc.get("total_pages", 1) if full_b_doc else 1),
                        "is_supplementary": False,
                        "_from_session_brain": True
                    })
                    logger.info(f"[MODE_DOCUMENTS] 🧠 [BRAIN-HIT] Dokumen aktif sesi {b_id} ('{doc_title}', {doc_nomor}) digunakan dari Brain.")
            else:
                yield format_sse(status="🔍 Menelusuri regulasi", status_key="SEARCHING_REGULATIONS", event_type=SSEEventType.STATUS)
                search_tags = routing_data.get("search_tags", [])
                logger.info(f"[MODE_DOCUMENTS] [TIER 1] Fetching candidate documents for query_judul: {query_judul_list} | search_tags: {search_tags}")
                candidate_docs = await get_candidate_documents_metadata(user_message, query_judul_list, rag_queries=rag_queries, search_tags=search_tags) or []

            # ⚡ CALL 1.1 CRAG VERIFIER (2-Turn Quality Control Gatekeeper)
            # Wajib mengevaluasi kandidat dokumen, baik yang bersumber dari Memori Sesi (Brain) maupun Database!
            from backend.app.services.pipeline.call1_crag_verifier import verify_retrieved_documents_crag, ENABLE_CALL1_1_CRAG
            search_tags = routing_data.get("search_tags", [])

            crag_primary_id = None
            crag_reference_ids = []
            if candidate_docs and ENABLE_CALL1_1_CRAG and not iso_id:
                # ── TURN 1: Validasi Awal (Kandidat Brain / MySQL) ─────────────────────────
                crag_eval_t1 = await verify_retrieved_documents_crag(
                    user_query=user_message,
                    target_judul_list=query_judul_list,
                    target_tags=search_tags,
                    candidate_docs=candidate_docs,
                    request=request,
                    turn=1,
                )
                crag_primary_id = crag_eval_t1.get("primary_doc_id")
                crag_reference_ids = crag_eval_t1.get("reference_doc_ids", [])

                if not crag_eval_t1.get("is_relevant"):
                    logger.warning(
                        f"[MODE_DOCUMENTS] ⚠️ Turn 1 Call 1.1 CRAG flagged candidates as NOT RELEVANT ({crag_eval_t1.get('reason')}). "
                        f"Running 1x targeted re-search with QC suggestions..."
                    )
                    yield format_sse(status="🔄 Menajamkan pencarian regulasi", status_key="CRAG_RETRY", event_type=SSEEventType.STATUS)

                    # Simpan cadangan kandidat awal jika retry DB tidak membuahkan hasil
                    initial_candidates = list(candidate_docs)
                    from_brain = any(doc.get("_from_session_brain") for doc in candidate_docs)
                    if from_brain:
                        logger.info("[MODE_DOCUMENTS] 🗑️ Rejecting stale Brain candidates for this query, switching to fresh Database search.")
                        candidate_docs = []

                    retry_qj = crag_eval_t1.get("suggested_query_judul") or query_judul_list
                    retry_tags = crag_eval_t1.get("suggested_tags") or search_tags
                    retry_queries = crag_eval_t1.get("suggested_queries") or rag_queries

                    retry_docs = await get_candidate_documents_metadata(
                        user_message,
                        retry_qj,
                        rag_queries=retry_queries,
                        search_tags=retry_tags
                    )

                    if retry_docs:
                        # ── TURN 2: Validasi Hasil Retry Pencarian ─────────────────────────
                        crag_eval_t2 = await verify_retrieved_documents_crag(
                            user_query=user_message,
                            target_judul_list=retry_qj,
                            target_tags=retry_tags,
                            candidate_docs=retry_docs,
                            request=request,
                            turn=2,
                        )
                        logger.info(
                            f"[MODE_DOCUMENTS] Turn 2 Call 1.1 CRAG result: is_relevant={crag_eval_t2.get('is_relevant')} | "
                            f"primary_doc_id={crag_eval_t2.get('primary_doc_id')} | refs={crag_eval_t2.get('reference_doc_ids')} | "
                            f"reason: {crag_eval_t2.get('reason')}"
                        )
                        # Gunakan kandidat hasil pencarian ulang
                        candidate_docs = retry_docs
                        crag_primary_id = crag_eval_t2.get("primary_doc_id")
                        crag_reference_ids = crag_eval_t2.get("reference_doc_ids", [])
                    else:
                        logger.info("[MODE_DOCUMENTS] ℹ️ Re-search did not return new docs, retaining initial candidates as best-effort.")
                        candidate_docs = initial_candidates


            if candidate_docs:
                # ── SPLIT: Dokumen Utama (Full PDF Read) vs Referensi/Historis (Ringkasan Saja) ──────
                # Cek apakah query user meminta perbandingan eksplisit antar dokumen
                is_comparative_query = bool(
                    routing_data.get("is_comparative") or
                    any(k in user_message.lower() for k in ["bandingkan", "perbandingan", "komparasi", "bedanya", "perbedaan"])
                )
                max_full_read = 2 if (is_comparative_query and len(candidate_docs) > 1) else 1

                # Urutkan kandidat: Dokumen primer hasil CRAG di paling atas, lalu Berlaku, lalu skor
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
                    status = doc.get("status_berlaku", "")

                    if is_supp:
                        historical_docs.append(doc)
                    elif len(full_read_docs) < max_full_read:
                        # Ambil dokumen aktif paling relevan (1 dokumen utama jika non-komparatif, maks 2 jika komparatif)
                        full_read_docs.append(doc)
                    else:
                        historical_docs.append(doc)

                # Fallback aman jika full_read_docs kosong
                if not full_read_docs and candidate_docs:
                    non_supp = [d for d in candidate_docs if not d.get("is_supplementary", False)]
                    full_read_docs = non_supp[:1] if non_supp else candidate_docs[:1]
                    historical_docs = [d for d in candidate_docs if d not in full_read_docs]

                doc_count = len(full_read_docs)
                hist_count = len(historical_docs)
                logger.info(
                    f"[MODE_DOCUMENTS] 📄 Seleksi Dokumen: {doc_count} Dokumen Utama (Full PDF Read) | "
                    f"{hist_count} Dokumen Referensi/Histori (Metadata Saja). Comparative={is_comparative_query}"
                )

                yield format_sse(status=f"📑 Menemukan {doc_count + hist_count} dokumen", status_key="DOCS_FOUND", event_type=SSEEventType.STATUS)
                
                global_page_pool = []
                all_source_metadata = []
                doc_text_maps = {}  # doc_id -> list of {"page_num": int, "text": str}
                
                cached_docs = {}
                uncached_docs = []
                for doc in full_read_docs:
                    d_key = str(doc.get("id"))
                    if brain and brain.has_document(d_key):
                        cached_item = brain.get_document(d_key)
                        if cached_item and "text_map" in cached_item:
                            cached_docs[doc["id"]] = cached_item
                            continue
                    uncached_docs.append(doc)

                # Emit status cerdas secara real-time tanpa penundaan artifisial
                if cached_docs and not uncached_docs:
                    yield format_sse(status="🧠 Dari memori sesi", status_key="BRAIN_HIT", event_type=SSEEventType.STATUS)
                elif cached_docs and uncached_docs:
                    yield format_sse(status="🧠 Dari memori sesi", status_key="BRAIN_HIT", event_type=SSEEventType.STATUS)
                    yield format_sse(status="📄 Memuat dokumen", status_key="DOC_LOADING", event_type=SSEEventType.STATUS)
                else:
                    yield format_sse(status="📄 Memuat dokumen", status_key="DOC_LOADING", event_type=SSEEventType.STATUS)

                newly_saved_count = 0
                for doc in full_read_docs:
                    doc_id = doc.get("id")
                    doc_id_key = str(doc_id)
                    valid_file = doc.get("valid_file") or ""

                    if doc_id in cached_docs:
                        text_map = cached_docs[doc_id]["text_map"]
                        page_count = cached_docs[doc_id].get("total_pages", len(text_map))
                    else:
                        if not valid_file or not os.path.exists(valid_file):
                            continue
                        cache_key = f"doc_{doc_id}"
                        text_map, _, page_count = await extract_and_ocr_document_async(valid_file, cache_key=cache_key, render_images=False)
                        if brain and should_run_rag and not is_chitchat_msg:
                            await brain.save_document(doc_id_key, {
                                "title": doc.get("judul", ""),
                                "text_map": text_map,
                                "total_pages": page_count,
                            })
                            newly_saved_count += 1

                    doc_text_maps[doc_id] = text_map



                    
                    for idx, item in enumerate(text_map):
                        p_val = item.get("page_num", 0)
                        p_num = (p_val + 1) if p_val > 0 else (idx + 1)
                        p_text = item.get("text", "")
                        global_page_pool.append({
                            "page_num": p_num,
                            "page_index": idx,
                            "text": p_text,
                            "doc_id": doc.get("id"),
                            "doc_title": doc.get("judul", ""),
                            "doc_noper": doc.get("noper", ""),
                            "doc_status": doc.get("status_berlaku", "Berlaku"),
                            "doc_tanggal": doc.get("tanggal", ""),
                            "doc_mencabut": doc.get("mencabut", ""),
                            "valid_file": valid_file,
                            "filename": doc.get("filename", ""),
                            "file_path": doc.get("file_path", valid_file),
                            "jenis": doc.get("jenis", "Regulasi")
                        })
                        
                    # Hindari duplikasi judul di nomor regulasi:
                    clean_nomor = str(doc.get("nomor") or doc.get("noper") or "").strip()
                    if clean_nomor and clean_nomor.lower() == str(doc.get("judul", "")).strip().lower():
                        clean_nomor = ""

                    final_total_pages = page_count if page_count > 0 else (len(text_map) if len(text_map) > 0 else 1)
                    is_brain_compact = bool(doc.get("_from_session_brain") and len(text_map) <= 30)

                    all_source_metadata.append({
                        "id": doc.get("id"),
                        "title": doc.get("judul", ""),
                        "document_title": doc.get("judul", ""),
                        "filename": doc.get("filename", ""),
                        "file_path": doc.get("file_path", valid_file),
                        "jenis": doc.get("jenis") or ("SKEP" if clean_nomor and clean_nomor.lower().startswith("skep") else "Regulasi"),
                        "nomor": clean_nomor,
                        "page_number": "" if is_brain_compact else "1",
                        "total_pages": str(final_total_pages),
                        "cache_hit": bool(doc.get("_from_session_brain")),
                        "score_label": "BRAIN_SESSION_ACTIVE" if doc.get("_from_session_brain") else "HYBRID_RERANKER",
                        "score": doc.get("score", 1.0),
                        "raw_judul": doc.get("judul", ""),
                        "raw_tag": doc.get("raw_tag", ""),
                        "raw_isi": doc.get("raw_isi", ""),
                        "tgl_obs": doc.get("tgl_obs", "")
                    })

                if newly_saved_count > 0:
                    yield format_sse(status="💾 Menyimpan ke memori", status_key="BRAIN_SAVE", event_type=SSEEventType.STATUS)
                
                # 1B. Historical docs — TIDAK baca PDF, buat daftar ringkas saja

                # Daftar ini akan disuntikkan ke judul_context sebagai blok referensi silang
                historical_summary_lines = []
                for doc in historical_docs[:15]:  # Maksimal 15 histori/tambahan
                    status_label = doc.get("status_berlaku", "Tidak Diketahui")
                    tgl_main = doc.get("tanggal", "-")[:10] if doc.get("tanggal") else "-"
                    tgl_obs_val = str(doc.get("tgl_obs") or "").strip()
                    obs_str = f" | Obsolete/Dicabut: {tgl_obs_val[:10]}" if tgl_obs_val and tgl_obs_val not in ("0000-00-00", "-", "None") else ""
                    
                    hist_line = (
                        f"• {doc.get('noper', 'N/A')} | {doc.get('judul', '')[:80]} | "
                        f"Tanggal: {tgl_main}{obs_str} | Status: {status_label}"
                    )
                    historical_summary_lines.append(hist_line)
                    # Tambahkan ke source metadata juga (untuk kartu sumber di UI)
                    all_source_metadata.append({
                        "id": doc.get("id"),
                        "title": doc.get("judul", ""),
                        "document_title": doc.get("judul", ""),
                        "filename": doc.get("filename"),
                        "file_path": doc.get("file_path"),
                        "jenis": doc.get("jenis", "Regulasi"),
                        "nomor": doc.get("noper", ""),
                        "page_number": "1",
                        "total_pages": "",
                        "cache_hit": False,
                        "score_label": "HISTORICAL_REF",
                        "score": doc.get("score", 0.5),
                        "raw_judul": doc.get("judul", ""),
                        "raw_tag": doc.get("raw_tag", ""),
                        "raw_isi": doc.get("raw_isi", ""),
                        "tgl_obs": doc.get("tgl_obs", "")
                    })

                
                if historical_summary_lines:
                    logger.info(f"[MODE_DOCUMENTS] 📋 {len(historical_summary_lines)} historical docs → ringkasan saja (skip PDF read)")

                    
                # 2. Global Cross-Document Page-Level Reranking & Tri-Window Context Expansion
                if global_page_pool:
                    total_p_count = len(global_page_pool)
                    yield format_sse(status="🎯 Menyaring pasal relevan", status_key="FILTERING_RELEVANT_ARTICLES", event_type=SSEEventType.STATUS)
                    
                    # Multi-Query gabungan untuk BGE page scoring: padukan query cerdas Call 1 dan pertanyaan user
                    rag_queries_clean = [q.strip() for q in rag_queries if q and q.strip()]
                    effective_page_query = " ".join(dict.fromkeys(rag_queries_clean + [user_message]))
                    logger.info(f"[MODE_DOCUMENTS] Scoring {len(global_page_pool)} pages using combined effective query: '{effective_page_query}'")

                    # BGE Scoring on all pages
                    page_corpus = [p["text"] if p["text"] else f"Dokumen {p['doc_title']} halaman {p['page_num']}" for p in global_page_pool]
                    scores = await reranker_service.compute_scores(effective_page_query, page_corpus)

                    # Ekstrak kata kunci fokus untuk Exact Keyword Boost (misal: "cuti", "remunerasi", "tunjangan", "gaji")
                    focus_keywords = set()
                    for text_src in (rag_queries_clean + [user_message]):
                        for token in text_src.lower().split():
                            clean_tok = re.sub(r"[^\w]", "", token)
                            if len(clean_tok) >= 4 and clean_tok not in [
                                "dokumen", "peraturan", "terkait", "dalam", "surat", "nomor",
                                "tentang", "mengenai", "pindad", "apakah", "bagaimana", "adalah"
                            ]:
                                focus_keywords.add(clean_tok)

                    logger.info(f"[MODE_DOCUMENTS] Exact Keyword Boost terms: {focus_keywords}")

                    for idx, score in enumerate(scores):
                        p_obj = global_page_pool[idx]
                        final_score = float(score)
                        p_text_lower = p_obj.get("text", "").lower()
                        # Jika teks halaman memuat exact keyword pencarian, berikan keyword match booster (+0.4)
                        if focus_keywords and any(kw in p_text_lower for kw in focus_keywords):
                            final_score += 0.4
                        p_obj["score"] = final_score

                    # Urutkan berdasarkan skor tertinggi
                    global_page_pool.sort(key=lambda x: x["score"], reverse=True)

                    # Ambil Top Seed Halaman Terbaik Lintas Dokumen
                    # 1 Dokumen utama: 4 seed halaman terbaik sudah mencakup topik secara luas
                    # Perbandingan komparatif 2 dokumen: maks 6 seed
                    max_seeds = 6 if is_comparative_query else 4
                    top_seeds = [p for p in global_page_pool if p["score"] > 0.35][:max_seeds]
                    if not top_seeds:
                        top_seeds = global_page_pool[:min(max_seeds, len(global_page_pool))]

                    # Kelompokkan seed per dokumen untuk Tri-Window Expansion
                    seeds_by_doc = {}
                    for seed in top_seeds:
                        d_id = seed["doc_id"]
                        if d_id not in seeds_by_doc:
                            seeds_by_doc[d_id] = []
                        seeds_by_doc[d_id].append(seed["page_index"])

                    # Terapkan Tri-Window Connected Context per dokumen
                    connected_pages_per_doc = {}
                    max_pages_per_doc = 8 if is_comparative_query else 12
                    for d_id, seed_indices in seeds_by_doc.items():
                        t_map = doc_text_maps.get(d_id, [])
                        expanded_indices = expand_tri_window_context(seed_indices, t_map, total_pages=len(t_map))
                        if len(expanded_indices) > max_pages_per_doc:
                            expanded_indices = expanded_indices[:max_pages_per_doc]
                        connected_pages_per_doc[d_id] = expanded_indices
                        logger.info(f"[MODE_DOCUMENTS] Doc {d_id} Expanded Pages: {expanded_indices} (from seeds: {seed_indices})")

                    # 🎯 TARGETED EXPLICIT PAGE FOCUS CHECK:
                    # Jika user secara eksplisit menyebutkan nomor halaman tertentu dalam query
                    # (misalnya melalui Document Interrogator badge [Fokus Dokumen ... Halaman 5] atau "halaman 5"),
                    # fokus HANYA pada halaman yang diminta dan hindari full-document injection!
                    explicit_pages_per_doc = {}
                    for doc in full_read_docs:
                        d_id = doc.get("id")
                        t_map = doc_text_maps.get(d_id, [])
                        exp_pages = extract_explicit_pages_from_query(user_message, total_pages=len(t_map))
                        if exp_pages:
                            explicit_pages_per_doc[d_id] = sorted(list(exp_pages))
                            connected_pages_per_doc[d_id] = explicit_pages_per_doc[d_id]
                            logger.info(f"[MODE_DOCUMENTS] 🎯 [PAGE-FOCUS] Explicit targeted pages for Doc {d_id}: {explicit_pages_per_doc[d_id]} (bypassing full read)")

                    # 🧠 ADAPTIVE BRAIN-FIRST FULL INCLUSION:
                    # Untuk dokumen aktif sesi dari Brain yang berukuran <= 30 halaman,
                    # sertakan seluruh halamannya secara utuh HANYA jika dokumen tersebut adalah satu-satunya dokumen
                    # atau dokumen tersebut memang memiliki seed yang relevan dengan pertanyaan user!
                    # PENTING: Jangan timpa jika user sudah menargetkan halaman spesifik.
                    for doc in full_read_docs:
                        d_id = doc.get("id")
                        if d_id in explicit_pages_per_doc:
                            continue
                        t_map = doc_text_maps.get(d_id, [])
                        if doc.get("_from_session_brain") and len(t_map) <= 30:
                            if len(full_read_docs) == 1 or d_id in seeds_by_doc:
                                connected_pages_per_doc[d_id] = list(range(len(t_map)))
                                logger.info(f"[MODE_DOCUMENTS] 🧠 [BRAIN-FULL] Doc {d_id} has {len(t_map)} pages (<= 30) -> Injected 100% full document context!")
                            else:
                                logger.info(f"[MODE_DOCUMENTS] ℹ️ Doc {d_id} from Brain has no relevant seeds for current topic, skipping full inclusion to prevent context crowding.")
                    
                    # Grouping summary untuk SSE status
                    summary_parts = []
                    for doc in full_read_docs:
                        d_id = doc.get("id")
                        if d_id in connected_pages_per_doc:
                            p_nums = [str(p + 1) for p in connected_pages_per_doc[d_id]]
                            d_jud = doc.get("judul", "")
                            short_t = d_jud[:28] + ("..." if len(d_jud) > 28 else "")
                            summary_parts.append(f"{short_t} (Hal {', '.join(p_nums)})")
                        
                    sse_summary = " & ".join(summary_parts)
                    yield format_sse(status="📄 Membaca pasal terpilih", status_key="READING_SELECTED_ARTICLES", event_type=SSEEventType.STATUS)
                    
                    # Susun judul_context dari Connected Pages yang utuh dan tidak terpotong
                    context_blocks = []
                    for doc in full_read_docs:
                        d_id = doc.get("id")
                        if d_id not in connected_pages_per_doc:
                            continue
                        
                        p_indices = connected_pages_per_doc[d_id]
                        t_map = doc_text_maps.get(d_id, [])
                        
                        doc_page_texts = []
                        for p_idx in p_indices:
                            page_text = t_map[p_idx]["text"] if p_idx < len(t_map) else ""
                            doc_page_texts.append(f"[HALAMAN {p_idx + 1}]\n{page_text}")
                        
                        meta_header = (
                            f"--- DOKUMEN: {doc.get('judul', '')} (HALAMAN TERHUBUNG: {', '.join(str(p+1) for p in p_indices)}) ---\n"
                            f"Status Berlaku: {doc.get('status_berlaku', 'Berlaku')}\n"
                            f"Tanggal Terbit: {doc.get('tanggal', '-')}\n"
                            f"Nomor Regulasi: {doc.get('noper', '-')}\n"
                            f"Mencabut: {doc.get('mencabut', '-')}\n"
                        )
                        full_doc_content = "\n\n".join(doc_page_texts)
                        context_blocks.append(f"{meta_header}Isi Halaman:\n{full_doc_content}\n-------------------")
                        
                    judul_context = "\n\n".join(context_blocks)
                    
                    # Suntikkan ringkasan historis ke dalam judul_context sebagai blok referensi
                    if historical_summary_lines:
                        hist_block = (
                            "\n\n--- RIWAYAT REGULASI SEBELUMNYA (Sudah Dicabut/Tidak Berlaku) ---\n"
                            "Dokumen-dokumen berikut adalah SELURUH versi regulasi terdahulu yang pernah berlaku dan kini TELAH DICABUT/DIGANTIKAN:\n"
                            + "\n".join(historical_summary_lines)
                            + "\n\n🚨 PANDUAN KRONOLOGI REGULASI:\n"
                            "- Tuliskan dan sebutkan SELURUH versi regulasi terdahulu di atas (secara kronologis) jika pengguna menanyakan sejarah atau versi lama.\n"
                            "- Anda WAJIB memasukkan dokumen aktif DAN SEMUA dokumen versi lama di atas ke dalam `<sources_json>` agar kartu rujukan dan unduhan dokumennya muncul di layar pengguna!\n"
                            "---"
                        )
                        judul_context += hist_block
                    
                    judul_sources = all_source_metadata
                    
                    # Update source metadata page numbers dengan halaman terhubung yang akurat
                    for src in judul_sources:
                        s_id = src["id"]
                        if s_id in connected_pages_per_doc:
                            p_nums = [str(p + 1) for p in connected_pages_per_doc[s_id]]
                            tot = int(src.get("total_pages") or len(p_nums) or 1)
                            # Jika halaman terhubung mencakup sebagian besar/seluruh dokumen atau dari Brain:
                            if len(p_nums) >= tot or len(p_nums) > 3 or src.get("cache_hit") or src.get("_from_session_brain"):
                                src["page_number"] = ""
                                src["total_pages"] = str(tot)
                            else:
                                src["page_number"] = ", ".join(p_nums)
                            
            # Hitung skor tertinggi dari Tier 1
            max_tier1_score = max([s.get('score', s.get('similarity', 0.0)) for s in judul_sources]) if judul_sources else 0.0
            
            # Cek apakah ada keyword relevan yang cocok langsung di judul / tag
            search_words = [w.lower() for w in query_judul_str.split() if len(w) > 2]
            has_keyword_match = False
            for src in judul_sources:
                j_title = str(src.get("title") or src.get("raw_judul") or "").lower()
                j_tag = str(src.get("raw_tag") or "").lower()
                if any(w in j_title or w in j_tag for w in search_words):
                    has_keyword_match = True
                    break
            
            # Ambang batas keyakinan: Jika ada dokumen resmi dengan skor reranker valid (>= 0.48) atau keyword cocok di Judul/Tag
            is_tier1_satisfying = bool(judul_sources) and (max_tier1_score >= 0.48 or has_keyword_match)
            
            if is_tier1_satisfying:
                logger.info(f"[MODE_DOCUMENTS] 🎯 [TIER 1 HIT & SATISFYING] Ditemukan {len(judul_sources)} dokumen resmi via MySQL (Max Score: {max_tier1_score:.4f}, Keyword Match: {has_keyword_match})! SKIP Vector RAG & Corpus.")
                rag_sources = list(judul_sources)
            else:
                # ─────────────────────────────────────────────────────────────
                # TIER 2: Fallback / Expansion Vector RAG & Community Knowledge
                # ─────────────────────────────────────────────────────────────
                if judul_sources:
                    logger.info(f"[MODE_DOCUMENTS] ⚠️ [TIER 1 LOW CONFIDENCE] Hasil MySQL ada tapi skor reranker kurang memuaskan ({max_tier1_score:.4f} < 0.70). Melakukan pencarian tambahan ke Vector Embedding & Corpus...")
                else:
                    logger.info("[MODE_DOCUMENTS] ℹ️ [TIER 1 MISS] MySQL nihil (0 hasil). Mengaktifkan Fallback Tier 2 Vector RAG & Community Knowledge...")
                
                yield format_sse(status="🔍 Menelusuri semantik vector", status_key="SEARCHING_VECTOR_SEMANTICS", event_type=SSEEventType.STATUS)
                
                from backend.app.services.pipeline.community_knowledge import search_community_knowledge
                from backend.app.services.rag.rag_pipeline import run_rag_pipeline
                from backend.app.services.rag.reranker_service import reranker_service
                
                task_community = asyncio.create_task(search_community_knowledge(user_message, is_guest=(current_user_npp == "GUEST")))
                
                vector_sources = []
                if rag_queries:
                    logger.info(f"[MODE_DOCUMENTS] [TIER 2] RAG triggered via Sub-Queries | queries={rag_queries}")
                    async for sse in run_rag_pipeline(
                        rewritten_queries=rag_queries,
                        limit_per_query=4,
                        npp=current_user_npp,
                        use_cache=False,
                    ):
                        raw = sse.strip()
                        if not raw:
                            continue
                        try:
                            data = json.loads(raw)
                            event_type = data.get("event_type")

                            if event_type == SSEEventType.PIPELINE_DATA:
                                rag_context = data["payload"].get("context")
                                vector_sources = data["payload"].get("sources") or []
                                logger.info(f"[MODE_DOCUMENTS] [TIER 2] Vector RAG done | {len(rag_context or '')} chars | {len(vector_sources)} sources")

                            if event_type in (SSEEventType.THINKING, SSEEventType.STATUS):
                                yield sse
                        except (json.JSONDecodeError, AttributeError):
                            yield sse

                community_context = await task_community
                
                # ── GABUNGKAN & RERANK ULANG SEMUA KANDIDAT BERSAMA (TIER 1 + TIER 2) ──
                all_raw_candidates = []
                if judul_sources:
                    all_raw_candidates.extend(judul_sources)
                if vector_sources:
                    all_raw_candidates.extend(vector_sources)
                
                if all_raw_candidates:
                    logger.info(f"[MODE_DOCUMENTS] 🔄 Mererank ulang {len(all_raw_candidates)} total kandidat (MySQL + Vector RAG)...")
                    candidate_texts = []
                    for c in all_raw_candidates:
                        txt = c.get("content") or c.get("text") or f"{c.get('title', '')} {c.get('raw_judul', '')}"
                        candidate_texts.append(txt[:800])
                    
                    combined_scores = await reranker_service.compute_scores(user_message, candidate_texts)
                    
                    for idx, score_val in enumerate(combined_scores):
                        all_raw_candidates[idx]["score"] = float(score_val)
                    
                    # Sort descending berdasarkan skor reranker baru
                    all_raw_candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
                    # Filter threshold minimum
                    rag_sources = [c for c in all_raw_candidates if c.get("score", 0.0) >= 0.40][:10]
                    
                    if rag_sources:
                        yield format_sse(status="📄 Menganalisis pasal", status_key="ANALYZING_ARTICLE", event_type=SSEEventType.STATUS)
                else:
                    rag_sources = []

        # ── 2D: EVALUASI DAN LOG HASIL PENCARIAN KE TERMINAL ──
        has_title = False
        has_tag = False
        has_isi = False
        has_rag = bool(rag_sources and not judul_sources)
        has_semantic = bool(judul_sources)
        has_community = bool(community_context and community_context.strip())

        search_words = [w.lower() for w in query_judul_str.split() if len(w) > 2]
        
        if judul_sources:
            for src in judul_sources:
                raw_judul = str(src.get("raw_judul", "")).lower()
                raw_tag = str(src.get("raw_tag", "")).lower()
                raw_isi = str(src.get("raw_isi", "")).lower()
                
                for word in search_words:
                    if word in raw_judul: has_title = True
                    if word in raw_tag: has_tag = True
                    if word in raw_isi: has_isi = True

        logger.info("\n" + "="*40 + "\n" +
                    "🔍 LOG STATUS PENCARIAN DOKUMEN (CASCADE)\n" +
                    f"TIER 1 - SEARCH_TITLE       : {'ADA' if has_title else 'TIDAK ADA'}\n" +
                    f"TIER 1 - SEARCH_TAG         : {'ADA' if has_tag else 'TIDAK ADA'}\n" +
                    f"TIER 1 - SEARCH_ISI_BERITA  : {'ADA' if has_isi else 'TIDAK ADA'}\n" +
                    f"TIER 1 - SEARCH_SEMANTIC    : {'ADA' if has_semantic else 'TIDAK ADA'}\n" +
                    f"TIER 2 - SEARCH_RAG         : {'ADA' if has_rag else 'TIDAK ADA'}\n" +
                    f"TIER 2 - AI_DIALOGUE_CORPUS : {'ADA' if has_community else 'TIDAK ADA'}\n" +
                    "="*40)

        # ── Context Aggregation & Deduplication ────────────────────────────────────

        if rag_sources:
            # Deduplikasi dokumen agar tidak ganda kartu di UI
            seen_ids = set()
            unique_rag_sources = []
            for s in rag_sources:
                s_key = str(s.get("id") or s.get("filename") or s.get("title") or "")
                if s_key and s_key not in seen_ids:
                    seen_ids.add(s_key)
                    unique_rag_sources.append(s)
            # Sort by similarity/score and take up to 20 documents to preserve complete genealogy/silsilah history.
            rag_sources = sorted(unique_rag_sources, key=lambda x: x.get('score', x.get('similarity', 0)), reverse=True)[:20]

        # ── Smart Context Truncation (Max ~28,000 chars / ~7,000 tokens) ──
        # Menjamin ruang token yang sangat lega untuk thinking & output generation Call 2
        rag_budget = 16000 if not judul_context else 8000
        judul_budget = 24000
        community_budget = 2500
        
        # Gabungkan dokumen fisik ke dalam satu block context
        combined_documents = ""
        if judul_context:
            combined_documents += judul_context[:judul_budget]
            if len(judul_context) > judul_budget:
                combined_documents += "\n...[Teks Terpotong]...\n"
                
        if rag_context:
            if combined_documents:
                combined_documents += "\n\n"
            combined_documents += rag_context[:rag_budget]
            
        safe_rag_context = combined_documents if combined_documents else None


        # Pilih modul Call 2 dengan konteks RAG yang valid (baik dari MySQL maupun Vector RAG)
        has_context = bool(safe_rag_context or rag_sources or judul_sources)
        module_name = select_call2_module(routing_data, has_rag_context=has_context)
        logger.info(f"[MODE_DOCUMENTS] Selected module: {module_name} (has_context={has_context})")

        # ── Log Agent Step for Hybrid RAG Search (Semantic + Title) ──
        session_uuid = routing_data.get("_session_uuid") if routing_data else None
        if session_uuid:
            from backend.app.services.chat.chat_history_service import chat_history_service
            
            formatted_queries = []
            for q in (rag_queries or []):
                formatted_queries.append({"text": q, "type": "SEMANTIC"})
            
            if query_judul_list:
                for q in (query_judul_list if isinstance(query_judul_list, list) else [query_judul_list]):
                    formatted_queries.append({"text": q, "type": "TITLE_SEARCH"})
                    
            if community_context and community_context.strip():
                formatted_queries.append({"text": "Konteks Perusahaan", "type": "COMMUNITY_KNOWLEDGE"})
                
            sources_data = []
            for s in (rag_sources or []):
                sources_data.append({
                    "title": s.get('title') or s.get('filename') or s.get('document_title', 'Unknown'),
                    "doc_id": s.get('dokumen_id') or s.get('id') or s.get('document_id', ''),
                    "score": s.get('score') or s.get('similarity', 0),
                    "type": "TITLE" if (judul_sources and s in judul_sources) else "SEMANTIC"
                })
                
            obs_json = {
                "msg": f"Found {len(rag_sources or [])} sources from Hybrid Search",
                "queries": formatted_queries,
                "sources": sources_data
            }
            # Non-blocking async background task: jangan gantung streaming generator untuk I/O DB
            asyncio.create_task(chat_history_service.save_agent_step(
                session_id=session_uuid,
                step_number=2,
                tool_called="RAG_SEARCH",
                tool_input=str(formatted_queries),
                observation=json.dumps(obs_json)
            ))

        system_prompt = build_call2_system_prompt(
            module_name=module_name,
            employee_name=employee_name,
            precheck=routing_data,
            is_thinking=is_thinking,
            rag_context=safe_rag_context,
            rag_sources=rag_sources
        )

        # Inject Employee Long-Term Memory (ai_memory)
        if current_user_npp and current_user_npp != "GUEST":
            from backend.app.services.memory.memory_service import memory_service
            is_recall = bool(routing_data and (routing_data.get("is_cross_session_recall") or routing_data.get("is_memory_recall")))
            employee_memory = await memory_service.get_employee_long_term_memory(
                current_user_npp,
                current_session_uuid=session_uuid,
                include_past_sessions=is_recall
            )
            if employee_memory:
                system_prompt += employee_memory

        # Inject Community Knowledge (Di awal atau sebelum history)
        if community_context:
            community_str = ""
            if not judul_context and not rag_context:
                community_str += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                community_str += "🚨 ATURAN WAJIB (MURNI INGATAN / AI CORPUS)\n"
                community_str += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                community_str += "Saat ini kamu MURNI menjawab menggunakan ingatanmu sendiri (AI Dialogue Corpus) karena tidak ada dokumen pendukung (RAG/Title) yang ditemukan untuk pertanyaan ini.\n"
                community_str += "OLEH KARENA ITU, KAMU DILARANG KERAS mengatakan 'Silakan cek dokumen sumber', 'Menurut dokumen di atas', atau menyuruh user membaca referensi dokumen pendukung (karena memang tidak ada). Jawablah langsung secara natural tanpa merujuk ke dokumen lampiran.\n\n"
            
            community_str += community_context[:community_budget]
            # Karena system_prompt sudah jadi, lebih aman kita taruh community di paling awal agar tidak merusak instruksi JSON di akhir
            system_prompt = community_str + "\n\n" + system_prompt

        # Tier 3: Anti-Halusinasi Guard jika pencarian regulasi 100% NIHIL
        if not judul_sources and not rag_sources and not is_chitchat_msg and should_run_rag:
            anti_hallucination_guard = (
                "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🚨 ATURAN KETAT: DOKUMEN / REGULASI TIDAK DITEMUKAN (100% NIHIL)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Topik, nomor regulasi, atau aturan yang ditanyakan user TIDAK DITEMUKAN di seluruh basis data internal PT Pindad.\n"
                "KAMU DILARANG KERAS mengarang isi pasal, berhalusinasi, atau mengasumsikan aturan dari instansi lain/perusahaan luar.\n"
                "Jawablah dengan jujur, ramah, dan profesional kepada user bahwa aturan/dokumen mengenai topik tersebut belum tercatat atau tidak ditemukan di database regulasi internal PT Pindad.\n"
            )
            system_prompt = anti_hallucination_guard + "\n\n" + system_prompt

        # Inject On-Demand / Manifest Session Memory
        retrieved_session_chunks = routing_data.get("_retrieved_session_chunks_text", "")
        if retrieved_session_chunks:
            system_prompt = retrieved_session_chunks + "\n\n" + system_prompt
        elif routing_data.get("_session_chunks_text"):
            # Masukkan katalog manifest ringkas
            manifest_text = routing_data.get("_session_chunks_text")
            system_prompt = manifest_text + "\n\n" + system_prompt

        from backend.app.services.pipeline.modes.mode_utils import resolve_history_messages
        needs_history = bool(routing_data.get("needs_history", False)) if routing_data else False
        active_pronoun = routing_data.get("pronoun", "formal_saya_anda") if routing_data else "formal_saya_anda"

        trimmed_messages = resolve_history_messages(
            chat_history=chat_history,
            user_message=user_message,
            needs_history=needs_history,
            max_turns=6,
            max_assistant_chars=600,
            active_pronoun=active_pronoun,
        )
        
        # 🛡️ ANTI-KONTAMINASI: Bersihkan history dari koding/web search sebelumnya jika RAG aktif
        if should_run_rag or routing_data.get("need_rag"):
            trimmed_messages = sanitize_history_for_rag(trimmed_messages)
            logger.info("[MODE_DOCUMENTS] 🛡️ History sanitized: past code blocks and web search artifacts stripped for clean RAG synthesis.")
        
        # Inject OCR Images ke user message HANYA jika dokumen murni berupa scan (tanpa teks ekstraksi)
        if ocr_attachments and (not safe_rag_context or len(safe_rag_context) < 300):
            images = [att["base64"] for att in ocr_attachments if att.get("type") == "image"][:1]
            if images:
                logger.info(f"[MODE_DOCUMENTS] 🖼️ Dokumen murni scan terdeteksi tanpa teks. Menginjeksikan 1 gambar ke Call 2")
                trimmed_messages[-1]["images"] = images
                
        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        module_config = get_module_config(module_name)
        num_ctx = module_config["num_ctx"]
        temperature = module_config["temperature"]

        # Hitung estimasi token (1 token ~ 4 karakter)
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in trimmed_messages) // 4
        rag_tokens = len(safe_rag_context or "") // 4
        total_used = sys_tokens + hist_tokens + rag_tokens
        
        # Log Agent Step for Call 2 Synthesis (Non-blocking background task)
        session_uuid = routing_data.get("_session_uuid") if routing_data else None
        if session_uuid:
            from backend.app.services.chat.chat_history_service import chat_history_service
            obs_dict = {
                "msg": f"Generating response using module: {module_name}",
                "memory": {
                    "system_tokens": sys_tokens,
                    "history_tokens": hist_tokens,
                    "rag_tokens": rag_tokens,
                    "total_used": total_used,
                    "max_ctx": num_ctx
                }
            }
            asyncio.create_task(chat_history_service.save_agent_step(
                session_id=session_uuid,
                step_number=3,
                tool_called="CALL_2_SYNTHESIS",
                tool_input=f"Prompt chars: {len(system_prompt)} | Contexts: {len(safe_rag_context or '')}",
                observation=json.dumps(obs_dict)
            ))

        # ── Step 3: LLM Execution (Call 2 via Agentic Interceptor) ─────────────────
        # Emit status tepat sebelum masuk ke LLM agar UI pengguna live aktif selama masa tunggu prefill GPU
        yield format_sse(status="✍️ Menyusun jawaban", status_key="DRAFTING_RESPONSE", event_type=SSEEventType.STATUS)

        precall2_elapsed_ms = (time.perf_counter() - t_mode_docs_start) * 1000
        logger.info(f"⚡ [TIMING_BENCHMARK] [PRE_CALL2_PREPARATION] Selesai seluruh persiapan dokumen & prompt dalam {precall2_elapsed_ms:.1f}ms ({precall2_elapsed_ms/1000:.2f}s) -> Dispatching ke Ollama Call 2.")

        try:
            from backend.app.services.pipeline.agentic_interceptor import agentic_stream_wrapper
            async for chunk in agentic_stream_wrapper(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:31b"),
                messages=stream_messages,
                request=request,
                is_thinking=is_thinking,
                employee_name=employee_name,
                session_uuid=session_uuid,
                rag_sources=rag_sources,
                max_tool_loops=2,
                **module_config,
            ):
                yield chunk

        except Exception as e:
            logger.error(f"[MODE_DOCUMENTS] Stream error: {e}", exc_info=True)
            yield format_sse(f"Maaf, terjadi kendala teknis: {str(e)}", "", False, event_type=SSEEventType.CHUNK)

        logger.info(f"[CALL2_DOCUMENTS] ✅ Finished generation | module={module_name} | needs_history={needs_history} | turns_sent={len(trimmed_messages)}")