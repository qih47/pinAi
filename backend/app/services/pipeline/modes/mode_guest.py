import logging
import json
import asyncio
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
        
        # 1. Tentukan modul Responder untuk Guest berdasarkan routing_data
        if not routing_data:
            routing_data = {}
            
        from backend.app.services.pipeline.modes.mode_utils import select_responder_module
        module_name = select_responder_module(routing_data, has_rag_context=False)
        logger.info(f"[MODE_GUEST] Selected guest module: {module_name}")
        
        # 2. Build Custom Guest System Prompt
        from backend.app.services.pipeline.guest_prompts import build_guest_responder_prompt
        system_prompt = build_guest_responder_prompt(module_name, precheck=routing_data)

        # 3. Fetch Community Knowledge untuk Guest
        from backend.app.services.pipeline.community_knowledge import search_community_knowledge
        community_context = await search_community_knowledge(user_message, is_guest=True)
        if community_context:
            system_prompt += community_context

        # 3b. Fetch External Public RAG Documents (STRICT ISOLATION: EXTERNAL ONLY)
        try:
            from backend.app.services.rag.rag_service import rag_service
            rag_context, retrieved_chunks = await rag_service.assemble_powerful_context(
                query=user_message,
                limit=3,
                allowed_access_tiers=["EXTERNAL"]  # Only public external documents
            )
            if rag_context:
                system_prompt += f"\n\n[DOKUMEN PANDUAN PUBLIK / EKSTERNAL]:\n{rag_context}\n"
        except Exception as e:
            logger.warning(f"[MODE_GUEST] Optional external RAG lookup skipped: {e}")

        # 3. Inject Session Context (URL content / web fetch / ai_document_chunks)
        # Persis seperti mode_flash — konten URL yang sudah di-fetch server-side diinjeksi ke sini
        session_chunks = routing_data.get("_retrieved_session_chunks_text") or routing_data.get("_session_chunks_text", "")
        if session_chunks:
            system_prompt += "\n\n" + session_chunks

        # 4. Persiapkan Messages untuk Ollama
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

        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        # 3. Parameter khusus Guest
        num_ctx = 16384
        temperature = 0.6
        # Pastikan thinking selalu off
        is_thinking = False
        # Standarisasi status SSE agar persis sama dengan Mode Flash
        if routing_data and routing_data.get("requires_visual"):
            if routing_data.get("visual_type") == "mermaid":
                yield format_sse(status="🔄 Menggambar diagram", status_key="DIAGRAM_RENDERING", event_type=SSEEventType.STATUS)
            elif routing_data.get("visual_type") == "chart":
                yield format_sse(status="📊 Membuat grafik", status_key="CHART_RENDERING", event_type=SSEEventType.STATUS)
            else:
                yield format_sse(status="✨ Merespons", status_key="PREPARING_RESPONSE", event_type=SSEEventType.STATUS)
        else:
            yield format_sse(status="✨ Merespons", status_key="PREPARING_RESPONSE", event_type=SSEEventType.STATUS)

        # Hitung estimasi token (1 token ~ 4 karakter)
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in trimmed_messages) // 4
        rag_tokens = 0 # Guest mode tidak pakai RAG
        total_used = sys_tokens + hist_tokens + rag_tokens

        # Log Agent Step for Responder Guest
        session_uuid_to_use = session_uuid or (routing_data.get("_session_uuid") if routing_data else None)
        if session_uuid_to_use:
            from backend.app.services.chat.chat_history_service import chat_history_service
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
            asyncio.create_task(chat_history_service.save_agent_step(
                session_id=session_uuid_to_use,
                step_number=2,
                tool_called="RESPONDER_GUEST",
                tool_input=f"Prompt chars: {len(system_prompt)}",
                observation=json.dumps(obs_dict)
            ))

        try:
            from backend.app.services.pipeline.agentic_interceptor import agentic_stream_wrapper
            async for chunk in agentic_stream_wrapper(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:31b"),
                messages=stream_messages,
                request=request,
                temperature=temperature,
                num_ctx=num_ctx,
                is_thinking=False,
                employee_name=employee_name,
                session_uuid=session_uuid_to_use,
                max_tool_loops=1
            ):
                yield chunk

        except Exception as e:
            logger.error(f"[MODE_GUEST] Streaming error: {str(e)}", exc_info=True)
            yield format_sse(
                "\n\n⚠️ *Maaf, terjadi kesalahan saat menyusun respons Guest.*",
                "",
                False,
                event_type=SSEEventType.CHUNK
            )

        yield format_sse("", "", True, event_type=SSEEventType.DONE)
        logger.info(f"[RESPONDER_GUEST] ✅ Finished generation | needs_history={needs_history} | turns_sent={len(trimmed_messages)} | hist_tokens={hist_tokens}")
