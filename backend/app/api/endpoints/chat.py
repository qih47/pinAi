"""
CAKRA AI — Chat Router
Pipeline: Layer 0 Gateway → Layer 1 Cognitive → Layer 2 Gemma Agentic
"""

import os
import time
import json
import shutil
import logging
import asyncio
from typing import List, Optional, AsyncGenerator
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    Request,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.responses import StreamingResponse

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.config import settings
from backend.app.core.paths import UPLOAD_DIR
from backend.app.services.chat_history_service import chat_history_service
from backend.app.services.rag_service import rag_service
from backend.app.core.database import get_db
from backend.app.services.pipeline_layer_executor import (
    extract_pdf_text,
    execute_layer_0_gateway,
    execute_layer_1_analyzer,
    execute_layer_2_gemma_agentic,
    _get_fallback_cognitive_params_rule_based,
    _format_sse,
)
from backend.app.api.schemas.chat import (
    ChatStreamRequest,
    TitleUpdateSchema,
    FeedbackSchema,
)
from backend.app.utils.upload_validator import (
    validate_uploaded_file,
    check_rate_limit,
    UploadValidationError,
)
from backend.app.utils.employee_cache import get_cached_employee_fullname, invalidate_employee_cache

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")


# ==============================================================================
# 📂 SECTION 1: MANAJEMEN SESI
# ==============================================================================


