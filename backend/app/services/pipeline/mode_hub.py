import logging
import json
import asyncio
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
        session_uuid: Optional[str] = None,
        has_new_document: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Main entry point for stream.py to route the request to the correct mode handler.
        """
        logger.info(f"[MODE_HUB] Starting execution for chat_mode: {chat_mode.upper()}")
        
        # ── Step 1: Pre-check rule-based ──────────────────────────────────────────
        has_attachment = bool(attachments) or has_new_document
        precheck = detect_precheck(user_message, chat_mode, has_attachment)
        precheck["_user_message"] = user_message

        # ── Fetch Long-Term Memory (ai_document_chunks) ────────────────────────
        session_chunks_text = ""
        visited_urls = []
        if session_uuid:
            from backend.app.services.chat.chat_history_service import chat_history_service
            chunks_with_meta = await chat_history_service.get_session_document_chunks_with_meta(session_uuid)
            if chunks_with_meta:
                text_chunks = [c["content"] for c in chunks_with_meta]
                session_chunks_text = "\n\n[KNOWLEDGE DARI FILE SEBELUMNYA DI SESI INI]\n" + "\n---\n".join(text_chunks)
                # Ekstrak domain URL yang pernah dikunjungi untuk multi-turn URL awareness
                for c in chunks_with_meta:
                    meta = c.get("metadata", {})
                    if meta.get("source") == "url_read":
                        visited_urls.extend(meta.get("urls", []))
                if visited_urls:
                    visited_urls = list(set(visited_urls))  # deduplicate
                    logger.info(f"[MODE_HUB] Loaded {len(visited_urls)} previously visited URL(s) from session memory")
        precheck["_session_chunks_text"] = session_chunks_text
        precheck["_session_uuid"] = session_uuid
        precheck["_visited_urls"] = visited_urls

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
                elif skipped:
                    # URL sudah pernah dikunjungi dan kontennya ada di session memory
                    precheck["has_url_context"] = True  # masih tandai agar routing paham ada URL context
                    logger.info("[MODE_HUB] All URLs already in session memory — using cached content, no re-fetch needed.")
        except ImportError:
            pass



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

        # ── Fast-path Bypass untuk Context Isolation (Focus Mode) ──────────────────
        if context_isolation and context_isolation.get("isolated_doc_id"):
            logger.info("[MODE_HUB] Context Isolation detected! Routing to Focus Mode.")
            if session_uuid:
                from backend.app.services.chat.chat_history_service import chat_history_service
                radar_scores = {"dokumen": 100, "coding": 10, "chitchat": 10, "analitik": 10, "ambigu": 10}
                obs_dict = {"msg": "Bypassing Call 1 -> FOCUS", "radar": radar_scores}
                asyncio.create_task(chat_history_service.save_agent_step(
                    session_id=session_uuid,
                    step_number=1,
                    tool_called="ROUTER_ENGINE",
                    tool_input="Context Isolation Active",
                    observation=json.dumps(obs_dict)
                ))
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
            if is_first_chat:
                title = f"Analisis {attachments[0].get('file_name', 'Lampiran')[:20]}" if attachments else "Analisis Dokumen"
                yield format_sse(session_title=title, event_type=SSEEventType.TITLE_UPDATE)

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

        call1_start_t = datetime.now()

        # ── ⚡ PARALLEL OPTIMIZATION: Call1 + URL Fetch berjalan bersamaan ─────────
        # Keduanya adalah I/O network murni — tidak perlu menunggu satu sama lain.
        async def _do_call1():
            return await execute_call1_routing(
                request=request,
                user_message=user_message,
                context_history_str=context_history_str,
                precheck=precheck,
                ocr_text=None,
                is_guest=is_guest,
                is_first_chat=is_first_chat,
            )

        # Siapkan url_fetch coroutine (kosong jika tidak ada URL)
        async def _do_url_fetch_safe():
            if not urls_in_text:
                return ""
            try:
                from backend.app.services.web_tools.url_reader import fetch_multiple_urls
                return await fetch_multiple_urls(urls_in_text)
            except Exception as e:
                logger.warning(f"[MODE_HUB] URL fetch failed: {e}")
                return ""

        # Jalankan keduanya bersamaan
        call1_task = asyncio.create_task(_do_call1())
        url_fetch_task = asyncio.create_task(_do_url_fetch_safe())

        if urls_in_text:
            yield format_sse(status=f"🌐 Membaca konten dari {len(urls_in_text)} tautan web...", event_type=SSEEventType.STATUS)

        routing_data, url_contexts = await asyncio.gather(call1_task, url_fetch_task)

        # Setelah paralel selesai, masukkan konten URL ke precheck
        if url_contexts and urls_in_text:
            precheck["_session_chunks_text"] = precheck.get("_session_chunks_text", "") + f"\n\n[KONTEN WEB DARI URL DI CHAT]\n{url_contexts}"
            logger.info(f"[MODE_HUB] URL context injected ({len(url_contexts)} chars) — fetched in parallel with Call1")
            # Simpan konten URL ke session memory (ai_document_chunks) agar tersedia di turn berikutnya
            if session_uuid and current_user_npp:
                from backend.app.services.chat.chat_history_service import chat_history_service
                asyncio.create_task(chat_history_service.save_document_chunk(
                    session_uuid=session_uuid,
                    npp=current_user_npp,
                    content=url_contexts[:30000],
                    file_id=None,
                    chunk_metadata={
                        "source": "url_read",
                        "urls": urls_in_text,
                        "fetched_at": datetime.now().isoformat()
                    }
                ))
                logger.info(f"[MODE_HUB] URL content scheduled for save to session memory (urls: {urls_in_text})")

        call1_ms = (datetime.now() - call1_start_t).total_seconds() * 1000
        logger.info(f"⚡ [TIMING_BENCHMARK] Call1 + URL Fetch (parallel) selesai dalam {call1_ms:.1f}ms ({call1_ms/1000:.2f}s)")


        logger.info(
            f"[MODE_HUB] Call 1 complete | need_rag={routing_data.get('need_rag')} | "
            f"is_coding={routing_data.get('is_coding')} | queries={routing_data.get('queries')}"
        )
        
        # ── Update Session Title (Gemma 4 Native / Fallback) ────────────────────────
        if routing_data.get("session_title") and session_uuid:
            try:
                new_title = routing_data["session_title"].strip().strip('"').strip("'").strip(".").title()
                from backend.app.services.chat.chat_history_service import chat_history_service
                await chat_history_service.update_title_direct(session_uuid, new_title)
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
            logger.info("[MODE_HUB] GUEST User detected — RAG forcefully disabled.")

        precheck.update(routing_data)

        # ── Override Router if URL Context Exists ─────────────────────────────────
        if precheck.get("has_url_context"):
            precheck["is_chitchat"] = False
            precheck["need_rag"] = False
            # Jika URL berhasil di-fetch (url_contexts ada isinya), TIDAK perlu web search lagi
            # — konten sudah diinject ke _session_chunks_text dan akan tersedia untuk LLM
            # Hanya fallback ke web search jika URL fetch gagal/kosong
            if url_contexts and url_contexts.strip():
                precheck["is_web_search"] = False
                logger.info("[MODE_HUB] URL content fetched successfully → skipping web search, using URL content directly")
            else:
                precheck["is_web_search"] = True
                logger.info("[MODE_HUB] URL fetch failed/empty → falling back to web search")

        # ── 🌍 Geocoding Tool Calling (Nominatim) ──────────────────────────────────
        if routing_data.get("is_map_query"):
            yield format_sse(status="🌍 Mencari koordinat peta (Nominatim)", event_type=SSEEventType.STATUS)
            from backend.app.services.tools.geocoding import geocode_osm
            
            # Ambil keyword lokasi dari queries LLM atau langsung dari pesan pengguna
            target_location = routing_data.get("queries", [user_message])[0] if routing_data.get("queries") else user_message
            
            coords = await geocode_osm(target_location)
            if coords:
                map_context = f"\n\n[TOOL: GEOCODING_RESULT]\nHasil pencarian lokasi untuk '{target_location}':\nLatitude: {coords['lat']}\nLongitude: {coords['lng']}\nAlamat Terdaftar: {coords['name']}\n\nINSTRUKSI KHUSUS: Gunakan koordinat ini di dalam JSON ```map yang akan kamu hasilkan. Selain memuntahkan JSON, berikan narasi singkat yang ramah dan antusias yang mengatakan 'Ini dia lokasi yang Boss cari beserta koordinatnya!'. DILARANG KERAS meminta maaf atau mengatakan keterbatasan data, karena data ini sudah sangat cukup untuk merender peta visual di sistem frontend!"
                precheck["_session_chunks_text"] = precheck.get("_session_chunks_text", "") + map_context
                
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
                yield format_sse(status="⚠️ Gagal menemukan koordinat lokasi tersebut", event_type=SSEEventType.STATUS)

        # ── Web Search Mode Routing ─────────────────────────────────────
        if precheck.get("is_web_search", False):
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

            # Gunakan query bersih dari Call 1 (queries[0]) alih-alih user_message mentah
            # Ini menghindari query kotor seperti "saya informasi crypto..." dikirim ke Google
            web_search_queries = precheck.get("queries", [])
            web_search_query = web_search_queries[0] if web_search_queries else user_message
            logger.info(f"[MODE_HUB] Web search query: '{web_search_query}' (from {'Call1 queries' if web_search_queries else 'user_message fallback'})")

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
        if (routing_data.get("is_generate_file") or routing_data.get("is_coding")) and not is_guest:
            logger.info("[MODE_HUB] Coding intent detected → routing to GENERATE_FILE mode")
            mode = "generate_file"
        elif routing_data.get("is_generate_email") and not is_guest:
            logger.info("[MODE_HUB] is_generate_email=True detected → routing to EMAIL mode")
            mode = "email"
        elif mode == "auto":
            # Gunakan precheck (bukan routing_data) agar override URL context (need_rag=False)
            # tidak tertimpa oleh nilai raw dari routing_data
            need_rag = precheck.get("need_rag", False)
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
