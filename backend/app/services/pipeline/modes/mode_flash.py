import logging
import json
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.pipeline.modes.mode_utils import select_call2_module, get_module_config, build_call2_system_prompt

logger = logging.getLogger("MODE_FLASH")

class ModeFlash:
    """
    Mode Flash: Lightning Fast Executor without RAG.
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
        logger.info("[MODE_FLASH] Starting execution")
        
        # Determine Precheck/Routing if not provided by ModeAuto
        if not routing_data:
            routing_data = {}
            routing_data["is_coding"] = False
            routing_data["need_analytic"] = False
            routing_data["is_self_correction"] = False
            routing_data["is_ambiguous"] = False
            routing_data["is_multi_document"] = False
        
        # Select module
        module_name = select_call2_module(routing_data, has_rag_context=False)
        logger.info(f"[MODE_FLASH] Selected module: {module_name}")

        # Build prompt
        system_prompt = build_call2_system_prompt(
            module_name=module_name,
            employee_name=employee_name,
            precheck=routing_data,
            is_thinking=is_thinking
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

        yield format_sse(status="⚡ Mengeksekusi (Flash Mode)", event_type=SSEEventType.STATUS)

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
                    
                    # # 🔴 === TAMBAHAN DEBUG LOG CCTV === 🔴
                    # # Log kalau emang beneran masuk ke key 'thought'
                    # if native_thought:
                    #     logger.info(f"[CCTV THINK] {native_thought.strip()}")
                        
                    # # Log kalau ternyata tag <think> nyampur di teks biasa
                    # if "<think>" in chunk_text or "</think>" in chunk_text:
                    #     logger.warning(f"[CCTV ALERT] Tag Think nyampur di chunk_text: {chunk_text}")
                    # # 🔴 ================================== 🔴

                except (json.JSONDecodeError, AttributeError):
                    chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                    native_thought = ""
                    eval_count = 0
                    eval_duration = 0

                # If UI requested NO THINKING, we suppress the thought
                if native_thought and is_thinking:
                    yield format_sse("", native_thought, False, event_type=SSEEventType.THINKING)
                elif chunk_text or (eval_count > 0):
                    yield format_sse(chunk_text, "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration)
        except Exception as e:
            logger.error(f"[MODE_FLASH] Stream error: {e}")
            yield format_sse(f"Maaf, terjadi kendala teknis: {str(e)}", "", False, event_type=SSEEventType.CHUNK)