@router.get("/sessions")
async def get_history_sessions(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    if not current_user_npp:
        return {"status": "success", "data": []}
    sessions = await chat_history_service.get_user_sessions(current_user_npp)
    return {"status": "success", "data": sessions}


@router.post("/sessions/create")
async def create_new_chat_session(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
    judul: Optional[str] = Query("Obrolan Baru"),
):
    npp_target = current_user_npp if current_user_npp else "GUEST"
    name_target = "Pegawai Pindad" if current_user_npp else "Guest User"
    new_session = await chat_history_service.create_new_session(
        npp=npp_target,
        username=name_target,
        model_name=settings.MODEL_PERSONA,
        judul=judul,
    )
    return {"status": "success", "data": new_session}


@router.put("/sessions/{session_uuid}/title")
async def rename_chat_title(session_uuid: str, payload: TitleUpdateSchema):
    success = await chat_history_service.update_session_title(
        session_uuid, payload.judul
    )
    if not success:
        raise HTTPException(status_code=500, detail="Gagal memperbarui judul sesi.")
    return {"status": "success", "message": "Judul sesi berhasil diperbarui!"}


@router.put("/sessions/{session_uuid}/pin")
async def pin_chat_session(session_uuid: str, is_pinned: bool = Query(...)):
    success = await chat_history_service.toggle_pin_session(session_uuid, is_pinned)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal merubah status sematan.")
    return {"status": "success", "message": "Status sematan berhasil diperbarui!"}


@router.delete("/sessions/{session_uuid}")
async def delete_chat_session(session_uuid: str):
    success = await chat_history_service.soft_delete_session(session_uuid)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal menghapus sesi.")
    return {"status": "success", "message": "Sesi berhasil dihapus!"}


@router.get("/sessions/{session_uuid}/messages")
async def get_session_messages_endpoint(session_uuid: str):
    messages = await chat_history_service.get_session_messages(session_uuid)
    return {"status": "success", "data": messages}


# ==============================================================================
# 🚀 SECTION 2: PIPELINE UTAMA
# ==============================================================================


async def _run_parallel_rag(
    rewritten_queries: List[str],
    limit_per_query: int = 3,
) -> tuple[str, List[dict]]:
    """
    Jalankan RAG paralel untuk semua rewritten_queries sekaligus.
    Gabungkan hasilnya, deduplicate by source id, ambil top N.
    """
    if not rewritten_queries:
        return "", []

    start_time = time.time()
    from backend.app.utils.embedding_cache import get_embedding_cache
    cache = get_embedding_cache()
    hits_before = cache.hits

    async def _fetch(query: str):
        try:
            ctx, sources = await rag_service.assemble_powerful_context(
                query=query, limit=limit_per_query
            )
            return ctx, sources
        except Exception as e:
            logger.warning(f"⚠️ [PARALLEL RAG] Query '{query[:50]}' error: {e}")
            return "", []

    results = await asyncio.gather(*[_fetch(q) for q in rewritten_queries])
    
    duration_ms = int((time.time() - start_time) * 1000)
    hits_after = cache.hits
    is_cache_hit = hits_after > hits_before

    # Gabungkan konteks, deduplicate sources by id
    combined_context_parts = []
    seen_ids = set()
    combined_sources = []

    for ctx, sources in results:
        if ctx:
            combined_context_parts.append(ctx)
        for src in sources:
            src_id = src.get("id") or src.get("chunk_id") or str(src)
            if src_id not in seen_ids:
                seen_ids.add(src_id)
                # Inject timing and cache metadata into source
                src["search_time_ms"] = duration_ms
                src["cache_hit"] = is_cache_hit
                combined_sources.append(src)

    combined_context = "\n\n---\n\n".join(combined_context_parts)
    logger.info(
        f"✅ [PARALLEL RAG] {len(rewritten_queries)} queries | "
        f"{len(combined_context)} chars | {len(combined_sources)} unique sources | "
        f"time={duration_ms}ms | cache_hit={is_cache_hit}"
    )
    return combined_context, combined_sources


async def _sequential_pipeline_generator(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str],
) -> AsyncGenerator[str, None]:

    user_label = f"NPP: {current_user_npp}" if current_user_npp else "GUEST"
    logger.info(f"💬 [PIPELINE] Starting dari {user_label}")

    if not payload.messages:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong!")

    user_message = payload.messages[-1].content
    chat_mode = getattr(payload, "mode", "auto")

    logger.info(f'👤 [USER] "{user_message[:100]}" | mode={chat_mode}')

    messages_for_pipeline = [
        {"role": msg.role, "content": msg.content} for msg in payload.messages
    ]

    # ── Klasifikasi attachment ──────────────────────────────────────────────
    ocr_text = None
    has_images = False
    pdf_paths = []

    if payload.attachment_paths:
        for path in payload.attachment_paths:
            path_lower = path.lower()
            if path_lower.endswith(".pdf"):
                pdf_paths.append(path)
            if any(
                path_lower.endswith(ext)
                for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]
            ):
                has_images = True

    # ── PDF Extraction (pymupdf primary) ───────────────────────────────────
    if pdf_paths:
        logger.info(f"[PDF] Ekstraksi {len(pdf_paths)} file...")
        yield _format_sse("", "📄 Membaca lampiran PDF...", False)
        try:
            pdf_result = await extract_pdf_text(pdf_paths)
            ocr_text = pdf_result.get("extracted_text", "")
            if payload.session_uuid:
                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=f"{user_message} [PDF Berhasil Dibaca]",
                )
        except Exception as e:
            logger.error(f"[PDF] Gagal: {e}")
            ocr_text = "[Gagal membaca PDF]"

    elif has_images:
        logger.info("📸 [IMAGE] Gambar murni → akan diteruskan ke Gemma Vision")
        yield _format_sse("", "🖼️ Mengantre analisis visual...", False)

    # ── Simpan pesan user ──────────────────────────────────────────────────
    if payload.session_uuid:
        attachment_info = (
            f" [Lampiran: {len(payload.attachment_paths)} file(s)]"
            if payload.attachment_paths
            else ""
        )
        await chat_history_service.save_chat_message(
            session_id=payload.session_uuid,
            role="user",
            text=f"{user_message}{attachment_info}",
            thought=f"Pipeline [Mode: {chat_mode}]",
        )

    # ==========================================================================
    # 🚦 LAYER 0: GATEWAY (routing + rewritten_queries)
    # ==========================================================================
    logger.info("[LAYER 0] Gateway starting...")
    yield _format_sse("", "🚦 Menentukan jalur pipeline...", False)

    try:
        gateway_result = await execute_layer_0_gateway(
            request=request,
            user_message=user_message,
            chat_mode=chat_mode,
        )
    except Exception as e:
        logger.error(f"[LAYER 0] Error: {e} → fallback flash")
        from backend.app.services.pipeline_layer_executor import _gateway_flash_result

        gateway_result = _gateway_flash_result()

    target_pipeline = gateway_result.get("target_pipeline", "flash")
    rewritten_queries = gateway_result.get("rewritten_queries", [])

    logger.info(
        f"[LAYER 0] target={target_pipeline} | "
        f"queries={len(rewritten_queries)} | "
        f"confidence={gateway_result.get('confidence', 0):.2f}"
    )

    logger.debug(f"[LAYER 0 OUTPUT] Gateway Result: {json.dumps(gateway_result, indent=2, ensure_ascii=False, default=str)}")

    # ==========================================================================
    # 📚 ROUTING FINAL
    # - documents: Layer 1 (Qwen 3B) + RAG paralel
    # - flash    : BYPASS Layer 1 total — params rule-based instan, no LLM
    # ==========================================================================
    preloaded_rag_context = None
    preloaded_rag_sources = None

    # context_history_str dibutuhkan rule-based params di jalur flash
    context_history_str = ""
    if len(messages_for_pipeline) > 1:
        # Ambil 5 turn terakhir (bukan 4)
        context_history_str = "\n".join(
            [
                f"{m['role'].upper()}: {m['content']}"
                for m in messages_for_pipeline[-5:-1]
            ]
        )
        logger.info(
            f"📜 [CONTEXT] {len(messages_for_pipeline[-5:-1])} turn history loaded"
        )

    if target_pipeline == "documents" and rewritten_queries:
        logger.info(
            f"[RAG PARALLEL] Menjalankan {len(rewritten_queries)} queries paralel..."
        )
        yield _format_sse("", "📚 Mencari dokumen regulasi relevan...", False)

        # Layer 1 HANYA dipanggil di jalur documents
        layer1_task = asyncio.create_task(
            execute_layer_1_analyzer(
                request=request,
                messages=messages_for_pipeline,
                gateway_result=gateway_result,
                employee_npp=current_user_npp,
                ocr_text=ocr_text,
                rag_metadata=None,
            )
        )

        try:
            rag_task = asyncio.create_task(
                _run_parallel_rag(rewritten_queries, limit_per_query=3)
            )

            (preloaded_rag_context, preloaded_rag_sources), cognitive_params = (
                await asyncio.gather(rag_task, layer1_task)
            )

            logger.info(
                f"[RAG + LAYER 1] Selesai paralel | "
                f"RAG: {len(preloaded_rag_context)} chars | "
                f"Intent: {cognitive_params.get('detected_intent')}"
            )

            if preloaded_rag_sources:
                yield _format_sse("", "", False, sources=preloaded_rag_sources)

        except Exception as e:
            logger.error(f"[RAG PARALLEL] Error: {e}")
            try:
                cognitive_params = await layer1_task
            except Exception as e2:
                logger.error(f"[LAYER 1] Error: {e2}")
                from backend.app.services.pipeline_layer_executor import (
                    _get_fallback_cognitive_params,
                )

                cognitive_params = _get_fallback_cognitive_params(user_message)
            preloaded_rag_context = None
            preloaded_rag_sources = None

        # ── Dump output Layer 1 ──────────────────────────────────────────
