import logging
import json
import asyncio
import os
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.pipeline.modes.mode_utils import select_call2_module, get_module_config, build_call2_system_prompt
from backend.app.core.paths import FILE_PERATURAN_DIR

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

        if is_chitchat_msg or not should_run_rag:
            logger.info("[MODE_DOCUMENTS] 💬 Sapaan ringan / chitchat terdeteksi di mode documents -> Lewati pencarian RAG & FTS!")
        else:
            from backend.app.services.peraturan_service import hybrid_document_search
            
            query_judul_list = routing_data.get("query_judul") or []
            query_judul_str = " ".join(query_judul_list) if isinstance(query_judul_list, list) else str(query_judul_list)
            
            # ─────────────────────────────────────────────────────────────────
            # TIER 1: Instant MySQL Search (Judul, Tag, Isi Berita, FTS)
            # ─────────────────────────────────────────────────────────────────
            yield format_sse(status="🔍 Memeriksa basis data regulasi Pindad...", event_type=SSEEventType.STATUS)
            logger.info(f"[MODE_DOCUMENTS] [TIER 1] Executing MySQL search for query_judul: {query_judul_list}")
            
            judul_context, ocr_attachments, judul_sources = await hybrid_document_search(user_message, query_judul_list)
            
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
                yield format_sse(status="📄 Dokumen referensi ditemukan, sedang menganalisis isi pasal...", event_type=SSEEventType.STATUS)
            else:
                # ─────────────────────────────────────────────────────────────
                # TIER 2: Fallback / Expansion Vector RAG & Community Knowledge
                # ─────────────────────────────────────────────────────────────
                if judul_sources:
                    logger.info(f"[MODE_DOCUMENTS] ⚠️ [TIER 1 LOW CONFIDENCE] Hasil MySQL ada tapi skor reranker kurang memuaskan ({max_tier1_score:.4f} < 0.70). Melakukan pencarian tambahan ke Vector Embedding & Corpus...")
                else:
                    logger.info("[MODE_DOCUMENTS] ℹ️ [TIER 1 MISS] MySQL nihil (0 hasil). Mengaktifkan Fallback Tier 2 Vector RAG & Community Knowledge...")
                
                yield format_sse(status="🔍 Mencari dokumen terkait via semantic vector & corpus...", event_type=SSEEventType.STATUS)
                
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
                        yield format_sse(status="📄 Dokumen referensi ditemukan, sedang menganalisis isi pasal...", event_type=SSEEventType.STATUS)
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
        module_name = select_call2_module(routing_data, has_rag_context=bool(rag_context))
        logger.info(f"[MODE_DOCUMENTS] Selected module: {module_name}")

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
            # Sort by similarity/score and take up to 15 documents to preserve genealogy/silsilah history.
            rag_sources = sorted(unique_rag_sources, key=lambda x: x.get('score', x.get('similarity', 0)), reverse=True)[:15]
            # SPRINT 5: Kita TUNDA pengiriman event SOURCES ke frontend di sini!
            # Event SOURCES baru akan dikirim nanti setelah di-filter lewat interceptor <sources_json>
            # yield format_sse("", "", False, sources=rag_sources, event_type=SSEEventType.SOURCES)


        # ── Log Agent Step for Hybrid RAG Search (Semantic + Title) ──
        session_uuid = routing_data.get("_session_uuid") if routing_data else None
        if session_uuid:
            from backend.app.services.chat.chat_history_service import chat_history_service
            
            # 1. Format Queries
            formatted_queries = []
            for q in (rag_queries or []):
                formatted_queries.append({"text": q, "type": "SEMANTIC"})
            
            if query_judul_list:
                for q in (query_judul_list if isinstance(query_judul_list, list) else [query_judul_list]):
                    formatted_queries.append({"text": q, "type": "TITLE_SEARCH"})
                    
            if community_context and community_context.strip():
                formatted_queries.append({"text": "Konteks Perusahaan", "type": "COMMUNITY_KNOWLEDGE"})
                
            # 2. Format Sources
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

        # Build prompt dengan parameter is_thinking dari FE
        # ── Smart Context Truncation (Max ~42,000 chars / ~12k tokens total) ──
        # Tujuannya agar tersisa 4000 token untuk generasi jawaban.
        
        # Alokasikan budget karakter (SPRINT 5 OPTIMIZED: 12000 char agar 5 dokumen juara BGE masuk utuh tanpa prefill TTFT lambat)
        rag_budget = 12000 if not judul_context else 8000
        judul_budget = 12000 if not rag_context else 8000
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
        
        system_prompt = build_call2_system_prompt(
            module_name=module_name,
            employee_name=employee_name,
            precheck=routing_data,
            is_thinking=is_thinking,
            rag_context=safe_rag_context,
            rag_sources=rag_sources
        )

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

        # Inject Long-Term Memory (ai_document_chunks)
        session_chunks = routing_data.get("_session_chunks_text", "")
        if session_chunks:
            system_prompt = session_chunks + "\n\n" + system_prompt

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        # Mengambil 5 history + 1 current message = 6
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
        
        # Inject OCR Images to the last user message (dibatasi max 2 gambar dan skip jika teks RAG sudah sangat lengkap)
        if ocr_attachments and len(rag_context or "") <= 20000:
            images = [att["base64"] for att in ocr_attachments if att.get("type") == "image"][:2]
            if images:
                logger.info(f"[MODE_DOCUMENTS] 🖼️ Menginjeksikan {len(images)} gambar (dibatasi max 2 agar tidak memboroskan KV cache LLM)")
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
        rag_tokens = len(rag_context or "") // 4
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
                tool_input=f"Prompt chars: {len(system_prompt)} | Contexts: {len(rag_context or '')}",
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
                temperature=temperature,
                keep_alive=-1,
                num_ctx=num_ctx,
                num_predict=-1,
                is_thinking=is_thinking,
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
                                            doc_id = str(doc.get("id", ""))
                                            found = False
                                            for src in rag_sources:
                                                if str(src.get("id", "")) == doc_id:
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
                                                        m_id = str(mdoc.get("id", ""))
                                                        m_judul = str(mdoc.get("judul", ""))
                                                        row = None
                                                        
                                                        # Coba fetch by ID dulu
                                                        if m_id.isdigit():
                                                            sql = """
                                                                SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.noper
                                                                FROM berita b
                                                                LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                                                                WHERE b.id_berita = %s
                                                            """
                                                            await cur.execute(sql, (int(m_id),))
                                                            candidate_row = await cur.fetchone()
                                                            
                                                            if candidate_row:
                                                                db_judul = candidate_row[1].lower()
                                                                db_words = {w for w in db_judul.replace("/", " ").replace("-", " ").split() if len(w) > 3}
                                                                llm_words = {w for w in m_judul.lower().replace("/", " ").replace("-", " ").split() if len(w) > 3}
                                                                # Validasi kemiripan
                                                                if db_words and llm_words and db_words.intersection(llm_words):
                                                                    row = candidate_row
                                                                else:
                                                                    logger.warning(f"[MODE_DOCUMENTS] ❌ REJECTED AI Memory ID {m_id}! DB Judul: '{db_judul}' != LLM Judul: '{m_judul}'")
                                                        
                                                        # Coba fetch by Noper jika m_id bukan angka (seringkali LLM menaruh noper di field ID)
                                                        if not row and m_id and not m_id.isdigit():
                                                            sql = """
                                                                SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.noper
                                                                FROM berita b
                                                                LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                                                                WHERE b.noper = %s OR b.judul LIKE %s
                                                                LIMIT 1
                                                            """
                                                            await cur.execute(sql, (m_id, f"%{m_id}%"))
                                                            candidate_row = await cur.fetchone()
                                                            if candidate_row:
                                                                row = candidate_row
                                                                logger.info(f"[MODE_DOCUMENTS] 🌟 AI Memory Recovered: Noper found in ID field: {m_id}")
                                                                
                                                        # Kalau ID salah (halusinasi), cari by judul (FULL TEXT SEARCH) sebagai Fallback Recovery
                                                        if not row and m_judul:
                                                            safe_judul = m_judul.replace("/", " ").replace("-", " ").replace(".", " ")
                                                            safe_judul = "".join([c for c in safe_judul[:100] if c.isalnum() or c.isspace()]).strip()
                                                            words = [w for w in safe_judul.split() if len(w) > 3]
                                                            if words:
                                                                match_str = " ".join([w for w in words[:6]]) # Tanpa `+` agar tidak wajib (soft match ranked)
                                                                sql = """
                                                                    SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.noper 
                                                                    FROM berita b 
                                                                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori 
                                                                    WHERE MATCH(b.judul, b.tag, b.isi_berita) AGAINST(%s IN NATURAL LANGUAGE MODE) 
                                                                    LIMIT 5
                                                                """
                                                                await cur.execute(sql, (match_str,))
                                                                candidates = await cur.fetchall()
                                                                
                                                                import difflib
                                                                best_match = None
                                                                best_ratio = 0.0
                                                                
                                                                llm_combined = f"{m_id} {m_judul}".lower()
                                                                for candidate_row in candidates:
                                                                    db_combined = f"{candidate_row[6] or ''} {candidate_row[1]}".lower()
                                                                    ratio = difflib.SequenceMatcher(None, db_combined, llm_combined).ratio()
                                                                    if ratio > best_ratio:
                                                                        best_ratio = ratio
                                                                        best_match = candidate_row
                                                                        
                                                                if best_match and best_ratio > 0.65:
                                                                    row = best_match
                                                                    logger.info(f"[MODE_DOCUMENTS] 🌟 AI Memory Recovered: Hallucinated ID {m_id} -> Found real ID {row[0]} using Title search: '{m_judul}' (Ratio: {best_ratio:.2f})")
                                                                else:
                                                                    logger.warning(f"[MODE_DOCUMENTS] ❌ FTS Fallback REJECTED! Best ratio {best_ratio:.2f} for LLM Judul: '{llm_combined}'")
                                                        
                                                        if row:
                                                            id_berita, db_judul, gambar, gambar2, gambar3, nama_kategori, noper = row
                                                            
                                                            valid_file = None
                                                            for file_name in [gambar, gambar2, gambar3]:
                                                                if file_name and isinstance(file_name, str) and file_name.lower().endswith(".pdf"):
                                                                    valid_file = file_name
                                                                    break
                                                            if valid_file:
                                                                filtered_sources.append({
                                                                    "id": str(id_berita),
                                                                    "title": db_judul,
                                                                    "document_title": db_judul,
                                                                    "filename": valid_file,
                                                                    "file_path": f"file_peraturan/{valid_file}",
                                                                    "jenis": nama_kategori or "Regulasi",
                                                                    "nomor": noper or "N/A",
                                                                    "score_label": "AI_MEMORY_RECOVERED",
                                                                    "score": 1.0
                                                                })
                                        parsing_success = True
                                except Exception as e:
                                    logger.warning(f"[MODE_DOCUMENTS] Gagal parse sources_json: {e}. Raw: {json_str}")
                                
                                if parsing_success:
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