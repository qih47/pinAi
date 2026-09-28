import logging
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.pipeline.modes.mode_utils import select_responder_module, get_module_config, build_responder_system_prompt, sanitize_history_for_pronoun

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
        
        if current_user_npp == "GUEST":
            routing_data["is_guest"] = True
            routing_data["is_docwriter"] = False
        
        # Select module
        module_name = select_responder_module(routing_data, has_rag_context=False)
        logger.info(f"[MODE_FLASH] Selected module: {module_name}")

        # Build prompt
        system_prompt = build_responder_system_prompt(
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

        # Inject Employee Long-Term Memory (ai_memory & cross-session topics)
        if current_user_npp and current_user_npp != "GUEST":
            from backend.app.services.memory.memory_service import memory_service
            # Khusus chitchat: jika tidak ada indikasi recall masa lalu, jangan dump 4 sesi lama ke prompt
            is_recall = bool(routing_data and (routing_data.get("is_cross_session_recall") or routing_data.get("is_memory_recall")))
            include_past = True if (module_name != "chitchat" or is_recall) else False
            employee_memory = await memory_service.get_employee_long_term_memory(
                current_user_npp, 
                current_session_uuid=session_uuid,
                include_past_sessions=include_past
            )
            if employee_memory:
                system_prompt += employee_memory

        # Inject Session Context (ai_document_chunks) — On-Demand atau Manifest
        # Khusus chitchat: jangan bawa teks mentah scraping URL lampau kecuali jika router meminta on-demand
        if module_name == "chitchat":
            session_chunks = routing_data.get("_retrieved_session_chunks_text", "")
        else:
            session_chunks = routing_data.get("_retrieved_session_chunks_text") or routing_data.get("_session_chunks_text", "")
        if session_chunks:
            system_prompt += "\n\n" + session_chunks

        # Inject Live Document Snapshot (Mata AI CAKRA Document Studio)
        if current_user_npp and current_user_npp != "GUEST":
            try:
                from backend.app.services.document_writer.doc_writer_service import doc_writer_service
                from backend.app.services.document_writer.document_structure_parser import document_structure_parser
                from pathlib import Path

                room_id = (context_isolation.get("room_id") if context_isolation else None) or (routing_data.get("room_id") if routing_data else None) or ""
                active_doc = doc_writer_service.get_active_document(
                    npp=current_user_npp,
                    session_id=session_uuid or "",
                    room_id=room_id
                )
                if active_doc and active_doc.get("file_path"):
                    doc_path = Path(active_doc["file_path"])
                    if doc_path.exists():
                        doc_snapshot = document_structure_parser.get_prompt_snapshot(doc_path)
                        if doc_snapshot:
                            system_prompt += f"\n\n{doc_snapshot}\n"
                            logger.info(f"[MODE_FLASH] Injected live DocWriter snapshot for {doc_path.name} into system prompt")
            except Exception as e:
                logger.warning(f"[MODE_FLASH] Gagal mengambil snapshot dokumen aktif: {e}")

        from backend.app.services.pipeline.modes.mode_utils import resolve_history_messages
        needs_history = bool(routing_data.get("needs_history", False)) if routing_data else False
        active_pronoun = routing_data.get("pronoun", "formal_saya_anda") if routing_data else "formal_saya_anda"
        max_turns = 4 if module_name == "chitchat" else 6
        max_assistant_chars = 400 if module_name == "chitchat" else 600

        trimmed_messages = resolve_history_messages(
            chat_history=chat_history,
            user_message=user_message,
            needs_history=needs_history,
            max_turns=max_turns,
            max_assistant_chars=max_assistant_chars,
            active_pronoun=active_pronoun,
        )

        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        module_config = get_module_config(module_name)
        num_ctx = module_config["num_ctx"]
        temperature = module_config["temperature"]

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
        rag_tokens = 0 # Flash mode tidak pakai RAG
        total_used = sys_tokens + hist_tokens + rag_tokens
        
        # Log Agent Step for Responder Flash
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
            asyncio.create_task(chat_history_service.save_agent_step(
                session_id=session_uuid_to_use,
                step_number=2,
                tool_called="RESPONDER_FLASH",
                tool_input=f"Prompt chars: {len(system_prompt)}",
                observation=json.dumps(obs_dict)
            ))

        try:
            from backend.app.services.pipeline.agentic_interceptor import agentic_stream_wrapper
            async for chunk in agentic_stream_wrapper(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:31b"),
                messages=stream_messages,
                request=request,
                is_thinking=is_thinking,
                employee_name=employee_name,
                session_uuid=session_uuid_to_use,
                current_user_npp=current_user_npp,
                max_tool_loops=2,
                **module_config,
            ):
                yield chunk
            logger.info(f"[RESPONDER_FLASH] ✅ Finished generation | module={module_name} | needs_history={needs_history} | turns_sent={len(trimmed_messages)} | hist_tokens={hist_tokens}")
        except Exception as e:
            logger.error(f"[MODE_FLASH] Stream error: {e}")
            yield format_sse(f"Maaf, terjadi kendala teknis: {str(e)}", "", False, event_type=SSEEventType.CHUNK)