logger.debug(f"[LAYER 1 OUTPUT] Cognitive params: {json.dumps(cognitive_params, indent=2, ensure_ascii=False, default=str)}")

    else:
        # FLASH: bypass Layer 1 sepenuhnya — no LLM call, instan
        logger.info(
            f"⚡ [BYPASS LAYER 1] target={target_pipeline} — generate params rule-based (instant, no LLM)"
        )
        yield _format_sse("", "⚡ Menyiapkan respons cepat...", False)

        cognitive_params = _get_fallback_cognitive_params_rule_based(
            user_message=user_message,
            previous_context=context_history_str,
            ocr_text=ocr_text,
            target_pipeline=target_pipeline,
            is_coding_from_gateway=gateway_result.get("is_coding", False),
        )

    # ── Inject metadata ke cognitive_params ───────────────────────────────
    cognitive_params["chat_mode"] = chat_mode
    cognitive_params["ocr_text"] = ocr_text
    cognitive_params["_gateway"] = gateway_result

    # Inject nama pegawai jika tersedia
    # ── Inject nama pegawai (multiple field fallback) ─────────────────────
    # Inject chat_mode dan ocr_text ke cognitive_params agar tersedia di Layer 2
    cognitive_params["chat_mode"] = chat_mode
    cognitive_params["ocr_text"] = ocr_text

    # ═══════════════════════════════════════════════════════════════════════════
    # 👤 INJECT NAMA EMPLOYEE (FIRST NAME ONLY FOR CASUAL SAPAAN) — CACHED
    # ═══════════════════════════════════════════════════════════════════════════
    employee_name = "Guest"
    if current_user_npp and current_user_npp != "GUEST":
        try:
            # Use cached employee lookup to avoid N+1 query
            async def fetch_employee_from_db(npp: str) -> Optional[str]:
                from backend.app.core.database import get_db
                async with get_db() as conn:
                    row = await conn.fetchrow(
                        "SELECT fullname FROM users WHERE npp = $1 LIMIT 1",
                        npp,
                    )
                    return row.get("fullname") if row else None

            full_name = await get_cached_employee_fullname(
                current_user_npp,
                db_fetch_func=fetch_employee_from_db,
            )

            if full_name:
                # 🔥 Ambil first name aja untuk sapaan casual
                name_parts = full_name.strip().split()
                if name_parts:
                    # Ambil kata pertama, title case biar rapi
                    employee_name = name_parts[0].title()
                    logger.info(
                        f"✅ [EMPLOYEE] First name extracted: {employee_name} (from: {full_name})"
                    )
                else:
                    employee_name = "Pegawai"
            else:
                logger.warning(
                    f"⚠️ [EMPLOYEE] NPP {current_user_npp} tidak ditemukan di tabel users"
                )
                employee_name = "Pegawai"

        except Exception as e:
            logger.warning(f"⚠️ [EMPLOYEE] Gagal ambil nama dari cache/DB: {e}")
            employee_name = "Pegawai"

    cognitive_params["employee_name"] = employee_name
    logger.info(f"👤 [EMPLOYEE FINAL] Sapaan untuk Gemma: '{employee_name}'")
    # ═════════════════════════════════════════════════════════════════════════════

    # ── Log dump Layer 1 ────────────────────────────────────────────────────────
    logger.debug(f"[LAYER 1 LOG DUMP] Cognitive params: {json.dumps(cognitive_params, indent=2, ensure_ascii=False)}")

    # ── Log dump FINAL: blueprint utuh yang diterima Gemma (Layer 2) ────────
    logger.info(
        f"[FINAL BLUEPRINT] target={target_pipeline} | "
        f"Intent: {cognitive_params.get('detected_intent')} | "
        f"RAG: {cognitive_params.get('need_rag')} | "
        f"Coding: {cognitive_params.get('is_coding')}"
    )
    logger.debug(f"[LAYER 2 INPUT] Blueprint for Gemma (pipeline: {target_pipeline}): {json.dumps(cognitive_params, indent=2, ensure_ascii=False, default=str)}")

    # ==========================================================================
    # ✍️ LAYER 2: GEMMA AGENTIC
    # ==========================================================================
    logger.info("[LAYER 2] Gemma Agentic starting...")

    full_response_text = ""
    start_time = datetime.now()

    try:
        async for sse_event in execute_layer_2_gemma_agentic(
            request=request,
            messages=messages_for_pipeline,
            cognitive_params=cognitive_params,
            preloaded_rag_context=preloaded_rag_context,
            preloaded_rag_sources=preloaded_rag_sources,
        ):
            try:
                event_data = json.loads(sse_event.strip())
                chunk_text = event_data.get("chunk", "")
                if chunk_text:
                    full_response_text += chunk_text
            except (json.JSONDecodeError, AttributeError):
                if sse_event and isinstance(sse_event, str):
                    full_response_text += sse_event

            yield sse_event

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"[LAYER 2] Selesai | {len(full_response_text)} chars | {elapsed:.2f}s"
        )

    except Exception as e:
        logger.error(f"[LAYER 2] Error: {e}")
        error_msg = f"Gagal mengeksekusi pipeline: {str(e)}"
        yield _format_sse(error_msg, "", False)
        full_response_text = error_msg

    # ==========================================================================
    # 💾 DATABASE PERSISTENCE
    # ==========================================================================
    if payload.session_uuid:
        await chat_history_service.auto_update_session_title(
            payload.session_uuid, user_message
        )
        await chat_history_service.save_chat_message(
            session_id=payload.session_uuid,
            role="assistant",
            text=full_response_text,
            thought=f"Pipeline: {target_pipeline} | Mode: {chat_mode}",
        )

        if not (payload.attachment_paths and len(payload.attachment_paths) > 0):
            try:
                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=user_message,
                    assistant_text=full_response_text,
                    context_document=f"Pipeline: {target_pipeline}",
                )
            except Exception as e:
                logger.warning(f"[DB] Gagal save dialogue corpus: {e}")

    logger.info("[PIPELINE] Complete ✅")
    yield _format_sse("", "", True)


