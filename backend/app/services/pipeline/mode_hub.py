import logging
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema, ChatMode
from backend.app.services.pipeline.modes.mode_flash import ModeFlash
from backend.app.services.pipeline.modes.mode_documents import ModeDocuments
from backend.app.services.pipeline.modes.mode_guest import ModeGuest
from backend.app.services.pipeline.modes.mode_attachment import ModeAttachment
from backend.app.services.pipeline.modes.mode_generate_file import ModeGenerateFile
from backend.app.services.pipeline.modes.mode_insight import ModeInsight
from backend.app.services.pipeline.modes.mode_focus import ModeFocus
from backend.app.services.pipeline.modes.mode_compliance import ModeCompliance
from backend.app.services.pipeline.modes.mode_redteam import ModeRedTeam
from backend.app.services.pipeline.modes.mode_email import ModeEmail

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
            "insight": ModeInsight(),
            "focus": ModeFocus(),
            "compliance": ModeCompliance(),
            "redteam": ModeRedTeam(),
            "email": ModeEmail()
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
        precheck["_session_uuid"] = session_uuid

        if chat_mode == "redteam":
            logger.info("[MODE_HUB] Routing to Red-Team Mode.")
            handler = self.mode_handlers["redteam"]
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
            
        if chat_mode == "compliance":
            logger.info("[MODE_HUB] Routing to Compliance Mode.")
            handler = self.mode_handlers["compliance"]
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

        if chat_mode == "insight":
            logger.info("[MODE_HUB] Explicit Insight Mode detected! Bypassing call 1.")
            if session_uuid:
                from backend.app.services.chat_history_service import chat_history_service
                radar_scores = {"dokumen": 10, "coding": 10, "chitchat": 10, "analitik": 100, "ambigu": 10}
                obs_dict = {"msg": "Bypassing Call 1 -> INSIGHT", "radar": radar_scores}
                await chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="ROUTER_ENGINE",
                    tool_input="Direct Insight Request",
                    observation=json.dumps(obs_dict)
                )
            handler = self.mode_handlers["insight"]
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

        # ── Fast-path Bypass untuk Context Isolation (Focus Mode) ──────────────────
        if context_isolation and context_isolation.get("isolated_doc_id"):
            logger.info("[MODE_HUB] Context Isolation detected! Routing to Focus Mode.")
            if session_uuid:
                from backend.app.services.chat_history_service import chat_history_service
                radar_scores = {"dokumen": 100, "coding": 10, "chitchat": 10, "analitik": 10, "ambigu": 10}
                obs_dict = {"msg": "Bypassing Call 1 -> FOCUS", "radar": radar_scores}
                await chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="ROUTER_ENGINE",
                    tool_input="Context Isolation Active",
                    observation=json.dumps(obs_dict)
                )
            from backend.app.services.pipeline.modes.mode_focus import ModeFocus
            if "focus" not in self.mode_handlers:
                self.mode_handlers["focus"] = ModeFocus()
            
            handler = self.mode_handlers["focus"]
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

        # ── Fast-path Bypass untuk Attachment ──────────────────────────────────────
        if has_attachment:
            logger.info("[MODE_HUB] Attachment detected! Bypassing Call 1 and routing to Attachment Mode.")
            if session_uuid:
                from backend.app.services.chat_history_service import chat_history_service
                radar_scores = {"dokumen": 100, "coding": 10, "chitchat": 10, "analitik": 100, "ambigu": 10}
                obs_dict = {"msg": "Bypassing Call 1 -> ATTACHMENT", "radar": radar_scores}
                await chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="ROUTER_ENGINE",
                    tool_input="File Attachment Found",
                    observation=json.dumps(obs_dict)
                )
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
        is_first_chat = len(chat_history) <= 1

        # Jangan bypass Call 1 jika ini adalah first chat, agar Gemma bisa merumuskan session_title!
        if not is_first_chat and (precheck.get("is_chitchat") or precheck.get("is_greeting")):
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
                is_first_chat=is_first_chat,
            )

        logger.info(
            f"[MODE_HUB] Call 1 complete | need_rag={routing_data.get('need_rag')} | "
            f"is_coding={routing_data.get('is_coding')} | queries={routing_data.get('queries')}"
        )
        
        # ── Update Session Title (Gemma 4 Native) ──────────────────────────────────
        if is_first_chat and routing_data.get("session_title") and session_uuid:
            try:
                new_title = routing_data["session_title"].strip().strip('"').strip("'").strip(".").title()
                from backend.app.services.chat.chat_history_service import chat_history_service
                asyncio.create_task(
                    chat_history_service.update_title_direct(session_uuid, new_title)
                )
            except Exception as e:
                logger.error(f"[MODE_HUB] Failed to update session title direct: {e}")
        
        # ── Self-Learning Tone Memory (Background) ────────────────────────────────
        if current_user_npp and current_user_npp != "GUEST":
            detected_pronoun = routing_data.get("pronoun", "unknown")
            if detected_pronoun in ["informal_gue_lo", "formal_saya_anda"]:
                from backend.app.services.memory.memory_service import memory_service
                asyncio.create_task(
                    memory_service.update_communication_style_memory(
                        npp=current_user_npp, 
                        pronoun=detected_pronoun
                    )
                )
        
        # Construct Agentic Decision Radar data — Additive Gradual Scoring (0-100)
        user_msg_lower = user_message.lower()
        doc_keywords = ["peraturan", "aturan", "regulasi", "kebijakan", "sk ", "dokumen", "sop", "pedoman", "ketentuan", "prosedur", "seragam", "gaji", "cuti", "tunjangan"]
        code_keywords = ["kode", "code", "fungsi", "function", "bug", "error", "script", "debug", "implementasi", "api", "library", "class", "method"]

        # DOKUMEN axis
        dok_score = 0
        if routing_data.get("need_rag"):
            dok_score += 60
        if any(kw in user_msg_lower for kw in doc_keywords):
            dok_score += 25
        if len(routing_data.get("queries", [])) >= 3:
            dok_score += 15
        elif len(routing_data.get("queries", [])) >= 1:
            dok_score += 8

        # CODING axis
        code_score = 0
        if routing_data.get("is_coding"):
            code_score += 60
        if routing_data.get("is_generate_file"):
            code_score += 25
        if routing_data.get("needs_code_analysis"):
            code_score += 15
        if any(kw in user_msg_lower for kw in code_keywords):
            code_score += 10

        # CHITCHAT axis
        chat_score = 0
        if precheck.get("is_greeting"):
            chat_score += 70
        if precheck.get("is_chitchat"):
            chat_score += 50
        if not routing_data.get("need_rag") and not routing_data.get("is_coding"):
            chat_score += 20
        if len(user_message.split()) <= 5:
            chat_score += 15

        # ANALITIK axis
        analitik_score = 0
        if routing_data.get("need_analytic"):
            analitik_score += 70
        if routing_data.get("is_multi_document"):
            analitik_score += 20
        if routing_data.get("is_multi_turn_task"):
            analitik_score += 10

        # AMBIGU axis
        ambigu_score = 0
        if routing_data.get("is_ambiguous"):
            ambigu_score += 70
        if routing_data.get("is_multi_document"):
            ambigu_score += 15
        if len(user_message.split()) <= 3:
            ambigu_score += 20

        radar_scores = {
            "dokumen":  min(100, max(5, dok_score)),
            "coding":   min(100, max(5, code_score)),
            "chitchat": min(100, max(5, chat_score)),
            "analitik": min(100, max(5, analitik_score)),
            "ambigu":   min(100, max(5, ambigu_score)),
        }
        
        # Log Router Agent Step
        if session_uuid:
            from backend.app.services.chat_history_service import chat_history_service
            
            queries = routing_data.get('queries', [])
            obs_dict = {
                "msg": f"Decided to use: {'RAG' if routing_data.get('need_rag') else 'Flash'} Mode. Queries: {queries}",
                "radar": radar_scores
            }
            await chat_history_service.save_agent_step(
                session_id=session_uuid,
                step_number=1,
                tool_called="ROUTER_ENGINE",
                tool_input=user_message[:200],
                observation=json.dumps(obs_dict)
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
        elif routing_data.get("is_generate_email") and not is_guest:
            logger.info("[MODE_HUB] is_generate_email=True detected → routing to EMAIL mode")
            mode = "email"
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
