"""
CAKRA AI — File Upload Validation Utilities
============================================
Validasi tipe file, ukuran, dan magic bytes untuk upload endpoint.

Catatan: check_rate_limit TIDAK lagi ada di sini.
Rate limiting sekarang terpusat di security_firewall.py (SlidingWindowRateLimiter).
"""

import logging
import os
from typing import Tuple

logger = logging.getLogger("CAKRA_UPLOAD_VALIDATOR")

# Configuration
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "application/pdf",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".pdf"}

# Magic bytes untuk deteksi tipe file
MAGIC_BYTES = {
    b'\xff\xd8\xff':        (".jpg",  "image/jpeg"),
    b'\x89PNG\r\n\x1a\n':  (".png",  "image/png"),
    b'RIFF':                (".webp", "image/webp"),
    b'BM':                  (".bmp",  "image/bmp"),
    b'%PDF':                (".pdf",  "application/pdf"),
}


class UploadValidationError(Exception):
    """Custom exception untuk validation error — ditangkap di upload.py."""
    pass


def validate_file_extension(filename: str) -> bool:
    if not filename:
        raise UploadValidationError("Filename tidak boleh kosong")
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Extension '{file_ext}' tidak didukung. Hanya: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return True


def validate_mime_type(content_type: str) -> bool:
    if not content_type:
        raise UploadValidationError("Content-Type tidak boleh kosong")
    if content_type not in ALLOWED_MIME_TYPES:
        raise UploadValidationError(
            f"MIME type '{content_type}' tidak didukung. Hanya: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    return True


def validate_file_size(file_bytes: bytes) -> bool:
    if not file_bytes:
        raise UploadValidationError("File kosong")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise UploadValidationError(
            f"File terlalu besar ({len(file_bytes) / 1024 / 1024:.2f}MB). Max {MAX_FILE_SIZE_MB}MB"
        )
    return True


def detect_file_type_by_magic_bytes(file_bytes: bytes) -> Tuple[str, str]:
    for magic_signature, (ext, mime_type) in MAGIC_BYTES.items():
        if file_bytes.startswith(magic_signature):
            logger.info(f"✅ [MAGIC BYTES] File terdeteksi sebagai {mime_type}")
            return ext, mime_type
    raise UploadValidationError("File tidak terdeteksi sebagai tipe yang valid. Magic bytes tidak cocok.")


def validate_uploaded_file(
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> Tuple[bool, str]:
    """
    Validasi komprehensif: extension → MIME → size → magic bytes → cross-check.
    Returns (is_valid, message).
    """
    try:
        validate_file_extension(filename)
        validate_mime_type(content_type)
        validate_file_size(file_bytes)

        detected_ext, detected_mime = detect_file_type_by_magic_bytes(file_bytes)

        if content_type != detected_mime:
            logger.warning(
                f"⚠️ [UPLOAD] MIME mismatch: client={content_type}, magic={detected_mime} "
                f"for file '{filename}'"
            )
            # Tetap tolak — magic bytes lebih dipercaya dari client header
            raise UploadValidationError(
                f"Tipe file tidak cocok: header menyatakan '{content_type}' "
                f"tapi isi file adalah '{detected_mime}'."
            )

        logger.info(f"✅ [VALIDATION] File '{filename}' lulus semua validasi")
        return True, "Validasi berhasil"

    except UploadValidationError as e:
        logger.warning(f"⚠️ [VALIDATION] Validasi gagal: {str(e)}")
        return False, str(e)
    except Exception as e:
        logger.error(f"❌ [VALIDATION] Unexpected error: {str(e)}", exc_info=True)
        return False, f"Error validasi: {str(e)}"