@router.post("/stream")
async def chat_stream_endpoint(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Chat streaming endpoint dengan proper resource cleanup (B8).
    
    Handles:
    - asyncio.CancelledError ketika client disconnect mid-stream
    - Database connection cleanup via proper finally block
    - Exception logging & recovery
    """
    async def wrapped_generator():
        """
        Wrapper generator dengan try/except/finally untuk resource management.
        B8: Memastikan DB connections di-return ke pool bahkan saat client disconnect.
        """
        try:
            async for chunk in _sequential_pipeline_generator(request, payload, current_user_npp):
                yield chunk
        except asyncio.CancelledError:
            logger.info(
                f"⚠️ [STREAM] Client disconnect detected (NPP: {current_user_npp}) — "
                f"cleaning up resources gracefully"
            )
            # Resources akan di-cleanup via context manager finally blocks
            raise
        except Exception as e:
            logger.error(f"❌ [STREAM] Error in generator: {e}")
            # Send error message ke client
            yield _format_sse("", f"Error: {str(e)[:100]}", True)
            raise
        finally:
            # Ensure cleanup even if no exception
            logger.debug("[STREAM] Generator cleanup completed — all connections returned to pool")
    
    return StreamingResponse(
        wrapped_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ==============================================================================
# 📎 SECTION 3: UPLOAD ATTACHMENT
# ==============================================================================


@router.post("/documents/upload")
async def upload_chat_attachments(
    files: List[UploadFile] = File(...),
    session_uuid: Optional[str] = Form(None),
    request: Request = None,  # Inject request untuk mendapat client IP
):
    """
    Upload file attachment dengan validasi ketat:
    1. Rate limiting per IP (max 10 uploads per 5 menit)
    2. Validasi extension file
    3. Validasi MIME type
    4. Validasi ukuran file (max 10MB)
    5. Validasi magic bytes (deteksi tipe sebenarnya)
    """
    
    # ───────────────────────────────────────────────────────────────────────
    # 1. RATE LIMITING CHECK
    # ───────────────────────────────────────────────────────────────────────
    client_ip = request.client.host if request and request.client else "unknown"
    if not check_rate_limit(client_ip):
        logger.warning(f"⚠️ [UPLOAD] Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak upload request. Coba lagi dalam beberapa menit."
        )
    
    uploaded_meta_list = []

    for file in files:
        try:
            # ───────────────────────────────────────────────────────────────
            # 2. READ FILE BYTES (untuk validasi comprehensive)
            # ───────────────────────────────────────────────────────────────
            file_bytes = await file.read()
            
            # ───────────────────────────────────────────────────────────────
            # 3. COMPREHENSIVE VALIDATION
            # ───────────────────────────────────────────────────────────────
            is_valid, validation_msg = validate_uploaded_file(
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream",
                file_bytes=file_bytes
            )
            
            if not is_valid:
                logger.warning(f"❌ [UPLOAD] Validasi gagal untuk {file.filename}: {validation_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Validasi file '{file.filename}' gagal: {validation_msg}"
                )
            
            # ───────────────────────────────────────────────────────────────
            # 4. WRITE TO DISK (setelah validasi lulus)
            # ───────────────────────────────────────────────────────────────
            unique_filename = f"{int(time.time())}_{file.filename}"
            absolute_write_path = os.path.join(UPLOAD_DIR, unique_filename)

            with open(absolute_write_path, "wb") as buffer:
                buffer.write(file_bytes)

            file_size = os.path.getsize(absolute_write_path)
            logger.info(f"✅ [UPLOAD] File '{file.filename}' ({file_size} bytes) tersimpan ke disk")

            # ───────────────────────────────────────────────────────────────
            # 5. SAVE METADATA TO DATABASE
            # ───────────────────────────────────────────────────────────────
            inserted_meta = await chat_history_service.save_chat_attachment(
                session_uuid=session_uuid,
                original_filename=file.filename,
                unique_filename=unique_filename,
                file_size=file_size,
                mime_type=file.content_type or "application/octet-stream",
                extracted_text=f"[Pending OCR: {file.filename}]",
            )

            if inserted_meta:
                uploaded_meta_list.append(inserted_meta)
                logger.info(f"📝 [UPLOAD] Metadata '{file.filename}' tersimpan ke database")
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Gagal menyimpan metadata {file.filename}.",
                )

        except HTTPException:
            raise
        except UploadValidationError as ve:
            logger.warning(f"❌ [UPLOAD] Validation error: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as err:
            logger.error(f"❌ [UPLOAD] Gagal proses {file.filename}: {err}", exc_info=True)
            if os.path.exists(absolute_write_path):
                os.remove(absolute_write_path)
                logger.info(f"🧹 [UPLOAD] File {absolute_write_path} dihapus karena error")
            raise HTTPException(
                status_code=500, detail=f"Gagal memproses {file.filename}."
            )

    logger.info(f"✅ [UPLOAD] {len(uploaded_meta_list)} file sukses diupload dari IP {client_ip}")
    return {"status": "success", "data": uploaded_meta_list}


# ==============================================================================
# ⭐ SECTION 4: FEEDBACK & RATING
# ==============================================================================


@router.post("/messages/{message_id}/feedback")
async def submit_message_feedback(
    message_id: int,
    feedback: FeedbackSchema,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Terima feedback/rating dari user terhadap respon AI.
    Simpan ke database untuk quality monitoring.
    
    Args:
        message_id: ID pesan yang di-feedback
        feedback: Rating (1-5) dan comment opsional
        current_user_npp: NPP user yang submit feedback
    
    Returns:
        {"status": "success", "message": "..."}
    """
    
    user_label = f"NPP: {current_user_npp}" if current_user_npp else "GUEST"
    logger.info(
        f"⭐ [FEEDBACK] Message ID: {message_id} | "
        f"Rating: {feedback.rating}/5 | User: {user_label}"
    )
    
    try:
        # Simpan feedback ke database melalui chat_history_service
        success = await chat_history_service.save_message_feedback(
            message_id=message_id,
            rating=feedback.rating,
            comment=feedback.comment,
            rated_by_npp=current_user_npp or "GUEST",
        )
        
        if not success:
            logger.warning(f"⚠️ [FEEDBACK] Gagal menyimpan feedback untuk message {message_id}")
            raise HTTPException(
                status_code=500,
                detail="Gagal menyimpan feedback. Coba lagi nanti."
            )
        
        logger.info(f"✅ [FEEDBACK] Berhasil tersimpan untuk message {message_id}")
        return {
            "status": "success",
            "message": f"Terima kasih! Rating {feedback.rating}/5 berhasil disimpan.",
            "message_id": message_id,
            "rating": feedback.rating,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [FEEDBACK] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan saat memproses feedback."
        )
