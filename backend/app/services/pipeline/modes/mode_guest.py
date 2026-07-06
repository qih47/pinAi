import logging
import json
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings

logger = logging.getLogger("MODE_GUEST")

class ModeGuest:
    """
    Mode Guest: Khusus untuk pengguna yang belum login.
    Fitur:
    - Tanpa RAG (Mengabaikan RAG sepenuhnya)
    - Tanpa Thinking Mode (dipaksa False)
    - Memiliki System Prompt tersendiri yang tidak menggunakan `system_prompts.py`
    - Memanggil pengguna dengan "Teman" atau "Rekan", dilarang menyebut "Guest".
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
        employee_name: str = "Pegawai",  # Akan di-ignore
        current_user_npp: Optional[str] = None,
        session_uuid: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        
        logger.info("[MODE_GUEST] Starting execution for Guest User")
        
        # 1. Tentukan modul Call 2 untuk Guest berdasarkan routing_data
        if not routing_data:
            routing_data = {}
            
        from backend.app.services.pipeline.modes.mode_utils import select_call2_module
        module_name = select_call2_module(routing_data, has_rag_context=False)
        logger.info(f"[MODE_GUEST] Selected guest module: {module_name}")
        
        # 2. Build Custom Guest System Prompt
        from backend.app.services.pipeline.guest_prompts import build_call2_system_prompt_guest
        system_prompt = build_call2_system_prompt_guest(module_name, precheck=routing_data)

        # 3. Fetch Community Knowledge untuk Guest
        from backend.app.services.pipeline.community_knowledge import search_community_knowledge
        community_context = await search_community_knowledge(user_message, is_guest=True)
        if community_context:
            system_prompt += community_context

        # 4. Persiapkan Messages untuk Ollama
        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        # Mengambil 5 history + 1 current message = 6
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
        
        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        # 3. Parameter khusus Guest (Hemat Resource)
        num_ctx = 16384
        temperature = 0.6
        # Pastikan thinking selalu off
        is_thinking = False

        yield format_sse(status="⚡ Mengeksekusi (Guest Mode)", event_type=SSEEventType.STATUS)

        # Hitung estimasi token (1 token ~ 4 karakter)
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in trimmed_messages) // 4
        rag_tokens = 0 # Guest mode tidak pakai RAG
        total_used = sys_tokens + hist_tokens + rag_tokens

        # Log Agent Step for Call 2 Guest
        session_uuid_to_use = session_uuid or (routing_data.get("_session_uuid") if routing_data else None)
        if session_uuid_to_use:
            from backend.app.services.chat_history_service import chat_history_service
            obs_dict = {
                "msg": "Generating fast response using module: guest",
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
                tool_called="CALL_2_GUEST",
                tool_input=f"Prompt chars: {len(system_prompt)}",
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
                num_predict=4096,
                is_thinking=is_thinking,
            ):
                try:
                    chunk_data = json.loads(chunk_line.strip())
                    chunk_text = chunk_data.get("chunk", "")
                    
                    if chunk_text:
                        yield format_sse(chunk_text, "", False, event_type=SSEEventType.CHUNK)
                        
                except (json.JSONDecodeError, AttributeError):
                    chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                    if chunk_text:
                        yield format_sse(chunk_text, "", False, event_type=SSEEventType.CHUNK)

        except Exception as e:
            logger.error(f"[MODE_GUEST] Streaming error: {str(e)}", exc_info=True)
            yield format_sse(
                "\n\n⚠️ *Maaf, terjadi kesalahan saat menyusun respons Guest.*",
                "",
                False,
                event_type=SSEEventType.CHUNK
            )

        yield format_sse("", "", True, event_type=SSEEventType.DONE)
        logger.info("[MODE_GUEST] Execution complete")
