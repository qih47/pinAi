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
    # Allow common code and text files
    "text/plain", "text/html", "text/css", "text/javascript", "text/csv",
    "application/json", "application/javascript", "application/xml",
    "application/x-httpd-php", "text/x-php", "text/x-python",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# We will allow all extensions except the dangerous ones in security_firewall.py
# So we don't strictly check ALLOWED_EXTENSIONS for text files.
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".pdf", 
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".css", ".js", ".jsx", ".ts", ".tsx",
    ".py", ".php", ".rb", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".swift", ".kt", ".dart",
    ".sh", ".yml", ".yaml", ".toml", ".ini", ".conf", ".docx"
}

# Magic bytes untuk deteksi tipe file (Hanya untuk file binary. File teks tidak wajib punya magic bytes)
MAGIC_BYTES = {
    b'\xff\xd8\xff':        (".jpg",  "image/jpeg"),
    b'\x89PNG\r\n\x1a\n':  (".png",  "image/png"),
    b'RIFF':                (".webp", "image/webp"),
    b'BM':                  (".bmp",  "image/bmp"),
    b'%PDF':                (".pdf",  "application/pdf"),
    b'PK\x03\x04':          (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


class UploadValidationError(Exception):
    """Custom exception untuk validation error — ditangkap di upload.py."""
    pass


def validate_file_extension(filename: str) -> bool:
    if not filename:
        raise UploadValidationError("Filename tidak boleh kosong")
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Block SQL explicitly
    if file_ext in [".sql", ".sqlite", ".db"]:
        raise UploadValidationError("File database/SQL tidak diizinkan untuk alasan keamanan.")
        
    if file_ext not in ALLOWED_EXTENSIONS:
        # If it's not in our known list, we still allow it as long as it's not blocked by firewall later.
        pass
        
    return True


def validate_mime_type(content_type: str) -> bool:
    if not content_type:
        raise UploadValidationError("Content-Type tidak boleh kosong")
    # For now, allow any content type if it's text
    if content_type.startswith("text/") or content_type in ALLOWED_MIME_TYPES or "octet-stream" in content_type:
        return True
    
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

        # Hanya cek magic bytes untuk file yang diharapkan punya magic bytes (gambar, pdf, zip/docx)
        is_binary_with_magic = False
        for _, (_, mime) in MAGIC_BYTES.items():
            if content_type == mime:
                is_binary_with_magic = True
                break

        if is_binary_with_magic:
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