import logging
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.pipeline.modes.mode_utils import select_call2_module, get_module_config, build_call2_system_prompt

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

        # ── Step 2: Parallel Data Fetching ────────────────────────────────────────
        # 2A: Setup Background Tasks
        from backend.app.services.pipeline.community_knowledge import search_community_knowledge
        from backend.app.services.peraturan_service import search_and_ocr_by_judul, search_and_ocr_by_synthetic_qa, hybrid_document_search
        
        task_community = asyncio.create_task(search_community_knowledge(user_message, is_guest=(current_user_npp == "GUEST")))
        query_judul_list = routing_data.get("query_judul") or []
        query_judul_str = " ".join(query_judul_list) if isinstance(query_judul_list, list) else str(query_judul_list)
        
        # FASE 3: HYBRID LATE FUSION RERANKING
        logger.info(f"[MODE_DOCUMENTS] Sending query_judul_list to Hybrid FTS: {query_judul_list}")
        task_peraturan = asyncio.create_task(hybrid_document_search(user_message, query_judul_list))

        # 2B: Stream RAG progress while tasks run in background
        if rag_queries:
            logger.info(f"[MODE_DOCUMENTS] RAG triggered via Sub-Queries | queries={rag_queries}")
            yield format_sse(status="🔍 Mencari dokumen regulasi terkait", event_type=SSEEventType.STATUS)
            
            from backend.app.services.rag.rag_pipeline import run_rag_pipeline

            async for sse in run_rag_pipeline(
                rewritten_queries=rag_queries,
                limit_per_query=3,
                npp=current_user_npp,
                use_cache=False, # SPRINT 5: Nonaktifkan semantic cache di mode documents
            ):
                raw = sse.strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    event_type = data.get("event_type")

                    if event_type == SSEEventType.PIPELINE_DATA:
                        rag_context = data["payload"].get("context")
                        rag_sources = data["payload"].get("sources")
                        logger.info(f"[MODE_DOCUMENTS] RAG done | {len(rag_context or '')} chars | {len(rag_sources or [])} sources")
                        
                        # Log Agent Step for RAG Search
                        session_uuid = routing_data.get("_session_uuid") if routing_data else None
                        if session_uuid:
                            from backend.app.services.chat.chat_history_service import chat_history_service
                            sources_data = []
                            for s in (rag_sources or []):
                                sources_data.append({
                                    "title": s.get('title') or s.get('filename') or s.get('document_title', 'Unknown'),
                                    "doc_id": s.get('dokumen_id') or s.get('id') or s.get('document_id', ''),
                                    "score": s.get('score') or s.get('similarity', 0)
                                })
                            obs_json = {
                                "msg": f"Found {len(rag_sources or [])} sources",
                                "queries": rag_queries,
                                "sources": sources_data
                            }
                            await chat_history_service.save_agent_step(
                                session_id=session_uuid,
                                step_number=2,
                                tool_called="RAG_SEARCH",
                                tool_input=str(rag_queries),
                                observation=json.dumps(obs_json)
                            )

                    if event_type in (SSEEventType.SOURCES, SSEEventType.THINKING, SSEEventType.STATUS):
                        if event_type == SSEEventType.SOURCES:
                            continue # Intercept and delay rendering sources to FE until we filter it
                        yield sse
                        await asyncio.sleep(0.005)

                except (json.JSONDecodeError, AttributeError):
                    yield sse
                    await asyncio.sleep(0.01)

        # 2C: Tunggu proses paralel selesai
        yield format_sse(status="⏳ Memproses riwayat percakapan & scan file...", event_type=SSEEventType.STATUS)
        community_context = await task_community
        judul_context, ocr_attachments, judul_sources = await task_peraturan

        # ── 2D: EVALUASI DAN LOG HASIL PENCARIAN KE TERMINAL ──
        has_title = False
        has_tag = False
        has_isi = False
        has_rag = bool(rag_sources)

        has_community = bool(community_context and community_context.strip())

        search_words = [w.lower() for w in query_judul_str.split() if len(w) > 2]
        
        if judul_sources:
            for src in judul_sources:
                raw_judul = str(src.pop("raw_judul", "")).lower()
                raw_tag = str(src.pop("raw_tag", "")).lower()
                raw_isi = str(src.pop("raw_isi", "")).lower()
                
                for word in search_words:
                    if word in raw_judul: has_title = True
                    if word in raw_tag: has_tag = True
                    if word in raw_isi: has_isi = True

        has_semantic = bool(judul_sources)
        
        logger.info("\n" + "="*40 + "\n" +
                    "🔍 LOG STATUS PENCARIAN DOKUMEN\n" +
                    f"SEARCH_TITLE               : {'ADA' if has_title else 'TIDAK ADA'}\n" +
                    f"SEARCH_TAG                 : {'ADA' if has_tag else 'TIDAK ADA'}\n" +
                    f"SEARCH_ISI_BERITA          : {'ADA' if has_isi else 'TIDAK ADA'}\n" +
                    f"SEARCH_SEMANTIC            : {'ADA' if has_semantic else 'TIDAK ADA'}\n" +
                    f"SEARCH_RAG                 : {'ADA' if has_rag else 'TIDAK ADA'}\n" +
                    f"SEARCH_AI_DIALOGUE_CORPUS  : {'ADA' if has_community else 'TIDAK ADA'}\n" +
                    "="*40)

        # ── Step 3: LLM Execution (Call 2) ────────────────────────────────────────
        module_name = select_call2_module(routing_data, has_rag_context=bool(rag_context))
        logger.info(f"[MODE_DOCUMENTS] Selected module: {module_name}")

        yield format_sse(status="✍️ Menyusun jawaban", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        # Jika dapet file spesifik dari MySQL (Peraturan Service), paksa gabungin ke RAG Sources!
        if judul_sources:
            if not rag_sources:
                rag_sources = []
            for src in reversed(judul_sources):
                rag_sources.insert(0, src) # Taruh di urutan pertama (paling relevan)

        if rag_sources:
            # Sort by similarity/score and take up to 15 documents to preserve genealogy/silsilah history.
            rag_sources = sorted(rag_sources, key=lambda x: x.get('score', x.get('similarity', 0)), reverse=True)[:15]
            # SPRINT 5: Kita TUNDA pengiriman event SOURCES ke frontend di sini!
            # Event SOURCES baru akan dikirim nanti setelah di-filter lewat interceptor <sources_json>
            # yield format_sse("", "", False, sources=rag_sources, event_type=SSEEventType.SOURCES)

        # Build prompt dengan parameter is_thinking dari FE
        # ── Smart Context Truncation (Max ~42,000 chars / ~12k tokens total) ──
        # Tujuannya agar tersisa 4000 token untuk generasi jawaban.
        
        # Alokasikan budget karakter
        rag_budget = 25000 if not judul_context else 15000
        judul_budget = 25000 if not rag_context else 15000
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

        # Inject Long-Term Memory (ai_document_chunks)
        session_chunks = routing_data.get("_session_chunks_text", "")
        if session_chunks:
            system_prompt = session_chunks + "\n\n" + system_prompt

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        # Mengambil 5 history + 1 current message = 6
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
        
        # Inject OCR Images to the last user message
        if ocr_attachments:
            images = [att["base64"] for att in ocr_attachments if att.get("type") == "image"]
            if images:
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
                num_predict=8192,
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
                                            import os
                                            PERATURAN_DIR = "/home/qisthi/pinAi/file_peraturan"
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
                                    final_sources = filtered_sources
                                else:
                                    final_sources = []
                                
                                yield format_sse("", "", False, sources=final_sources, event_type=SSEEventType.SOURCES)
                                
                                remainder = intercept_buffer[end_idx + len("</sources_json>"):]
                                if remainder:
                                    yield format_sse(remainder, "", False, event_type=SSEEventType.CHUNK)
                                intercept_buffer = ""
                        else:
                            if len(intercept_buffer) > 25 and "<sources_json>" not in intercept_buffer:
                                json_intercepted = True
                                yield format_sse("", "", False, sources=rag_sources[:10] if rag_sources else [], event_type=SSEEventType.SOURCES)
                                yield format_sse(intercept_buffer, "", False, event_type=SSEEventType.CHUNK)
                                intercept_buffer = ""
                    else:
                        yield format_sse(chunk_text, "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration)
                elif eval_count > 0:
                    yield format_sse("", "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration)

        except Exception as e:
            logger.error(f"[MODE_DOCUMENTS] Stream error: {e}")
            yield format_sse(f"Maaf, terjadi kendala teknis: {str(e)}", "", False, event_type=SSEEventType.CHUNK)
            
        # Ensure we flush if stream ends before interceptor finishes
        if not json_intercepted:
            yield format_sse("", "", False, sources=rag_sources[:10] if rag_sources else [], event_type=SSEEventType.SOURCES)
            if intercept_buffer:
                yield format_sse(intercept_buffer, "", False, event_type=SSEEventType.CHUNK)