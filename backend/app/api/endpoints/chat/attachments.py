import os
import time
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request

from backend.app.core.paths import UPLOAD_DIR
from backend.app.services.chat_history_service import chat_history_service
from backend.app.utils.upload_validator import (
    validate_uploaded_file,
    UploadValidationError,
)
# check_rate_limit sekarang dari security_firewall (sliding window, lebih akurat)
from backend.app.utils.security_firewall import (
    check_rate_limit,
    validate_attachment_security,
)

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")

@router.post("/documents/upload")
async def upload_chat_attachments(
    files: List[UploadFile] = File(...),
    session_uuid: Optional[str] = Form(None),
    request: Request = None,
):
    """
    Upload file attachment dengan validasi berlapis:
    1. Rate limiting per IP (sliding window, 10 uploads/5min)
    2. Security firewall: path traversal, extension, MIME, magic bytes
    3. Comprehensive validation: extension, MIME, size, magic bytes
    4. Write to disk & save metadata
    """

    client_ip = request.client.host if request and request.client else "unknown"

    # ── 1. Rate Limiting (policy "upload": 10 req / 300s) ────────────────────
    if not check_rate_limit(client_ip, "upload"):
        logger.warning(f"⚠️ [UPLOAD] Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak upload request. Coba lagi dalam beberapa menit."
        )

    uploaded_meta_list = []

    for file in files:
        absolute_write_path = ""
        try:
            # ── 2. Security Firewall (Layer 5) ───────────────────────────────
            await validate_attachment_security(file)

            # ── 3. Read bytes for comprehensive validation ────────────────────
            file_bytes = await file.read()

            is_valid, validation_msg = validate_uploaded_file(
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream",
                file_bytes=file_bytes,
            )

            if not is_valid:
                logger.warning(f"❌ [UPLOAD] Validasi gagal untuk {file.filename}: {validation_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Validasi file '{file.filename}' gagal: {validation_msg}",
                )

            # ── 4. Write to disk ──────────────────────────────────────────────
            unique_filename = f"{int(time.time())}_{file.filename}"
            absolute_write_path = os.path.join(UPLOAD_DIR, unique_filename)

            with open(absolute_write_path, "wb") as buffer:
                buffer.write(file_bytes)

            file_size = os.path.getsize(absolute_write_path)
            logger.info(f"✅ [UPLOAD] File '{file.filename}' ({file_size} bytes) tersimpan ke disk")

            # ── 5. Save metadata to DB ────────────────────────────────────────
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
            if absolute_write_path and os.path.exists(absolute_write_path):
                os.remove(absolute_write_path)
                logger.info(f"🧹 [UPLOAD] File {absolute_write_path} dihapus karena error")
            raise HTTPException(
                status_code=500, detail=f"Gagal memproses {file.filename}."
            )

    logger.info(f"✅ [UPLOAD] {len(uploaded_meta_list)} file sukses diupload dari IP {client_ip}")
    return {"status": "success", "data": uploaded_meta_list}