import logging
import json
import asyncio
import os
import re
from datetime import datetime
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
from backend.app.services.pipeline.modes.mode_collab import ModeCollab

from backend.app.services.pipeline.modes.mode_utils import detect_precheck, format_session_title
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
            "email": ModeEmail(),
            "collab": ModeCollab()
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
        session_uuid: Optional[str] = None,
        has_new_document: bool = False,
        active_topic: Optional[str] = None,
        key_subject: Optional[str] = None,
        client_context: Optional[Dict[str, Any]] = None,
        forced_mode: Optional[str] = None,
        bypass_router: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Main entry point for stream.py to route the request to the correct mode handler.
        """
        logger.info(f"[MODE_HUB] Starting execution for chat_mode: {chat_mode.upper()}")
        
        # ── Step 1: Pre-check rule-based ──────────────────────────────────────────
        has_attachment = bool(attachments) or has_new_document

        # Ambil preferensi komunikasi default user dari database lintas sesi (cross-session memory)
        from backend.app.services.memory.memory_service import memory_service
        user_default_pronoun = await memory_service.get_employee_communication_preference(current_user_npp) if current_user_npp else "formal_saya_anda"

        precheck = detect_precheck(
            user_message, 
            chat_mode, 
            has_attachment, 
            user_default_pronoun=user_default_pronoun,
            chat_history=chat_history
        )
        precheck["_user_message"] = user_message
        precheck["user_default_pronoun"] = user_default_pronoun
        precheck["client_context"] = client_context

        is_guest = (current_user_npp == "GUEST")
        precheck["is_guest"] = is_guest
        if is_guest:
            precheck["is_docwriter"] = False
        # ── Fetch Long-Term Memory (ai_document_chunks) & Check Generic Title ────────
        session_chunks_text = ""
        visited_urls = []
        is_title_generic = False
        if session_uuid:
            from backend.app.services.chat.chat_history_service import chat_history_service
            # Paralelkan pembacaan title, manifest, dan document chunks untuk memangkas latensi I/O DB
            existing_title, session_chunks_text, chunks_with_meta = await asyncio.gather(
                chat_history_service.get_session_title(session_uuid),
                chat_history_service.get_session_knowledge_manifest(session_uuid),
                chat_history_service.get_session_document_chunks_with_meta(session_uuid),
                return_exceptions=True
            )
            existing_title = existing_title if isinstance(existing_title, str) else ""
            session_chunks_text = session_chunks_text if isinstance(session_chunks_text, str) else ""
            chunks_with_meta = chunks_with_meta if isinstance(chunks_with_meta, list) else []

            GENERIC_TITLES = {"obrolan baru", "percakapan baru", "salam", "sapaan", "sapaan pembuka", "obrolan cakra ai", "new chat", "untitled", "halo", "hai", ""}
            is_title_generic = not existing_title or existing_title.strip().lower() in GENERIC_TITLES

            if chunks_with_meta:
                # Ekstrak domain URL yang pernah dikunjungi untuk multi-turn URL awareness
                for c in chunks_with_meta:
                    meta = c.get("metadata", {})
                    if meta.get("source") == "url_read":
                        visited_urls.extend(meta.get("urls", []))

            # Ekstrak juga URL dari riwayat pesan chat langsung (agar instan tanpa lag async DB)
            if chat_history:
                try:
                    from backend.app.services.web_tools.url_reader import extract_urls_from_text
                    for m in chat_history:
                        content_str = getattr(m, "content", "") or ""
                        if content_str:
                            for u in extract_urls_from_text(content_str):
                                if u not in visited_urls:
                                    visited_urls.append(u)
                except Exception:
                    pass

            if visited_urls:
                visited_urls = list(set(visited_urls))  # deduplicate
                logger.info(f"[MODE_HUB] Loaded {len(visited_urls)} previously visited URL(s) from session memory & chat history: {visited_urls}")

        is_first_chat = (len(chat_history) <= 1)
        needs_title_update = is_first_chat or is_title_generic
        precheck["needs_title_update"] = needs_title_update
        precheck["has_prior_context"] = not is_first_chat
        precheck["_session_chunks_text"] = session_chunks_text
        precheck["_session_uuid"] = session_uuid
        precheck["_visited_urls"] = visited_urls

        # ── Ekstrak Context History untuk Multi-Turn Reasoning (Universal Call 1/Preset ⇄ Call 2 Sync) ──
        from backend.app.services.pipeline.modes.mode_utils import build_call2_history_context
        context_history_str, last_call2_state = build_call2_history_context(chat_history, user_message=user_message)
        
        # Inject state Call 2 terakhir ke precheck agar Preset dan Call 1 Utama mengetahui aksi Call 2 sebelumnya
        if last_call2_state:
            precheck.update(last_call2_state)
            logger.info(
                f"[MODE_HUB] 🔄 Universal Call 2 State Sync: action={last_call2_state.get('last_call2_action')} | "
                f"replying_wizard={last_call2_state.get('is_replying_to_wizard')} | "
                f"wizard_confirm={last_call2_state.get('is_wizard_confirmation')} | "
                f"prior_visual={last_call2_state.get('has_prior_visual')} | "
                f"prior_coding={last_call2_state.get('has_prior_coding')} | "
                f"prior_chitchat={last_call2_state.get('has_prior_chitchat')}"
            )

        # ── Step 1.5: Intercept URLs (Web Reader) — deteksi dulu, fetch nanti paralel ─────
        urls_in_text = []
        try:
            from backend.app.services.web_tools.url_reader import extract_urls_from_text
            detected_urls = extract_urls_from_text(user_message)
            if detected_urls:
                # Skip URL yang domain-nya sudah ada di session memory agar tidak double-inject context
                already_visited = set(visited_urls)
                urls_in_text = [u for u in detected_urls if u not in already_visited]
                skipped = [u for u in detected_urls if u in already_visited]
                if skipped:
                    logger.info(f"[MODE_HUB] Skipping {len(skipped)} already-visited URL(s): {skipped}")
                if urls_in_text:
                    logger.info(f"[MODE_HUB] Detected {len(urls_in_text)} new URL(s). Will fetch in parallel with Call1.")
                    precheck["has_url_context"] = True  # tandai dulu agar routing tahu
                    precheck["_detected_urls"] = urls_in_text
                elif skipped:
                    # URL sudah pernah dikunjungi dan kontennya ada di session memory
                    precheck["has_url_context"] = True  # masih tandai agar routing paham ada URL context
                    precheck["_detected_urls"] = skipped
                    logger.info("[MODE_HUB] All URLs already in session memory — using cached content, no re-fetch needed.")
            else:
                # Cek apakah user merujuk ke link/web dari turn sebelumnya (anaphora: "link itu", "web tadi", dll.)
                user_msg_lower = user_message.lower()
                LINK_REF_SIGNALS = [
                    "link itu", "link tadi", "link tersebut", "link nya", "linknya",
                    "web itu", "web tadi", "web tersebut", "web nya", "webnya",
                    "website itu", "website tadi", "website tersebut", "websitenya",
                    "tautan itu", "tautan tadi", "tautan tersebut", "tautannya",
                    "situs itu", "situs tadi", "situs tersebut", "situsnya"
                ]
                if any(sig in user_msg_lower for sig in LINK_REF_SIGNALS) and visited_urls:
                    logger.info(f"[MODE_HUB] 🔗 Multi-turn link reference detected ('link itu'/'web tadi'). Inheriting visited URLs: {visited_urls}")
                    precheck["has_url_context"] = True
                    precheck["_detected_urls"] = visited_urls
                    precheck["is_web_search"] = True
                    precheck["need_rag"] = False
        except ImportError:
            pass



        # ── ⚡ FAST-PATH BYPASS CALL 1 ROUTER (Jalur A: Klik Preset / Hint Item) ───
        if (bypass_router or forced_mode) and forced_mode:
            logger.info(f"[MODE_HUB] ⚡ Bypassing Call 1 Router due to explicit preset hint selection. Forced Mode: {forced_mode}")
            forced_mode_clean = forced_mode.lower().strip()

            # 🎯 JALUR PRESET ROUTING: Panggil e4b untuk deteksi ambiguitas, multi-turn queries, + generate title
            from backend.app.services.pipeline.call1_router import generate_call1_preset_routing
            preset_routing = await generate_call1_preset_routing(
                user_message=user_message,
                forced_mode=forced_mode_clean,
                is_first_chat=is_first_chat,
                context_history_str=context_history_str,
                previous_topic=active_topic or precheck.get("active_topic"),
                previous_subject=key_subject or precheck.get("key_subject"),
                precheck=precheck,
                request=request,
            )

            # Inject routing params ke precheck secara dinamis & konsisten (17 Kapabilitas Lengkap)
            for cap in [
                "is_ambiguous", "requires_visual", "need_analytic", "is_troubleshooting",
                "is_comparative", "has_actionable_workflow", "is_deep_research", "is_security_critical",
                "is_generate_file", "is_generate_email", "is_docwriter", "is_coding",
                "is_map_query", "is_chitchat", "is_web_search", "need_rag", "needs_history"
            ]:
                if preset_routing.get(cap) is True:
                    precheck[cap] = True

            for list_field in ["visual_types", "queries", "query_judul", "search_tags", "fetch_urls"]:
                if preset_routing.get(list_field):
                    precheck[list_field] = preset_routing[list_field]

            for str_field in ["active_topic", "key_subject", "ambiguity_reason"]:
                if preset_routing.get(str_field):
                    precheck[str_field] = preset_routing[str_field]

            if session_uuid:
                from backend.app.services.chat.chat_history_service import chat_history_service
                obs_dict = {"msg": f"Fast-Path Bypass Call 1 -> {forced_mode_clean.upper()}", "queries": precheck.get("queries", [user_message])}
                asyncio.create_task(chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="FAST_PATH_BYPASS",
                    tool_input=user_message[:200],
                    observation=json.dumps(obs_dict)
                ))

                # Update title sesi jika judul belum ada atau masih placeholder generik
                if needs_title_update:
                    preset_title = preset_routing.get("session_title")
                    if preset_title:
                        await chat_history_service.update_title_direct(session_uuid, preset_title)
                        logger.info(f"[MODE_HUB] ⚡ Preset routing generated title: '{preset_title}'")
                        yield json.dumps({
                            "event_type": "topic_update",
                            "topic": forced_mode_clean.title(),
                            "key_subject": preset_title
                        }) + "\n"
                elif preset_routing.get("active_topic") or preset_routing.get("key_subject"):
                    yield json.dumps({
                        "event_type": "topic_update",
                        "topic": preset_routing.get("active_topic", forced_mode_clean.title()),
                        "key_subject": preset_routing.get("key_subject", "")
                    }) + "\n"



            # 1. Web Search Mode Bypass
            if forced_mode_clean in ["websearch", "search", "web"]:
                yield format_sse(status="🌐 Menjelajah web", status_key="WEB_INIT", event_type=SSEEventType.STATUS)
                from backend.app.services.pipeline.modes.mode_web_search import handle_web_search
                history_dicts = [m.model_dump() for m in chat_history]
                if not history_dicts or history_dicts[-1]["content"] != user_message:
                    history_dicts.append({"role": "user", "content": user_message})

                precheck["is_web_search"] = True
                precheck["need_rag"] = False

                from backend.app.services.pipeline.call1_router import generate_call1_web_queries
                clean_queries = await generate_call1_web_queries(user_message, request)
                precheck["queries"] = clean_queries if clean_queries else [user_message]

                async for chunk in handle_web_search(
                    query=user_message,
                    messages=history_dicts,
                    request=request,
                    employee_name=employee_name,
                    precheck=precheck,
                    is_thinking=is_thinking
                ):
                    yield chunk
                return

            # 2. Document Search & Focus / Audit / Compliance / Redteam Mode Bypass
            elif forced_mode_clean in ["documents", "document", "rag", "focus", "audit", "compliance", "redteam"]:
                if is_guest:
                    logger.warning("[MODE_HUB] 🛡️ Blocked Guest from accessing internal documents via forced_mode bypass!")
                    yield format_sse(status="🔒 Akses Dokumen Terbatas", status_key="ACCESS_DENIED", event_type=SSEEventType.STATUS)
                    yield format_sse(
                        "🔒 **Akses Dokumen Internal Terbatas**\n\n"
                        "Mohon maaf, fitur penelusuran dokumen, regulasi, dan arsip internal PT Pindad hanya dapat diakses oleh **Pegawai Resmi PT Pindad**.\n\n"
                        "Silakan masuk (*Login*) menggunakan akun NPP Anda untuk membuka akses penuh ke arsip dan regulasi internal.",
                        "",
                        False,
                        event_type=SSEEventType.CHUNK
                    )
                    yield format_sse("", "", True, event_type=SSEEventType.DONE)
                    return

                yield format_sse(status="📚 Membuka arsip", status_key="DOCS_INIT", event_type=SSEEventType.STATUS)
                precheck["need_rag"] = True
                precheck["is_chitchat"] = False
                if not precheck.get("queries"):
                    precheck["queries"] = [user_message]

                # Jika terdapat context_isolation (misal user klik dokumen PKB/SOP dari hint):
                # Tentukan handler yang sesuai (compliance, redteam, atau focus)
                if context_isolation and (context_isolation.get("isolated_doc_id") or context_isolation.get("doc_id") or context_isolation.get("id_dokumen")):
                    target_mode_key = "focus"
                    if forced_mode_clean == "compliance" or chat_mode == "compliance":
                        target_mode_key = "compliance"
                    elif forced_mode_clean == "redteam" or chat_mode == "redteam":
                        target_mode_key = "redteam"

                    logger.info(f"[MODE_HUB] 🎯 Fast-Path Bypass routed directly to MODE_{target_mode_key.upper()} for isolated document: {context_isolation}")
                    handler = self.mode_handlers[target_mode_key]
                else:
                    handler = self.mode_handlers["documents"]

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
                return

            # 3. Code / Generate File Mode Bypass
            elif forced_mode_clean in ["code", "coding", "generate_file", "create_file"]:
                yield format_sse(status="💻 Menyiapkan kode", status_key="CODE_INIT", event_type=SSEEventType.STATUS)
                precheck["is_coding"] = True
                precheck["is_generate_file"] = True
                handler = self.mode_handlers["generate_file"]
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
                return

            # 4. Diagram / Flowchart Bypass
            elif forced_mode_clean in ["diagram", "flow", "flowchart"]:
                yield format_sse(status="📐 Merancang alur", status_key="DIAGRAM_INIT", event_type=SSEEventType.STATUS)
                precheck["requires_visual"] = True
                precheck["visual_type"] = "mermaid"
                precheck["is_web_search"] = False
                precheck["need_rag"] = False
                precheck["is_chitchat"] = False
                handler = self.mode_handlers["flash"]
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
                return

            # 5. Chart / Data Visualization Bypass
            elif forced_mode_clean in ["chart", "data", "visualization"]:
                yield format_sse(status="📈 Mengolah data", status_key="CHART_INIT", event_type=SSEEventType.STATUS)
                precheck["requires_visual"] = True
                precheck["visual_type"] = "chart"
                precheck["is_web_search"] = False
                precheck["need_rag"] = False
                precheck["is_chitchat"] = False
                handler = self.mode_handlers["flash"]
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
                return

            # 6. Smart Mail / Draft Surat Bypass
            elif forced_mode_clean in ["smart_mail", "mail", "email", "surat"]:
                yield format_sse(status="✉️ Menyusun surat", status_key="MAIL_INIT", event_type=SSEEventType.STATUS)
                handler = self.mode_handlers["email"]
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
                return

            # 7. Focus Mode Bypass
            elif forced_mode_clean in ["focus", "compliance"]:
                target_mode = forced_mode_clean if forced_mode_clean in self.mode_handlers else "focus"
                handler = self.mode_handlers[target_mode]
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
                return

        if chat_mode in ["redteam", "compliance", "insight"] or (context_isolation and context_isolation.get("isolated_doc_id")):
            if is_guest:
                logger.warning(f"[MODE_HUB] 🛡️ Blocked Guest from accessing internal mode ({chat_mode}) / context isolation!")
                yield format_sse(status="🔒 Fitur Khusus Pegawai", status_key="ACCESS_DENIED", event_type=SSEEventType.STATUS)
                yield format_sse(
                    "🔒 **Fitur Khusus Pegawai PT Pindad**\n\n"
                    "Fitur analisis mendalam, audit kepatuhan regulasi, red-teaming, dan penelusuran dokumen internal hanya dapat diakses oleh **Pegawai Resmi PT Pindad**.\n\n"
                    "Silakan masuk (*Login*) menggunakan akun NPP Anda untuk menggunakan fitur ini.",
                    "",
                    False,
                    event_type=SSEEventType.CHUNK
                )
                yield format_sse("", "", True, event_type=SSEEventType.DONE)
                return

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
                from backend.app.services.chat.chat_history_service import chat_history_service
                radar_scores = {"dokumen": 10, "coding": 10, "chitchat": 10, "analitik": 100, "ambigu": 10}
                obs_dict = {"msg": "Bypassing Call 1 -> INSIGHT", "radar": radar_scores}
                asyncio.create_task(chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="ROUTER_ENGINE",
                    tool_input="Direct Insight Request",
                    observation=json.dumps(obs_dict)
                ))
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

        # ── Fast-path Bypass untuk Context Isolation (Focus / Compliance / Redteam Mode) ──
        if context_isolation and (context_isolation.get("isolated_doc_id") or context_isolation.get("doc_id") or context_isolation.get("id_dokumen")):
            target_iso_mode = "focus"
            if chat_mode == "compliance" or forced_mode_clean == "compliance":
                target_iso_mode = "compliance"
            elif chat_mode == "redteam" or forced_mode_clean == "redteam":
                target_iso_mode = "redteam"

            logger.info(f"[MODE_HUB] Context Isolation detected! Routing to {target_iso_mode.upper()} Mode.")
            if session_uuid:
                from backend.app.services.chat.chat_history_service import chat_history_service
                radar_scores = {"dokumen": 100, "coding": 10, "chitchat": 10, "analitik": 10, "ambigu": 10}
                obs_dict = {"msg": f"Bypassing Call 1 -> {target_iso_mode.upper()}", "radar": radar_scores}
                asyncio.create_task(chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="ROUTER_ENGINE",
                    tool_input="Context Isolation Active",
                    observation=json.dumps(obs_dict)
                ))
            
            handler = self.mode_handlers.get(target_iso_mode, self.mode_handlers["focus"])
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
            return

        # ── Fast-path Interceptor: Document Interrogator Explicit Focus ──────────
        # Deteksi format [Fokus Dokumen "filename.pdf" Halaman X]: ...
        if not has_attachment:
            interrogator_match = re.search(
                r'\[Fokus Dokumen\s+"([^"]+)"(?:\s+Halaman\s+([0-9\s,\-]+))?\]:\s*(.*)', 
                user_message, 
                re.DOTALL | re.IGNORECASE
            )
            if interrogator_match:
                focus_filename = interrogator_match.group(1).strip()
                focus_clean_name = os.path.basename(focus_filename)
                
                # Cari berkas fisik di lokasi-lokasi potensial (Brain images, uploads, peraturan)
                candidate_paths = []
                if session_uuid and current_user_npp:
                    from backend.app.services.session.session_brain_service import SessionBrainService
                    brain_svc = SessionBrainService(current_user_npp, session_uuid)
                    candidate_paths.append(str(brain_svc.brain_dir / "images" / focus_clean_name))
                    candidate_paths.append(str(brain_svc.brain_dir / "documents" / focus_clean_name))
                
                from backend.app.core.paths import UPLOAD_DIR, FILE_PERATURAN_DIR
                candidate_paths.append(os.path.join(UPLOAD_DIR, focus_clean_name))
                candidate_paths.append(os.path.join(FILE_PERATURAN_DIR, focus_clean_name))
                
                from backend.app.services.peraturan_service import _find_valid_pdf_file
                cand_p = _find_valid_pdf_file(focus_clean_name)
                if cand_p:
                    candidate_paths.append(cand_p)

                found_focus_path = None
                for cp in candidate_paths:
                    if cp and os.path.exists(cp) and os.path.isfile(cp):
                        found_focus_path = cp
                        break

                if found_focus_path:
                    logger.info(f"[MODE_HUB] 🎯 Interrogator Focus detected! Resolved physical file: {found_focus_path}")
                    attachments = [{
                        "name": focus_clean_name,
                        "file_path": found_focus_path,
                        "path": found_focus_path,
                        "mime_type": "application/pdf"
                    }]
                    has_attachment = True
                    precheck["has_attachment"] = True

        # ── Fast-path Bypass untuk Attachment ──────────────────────────────────────
        if has_attachment:
            logger.info("[MODE_HUB] Attachment detected! Bypassing Call 1 and routing to Attachment Mode.")
            if session_uuid:
                from backend.app.services.chat.chat_history_service import chat_history_service
                radar_scores = {"dokumen": 100, "coding": 10, "chitchat": 10, "analitik": 100, "ambigu": 10}
                obs_dict = {"msg": "Bypassing Call 1 -> ATTACHMENT", "radar": radar_scores}
                asyncio.create_task(chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="ROUTER_ENGINE",
                    tool_input="File Attachment Found",
                    observation=json.dumps(obs_dict)
                ))
            if needs_title_update and session_uuid:
                try:
                    from backend.app.services.chat.chat_history_service import chat_history_service
                    file_name = attachments[0].get('file_name', 'Lampiran') if attachments else 'Lampiran'
                    base_name = format_session_title(file_name.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' '))
                    title = f"Analisis {base_name[:28]}"
                    asyncio.create_task(chat_history_service.update_session_title(session_uuid, title))
                    logger.info(f"[MODE_HUB] Attachment First-Chat Title updated -> '{title}'")
                except Exception as e:
                    logger.warning(f"[MODE_HUB] Gagal update attachment title: {e}")

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
                current_user_npp=current_user_npp,
                session_uuid=session_uuid
            ):
                yield chunk
            return

        # ── Fast-path Bypass untuk Lanjutan Audit Dokumen Sesi (Multi-Turn) ─────────
        if not has_attachment and session_uuid and current_user_npp:
            try:
                from backend.app.services.session.session_brain_service import SessionBrainService
                from backend.app.services.pipeline.modes.mode_attachment import is_continuation_intent, is_audit_intent
                brain = SessionBrainService(current_user_npp, session_uuid)
                active_audit = brain.get_active_audit()
                if active_audit and (is_continuation_intent(user_message) or is_audit_intent(user_message)):
                    logger.info(f"[MODE_HUB] 📑 Active Document Audit continuation detected! Resuming batch: {active_audit.get('current_batch_label')}")
                    handler = self.mode_handlers["attachment"]
                    async for chunk in handler.execute(
                        user_message=user_message,
                        chat_history=chat_history,
                        is_thinking=is_thinking,
                        attachments=None,
                        context_isolation=context_isolation,
                        routing_data=precheck,
                        request=request,
                        employee_name=employee_name,
                        current_user_npp=current_user_npp,
                        session_uuid=session_uuid
                    ):
                        yield chunk
                    return
            except Exception as e:
                logger.warning(f"[MODE_HUB] Gagal cek active audit continuation: {e}")

        # ── Step 2: Call 1 — Intent Classification & Routing ──────────────────────
        yield format_sse(status="🧠 Menganalisis", status_key="ANALYZING_INTENT", event_type=SSEEventType.STATUS)

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        
        # Ekstrak 1 history pesan terakhir (pesan AI sebelumnya) untuk Call 1
        # ── Step 3: Fast-path Bypass atau Call 1 Router ─────────────────────────
        # context_history_str sudah diekstrak di awal eksekusi


        call1_start_t = datetime.now()

        # ── Call 1 Router (gemma4:e4b) ──────────────────────────────────────────
        routing_data = await execute_call1_routing(
            request=request,
            user_message=user_message,
            context_history_str=context_history_str,
            precheck=precheck,
            ocr_text=None,
            is_guest=is_guest,
            is_first_chat=needs_title_update,
            previous_topic=active_topic or precheck.get("active_topic"),
            previous_subject=key_subject or precheck.get("key_subject"),
        )

        call1_ms = (datetime.now() - call1_start_t).total_seconds() * 1000
        logger.info(f"⚡ [TIMING_BENCHMARK] Call1 Router selesai dalam {call1_ms:.1f}ms ({call1_ms/1000:.2f}s) | Active Topic: {routing_data.get('active_topic')} | Key Subject: {routing_data.get('key_subject')}")

        # ── Step 3.2: Emit Dynamic Topic & Entity Update to Frontend Store ───────
        current_active_topic = routing_data.get("active_topic")
        current_key_subject = routing_data.get("key_subject")
        if current_active_topic:
            yield json.dumps({
                "event_type": "topic_update",
                "topic": current_active_topic,
                "key_subject": current_key_subject
            }) + "\n"

        # Emit Call 1 Router token metrics
        router_p_tokens = routing_data.get("_router_prompt_tokens") or 0
        router_c_tokens = routing_data.get("_router_completion_tokens") or 0
        if router_p_tokens > 0 or router_c_tokens > 0:
            yield json.dumps({
                "event_type": "pipeline_tokens",
                "router_prompt_tokens": router_p_tokens,
                "router_completion_tokens": router_c_tokens,
            }) + "\n"

        # ── Step 3.5: Progressive URL Fetching Stepper (100% Call 1 Single Source of Truth) ───
        url_contexts = ""
        from backend.app.services.web_tools.url_reader import extract_url_display_info, fetch_webpage_content, fetch_webpage_with_discovery
        
        approved_fetch_urls = routing_data.get("fetch_urls", [])

        if approved_fetch_urls:
            logger.info(f"[MODE_HUB] Call 1 approved {len(approved_fetch_urls)} URL(s) for live progressive fetching: {approved_fetch_urls}")
            
            collected_nodes = []
            for u in approved_fetch_urls:
                display_info = extract_url_display_info(u)
                
                # Emit status Fetching dinamis untuk URL yang sedang diproses (tanpa trailing dots)
                domain_name = display_info.get("domain") or u
                yield format_sse(status=f"🌐 Mengunduh {domain_name}", event_type=SSEEventType.STATUS)
                
                content, sub_nodes = await fetch_webpage_with_discovery(u, user_query=user_message)
                if content:
                    url_contexts += f"\n\n==== ISI WEB: {u} ====\n\n{content}\n\n========================\n"
                    
                if sub_nodes:
                    collected_nodes.extend(sub_nodes)
                else:
                    collected_nodes.append({
                        "title": display_info["title"],
                        "domain": display_info["domain"],
                        "url": u
                    })
            
            # Buat status aktivitas kontekstual di bagian bawah (Clock Icon) dalam Bahasa Indonesia
            msg_lower = user_message.lower()
            if any(k in msg_lower for k in ["banding", "compare", "vs", "beda"]):
                activity_text = "Membandingkan informasi dari tautan web"
            elif any(k in msg_lower for k in ["spesifikasi", "spek", "fitur", "detail", "rincian", "ukuran", "dimensi"]):
                activity_text = "Menelaah rincian spesifikasi dari tautan web"
            elif any(k in msg_lower for k in ["berita", "kabar", "update", "terbaru"]):
                activity_text = "Mengekstrak informasi berita terbaru dari tautan web"
            elif any(k in msg_lower for k in ["rangkum", "summary", "ringkas", "baca", "jelaskan", "isi"]):
                activity_text = "Menganalisis isi konten halaman web"
            else:
                activity_text = "Menelaah referensi tautan web"
            
            if url_contexts and url_contexts.strip():
                final_fetch_payload = {
                    "nodes": collected_nodes,
                    "fetching": None,
                    "activity": activity_text
                }
                # Kirim TEPAT 1 blok markdown ```urlfetch HANYA jika konten URL berhasil diunduh
                yield format_sse(chunk=f"```urlfetch\n{json.dumps(final_fetch_payload)}\n```\n\n", event_type=SSEEventType.CHUNK)
                yield format_sse(status="📖 Mengekstrak konten web", event_type=SSEEventType.STATUS)
                precheck["_session_chunks_text"] = precheck.get("_session_chunks_text", "") + f"\n\n[KONTEN WEB DARI URL DI CHAT]\n{url_contexts}"
                precheck["has_url_context"] = True

                # Murni URL reader untuk URL yang di-fetch: matikan web_search dan need_rag
                precheck["is_web_search"] = False
                routing_data["is_web_search"] = False
                precheck["need_rag"] = False
                routing_data["need_rag"] = False
                logger.info(f"[MODE_HUB] URL fetched ({len(url_contexts)} chars). Murni URL reader -> is_web_search=False, need_rag=False.")

                # Simpan ke session memory document chunks agar multi-turn aware
                if session_uuid and current_user_npp:
                    from backend.app.services.chat.chat_history_service import chat_history_service
                    clean_web_sample = " ".join(url_contexts.replace("==== ISI WEB:", "").split())[:180]
                    target_title = approved_fetch_urls[0] if approved_fetch_urls else "Tautan Web"
                    web_summary = f"Konten web {target_title}: {clean_web_sample}..."
                    asyncio.create_task(chat_history_service.save_document_chunk(
                        session_uuid=session_uuid,
                        npp=current_user_npp,
                        content=url_contexts[:30000],
                        file_id=None,
                        chunk_metadata={
                            "type": "web",
                            "source": "url_read",
                            "title": target_title,
                            "urls": approved_fetch_urls,
                            "summary": web_summary,
                            "fetched_at": datetime.now().isoformat()
                        }
                    ))
            else:
                logger.warning(f"[MODE_HUB] Fetching failed or yielded empty content for {approved_fetch_urls}. Suppressing urlfetch widget and allowing fallback.")

        logger.info(
            f"[MODE_HUB] Call 1 complete | need_rag={routing_data.get('need_rag')} | "
            f"is_coding={routing_data.get('is_coding')} | queries={routing_data.get('queries')}"
        )

        # ── On-Demand Retrieval dari Dokumen Sesi Sebelumnya ───────────────────
        session_chunk_ids = routing_data.get("session_chunk_ids", [])
        if session_chunk_ids and isinstance(session_chunk_ids, list):
            try:
                from backend.app.services.chat.chat_history_service import chat_history_service
                valid_ids = [int(cid) for cid in session_chunk_ids if str(cid).isdigit()]
                if valid_ids:
                    retrieved_chunks = await chat_history_service.get_document_chunks_by_ids(valid_ids)
                    if retrieved_chunks:
                        logger.info(f"[MODE_HUB] On-Demand retrieved {len(retrieved_chunks)} session document chunk(s) for IDs: {valid_ids}")
                        retrieved_text = "\n\n[KONTEN DOKUMEN SESI YANG DIPANGGIL KEMBALI]\n" + "\n---\n".join(
                            f"--- DOKUMEN #{c['id']} ({c.get('metadata', {}).get('title', 'Dokumen')}) ---\n{c['content']}"
                            for c in retrieved_chunks
                        )
                        precheck["_retrieved_session_chunks_text"] = retrieved_text
            except Exception as e:
                logger.error(f"[MODE_HUB] Failed on-demand chunk retrieval: {e}")
        
        # ── Update Session Title (Gemma 4 Native / Fallback) (Non-blocking background) ────────
        if routing_data.get("session_title") and session_uuid:
            try:
                new_title = format_session_title(routing_data["session_title"], user_message=user_message)
                from backend.app.services.chat.chat_history_service import chat_history_service
                asyncio.create_task(chat_history_service.update_title_direct(session_uuid, new_title))
            except Exception as e:
                logger.error(f"[MODE_HUB] Failed to update session title direct: {e}")
        
        # ── Self-Learning Tone Memory (Background) ────────────────────────────────
        if current_user_npp and current_user_npp != "GUEST":
            from backend.app.services.memory.memory_service import memory_service
            asyncio.create_task(
                memory_service.update_communication_style_memory(
                    npp=current_user_npp, 
                    user_message=user_message
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
            from backend.app.services.chat.chat_history_service import chat_history_service
            
            queries = routing_data.get('queries', [])
            obs_dict = {
                "msg": f"Decided to use: {'RAG' if routing_data.get('need_rag') else 'Flash'} Mode. Queries: {queries}",
                "radar": radar_scores
            }
            asyncio.create_task(chat_history_service.save_agent_step(
                session_id=session_uuid,
                step_number=1,
                tool_called="ROUTER_ENGINE",
                tool_input=user_message[:200],
                observation=json.dumps(obs_dict)
            ))

        if current_user_npp == "GUEST":
            routing_data["need_rag"] = False
        # 🛡️ Proteksi Kata Ganti: Preferensi eksplisit akun (settings/onboarding) adalah prioritas mutlak
        router_pronoun = routing_data.pop("pronoun", None)
        precheck.update(routing_data)
        from backend.app.services.pipeline.intent_dictionary import extract_slang_mirror
        if user_default_pronoun in ["informal_gue_lo", "formal_saya_anda", "familiar_aku_kamu"]:
            precheck["pronoun"] = user_default_pronoun
            if user_default_pronoun == "formal_saya_anda":
                precheck["mirroring"] = "stay_formal_safe"
                precheck["slang"] = []
                precheck["slang_mirror"] = extract_slang_mirror(user_message, user_pronoun="formal_saya_anda")
                if precheck.get("tone_hint") in ["casual", "friendly"]:
                    precheck["tone_hint"] = "formal"
            elif user_default_pronoun == "familiar_aku_kamu":
                precheck["mirroring"] = "stay_formal_safe"
                precheck["slang"] = [s for s in precheck.get("slang", []) if s in ["bro", "sis", "bang", "mas", "mba", "aa", "teteh"]]
                precheck["slang_mirror"] = extract_slang_mirror(user_message, user_pronoun="familiar_aku_kamu")
                if precheck.get("tone_hint") in ["casual", "formal"]:
                    precheck["tone_hint"] = "friendly"
            elif user_default_pronoun == "informal_gue_lo":
                precheck["mirroring"] = "mirror_casual"
                precheck["slang_mirror"] = extract_slang_mirror(user_message, user_pronoun="informal_gue_lo")
                if precheck.get("tone_hint") == "formal":
                    precheck["tone_hint"] = "casual"
        elif user_default_pronoun == "adaptive_mirroring":
            precheck["user_default_pronoun"] = "adaptive_mirroring"
            # Prioritaskan pronoun yang sudah terdeteksi dari pesan / kontinuitas history
            detected = precheck.get("pronoun")
            if detected in ["informal_gue_lo", "familiar_aku_kamu", "formal_saya_anda"]:
                pass
            elif router_pronoun in ["informal_gue_lo", "familiar_aku_kamu", "formal_saya_anda"]:
                precheck["pronoun"] = router_pronoun
            else:
                precheck["pronoun"] = "adaptive_mirroring"
            precheck["slang_mirror"] = extract_slang_mirror(user_message, user_pronoun="adaptive_mirroring")
        elif router_pronoun:
            precheck["pronoun"] = router_pronoun

        # ── 🛡️ Lock intent if forced_mode is active from FE Tag ──
        effective_req_mode = (forced_mode or "").lower().strip()
        if effective_req_mode in ["documents", "document", "rag"]:
            if not precheck.get("is_web_search"):
                precheck["need_rag"] = True
                precheck["is_web_search"] = False
                precheck["is_chitchat"] = False
                precheck["is_coding"] = False
                precheck["is_generate_file"] = False
                if not precheck.get("queries"):
                    precheck["queries"] = [user_message]
                chat_mode = "documents"
                logger.info(f"[MODE_HUB] 🔒 Enforcing need_rag=True & is_web_search=False due to forced_mode={effective_req_mode}")
        elif effective_req_mode in ["websearch", "search", "web"]:
            precheck["is_web_search"] = True
            precheck["need_rag"] = False
            precheck["is_chitchat"] = False
            logger.info(f"[MODE_HUB] 🔒 Enforcing is_web_search=True due to mode={effective_req_mode}")
        elif effective_req_mode in ["code", "coding", "generate_file"]:
            precheck["is_coding"] = True
            precheck["is_generate_file"] = True
            precheck["is_chitchat"] = False
            logger.info(f"[MODE_HUB] 🔒 Enforcing is_coding=True due to mode={effective_req_mode}")
        elif effective_req_mode in ["focus", "compliance"]:
            chat_mode = effective_req_mode
            logger.info(f"[MODE_HUB] 🔒 Enforcing chat_mode={chat_mode} due to mode={effective_req_mode}")
        elif effective_req_mode in ["diagram", "flow", "flowchart"]:
            precheck["requires_visual"] = True
            precheck["visual_type"] = "mermaid"
            precheck["is_web_search"] = False
            precheck["need_rag"] = False
            precheck["is_chitchat"] = False
            logger.info(f"[MODE_HUB] 🔒 Enforcing requires_visual=True (mermaid) & is_web_search=False due to mode={effective_req_mode}")
        elif effective_req_mode in ["chart", "data", "visualization"]:
            precheck["requires_visual"] = True
            precheck["visual_type"] = "chart"
            precheck["is_web_search"] = False
            precheck["need_rag"] = False
            precheck["is_chitchat"] = False
            logger.info(f"[MODE_HUB] 🔒 Enforcing requires_visual=True (chart) & is_web_search=False due to mode={effective_req_mode}")
        elif effective_req_mode in ["smart_mail", "mail", "email", "surat"]:
            precheck["is_generate_email"] = True
            precheck["is_web_search"] = False
            precheck["need_rag"] = False
            precheck["is_chitchat"] = False
            chat_mode = "email"
            logger.info(f"[MODE_HUB] 🔒 Enforcing email mode due to mode={effective_req_mode}")

        # ── Override Router if URL Context Exists ─────────────────────────────────
        if precheck.get("has_url_context"):
            precheck["is_chitchat"] = False
            precheck["need_rag"] = False
            # Jika URL berhasil di-fetch (url_contexts ada isinya), TIDAK perlu web search lagi
            # — konten sudah diinject ke _session_chunks_text dan akan tersedia untuk LLM
            # Hanya fallback ke web search jika URL fetch gagal/kosong
            if url_contexts and url_contexts.strip():
                precheck["is_web_search"] = False
                logger.info("[MODE_HUB] URL content fetched successfully → murni URL reader, skipping web search")
            else:
                precheck["is_web_search"] = True
                logger.info("[MODE_HUB] URL fetch failed/empty → falling back to web search")

        # ── 🌍 Geocoding Tool Calling (Nominatim) ──────────────────────────────────
        is_map = bool(routing_data.get("is_map_query")) or bool(precheck.get("is_map_query"))
        if is_map:
            yield format_sse(status="🌍 Mencari koordinat peta", event_type=SSEEventType.STATUS)
            from backend.app.services.tools.geocoding import geocode_osm
            
            # Ambil keyword lokasi dari queries LLM atau langsung dari pesan pengguna
            target_location = routing_data.get("queries", [user_message])[0] if routing_data.get("queries") else user_message
            
            coords = await geocode_osm(target_location)
            if coords:
                division_info = f"\nDivisi/Fasilitas: {coords['division']}" if coords.get("division") else ""
                map_context = f"\n\n[TOOL: GEOCODING_RESULT]\nHasil pencarian lokasi untuk '{target_location}':\nLatitude: {coords['lat']}\nLongitude: {coords['lng']}\nAlamat Terdaftar: {coords['name']}{division_info}\n\nINSTRUKSI KHUSUS: Gunakan informasi ini untuk menjawab pertanyaan pengguna dengan lengkap, informatif, dan ramah. Sebutkan alamat lengkap, pembagian divisi/fasilitas yang ada di sana, dan koordinat GPS presisi."
                precheck["_session_chunks_text"] = precheck.get("_session_chunks_text", "") + map_context
                precheck["need_rag"] = False
                
                if session_uuid:
                    from backend.app.services.chat.chat_history_service import chat_history_service
                    asyncio.create_task(chat_history_service.save_agent_step(
                        session_id=session_uuid,
                        step_number=2,
                        tool_called="GEOCODING_NOMINATIM",
                        tool_input=target_location,
                        observation=json.dumps({"lat": coords["lat"], "lng": coords["lng"], "name": coords["name"]})
                    ))
            else:
                yield format_sse(status="⚠️ Lokasi tidak ditemukan", event_type=SSEEventType.STATUS)

        # ── Web Search Mode Routing ─────────────────────────────────────
        # JANGAN izinkan web search jika need_rag bernilai True atau user secara eksplisit mengunci mode Dokumen
        if precheck.get("is_web_search", False) and not precheck.get("need_rag", False) and effective_req_mode not in ["documents", "document", "rag"]:
            logger.info("[MODE_HUB] Routing to Web Search Mode.")
            from backend.app.services.pipeline.modes.mode_web_search import handle_web_search
            # Convert ChatMessageSchema to dict
            history_dicts = [m.model_dump() for m in chat_history]
            # Ensure the current user_message (potentially with URL contents appended) is at the end
            if not history_dicts or history_dicts[-1]["content"] != user_message:
                # Replace the last user message with the appended one, or just add if empty
                if history_dicts and history_dicts[-1]["role"] == "user":
                    history_dicts[-1]["content"] = user_message
                else:
                    history_dicts.append({"role": "user", "content": user_message})

            needs_history_web = bool(routing_data.get("needs_history", False)) or bool(precheck.get("needs_history", False))
            if not needs_history_web and len(history_dicts) > 1:
                logger.info(f"[MODE_HUB] ⚡ Standalone web search (needs_history=False). Bypassing {len(history_dicts)-1} past turn(s) -> Sent 1 lean turn to Call 2.")
                history_dicts = [history_dicts[-1]]

            # Gunakan query bersih dari Call 1 (queries[0]) alih-alih user_message mentah
            # Ini menghindari query kotor atau kombinasi kata penghubung '&' yang merusak hasil pencarian Google
            web_search_queries = precheck.get("queries", [])
            if web_search_queries:
                web_search_query = web_search_queries[0]
            else:
                web_search_query = user_message
            logger.info(f"[MODE_HUB] Web search queries: {web_search_queries} | effective query: '{web_search_query}'")

            async for chunk in handle_web_search(
                query=web_search_query,
                messages=history_dicts,
                request=request,
                employee_name=employee_name,
                precheck=precheck,
                is_thinking=is_thinking
            ):
                yield chunk
            return

        # ── Step 3: Route to specific mode ──────────────────────────────────────────
        # Ensure mode exists, fallback to auto
        mode = chat_mode if chat_mode in self.mode_handlers else "auto"

        # ── Priority 1: is_generate_file / is_coding intent (Interceptor-Analyst Pipeline) ──────
        # Hanya masuk ke generate_file jika BUKAN ambigu (artinya spesifikasi sudah jelas/lengkap)
        if (routing_data.get("is_generate_file") or routing_data.get("is_coding")) and not is_guest and not routing_data.get("is_ambiguous"):
            logger.info("[MODE_HUB] Coding intent detected & not ambiguous → routing to GENERATE_FILE mode")
            mode = "generate_file"
        elif routing_data.get("is_generate_email") and not is_guest and not routing_data.get("is_ambiguous"):
            logger.info("[MODE_HUB] is_generate_email=True detected & not ambiguous → routing to EMAIL mode")
            mode = "email"
        elif (routing_data.get("is_docwriter") or precheck.get("is_docwriter")) and not is_guest:
            logger.info("[MODE_HUB] is_docwriter=True detected → routing to FLASH mode for Document Writer")
            mode = "flash"
        elif mode == "auto":
            # Jika is_ambiguous True, pastikan masuk flash mode untuk klarifikasi wizard
            if routing_data.get("is_ambiguous"):
                logger.info("[MODE_HUB] Ambiguous intent detected → routing to FLASH mode for guided wizard clarification")
                mode = "flash"
            else:
                # Gunakan precheck (bukan routing_data) agar override URL context (need_rag=False)
                # tidak tertimpa oleh nilai raw dari routing_data
                need_rag = precheck.get("need_rag", False) and not (precheck.get("is_map_query", False) or routing_data.get("is_map_query", False))
                if need_rag and not is_guest:
                    mode = "documents"
                else:
                    mode = "guest" if is_guest else "flash"
        elif routing_data.get("is_ambiguous"):
            logger.info(f"[MODE_HUB] Ambiguous intent detected with mode={mode} → redirecting to {'GUEST' if is_guest else 'FLASH'} mode")
            mode = "guest" if is_guest else "flash"
        
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
