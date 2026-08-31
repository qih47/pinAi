import logging
import json
import asyncio
import os
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.config import settings
from backend.app.core.paths import FILE_PERATURAN_DIR
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.peraturan_service import _find_valid_pdf_file
from backend.app.services.pipeline.modes.mode_utils import (
    select_call2_module, 
    get_module_config, 
    build_call2_system_prompt,
    sanitize_history_for_rag
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
                expand_tri_window_context
            )
            
            query_judul_list = routing_data.get("query_judul") or []
            query_judul_str = " ".join(query_judul_list) if isinstance(query_judul_list, list) else str(query_judul_list)
            
            # ─────────────────────────────────────────────────────────────────
            # TIER 1: Progressive Document Stepper & Global Page-Level Reranking
            # ─────────────────────────────────────────────────────────────────
            yield format_sse(status="🔍 Menelusuri regulasi", event_type=SSEEventType.STATUS)
            logger.info(f"[MODE_DOCUMENTS] [TIER 1] Fetching candidate documents for query_judul: {query_judul_list}")
            
            candidate_docs = await get_candidate_documents_metadata(user_message, query_judul_list, rag_queries=rag_queries)
            
            if candidate_docs:
                # ── SPLIT: Aktif/Terbaru (Full PDF Read) vs Historis (Ringkasan Saja) ──────
                # Kandidat sudah diurutkan: berlaku + terbaru di atas (dari scoring peraturan_service)
                full_read_docs = []
                historical_docs = []
                for doc in candidate_docs:
                    is_supp = doc.get("is_supplementary", False)
                    status = doc.get("status_berlaku", "")
                    
                    if is_supp:
                        historical_docs.append(doc)
                    elif status == "Berlaku" or len(full_read_docs) < 1:
                        # Ambil dokumen aktif (atau minimal 1 dokumen) hingga maksimal 5 dokumen
                        if len(full_read_docs) < 5:
                            full_read_docs.append(doc)
                        else:
                            historical_docs.append(doc)
                    else:
                        historical_docs.append(doc)
                
                # Jika tidak ada yang berstatus Berlaku sama sekali, ambil hingga 5 teratas yang bukan supplementary sebagai full_read
                if not full_read_docs:
                    non_supp = [d for d in candidate_docs if not d.get("is_supplementary", False)]
                    full_read_docs = non_supp[:5] if non_supp else candidate_docs[:3]
                    historical_docs = [d for d in candidate_docs if d not in full_read_docs]
                
                doc_count = len(full_read_docs)
                hist_count = len(historical_docs)
                yield format_sse(status=f"📑 Menemukan {doc_count + hist_count} dokumen", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.02)
                
                global_page_pool = []
                all_source_metadata = []
                doc_text_maps = {}  # doc_id -> list of {"page_num": int, "text": str}
                
                # 1A. Progressive per-file reading stepper (Document Intelligence & In-Memory Cache)
                for doc in full_read_docs:
                    valid_file = doc.get("valid_file")
                    if not valid_file or not os.path.exists(valid_file):
                        continue
                        
                    doc_title_display = doc['judul'][:38].strip()
                    yield format_sse(status=f"📖 Membaca {doc_title_display}", event_type=SSEEventType.STATUS)
                    await asyncio.sleep(0.02)
                    
                    cache_key = f"doc_{doc['id']}"
                    text_map, _, page_count = await extract_and_ocr_document_async(valid_file, cache_key=cache_key)
                    doc_text_maps[doc["id"]] = text_map
                    
                    for item in text_map:
                        p_num = item["page_num"] + 1  # 1-based page number
                        p_text = item["text"]
                        global_page_pool.append({
                            "page_num": p_num,
                            "page_index": item["page_num"],
                            "text": p_text,
                            "doc_id": doc["id"],
                            "doc_title": doc["judul"],
                            "doc_noper": doc["noper"],
                            "doc_status": doc["status_berlaku"],
                            "doc_tanggal": doc["tanggal"],
                            "doc_mencabut": doc["mencabut"],
                            "valid_file": valid_file,
                            "filename": doc["filename"],
                            "file_path": doc["file_path"],
                            "jenis": doc["jenis"]
                        })
                        
                    all_source_metadata.append({
                        "id": doc["id"],
                        "title": doc["judul"],
                        "document_title": doc["judul"],
                        "filename": doc["filename"],
                        "file_path": doc["file_path"],
                        "jenis": doc["jenis"],
                        "nomor": doc["noper"],
                        "page_number": "1",
                        "total_pages": str(page_count) if page_count > 0 else "",
                        "cache_hit": False,
                        "score_label": "HYBRID_RERANKER",
                        "score": doc["score"],
                        "raw_judul": doc["judul"],
                        "raw_tag": doc.get("raw_tag", ""),
                        "raw_isi": doc.get("raw_isi", ""),
                        "tgl_obs": doc.get("tgl_obs", "")
                    })
                
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
                        "id": doc["id"],
                        "title": doc["judul"],
                        "document_title": doc["judul"],
                        "filename": doc.get("filename"),
                        "file_path": doc.get("file_path"),
                        "jenis": doc["jenis"],
                        "nomor": doc["noper"],
                        "page_number": "1",
                        "total_pages": "",
                        "cache_hit": False,
                        "score_label": "HISTORICAL_REF",
                        "score": doc["score"],
                        "raw_judul": doc["judul"],
                        "raw_tag": doc.get("raw_tag", ""),
                        "raw_isi": doc.get("raw_isi", ""),
                        "tgl_obs": doc.get("tgl_obs", "")
                    })
                
                if historical_summary_lines:
                    logger.info(f"[MODE_DOCUMENTS] 📋 {len(historical_summary_lines)} historical docs → ringkasan saja (skip PDF read)")

                    
                # 2. Global Cross-Document Page-Level Reranking & Tri-Window Context Expansion
                if global_page_pool:
                    total_p_count = len(global_page_pool)
                    yield format_sse(status="🎯 Menyaring pasal relevan", event_type=SSEEventType.STATUS)
                    await asyncio.sleep(0.02)
                    
                    # Effective query untuk BGE page scoring: gunakan rag_queries[0] murni saja.
                    effective_page_query = rag_queries[0].strip() if rag_queries else user_message
                    logger.info(f"[MODE_DOCUMENTS] Scoring {len(global_page_pool)} pages using effective query: '{effective_page_query}'")
                    
                    # BGE Scoring on all pages
                    page_corpus = [p["text"] if p["text"] else f"Dokumen {p['doc_title']} halaman {p['page_num']}" for p in global_page_pool]
                    scores = await reranker_service.compute_scores(effective_page_query, page_corpus)
                    
                    for idx, score in enumerate(scores):
                        global_page_pool[idx]["score"] = float(score)
                        
                    # Urutkan berdasarkan skor tertinggi
                    global_page_pool.sort(key=lambda x: x["score"], reverse=True)
                    
                    # Ambil Top 6 Seed Halaman Terbaik Lintas Dokumen
                    top_seeds = [p for p in global_page_pool if p["score"] > 0.35][:6]
                    if not top_seeds:
                        top_seeds = global_page_pool[:3]
                        
                    # Kelompokkan seed per dokumen untuk Tri-Window Expansion
                    seeds_by_doc = {}
                    for seed in top_seeds:
                        d_id = seed["doc_id"]
                        if d_id not in seeds_by_doc:
                            seeds_by_doc[d_id] = []
                        seeds_by_doc[d_id].append(seed["page_index"])
                    
                    # Terapkan Tri-Window Connected Context per dokumen
                    connected_pages_per_doc = {}
                    for d_id, seed_indices in seeds_by_doc.items():
                        t_map = doc_text_maps.get(d_id, [])
                        expanded_indices = expand_tri_window_context(seed_indices, t_map, total_pages=len(t_map))
                        connected_pages_per_doc[d_id] = expanded_indices
                        logger.info(f"[MODE_DOCUMENTS] Doc {d_id} Expanded Pages: {expanded_indices} (from seeds: {seed_indices})")
                    
                    # Grouping summary untuk SSE status
                    summary_parts = []
                    for doc in full_read_docs:
                        d_id = doc["id"]
                        if d_id in connected_pages_per_doc:
                            p_nums = [str(p + 1) for p in connected_pages_per_doc[d_id]]
                            short_t = doc["judul"][:28] + ("..." if len(doc["judul"]) > 28 else "")
                            summary_parts.append(f"{short_t} (Hal {', '.join(p_nums)})")
                        
                    sse_summary = " & ".join(summary_parts)
                    yield format_sse(status="📄 Membaca pasal terpilih", event_type=SSEEventType.STATUS)
                    await asyncio.sleep(0.02)
                    
                    # Susun judul_context dari Connected Pages yang utuh dan tidak terpotong
                    context_blocks = []
                    for doc in full_read_docs:
                        d_id = doc["id"]
                        if d_id not in connected_pages_per_doc:
                            continue
                        
                        p_indices = connected_pages_per_doc[d_id]
                        t_map = doc_text_maps.get(d_id, [])
                        
                        doc_page_texts = []
                        for p_idx in p_indices:
                            page_text = t_map[p_idx]["text"] if p_idx < len(t_map) else ""
                            doc_page_texts.append(f"[HALAMAN {p_idx + 1}]\n{page_text}")
                        
                        meta_header = (
                            f"--- DOKUMEN: {doc['judul']} (HALAMAN TERHUBUNG: {', '.join(str(p+1) for p in p_indices)}) ---\n"
                            f"Status Berlaku: {doc['status_berlaku']}\n"
                            f"Tanggal Terbit: {doc['tanggal']}\n"
                            f"Nomor Regulasi: {doc['noper']}\n"
                            f"Mencabut: {doc['mencabut']}\n"
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
                
                yield format_sse(status="🔍 Menelusuri semantik vector", event_type=SSEEventType.STATUS)
                
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
                                await asyncio.sleep(0.005)
                        except (json.JSONDecodeError, AttributeError):
                            yield sse
                            await asyncio.sleep(0.01)

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
                        yield format_sse(status="📄 Menganalisis pasal", event_type=SSEEventType.STATUS)
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

        # ── Step 3: LLM Execution (Call 2) ────────────────────────────────────────
        yield format_sse(status="✍️ Menyusun jawaban", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

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

        # ── Smart Context Truncation (Max ~50,000 chars total) ──
        rag_budget = 40000 if not judul_context else 20000
        judul_budget = 45000
        community_budget = 3000
        
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
            await chat_history_service.save_agent_step(
                session_id=session_uuid,
                step_number=2,
                tool_called="RAG_SEARCH",
                tool_input=str(formatted_queries),
                observation=json.dumps(obs_json)
            )

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
            employee_memory = await memory_service.get_employee_long_term_memory(current_user_npp)
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

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        # Mengambil 5 history + 1 current message = 6
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
        
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
        
        # Log Agent Step for Call 2 Synthesis
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
            await chat_history_service.save_agent_step(
                session_id=session_uuid,
                step_number=3,
                tool_called="CALL_2_SYNTHESIS",
                tool_input=f"Prompt chars: {len(system_prompt)} | Contexts: {len(safe_rag_context or '')}",
                observation=json.dumps(obs_dict)
            )

        # State variables for stream interception
        import re
        intercept_buffer = ""
        is_intercepting = False
        json_intercepted = False
        
        try:
            async for chunk_line in stream_ollama_chat(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
                messages=stream_messages,
                request=request,
                keep_alive=-1,
                is_thinking=is_thinking,
                **module_config,
            ):
                try:
                    chunk_data = json.loads(chunk_line.strip())
                    chunk_text = chunk_data.get("chunk", "")
                    native_thought = chunk_data.get("thinking", "")
                    
                    eval_count = chunk_data.get("eval_count", 0)
                    eval_duration = chunk_data.get("eval_duration", 0)
                    
                    # # Log CCTV untuk debug tag <think>
                    # if native_thought:
                    #     logger.info(f"[CCTV THINK] {native_thought.strip()}")
                    # if "<think>" in chunk_text or "</think>" in chunk_text:
                    #     logger.warning(f"[CCTV ALERT] Tag Think nyampur di chunk_text: {chunk_text}")

                except (json.JSONDecodeError, AttributeError):
                    chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                    native_thought = ""
                    eval_count = 0
                    eval_duration = 0

                # Tampilkan thought hanya jika is_thinking (dari FE) True
                if native_thought and is_thinking:
                    yield format_sse("", native_thought, False, event_type=SSEEventType.THINKING)
                    
                if chunk_text:
                    if not json_intercepted:
                        intercept_buffer += chunk_text
                        if "<sources_json>" in intercept_buffer and not is_intercepting:
                            is_intercepting = True
                            
                        if is_intercepting:
                            if "</sources_json>" in intercept_buffer:
                                is_intercepting = False
                                json_intercepted = True
                                
                                start_idx = intercept_buffer.find("<sources_json>") + len("<sources_json>")
                                end_idx = intercept_buffer.find("</sources_json>")
                                json_str = intercept_buffer[start_idx:end_idx].strip()
                                
                                filtered_sources = []
                                parsing_success = False
                                try:
                                    if json_str:
                                        json_str = re.sub(r'```json|```', '', json_str).strip()
                                        used_docs = json.loads(json_str)
                                        
                                        # SPRINT 5: Python-level filter to forcefully drop hallucinated unused docs
                                        valid_used_docs = []
                                        for doc in used_docs:
                                            alasan = str(doc.get("alasan", "")).lower()
                                            if any(neg in alasan for neg in ["tidak digunakan", "tidak relevan", "tidak dipakai", "tidak merujuk", "tidak digunakan karena"]):
                                                logger.warning(f"[MODE_DOCUMENTS] 🚫 Membuang doc {doc.get('id')} secara paksa karena alasan: {alasan}")
                                                continue
                                            valid_used_docs.append(doc)
                                        used_docs = valid_used_docs
                                        
                                        used_ids = [str(doc.get("id", "")) for doc in used_docs]
                                        
                                        missing_docs = []
                                        for doc in used_docs:
                                            doc_id = str(doc.get("id", "")).strip()
                                            doc_judul = str(doc.get("judul", "")).strip().lower()
                                            found = False
                                            
                                            # 1. Coba cocokkan langsung di memory (rag_sources) via ID, Noper, atau Judul
                                            for src in rag_sources:
                                                src_id = str(src.get("id", "")).strip()
                                                src_nomor = str(src.get("nomor") or src.get("noper") or "").strip().lower()
                                                src_title = str(src.get("title") or src.get("judul") or src.get("raw_judul") or "").strip().lower()
                                                
                                                # Match by ID
                                                if doc_id and (doc_id == src_id):
                                                    if src not in filtered_sources:
                                                        filtered_sources.append(src)
                                                    found = True
                                                    break
                                                    
                                                # Match by Noper (contoh: "SKEP/1/P/BD/II/2025" ada di "SKEP/1/P/BD/II/2025, SKEP/1a/P/BD/II/2025")
                                                if doc_id and src_nomor and (doc_id.lower() in src_nomor or src_nomor in doc_id.lower()):
                                                    if src not in filtered_sources:
                                                        filtered_sources.append(src)
                                                    found = True
                                                    break
                                                    
                                                # Match by Judul
                                                if doc_judul and src_title and len(doc_judul) > 5 and (doc_judul in src_title or src_title in doc_judul):
                                                    if src not in filtered_sources:
                                                        filtered_sources.append(src)
                                                    found = True
                                                    break
                                                    
                                            if not found:
                                                missing_docs.append(doc)
                                                
                                        if missing_docs:
                                            from backend.app.core.database import get_peraturan_db
                                            async with get_peraturan_db() as conn_my:
                                                async with conn_my.cursor() as cur:
                                                    for mdoc in missing_docs:
                                                        m_id = str(mdoc.get("id", "")).strip()
                                                        m_judul = str(mdoc.get("judul", "")).strip()
                                                        row = None
                                                        
                                                        # Coba fetch by ID jika angka
                                                        if m_id.isdigit():
                                                            sql = """
                                                                SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.noper
                                                                FROM berita b
                                                                LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                                                                WHERE b.id_berita = %s
                                                            """
                                                            await cur.execute(sql, (int(m_id),))
                                                            row = await cur.fetchone()
                                                        
                                                        # Coba fetch by Noper atau Judul LIKE
                                                        if not row and m_id:
                                                            sql = """
                                                                SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.noper
                                                                FROM berita b
                                                                LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                                                                WHERE b.noper LIKE %s OR b.judul LIKE %s
                                                                ORDER BY b.id_berita DESC
                                                                LIMIT 1
                                                            """
                                                            noper_like = f"%{m_id}%"
                                                            judul_like = f"%{m_judul}%" if m_judul else noper_like
                                                            await cur.execute(sql, (noper_like, judul_like))
                                                            row = await cur.fetchone()
                                                            if row:
                                                                logger.info(f"[MODE_DOCUMENTS] 🌟 AI Memory Recovered from DB by Noper/Judul: '{m_id}' -> ID {row[0]}")
                                                        
                                                        if row:
                                                            id_berita, db_judul, gambar, gambar2, gambar3, nama_kategori, noper = row
                                                            
                                                            valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
                                                            filtered_sources.append({
                                                                "id": str(id_berita),
                                                                "title": db_judul,
                                                                "document_title": db_judul,
                                                                "filename": os.path.basename(valid_file) if valid_file else None,
                                                                "file_path": f"file_peraturan/{os.path.basename(valid_file)}" if valid_file else None,
                                                                "jenis": nama_kategori or "Regulasi",
                                                                "nomor": noper or "N/A",
                                                                "score_label": "AI_MEMORY_RECOVERED",
                                                                "score": 1.0
                                                            })
                                        parsing_success = True
                                except Exception as e:
                                    logger.warning(f"[MODE_DOCUMENTS] Gagal parse sources_json: {e}. Raw: {json_str}")
                                
                                if parsing_success and filtered_sources:
                                    seen_final = set()
                                    unique_final = []
                                    for f_src in filtered_sources:
                                        f_key = str(f_src.get("id") or f_src.get("filename") or f_src.get("title") or "")
                                        if f_key and f_key not in seen_final:
                                            seen_final.add(f_key)
                                            unique_final.append(f_src)
                                    final_sources = unique_final
                                else:
                                    final_sources = []


                                # ── Enrich final_sources dengan total_pages ────────────────
                                # Hitung HANYA untuk dokumen yang benar-benar digunakan Gemma
                                # (bukan semua kandidat RAG). Jalankan paralel via executor.
                                if final_sources:
                                    def _count_pages_sync(abs_path: str) -> int:
                                        try:
                                            import fitz
                                            doc = fitz.open(abs_path)
                                            n = len(doc)
                                            doc.close()
                                            return n
                                        except Exception:
                                            return 0

                                    _loop = asyncio.get_running_loop()
                                    _tasks = []
                                    for _src in final_sources:
                                        _filename = os.path.basename(_src.get("file_path", "") or "")
                                        _abs = os.path.join(FILE_PERATURAN_DIR, _filename) if _filename else ""
                                        if _abs and os.path.exists(_abs):
                                            _tasks.append(_loop.run_in_executor(None, _count_pages_sync, _abs))
                                        else:
                                            async def _zero(): return 0
                                            _tasks.append(_zero())

                                    _page_results = await asyncio.gather(*_tasks, return_exceptions=True)
                                    for _src, _n in zip(final_sources, _page_results):
                                        n_pages = _n if isinstance(_n, int) else 0
                                        _src["total_pages"] = str(n_pages) if n_pages > 0 else ""
                                    logger.info(f"[MODE_DOCUMENTS] ✅ total_pages dihitung untuk {len(final_sources)} dokumen terpilih Gemma")
                                
                                yield format_sse("", "", False, sources=final_sources, event_type=SSEEventType.SOURCES)
                                
                                remainder = intercept_buffer[end_idx + len("</sources_json>"):]
                                if remainder:
                                    yield format_sse(remainder, "", False, event_type=SSEEventType.CHUNK)
                                intercept_buffer = ""
                        else:
                            # Jika tidak ada tag <sources_json> di awal, jangan dump raw rag_sources ke FE
                            if len(intercept_buffer) > 25 and "<sources_json>" not in intercept_buffer:
                                json_intercepted = True
                                yield format_sse(intercept_buffer, "", False, event_type=SSEEventType.CHUNK)
                                intercept_buffer = ""
                    else:
                        yield format_sse(chunk_text, "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration)
                elif eval_count > 0:
                    yield format_sse("", "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration)

        except Exception as e:
            logger.error(f"[MODE_DOCUMENTS] Stream error: {e}")
            yield format_sse(f"Maaf, terjadi kendala teknis: {str(e)}", "", False, event_type=SSEEventType.CHUNK)
            
        # Flush buffer sisa jika stream selesai
        if intercept_buffer:
            yield format_sse(intercept_buffer, "", False, event_type=SSEEventType.CHUNK)