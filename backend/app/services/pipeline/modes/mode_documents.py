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
        current_user_npp: Optional[str] = None
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

        # ── Step 2: RAG Pipeline Execution ────────────────────────────────────────
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

                    if event_type in (SSEEventType.SOURCES, SSEEventType.THINKING, SSEEventType.STATUS):
                        yield sse
                        await asyncio.sleep(0.005)

                except (json.JSONDecodeError, AttributeError):
                    yield sse
                    await asyncio.sleep(0.01)

        # ── Step 3: LLM Execution (Call 2) ────────────────────────────────────────
        module_name = select_call2_module(routing_data, has_rag_context=bool(rag_context))
        logger.info(f"[MODE_DOCUMENTS] Selected module: {module_name}")

        yield format_sse(status="✍️ Menyusun jawaban", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        if rag_sources:
            yield format_sse("", "", False, sources=rag_sources, event_type=SSEEventType.SOURCES)
            await asyncio.sleep(0.01)

        # Build prompt dengan parameter is_thinking dari FE
        system_prompt = build_call2_system_prompt(
            module_name=module_name,
            employee_name=employee_name,
            precheck=routing_data,
            is_thinking=is_thinking,
            rag_context=rag_context,
            rag_sources=rag_sources
        )

        # Fetch Community Knowledge untuk User Resmi (is_guest=False)
        from backend.app.services.pipeline.community_knowledge import search_community_knowledge
        community_context = await search_community_knowledge(user_message, is_guest=False)
        if community_context:
            system_prompt += community_context

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        # Mengambil 5 history + 1 current message = 6
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
        
        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        module_config = get_module_config(module_name)
        num_ctx = module_config["num_ctx"]
        temperature = module_config["temperature"]

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