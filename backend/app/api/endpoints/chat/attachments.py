import os
import time
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Depends

from backend.app.core.paths import get_account_dir
from backend.app.services.chat.chat_history_service import chat_history_service
from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.utils.upload_validator import (
    validate_uploaded_file,
    UploadValidationError,
)
# check_rate_limit sekarang dari security_firewall (sliding window, lebih akurat)
from backend.app.utils.security_firewall import (
    check_rate_limit,
    validate_attachment_security,
    _scan_for_injections,
    InjectionException
)

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")

@router.post("/documents/upload")
async def upload_chat_attachments(
    files: List[UploadFile] = File(...),
    session_uuid: Optional[str] = Form(None),
    current_user_npp: str = Depends(get_current_user_npp),
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
        
    # ── 1.5 Firewall Scan for Form Data (Session UUID) ────────────────────────
    if session_uuid:
        try:
            _scan_for_injections(session_uuid, "form_data:session_uuid")
        except InjectionException as e:
            logger.warning(f"🚨 [FIREWALL] Form data injection blocked in {e.field_name}")
            raise HTTPException(status_code=403, detail="Permintaan tidak valid (Form Data).")

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
            from backend.app.core.paths import get_account_session_dir
            account_images_dir = get_account_session_dir(current_user_npp, session_uuid, "images")
            absolute_write_path = os.path.join(account_images_dir, unique_filename)

            with open(absolute_write_path, "wb") as buffer:
                buffer.write(file_bytes)

            file_size = os.path.getsize(absolute_write_path)
            logger.info(f"✅ [UPLOAD] File '{file.filename}' ({file_size} bytes) tersimpan ke disk")

            # Hitung path relatif dari folder ROOT "accounts/"
            # Supaya frontend/static files bisa langsung load via: /accounts/{npp}/{session_id}/brain/images/filename
            relative_account_path = f"accounts/{current_user_npp}/{session_uuid}/brain/images/{unique_filename}"

            # ── 5. Ekstrak konten teks jika file adalah file teks ─────────────
            TEXT_MIME_PREFIXES = ("text/", "application/json", "application/xml")
            TEXT_EXTENSIONS_UPLOAD = {
                "txt", "csv", "md", "py", "js", "jsx", "ts", "tsx", "html", "css",
                "json", "yaml", "yml", "xml", "php", "java", "cpp", "c", "h",
                "sh", "bash", "dart", "swift", "go", "rs", "sql", "toml", "ini", "conf"
            }
            file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
            is_text_upload = (
                file_ext in TEXT_EXTENSIONS_UPLOAD or
                any(file.content_type.startswith(p) for p in TEXT_MIME_PREFIXES if file.content_type)
            )

            if is_text_upload:
                try:
                    raw_extracted = file_bytes.decode("utf-8", errors="replace")
                    logger.info(f"📄 [UPLOAD] Konten teks diekstrak: {len(raw_extracted)} chars dari '{file.filename}'")
                except Exception:
                    raw_extracted = "[Gagal membaca konten teks]"
            else:
                raw_extracted = f"[Pending OCR: {file.filename}]"

            # ── 6. Save metadata to DB ────────────────────────────────────────
            inserted_meta = await chat_history_service.save_chat_attachment(
                session_uuid=session_uuid,
                original_filename=file.filename,
                unique_filename=relative_account_path,
                file_size=file_size,
                mime_type=file.content_type or "application/octet-stream",
                extracted_text=raw_extracted,
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

@router.get("/documents/extract")
async def extract_file_content(path: str):
    """
    Endpoint untuk mengekstrak teks dari file PDF, Word, atau Kode/Text.
    Digunakan oleh UI untuk Document Preview.
    """
    if not path:
        raise HTTPException(status_code=400, detail="Path tidak boleh kosong.")
    
    # Path sanitization
    if ".." in path or "\\" in path:
        raise HTTPException(status_code=400, detail="Path file tidak valid.")
    
    filename = path.split("/")[-1]
    
    from backend.app.core.paths import get_abs_path
    if path.startswith("accounts/"):
        abs_path = get_abs_path(path)
        # Smart resolver fallback untuk path accounts
        if not os.path.exists(abs_path):
            parts = Path(path).parts
            if len(parts) >= 4 and parts[3] != "brain":
                alt_parts = list(parts[:3]) + ["brain"] + list(parts[3:])
                alt_path = get_abs_path("/".join(alt_parts))
                if os.path.exists(alt_path):
                    abs_path = alt_path
            elif len(parts) >= 5 and parts[3] == "brain":
                alt_parts = list(parts[:3]) + list(parts[4:])
                alt_path = get_abs_path("/".join(alt_parts))
                if os.path.exists(alt_path):
                    abs_path = alt_path
    else:
        abs_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")

    
    try:
        from backend.app.services.tools.unified_extractor import extract_document
        doc = await extract_document(abs_path)
        content = doc.full_text.strip()
        if not content:
            content = "[Teks tidak dapat diekstrak dari dokumen atau file kosong]"
        return {"content": content, "total_pages": doc.total_pages, "is_scanned": doc.is_scanned}
    except Exception as e:
        logger.error(f"[EXTRACT] Gagal mengekstrak file {filename}: {e}")
        # Fallback sederhana jika extractor gagal
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                return {"content": f.read()}
        except Exception:
            raise HTTPException(status_code=500, detail=f"Gagal mengekstrak isi file: {str(e)}")