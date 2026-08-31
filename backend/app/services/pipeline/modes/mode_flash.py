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
        current_user_npp: Optional[str] = None,
        session_uuid: Optional[str] = None
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

        # Fetch Community Knowledge untuk User Resmi (is_guest=False), SKIP jika modul chitchat atau sapaan sederhana
        if module_name != "chitchat":
            from backend.app.services.pipeline.community_knowledge import search_community_knowledge
            clean_msg = user_message.strip().lower()
            simple_greetings = {"hai", "halo", "hallo", "helo", "pagi", "siang", "sore", "malam", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "terima kasih", "makasih", "ok", "oke", "siap", "baik", "test", "tes"}
            if len(clean_msg) >= 10 and clean_msg not in simple_greetings:
                community_context = await search_community_knowledge(user_message, is_guest=False)
                if community_context:
                    system_prompt += community_context
        else:
            logger.info("[MODE_FLASH] Skipping community knowledge search for chitchat/greeting module.")

        # Inject Employee Long-Term Memory (ai_memory) - lewati pada modul sapaan agar respon instan
        if current_user_npp and current_user_npp != "GUEST" and module_name != "chitchat":
            from backend.app.services.memory.memory_service import memory_service
            employee_memory = await memory_service.get_employee_long_term_memory(current_user_npp)
            if employee_memory:
                system_prompt += employee_memory

        # Inject Session Context (ai_document_chunks) — On-Demand atau Manifest
        session_chunks = routing_data.get("_retrieved_session_chunks_text") or routing_data.get("_session_chunks_text", "")
        if session_chunks:
            system_prompt += "\n\n" + session_chunks

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        # Mengambil lean history: 4 pesan terakhir untuk chitchat, 6 pesan untuk modul lainnya
        if module_name == "chitchat":
            trimmed_messages = messages_dict[-4:] if len(messages_dict) > 4 else messages_dict
        else:
            trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
        
        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        module_config = get_module_config(module_name)
        num_ctx = module_config["num_ctx"]
        temperature = module_config["temperature"]

        yield format_sse(status="⚡ Menyiapkan respon", event_type=SSEEventType.STATUS)

        # Hitung estimasi token (1 token ~ 4 karakter)
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in trimmed_messages) // 4
        rag_tokens = 0 # Flash mode tidak pakai RAG
        total_used = sys_tokens + hist_tokens + rag_tokens
        
        # Log Agent Step for Call 2 Flash
        session_uuid_to_use = session_uuid or (routing_data.get("_session_uuid") if routing_data else None)
        if session_uuid_to_use:
            from backend.app.services.chat.chat_history_service import chat_history_service
            obs_dict = {
                "msg": f"Generating fast response using module: {module_name}",
                "memory": {
                    "system_tokens": sys_tokens,
                    "history_tokens": hist_tokens,
                    "rag_tokens": rag_tokens,
                    "total_used": total_used,
                    "max_ctx": num_ctx
                }
            }
            await chat_history_service.save_agent_step(
                session_id=session_uuid_to_use,
                step_number=2,
                tool_called="CALL_2_FLASH",
                tool_input=f"Prompt chars: {len(system_prompt)}",
                observation=json.dumps(obs_dict)
            )

        try:
            from backend.app.services.pipeline.agentic_interceptor import agentic_stream_wrapper
            async for chunk in agentic_stream_wrapper(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
                messages=stream_messages,
                request=request,
                is_thinking=is_thinking,
                employee_name=employee_name,
                session_uuid=session_uuid_to_use,
                max_tool_loops=1,
                **module_config,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"[MODE_FLASH] Stream error: {e}")
            yield format_sse(f"Maaf, terjadi kendala teknis: {str(e)}", "", False, event_type=SSEEventType.CHUNK)
