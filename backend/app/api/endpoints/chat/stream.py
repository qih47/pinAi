import json
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.chat_history_service import chat_history_service
from backend.app.api.schemas.chat import ChatStreamRequest
from backend.app.utils.employee_cache import get_cached_employee_fullname
from backend.app.services.pipeline import (
    execute_gemma_agentic,
    format_sse,
    SSEEventType,
)
from backend.app.services.pipeline.sse_validation import format_sse_pipeline_data
from backend.app.core.config import settings
from backend.app.services.pipeline.continuation_orchestrator import execute_gemma_agentic_v2

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")


async def execute_vision_pipeline(
    request: Request,
    pdf_paths: List[str],
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Vision pipeline: PDF → convert ke image → MiniCPM OCR → return ocr_text.
    Hasilnya dikirim ke gemma_agentic_engine sebagai ocr_text.
    """
    raise NotImplementedError(
        "execute_vision_pipeline belum diimplementasi. "
        "Sambungkan ke vision_service (MiniCPM) di sini."
    )
    yield


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

    # ── PDF → Vision OCR ─────────────────────────────────────────────────────
    if pdf_paths:
        logger.info(f"[PDF] Mengirim {len(pdf_paths)} file ke vision pipeline...")
        async for sse in execute_vision_pipeline(
            request=request,
            pdf_paths=pdf_paths,
            user_message=user_message,
        ):
            raw = sse.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
                if data.get("event_type") == SSEEventType.PIPELINE_DATA:
                    ocr_text = data["payload"].get("ocr_text", "")
                    logger.info(f"[PDF] OCR selesai | {len(ocr_text)} chars")
                else:
                    yield sse
                    await asyncio.sleep(0.01)
            except (json.JSONDecodeError, AttributeError):
                yield sse
                await asyncio.sleep(0.01)

    if has_images:
        logger.info("[PIPELINE] Image attachment detected → akan diteruskan langsung ke Gemma")

    # ── Save user message ─────────────────────────────────────────────────────
    if payload.session_uuid:
        attachment_info = (
            f" [Lampiran: {len(payload.attachment_paths)} file(s)]"
            if payload.attachment_paths else ""
        )
        user_text = f"{user_message}{attachment_info}"
        
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

    # ── Resolve employee name ─────────────────────────────────────────────────
    employee_name = "Pegawai"
    if current_user_npp and current_user_npp != "GUEST":
        try:
            async def fetch_employee_from_db(npp: str) -> Optional[str]:
                from backend.app.core.database import get_db
                async with get_db() as conn:
                    row = await conn.fetchrow(
                        "SELECT fullname FROM users WHERE npp = $1 LIMIT 1", npp
                    )
                    return row.get("fullname") if row else None

            full_name = await get_cached_employee_fullname(
                current_user_npp,
                db_fetch_func=fetch_employee_from_db,
            )
            if full_name:
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
    start_time = datetime.now()

    try:
        if getattr(settings, "ENABLE_TOKEN_CONTINUATION", False):
            agentic_engine = execute_gemma_agentic_v2(
                request=request,
                messages=messages_for_pipeline,
                chat_mode=chat_mode,
                has_attachment=has_attachment,
                ocr_text=ocr_text,
                employee_name=employee_name,
                session_uuid=payload.session_uuid,
            )
        else:
            agentic_engine = execute_gemma_agentic(
                request=request,
                messages=messages_for_pipeline,
                chat_mode=chat_mode,
                has_attachment=has_attachment,
                ocr_text=ocr_text,
                employee_name=employee_name,
            )

        async for sse in agentic_engine:
            raw = sse.strip()
            if not raw:
                continue

            try:
                event_data = json.loads(raw)
                event_type = event_data.get("event_type")

                if event_type == SSEEventType.DONE:
                    continue
                elif event_type == SSEEventType.SOURCES:
                    preloaded_rag_sources = event_data.get("sources")
                elif event_type == SSEEventType.CHUNK:
                    chunk_text = event_data.get("chunk", "")
                    if chunk_text:
                        full_response_text += chunk_text
                elif event_type == SSEEventType.THINKING:
                    thinking_chunk = event_data.get("thinking", "")
                    if thinking_chunk:
                        full_thinking_text += thinking_chunk

            except (json.JSONDecodeError, AttributeError):
                pass

            # Tetap kirimkan sse chunk/sources asli ke client browser
            yield sse

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[AGENTIC] Selesai | {len(full_response_text)} chars | {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"[AGENTIC] Error: {e}")
        error_msg = f"Gagal mengeksekusi pipeline: {str(e)}"
        yield format_sse(error_msg, "", False, event_type=SSEEventType.CHUNK)
        full_response_text = error_msg

    # ── Save assistant response & finalize ────────────────────────────────────
    if payload.session_uuid:
        await chat_history_service.auto_update_session_title(
            payload.session_uuid, user_message
        )
        
        ast_thought = full_thinking_text.strip() if full_thinking_text else f"Gemma Agentic | Mode: {chat_mode}"
        
        if payload.edit_index is not None:
            await chat_history_service.update_chat_message(
                session_id=payload.session_uuid,
                edit_index=payload.edit_index + 1,
                role="assistant",
                text=full_response_text,
                thought=ast_thought,
                sources=preloaded_rag_sources,
            )
        else:
            await chat_history_service.save_chat_message(
                session_id=payload.session_uuid,
                role="assistant",
                text=full_response_text,
                thought=ast_thought,
                sources=preloaded_rag_sources,
            )
        if not (payload.attachment_paths and len(payload.attachment_paths) > 0):
            try:
                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=user_message,
                    assistant_text=full_response_text,
                    context_document=f"Gemma Agentic | Mode: {chat_mode}",
                )
            except Exception as e:
                logger.warning(f"[DB] Gagal save dialogue corpus: {e}")

    logger.info("[PIPELINE] Complete ✅")
    yield format_sse("", "", True, sources=preloaded_rag_sources, event_type=SSEEventType.DONE)


@router.post("/stream")
async def chat_stream_endpoint(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    async def wrapped_generator():
        try:
            async for chunk in _sequential_pipeline_generator(request, payload, current_user_npp):
                yield chunk
        except asyncio.CancelledError:
            logger.info(
                f"⚠️ [STREAM] Client disconnect (NPP: {current_user_npp}) — "
                f"cleaning up gracefully"
            )
            raise
        except Exception as e:
            logger.error(f"❌ [STREAM] Error in generator: {e}")
            yield format_sse("", f"Error: {str(e)[:100]}", True)
            raise
        finally:
            logger.debug("[STREAM] Generator cleanup completed")

    return StreamingResponse(
        wrapped_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )