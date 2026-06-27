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
    format_sse,
    SSEEventType,
)
from backend.app.services.pipeline.sse_validation import format_sse_pipeline_data
from backend.app.core.config import settings

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
        from backend.app.core.paths import UPLOAD_DIR
        import base64
        
        for path in payload.attachment_paths:
            path_lower = path.lower()
            filename = os.path.basename(path)
            abs_path = os.path.join(UPLOAD_DIR, filename)
            
            if not os.path.exists(abs_path):
                continue
                
            if any(path_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]):
                has_images = True
                try:
                    with open(abs_path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                        formatted_attachments.append({"base64": encoded, "type": "image"})
                except Exception as e:
                    logger.error(f"[PIPELINE] Gagal membaca gambar {path}: {e}")
            else:
                # Text/PDF/Doc extraction
                try:
                    ext = os.path.splitext(filename)[1].lower()
                    extracted = ""
                    if ext == ".pdf":
                        import PyPDF2
                        with open(abs_path, "rb") as f:
                            reader = PyPDF2.PdfReader(f)
                            for page in reader.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    extracted += page_text + "\n"
                        
                        # Fallback untuk PDF Scan (kosong teksnya), jalankan pre-restorasi OCRmyPDF lalu render jadi gambar
                        if not extracted.strip():
                            import fitz
                            import base64
                            
                            restored_pdf = abs_path + ".restored.pdf"
                            try:
                                import ocrmypdf
                                ocrmypdf.ocr(abs_path, restored_pdf, deskew=True, force_ocr=True, optimize=1)
                                target_pdf = restored_pdf
                            except Exception as e:
                                logger.warning(f"[OCR] ocrmypdf failed, fallback to original: {e}")
                                target_pdf = abs_path

                            doc = fitz.open(target_pdf)
                            # Render semua halaman karena Gemma4 memiliki 256K context
                            for page_num in range(len(doc)):
                                page = doc.load_page(page_num)
                                pix = page.get_pixmap(dpi=150) # Resolusi cukup tinggi untuk OCR mandiri VLM
                                img_data = pix.tobytes("png")
                                encoded = base64.b64encode(img_data).decode("utf-8")
                                formatted_attachments.append({"base64": encoded, "type": "image"})
                            
                            has_images = True
                    elif ext == ".docx":
                        import docx
                        doc = docx.Document(abs_path)
                        extracted = "\n".join([para.text for para in doc.paragraphs])
                    else:
                        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                            extracted = f.read()
                            
                    if extracted.strip():
                        extracted_file_texts.append(f"--- ISI FILE: {filename} ---\n{extracted.strip()}\n-------------------")
                        
                        # Save to memory (ai_document_chunks)
                        if payload.session_uuid and current_user_npp:
                            await chat_history_service.save_document_chunk(
                                session_uuid=payload.session_uuid,
                                npp=current_user_npp,
                                content=extracted.strip(),
                                chunk_metadata={"source": path}
                            )
                except Exception as e:
                    logger.error(f"[PIPELINE] Gagal mengekstrak isi file {path}: {e}")
                    
    # Append extracted texts to user message
    if extracted_file_texts:
        user_message += "\n\n" + "\n\n".join(extracted_file_texts)
        if payload.messages:
            payload.messages[-1].content = user_message

    # ── Save user message ─────────────────────────────────────────────────────
    if payload.session_uuid:
        user_text = f"{user_message}"
        
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
    generated_artifacts = []
    start_time = datetime.now()

    try:
        from backend.app.services.pipeline.mode_hub import mode_hub
        agentic_engine = mode_hub.execute(
            request=request,
            user_message=user_message,
            chat_history=payload.messages,
            chat_mode=chat_mode,
            is_thinking=payload.thinking if hasattr(payload, 'thinking') else True,
            attachments=formatted_attachments,
            context_isolation={"isolated_doc_id": payload.isolated_doc_id} if payload.isolated_doc_id else None,
            employee_name=employee_name,
            current_user_npp=current_user_npp,
            session_uuid=payload.session_uuid
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
                elif event_type == SSEEventType.FILE_STATUS:
                    fs = event_data.get("file_status", {})
                    if fs.get("stage") == "done" and fs.get("file_path"):
                        generated_artifacts.append({
                            "filename": fs.get("filename"),
                            "file_path": fs.get("file_path"),
                            "lines_count": fs.get("lines_count", 1)
                        })
                
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
        logger.error(f"[AGENTIC] Error: {e}")
        error_msg = f"Gagal mengeksekusi pipeline: {str(e)}"
        yield format_sse(error_msg, "", False, event_type=SSEEventType.CHUNK)
        full_response_text = error_msg

    # ── Save assistant response & finalize ────────────────────────────────────
    new_title = None
    if payload.session_uuid:
        try:
            # Panggil auto_update_session_title secara sinkron agar bisa diumpankan ke DONE event
            new_title = await chat_history_service.auto_update_session_title(
                payload.session_uuid, user_message, full_response_text
            )
        except Exception as e:
            logger.error(f"[TITLE] Gagal mengupdate judul sesi secara sinkron: {e}")

    async def _save_to_db():
        try:
            if payload.session_uuid:
                ast_thought = full_thinking_text.strip() if full_thinking_text else f"Gemma Agentic | Mode: {chat_mode}"
                
                if payload.edit_index is not None:
                    await chat_history_service.update_chat_message(
                        session_id=payload.session_uuid,
                        edit_index=payload.edit_index + 1,
                        role="assistant",
                        text=full_response_text,
                        thought=ast_thought,
                        sources=preloaded_rag_sources,
                        metadata={"artifacts": generated_artifacts} if generated_artifacts else None
                    )
                else:
                    await chat_history_service.save_chat_message(
                        session_id=payload.session_uuid,
                        role="assistant",
                        text=full_response_text,
                        thought=ast_thought,
                        sources=preloaded_rag_sources,
                        metadata={"artifacts": generated_artifacts} if generated_artifacts else None
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

    logger.info(f"[PIPELINE] Complete ✅ | Title: {new_title}")
    yield format_sse("", "", True, sources=preloaded_rag_sources, event_type=SSEEventType.DONE, title=new_title)


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