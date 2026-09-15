import os
import re
import json
import base64
import logging
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime
from fastapi import Request, HTTPException
import asyncio

from backend.app.api.schemas.chat_schemas import ChatStreamRequest
from backend.app.services.chat.chat_history_service import chat_history_service
from backend.app.core.config import settings
from backend.app.utils.employee_cache import get_cached_employee_data
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.mode_hub import mode_hub

logger = logging.getLogger("CAKRA_PIPELINE")


async def _sequential_pipeline_generator(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str],
) -> AsyncGenerator[str, None]:

    user_label = f"NPP: {current_user_npp}" if current_user_npp else "GUEST"
    logger.info(f"[PIPELINE] Stream started | user={user_label}")

    if not payload.messages:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong!")

    user_message = payload.messages[-1].content
    chat_mode = getattr(payload, "mode", "auto")

    logger.info(f'[PIPELINE] User message | "{user_message[:100]}" | mode={chat_mode}')
    if not current_user_npp or current_user_npp == "GUEST":
        chat_mode = "guest"
        is_thinking = False
    else:
        is_thinking = payload.thinking if hasattr(payload, 'thinking') else True
    logger.info(f'[PIPELINE] Thinking status | is_thinking={is_thinking} | requested_by=NPP:{current_user_npp}')

    messages_for_pipeline = [
        {"role": msg.role, "content": msg.content} for msg in payload.messages
    ]

    # ── Attachment detection ───────────────────────────────────────────────────
    ocr_text = None
    pdf_paths = []
    has_images = False
    has_attachment = bool(payload.attachment_paths)

    if payload.attachment_paths:
        for path in payload.attachment_paths:
            path_lower = path.lower()
            if path_lower.endswith(".pdf"):
                pdf_paths.append(path)
            elif any(path_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]):
                has_images = True

    # ── PDF & Document / Code Extraction ─────────────────────────────────────
    extracted_file_texts = []
    formatted_attachments = []
    
    if payload.attachment_paths:
        import os
        from backend.app.core.paths import UPLOAD_DIR, BASE_DIR, get_abs_path
        import base64
        
        for path in payload.attachment_paths:
            path_lower = path.lower()
            filename = os.path.basename(path)
            
            cand_paths = [
                path if os.path.isabs(path) else None,
                os.path.join(UPLOAD_DIR, filename),
                os.path.join(BASE_DIR, path),
                os.path.join(BASE_DIR, "file_peraturan", filename),
                get_abs_path(path)
            ]
            abs_path = next((p for p in cand_paths if p and os.path.exists(p)), None)
            
            if not abs_path:
                logger.warning(f"[PIPELINE] Attachment not found in candidate paths: {path}")
                continue
                
            if any(path_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]):
                has_images = True
                try:
                    with open(abs_path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                        formatted_attachments.append({"base64": encoded, "type": "image"})
                except Exception as e:
                    logger.error(f"[PIPELINE] Gagal membaca gambar {path}: {e}")
            elif path_lower.endswith(".pdf"):
                # Lampiran PDF: teruskan path dan metadata terstruktur ke mode_attachment
                # agar diproses menggunakan Parallel OCR & Two-Stage Context Intelligence secara utuh
                formatted_attachments.append({
                    "type": "pdf",
                    "mime_type": "application/pdf",
                    "file_path": abs_path,
                    "file_name": filename
                })
            else:
                # Text/Doc/Spreadsheet/Code extraction via unified_extractor
                try:
                    from backend.app.services.tools.unified_extractor import extract_document
                    doc = await extract_document(abs_path)
                    extracted = doc.full_text
                except Exception as extract_err:
                    logger.warning(f"[PIPELINE] unified_extractor fallback for {filename}: {extract_err}")
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                            extracted = f.read()
                    except Exception as fallback_err:
                        logger.error(f"[PIPELINE] Gagal membaca attachment {filename}: {fallback_err}")
                        extracted = ""

                if extracted and extracted.strip():
                    extracted_file_texts.append(f"--- ISI FILE: {filename} ---\n{extracted.strip()}\n-------------------")
                    
    # Save original user message for DB saving, so DB isn't bloated

    original_user_message = user_message
    
    # Append extracted texts to user message so LLM sees it directly
    if extracted_file_texts:
        # Tingkatkan limit karakter menjadi 250000 (sekitar 60K-80K tokens) agar Gemma 12b bisa membaca penuh file teks.
        truncated_texts = [txt[:250000] + "\n\n...[TEKS DIPOTONG KARENA TERLALU PANJANG]" if len(txt) > 250000 else txt for txt in extracted_file_texts]
        user_message += "\n\n[DOKUMEN LAMPIRAN BARU]\n" + "\n\n".join(truncated_texts)
        if payload.messages:
            payload.messages[-1].content = user_message

    # ── Save user message (Hanya jika bukan event regenerate) ────────────────
    is_regenerate_event = bool(
        getattr(payload, 'is_regenerate', False) 
        or payload.regenerated_from_id is not None
    )
    if payload.session_uuid and not is_regenerate_event:
        user_text = f"{original_user_message}"
        
        if payload.edit_index is not None:
            await chat_history_service.update_chat_message(
                session_id=payload.session_uuid,
                edit_index=payload.edit_index,
                role="user",
                text=user_text,
                thought=f"Gemma Agentic [Mode: {chat_mode} - Edited]",
            )
        else:
            await chat_history_service.save_chat_message(
                session_id=payload.session_uuid,
                role="user",
                text=user_text,
                thought=f"Gemma Agentic [Mode: {chat_mode}]",
            )

    # ── Content Safety Filter (Pornography, Abuse) ────────────────────────────
    from backend.app.utils.content_filter import contains_prohibited_content
    if contains_prohibited_content(user_message):
        logger.warning(f"[SAFETY_FILTER] Blocked user message from NPP {current_user_npp}")
        error_msg = "Maaf, permintaan Anda melanggar Kebijakan Penggunaan Cakra AI (Mengandung konten SARA/Pornografi/Kekerasan)."
        yield format_sse(error_msg, "", False, event_type=SSEEventType.CHUNK)
        yield format_sse("", "", True, event_type=SSEEventType.DONE)
        return

    # ── Resolve employee name & Guest Override ────────────────────────────────
    employee_name = "Pegawai"
    if current_user_npp == "GUEST":
        # HARD GUARD FOR GUEST
        chat_mode = "guest"
        is_thinking = False
    elif current_user_npp:
        try:
            async def fetch_employee_from_db(npp: str) -> Optional[dict]:
                from backend.app.core.database import get_db
                async with get_db() as conn:
                    row = await conn.fetchrow(
                        "SELECT fullname, preferred_name FROM users WHERE npp = $1 LIMIT 1", npp
                    )
                    return dict(row) if row else None

            emp_data = await get_cached_employee_data(
                current_user_npp,
                db_fetch_func=fetch_employee_from_db,
            )
            if emp_data:
                if emp_data.get("preferred_name"):
                    employee_name = emp_data["preferred_name"]
                else:
                    full_name = emp_data.get("fullname") or ""
                    name_parts = full_name.strip().split()
                    employee_name = name_parts[0].title() if name_parts else "Pegawai"
        except Exception:
            employee_name = "Pegawai"

    logger.info(f"[PIPELINE] Employee resolved: {employee_name}")

    # ── Gemma Agentic Engine (single model, handles everything) ───────────────
    logger.info("[AGENTIC] Gemma Agentic Engine starting...")

    full_response_text = ""
    full_thinking_text = ""
    preloaded_rag_sources = None
    generated_artifacts = []
    start_time = datetime.now()

    try:
        from backend.app.services.pipeline.mode_hub import mode_hub
        import re
        cleaned_history = []
        for msg in payload.messages:
            if hasattr(msg, "role") and msg.role == "assistant" and msg.content:
                new_content = re.sub(r'<\|channel>thought.*?<channel\|>', '', msg.content, flags=re.DOTALL)
                new_content = re.sub(r'```websearch.*?```', '', new_content, flags=re.DOTALL).strip()
                try:
                    cleaned_msg = msg.model_copy(update={'content': new_content})
                except AttributeError:
                    cleaned_msg = msg.copy(update={'content': new_content})
                cleaned_history.append(cleaned_msg)
            else:
                cleaned_history.append(msg)

        # 🧠 ISOLATED DOC HANDLING:
        # Hanya aktifkan bypass_router & forced_mode='documents' jika client secara EKSPLISIT
        # mengirimkan payload.isolated_doc_id (misalnya mode fokus per dokumen dari FE).
        # Jangan pernah auto-force bypass router dari Brain agar Call 1 tetap bisa mengevaluasi mode lain (koding, web search, sapaan, dll).
        active_isolated_doc_id = payload.isolated_doc_id
        active_doc_title = getattr(payload, 'doc_title', None)
        active_hint_source = getattr(payload, 'hint_source', None) or {}
        raw_ctx_isolation = getattr(payload, 'context_isolation', None) or {}

        active_forced_mode = getattr(payload, 'forced_mode', None)
        active_bypass_router = bool(getattr(payload, 'bypass_router', False))
        if active_isolated_doc_id and not active_forced_mode:
            active_forced_mode = "documents"
            active_bypass_router = True
            logger.info(f"[PIPELINE] ⚡ Client explicit isolated_doc_id={active_isolated_doc_id} -> activating bypass_router & forced_mode='documents'")

        # Susun context_isolation lengkap dengan identitas resmi dokumen (nomor, jenis, tanggal, judul)
        full_context_isolation = None
        if active_isolated_doc_id or active_hint_source or raw_ctx_isolation:
            full_context_isolation = {
                "isolated_doc_id": active_isolated_doc_id or active_hint_source.get("id") or raw_ctx_isolation.get("isolated_doc_id"),
                "id_dokumen": active_isolated_doc_id or active_hint_source.get("id"),
                "doc_id": active_isolated_doc_id or active_hint_source.get("id"),
                "title": active_doc_title or active_hint_source.get("title") or raw_ctx_isolation.get("title"),
                "doc_title": active_doc_title or active_hint_source.get("title") or raw_ctx_isolation.get("title"),
                "nomor": active_hint_source.get("nomor") or raw_ctx_isolation.get("nomor") or "",
                "tanggal": active_hint_source.get("tanggal") or raw_ctx_isolation.get("tanggal") or "",
                "jenis": active_hint_source.get("jenis") or active_hint_source.get("category") or raw_ctx_isolation.get("jenis") or "Regulasi",
                "filename": active_hint_source.get("filename") or raw_ctx_isolation.get("filename"),
                "file_path": active_hint_source.get("file_path") or raw_ctx_isolation.get("file_path"),
            }
            logger.info(f"[PIPELINE] 📑 Context Isolation Active: title='{full_context_isolation.get('title')}', nomor='{full_context_isolation.get('nomor')}', id={full_context_isolation.get('isolated_doc_id')}")

        agentic_engine = mode_hub.execute(
            request=request,
            user_message=user_message,
            chat_history=cleaned_history,
            chat_mode=chat_mode,
            is_thinking=payload.thinking if hasattr(payload, 'thinking') else True,
            attachments=formatted_attachments,
            context_isolation=full_context_isolation,
            employee_name=employee_name,
            current_user_npp=current_user_npp,
            session_uuid=payload.session_uuid,
            has_new_document=bool(extracted_file_texts),
            active_topic=getattr(payload, 'active_topic', None),
            key_subject=getattr(payload, 'key_subject', None),
            client_context=getattr(payload, 'client_context', None),
            forced_mode=active_forced_mode,
            bypass_router=active_bypass_router,
        )


        router_prompt_tokens = 0
        router_completion_tokens = 0
        gen_prompt_tokens = 0
        gen_completion_tokens = 0

        async for sse in agentic_engine:
            raw = sse.strip()
            if not raw:
                continue

            try:
                event_data = json.loads(raw)
                event_type = event_data.get("event_type")

                if event_type == "pipeline_tokens":
                    router_prompt_tokens = event_data.get("router_prompt_tokens", 0)
                    router_completion_tokens = event_data.get("router_completion_tokens", 0)
                    continue
                elif event_type == SSEEventType.DONE:
                    continue
                elif event_type == SSEEventType.SOURCES:
                    preloaded_rag_sources = event_data.get("sources")
                elif event_type == SSEEventType.FILE_STATUS:
                    fs = event_data.get("file_status", {})
                    if fs.get("stage") == "done" and fs.get("file_path"):
                        generated_artifacts.append({
                            "filename": fs.get("filename"),
                            "file_path": fs.get("file_path"),
                            "lines_count": fs.get("lines_count", 1)
                        })

                # Capture token counts if present in chunk/status/file events
                if event_data.get("eval_count"):
                    gen_completion_tokens = event_data.get("eval_count", 0)
                if event_data.get("prompt_eval_count"):
                    gen_prompt_tokens = event_data.get("prompt_eval_count", 0)
                
                # Extract chunk and thinking independently of event_type
                chunk_text = event_data.get("chunk", "")
                if chunk_text:
                    full_response_text += chunk_text
                    
                thinking_chunk = event_data.get("thinking", "")
                if thinking_chunk:
                    full_thinking_text += thinking_chunk

            except (json.JSONDecodeError, AttributeError):
                pass

            # Tetap kirimkan sse chunk/sources asli ke client browser
            yield sse

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[AGENTIC] Selesai | {len(full_response_text)} chars | {elapsed:.2f}s")

    except asyncio.CancelledError:
        logger.warning("[AGENTIC] Client disconnected / Stream aborted.")
        full_response_text += " *Respons dihentikan*"
        # Biarkan eksekusi berlanjut ke bagian save DB di bawah
    except Exception as e:
        logger.error(f"[AGENTIC] Error: {e}", exc_info=True)
        error_msg = f"Gagal mengeksekusi pipeline: {str(e)}"
        yield format_sse(error_msg, "", False, event_type=SSEEventType.CHUNK)
        full_response_text = error_msg

    # ── Save assistant response & finalize ────────────────────────────────────

    async def _save_to_db():
        nonlocal full_response_text, gen_prompt_tokens, gen_completion_tokens, router_prompt_tokens, router_completion_tokens
        try:
            if payload.session_uuid:
                # --- INTERCEPT SHORT/TRUNCATED RESPONSE ---
                clean_content = full_response_text.strip()
                has_files = len(generated_artifacts) > 0
                if not has_files and len(clean_content) < 12 and "Respons dihentikan" not in full_response_text:
                    logger.warning(f"[AGENTIC] Respons terlalu pendek ({len(clean_content)} chars). Menggunakan fallback.")
                    full_response_text = "Mohon maaf, saya tidak dapat memproses pesan Anda dengan baik. Silakan coba beberapa saat lagi atau perjelas pertanyaan Anda."

                ast_thought = full_thinking_text.strip() if full_thinking_text else f"Gemma Agentic | Mode: {chat_mode}"

                # ── Perhitungan & Audit Token Riil ────────────────────────────
                if gen_completion_tokens == 0:
                    gen_completion_tokens = max(1, len(full_response_text) // 4)
                if gen_prompt_tokens == 0:
                    gen_prompt_tokens = max(10, (len(user_message) + len(full_thinking_text)) // 4)
                if router_prompt_tokens == 0:
                    router_prompt_tokens = 850
                if router_completion_tokens == 0:
                    router_completion_tokens = 40

                tot_prompt = router_prompt_tokens + gen_prompt_tokens
                tot_completion = router_completion_tokens + gen_completion_tokens
                tot_tokens = tot_prompt + tot_completion

                token_meta = {
                    "prompt_tokens": tot_prompt,
                    "completion_tokens": tot_completion,
                    "total_tokens": tot_tokens,
                    "router": {"prompt": router_prompt_tokens, "completion": router_completion_tokens},
                    "generator": {"prompt": gen_prompt_tokens, "completion": gen_completion_tokens},
                }

                # Simpan metrik ke tabel request_token_usage
                try:
                    from backend.app.services.analytics_service import record_request_tokens
                    req_id = None
                    if request:
                        req_id = request.headers.get("X-Request-ID")
                    if not req_id:
                        from backend.app.utils.request_logging import get_request_id
                        req_id = get_request_id()

                    duration_val = elapsed * 1000 if 'elapsed' in locals() else 0.0
                    asyncio.create_task(record_request_tokens(
                        request_id=req_id,
                        session_uuid=payload.session_uuid,
                        user_npp=current_user_npp or "GUEST",
                        mode=chat_mode,
                        model_router=getattr(settings, "MODEL_ROUTER", "gemma4:e4b"),
                        model_generator=getattr(settings, "MODEL_PERSONA", "gemma4:31b"),
                        router_prompt_tokens=router_prompt_tokens,
                        router_completion_tokens=router_completion_tokens,
                        gen_prompt_tokens=gen_prompt_tokens,
                        gen_completion_tokens=gen_completion_tokens,
                        duration_ms=duration_val,
                    ))
                except Exception as t_err:
                    logger.warning(f"[TOKEN_AUDIT] Gagal submit record_request_tokens task: {t_err}")

                message_metadata = {"tokens": token_meta}
                if generated_artifacts:
                    message_metadata["artifacts"] = generated_artifacts
                
                if is_regenerate_event:
                    # REGENERATE: Simpan sebagai varian baru tanpa menimpa respons sebelumnya
                    actual_parent_id = payload.parent_id
                    actual_regen_from_id = payload.regenerated_from_id

                    if actual_regen_from_id is None or actual_parent_id is None:
                        try:
                            from backend.app.core.database import get_db
                            async with get_db() as conn:
                                session_pk = await chat_history_service._resolve_session_pk(conn, payload.session_uuid)
                                if session_pk:
                                    target_offset = getattr(payload, 'target_index', None)
                                    if target_offset is not None and actual_regen_from_id is None:
                                        row_target = await conn.fetchrow(
                                            "SELECT id, parent_id FROM chat_messages WHERE session_id = $1 ORDER BY timestamp ASC, id ASC OFFSET $2 LIMIT 1",
                                            session_pk, target_offset
                                        )
                                        if row_target:
                                            actual_regen_from_id = row_target["id"]
                                            if not actual_parent_id:
                                                actual_parent_id = row_target["parent_id"]

                                    if actual_regen_from_id and not actual_parent_id:
                                        actual_parent_id = await conn.fetchval(
                                            "SELECT parent_id FROM chat_messages WHERE id = $1",
                                            actual_regen_from_id
                                        )

                                    if not actual_parent_id:
                                        parent_offset = getattr(payload, 'parent_index', None)
                                        if parent_offset is not None:
                                            actual_parent_id = await conn.fetchval(
                                                "SELECT id FROM chat_messages WHERE session_id = $1 ORDER BY timestamp ASC, id ASC OFFSET $2 LIMIT 1",
                                                session_pk, parent_offset
                                            )
                                        else:
                                            actual_parent_id = await conn.fetchval(
                                                "SELECT id FROM chat_messages WHERE session_id = $1 AND role = 'user' ORDER BY timestamp DESC, id DESC LIMIT 1",
                                                session_pk
                                            )
                        except Exception as res_err:
                            logger.error(f"[PIPELINE_REGEN] Gagal me-resolve parent_id/regen_id: {res_err}")

                    await chat_history_service.save_chat_message(
                        session_id=payload.session_uuid,
                        role="assistant",
                        text=full_response_text,
                        thought=ast_thought,
                        sources=preloaded_rag_sources,
                        metadata=message_metadata,
                        parent_id=actual_parent_id,
                        regenerated_from_id=actual_regen_from_id
                    )
                elif payload.edit_index is not None:
                    await chat_history_service.update_chat_message(
                        session_id=payload.session_uuid,
                        edit_index=payload.edit_index + 1,
                        role="assistant",
                        text=full_response_text,
                        thought=ast_thought,
                        sources=preloaded_rag_sources,
                        metadata=message_metadata
                    )
                else:
                    await chat_history_service.save_chat_message(
                        session_id=payload.session_uuid,
                        role="assistant",
                        text=full_response_text,
                        thought=ast_thought,
                        sources=preloaded_rag_sources,
                        metadata=message_metadata,
                        parent_id=payload.parent_id
                    )
                if not (payload.attachment_paths and len(payload.attachment_paths) > 0):
                    try:
                        await chat_history_service.save_dialogue_corpus(
                            session_uuid=payload.session_uuid,
                            user_text=user_message,
                            assistant_text=full_response_text,
                            context_document=f"Gemma Agentic | Mode: {chat_mode}",
                            metadata={
                                "mode": chat_mode, 
                                "sources_count": len(preloaded_rag_sources) if preloaded_rag_sources else 0,
                                "artifacts": generated_artifacts
                            }
                        )
                    except Exception as e:
                        logger.warning(f"[DB] Gagal save dialogue corpus: {e}")
        except Exception as err:
            logger.error(f"[DB] Gagal save data setelah stream: {err}")

    # Jalankan save (selain title) di background agar kebal terhadap CancelledError
    asyncio.create_task(_save_to_db())

    # Ambil judul terbaru (ditetapkan oleh Call 1 Normal atau Call 1 Preset)
    new_title = None
    if payload.session_uuid:
        new_title = await chat_history_service.get_session_title(payload.session_uuid)

    logger.info(f"[PIPELINE] Complete ✅ | Title: {new_title}")
    yield format_sse("", "", True, sources=preloaded_rag_sources, event_type=SSEEventType.DONE, title=new_title)
