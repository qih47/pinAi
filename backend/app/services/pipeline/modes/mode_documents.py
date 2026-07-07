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

        rag_context = None
        rag_sources = None

        # ── Step 2: Parallel Data Fetching ────────────────────────────────────────
        # 2A: Setup Background Tasks
        from backend.app.services.pipeline.community_knowledge import search_community_knowledge
        from backend.app.services.peraturan_service import search_and_ocr_by_judul
        
        task_community = asyncio.create_task(search_community_knowledge(user_message, is_guest=(current_user_npp == "GUEST")))
        query_judul = routing_data.get("query_judul")
        task_peraturan = asyncio.create_task(search_and_ocr_by_judul(query_judul))

        # 2B: Stream RAG progress while tasks run in background
        if rag_queries:
            logger.info(f"[MODE_DOCUMENTS] RAG triggered via Sub-Queries | queries={rag_queries}")
            yield format_sse(status="🔍 Mencari dokumen regulasi terkait", event_type=SSEEventType.STATUS)
            
            from backend.app.services.rag.rag_pipeline import run_rag_pipeline

            async for sse in run_rag_pipeline(
                rewritten_queries=rag_queries,
                limit_per_query=3,
                npp=current_user_npp,
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
                            from backend.app.services.chat_history_service import chat_history_service
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
            # Sort by similarity/score and take only the TOP 3 most relevant documents for the UI & LLM.
            rag_sources = sorted(rag_sources, key=lambda x: x.get('score', x.get('similarity', 0)), reverse=True)[:3]
            yield format_sse("", "", False, sources=rag_sources, event_type=SSEEventType.SOURCES)
            await asyncio.sleep(0.01)

        # Build prompt dengan parameter is_thinking dari FE
        # Amankan ukuran RAG context sebelum dirender
        safe_rag_context = rag_context[:25000] if rag_context else None
        
        system_prompt = build_call2_system_prompt(
            module_name=module_name,
            employee_name=employee_name,
            precheck=routing_data,
            is_thinking=is_thinking,
            rag_context=safe_rag_context,
            rag_sources=rag_sources
        )

        # ── Smart Context Truncation (Max ~42,000 chars / ~12k tokens total) ──
        # Tujuannya agar tersisa 4000 token untuk generasi jawaban.
        
        # Alokasikan budget karakter
        rag_budget = 25000 if not judul_context else 15000
        judul_budget = 25000 if not rag_context else 15000
        community_budget = 3000
        
        # Inject Community Knowledge
        if community_context:
            system_prompt += "\n\n" + community_context[:community_budget]
            
        # Inject Peraturan/Title Context
        if judul_context:
            system_prompt += "\n\n" + judul_context[:judul_budget]
            if len(judul_context) > judul_budget:
                system_prompt += "\n...[Teks Terpotong]..."
                
        # Perbaiki rag_context yang sebelumnya mungkin terlalu besar saat di-render di mode_utils
        # (Karena render prompt sudah terjadi, kita tidak bisa motong rag_context yang sudah di-inject,
        # TAPI kita harus pastikan RAG context di awal juga tidak kebesaran.
        # RAG context dibatasi oleh _RAG_CONTEXT_MAX_CHARS di rag_prompts.py, tapi kita potong aja textnya 
        # sebelum di pass ke build_call2_system_prompt di atas)

        # Inject Long-Term Memory (ai_document_chunks)
        session_chunks = routing_data.get("_session_chunks_text", "")
        if session_chunks:
            system_prompt += session_chunks

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
            from backend.app.services.chat_history_service import chat_history_service
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
                elif chunk_text or (eval_count > 0):
                    yield format_sse(chunk_text, "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration)

        except Exception as e:
            logger.error(f"[MODE_DOCUMENTS] Stream error: {e}")
            yield format_sse(f"Maaf, terjadi kendala teknis: {str(e)}", "", False, event_type=SSEEventType.CHUNK)