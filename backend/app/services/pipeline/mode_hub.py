import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.modes.mode_flash import ModeFlash
from backend.app.services.pipeline.modes.mode_documents import ModeDocuments
from backend.app.services.pipeline.modes.mode_guest import ModeGuest
from backend.app.services.pipeline.modes.mode_attachment import ModeAttachment
from backend.app.services.pipeline.modes.mode_generate_file import ModeGenerateFile

from backend.app.services.pipeline.modes.mode_utils import detect_precheck
from backend.app.services.pipeline.call1_router import execute_call1_routing
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType

logger = logging.getLogger("CAKRA_MODE_HUB")

class ModeHub:
    """
    Facade / Hub Pattern for Chat Modes.
    Centralizes Call 1 routing before dispatching to Flash or Documents.
    """

    def __init__(self):
        self.mode_handlers = {
            "flash": ModeFlash(),
            "documents": ModeDocuments(),
            "guest": ModeGuest(),
            "attachment": ModeAttachment(),
            "generate_file": ModeGenerateFile(),  # Interceptor-Analyst Pipeline
        }

    async def execute(
        self,
        user_message: str,
        chat_history: List[ChatMessageSchema],
        chat_mode: str,
        is_thinking: bool,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_isolation: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        employee_name: str = "Pegawai",
        current_user_npp: Optional[str] = None,
        session_uuid: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Main entry point for stream.py to route the request to the correct mode handler.
        """
        logger.info(f"[MODE_HUB] Starting execution for chat_mode: {chat_mode.upper()}")
        
        # ── Step 1: Pre-check rule-based ──────────────────────────────────────────
        has_attachment = bool(attachments)
        precheck = detect_precheck(user_message, chat_mode, has_attachment)
        precheck["_user_message"] = user_message

        # ── Fetch Long-Term Memory (ai_document_chunks) ────────────────────────
        session_chunks_text = ""
        if session_uuid:
            from backend.app.services.chat_history_service import chat_history_service
            chunks = await chat_history_service.get_session_document_chunks(session_uuid)
            if chunks:
                session_chunks_text = "\n\n[KNOWLEDGE DARI FILE SEBELUMNYA DI SESI INI]\n" + "\n---\n".join(chunks)
        precheck["_session_chunks_text"] = session_chunks_text

        # ── Fast-path Bypass untuk Attachment ──────────────────────────────────────
        if has_attachment:
            logger.info("[MODE_HUB] Attachment detected! Bypassing Call 1 and routing to Attachment Mode.")
            handler = self.mode_handlers["attachment"]
            async for chunk in handler.execute(
                user_message=user_message,
                chat_history=chat_history,
                is_thinking=is_thinking,
                attachments=attachments,
                context_isolation=context_isolation,
                routing_data=precheck,
                request=request,
                employee_name=employee_name,
                current_user_npp=current_user_npp
            ):
                yield chunk
            return

        # ── Step 2: Call 1 — Intent Classification & Routing ──────────────────────
        yield format_sse(status="🧠 Menganalisis intent pesan", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        
        # Ekstrak 1 history pesan terakhir (pesan AI sebelumnya) untuk Call 1
        context_history_str = ""
        if len(messages_dict) >= 2:
            last_ai_msg = messages_dict[-2]
            # Pastikan ini benar-benar pesan AI/assistant
            if last_ai_msg['role'] != 'user':
                full_text = last_ai_msg['content']
                trimmed_text = full_text[-500:] if len(full_text) > 500 else full_text
                context_history_str = f"{last_ai_msg['role'].upper()} (Last Words): ...{trimmed_text}"
            elif len(messages_dict) >= 3:
                # Fallback jika yang kedua terakhir adalah user, ambil yang ketiga terakhir
                last_ai_msg = messages_dict[-3]
                full_text = last_ai_msg['content']
                trimmed_text = full_text[-500:] if len(full_text) > 500 else full_text
                context_history_str = f"{last_ai_msg['role'].upper()} (Last Words): ...{trimmed_text}"

        # ── Fast-path Bypass untuk Sapaan Ringan ──────────────────────────────────
        is_guest = (current_user_npp == "GUEST")

        if precheck.get("is_chitchat") or precheck.get("is_greeting"):
            from backend.app.services.pipeline.call1_router import _build_fallback_routing
            logger.info("[MODE_HUB] Bypassing Call 1 for simple chitchat/greeting")
            routing_data = _build_fallback_routing(precheck)
        else:
            routing_data = await execute_call1_routing(
                request=request,
                user_message=user_message,
                context_history_str=context_history_str,
                precheck=precheck,
                ocr_text=None,
                is_guest=is_guest,
            )

        logger.info(
            f"[MODE_HUB] Call 1 complete | need_rag={routing_data.get('need_rag')} | "
            f"is_coding={routing_data.get('is_coding')} | queries={routing_data.get('queries')}"
        )

        if current_user_npp == "GUEST":
            routing_data["need_rag"] = False
            logger.info("[MODE_HUB] GUEST User detected — RAG forcefully disabled.")

        precheck.update(routing_data)

        # ── Step 3: Route to specific mode ──────────────────────────────────────────
        # Ensure mode exists, fallback to auto
        mode = chat_mode if chat_mode in self.mode_handlers else "auto"

        # ── Priority 1: is_generate_file intent (Interceptor-Analyst Pipeline) ──────
        if routing_data.get("is_generate_file") and not is_guest:
            logger.info("[MODE_HUB] is_generate_file=True detected → routing to GENERATE_FILE mode")
            mode = "generate_file"
        elif mode == "auto":
            need_rag = routing_data.get("need_rag", False)
            if need_rag:
                mode = "documents"
            else:
                mode = "flash"
        
        logger.info(f"[MODE_HUB] Dispatching request to Mode: {mode.upper()}")
        
        handler = self.mode_handlers[mode]
        
        # We delegate the actual generator execution to the handler
        async for chunk in handler.execute(
            user_message=user_message,
            chat_history=chat_history,
            is_thinking=is_thinking,
            attachments=attachments,
            context_isolation=context_isolation,
            routing_data=precheck,
            request=request,
            employee_name=employee_name,
            current_user_npp=current_user_npp,
            session_uuid=session_uuid
        ):
            yield chunk

mode_hub = ModeHub()
