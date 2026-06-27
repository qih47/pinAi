import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.modes.mode_utils import detect_precheck
from backend.app.services.pipeline.call1_router import execute_call1_routing

logger = logging.getLogger("MODE_AUTO")

class ModeAuto:
    """
    Mode Auto: Intelligent Router.
    Executes Precheck -> Call 1 -> Routes to Flash or Documents mode.
    """
    async def execute(
        self,
        user_message: str,
        chat_history: List[ChatMessageSchema],
        is_thinking: bool,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_isolation: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        employee_name: str = "Pegawai",
        current_user_npp: Optional[str] = None,
        session_uuid: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        logger.info("[MODE_AUTO] Starting execution. Running precheck and Call 1.")
        
        has_attachment = bool(attachments)
        chat_mode = "auto"
        ocr_text = None 

        # ── Step 1: Pre-check rule-based ──────────────────────────────────────────
        precheck = detect_precheck(user_message, chat_mode, has_attachment)
        precheck["_user_message"] = user_message

        # ── Step 2: Call 1 — Intent Classification & Routing ──────────────────────
        yield format_sse(status="🧠 Menganalisis intent pesan", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        context_history_str = ""
        if len(messages_dict) > 1:
            context_history_str = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in messages_dict[-5:-1]]
            )

        # Call 1 dijalankan SECARA INDEPENDEN (tidak pakai is_thinking dari FE)
        routing = await execute_call1_routing(
            request=request,
            user_message=user_message,
            context_history_str=context_history_str,
            precheck=precheck,
            ocr_text=ocr_text,
        )

        logger.info(
            f"[MODE_AUTO] Call 1 complete | need_rag={routing.get('need_rag')} | "
            f"is_coding={routing.get('is_coding')} | queries={routing.get('queries')}"
        )

        precheck.update(routing)

        # ── Step 3: Route to specific mode ──────────────────────────────────────────
        need_rag = routing.get("need_rag", False)
        
        # Lazy load to avoid circular imports
        if need_rag:
            logger.info("[MODE_AUTO] Routing to ModeDocuments")
            from backend.app.services.pipeline.modes.mode_documents import ModeDocuments
            mode_handler = ModeDocuments()
        else:
            logger.info("[MODE_AUTO] Routing to ModeFlash")
            from backend.app.services.pipeline.modes.mode_flash import ModeFlash
            mode_handler = ModeFlash()

        # Oper Eksekusi Call 2 (Di sinilah is_thinking dari FE dipakai)
        async for chunk in mode_handler.execute(
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