"""
CAKRA AI — File Upload Validation Utilities
============================================
Validasi tipe file, ukuran, magic bytes, dan rate limiting untuk upload endpoint.
"""

import logging
import os
from typing import Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger("CAKRA_UPLOAD_VALIDATOR")

# Configuration
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png", 
    "image/webp",
    "image/bmp",
    "application/pdf"
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".pdf"}

# Magic bytes untuk deteksi tipe file
MAGIC_BYTES = {
    b'\xff\xd8\xff': (".jpg", "image/jpeg"),      # JPEG
    b'\x89PNG\r\n\x1a\n': (".png", "image/png"),  # PNG
    b'RIFF': (".webp", "image/webp"),              # WEBP (simplified)
    b'BM': (".bmp", "image/bmp"),                  # BMP
    b'%PDF': (".pdf", "application/pdf"),          # PDF
}

# Rate limiting: {ip_address: [(timestamp, count), ...]}
rate_limit_tracker = defaultdict(list)
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_MINUTES = 5


class UploadValidationError(Exception):
    """Custom exception untuk validation error"""
    pass


def validate_file_extension(filename: str) -> bool:
    """
    Validasi extension file dari nama file.
    """
    if not filename:
        raise UploadValidationError("Filename tidak boleh kosong")
    
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Extension '{file_ext}' tidak didukung. Hanya: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return True


def validate_mime_type(content_type: str) -> bool:
    """
    Validasi MIME type yang dikirim dari client.
    Catatan: MIME type bisa dipalsukan, gunakan magic bytes check juga!
    """
    if not content_type:
        raise UploadValidationError("Content-Type tidak boleh kosong")
    
    if content_type not in ALLOWED_MIME_TYPES:
        raise UploadValidationError(
            f"MIME type '{content_type}' tidak didukung. Hanya: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    return True


def validate_file_size(file_bytes: bytes) -> bool:
    """
    Validasi ukuran file.
    """
    if not file_bytes:
        raise UploadValidationError("File kosong")
    
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise UploadValidationError(
            f"File terlalu besar ({len(file_bytes) / 1024 / 1024:.2f}MB). Max {MAX_FILE_SIZE_MB}MB"
        )
    return True


def detect_file_type_by_magic_bytes(file_bytes: bytes) -> Tuple[str, str]:
    """
    Deteksi tipe file dari magic bytes (file signature).
    Returns: (extension, mime_type) atau raise UploadValidationError
    """
    for magic_signature, (ext, mime_type) in MAGIC_BYTES.items():
        if file_bytes.startswith(magic_signature):
            logger.info(f"✅ [MAGIC BYTES] File terdeteksi sebagai {mime_type}")
            return ext, mime_type
    
    raise UploadValidationError(
        f"File tidak terdeteksi sebagai tipe yang valid. Magic bytes tidak cocok."
    )


def validate_uploaded_file(
    filename: str,
    content_type: str,
    file_bytes: bytes
) -> Tuple[bool, str]:
    """
    Validasi file upload secara komprehensif:
    1. Extension
    2. MIME type (dari client)
    3. Ukuran file
    4. Magic bytes (deteksi tipe sebenarnya)
    
    Returns: (is_valid, message)
    """
    try:
        # Step 1: Validasi extension
        validate_file_extension(filename)
        
        # Step 2: Validasi MIME type dari client
        validate_mime_type(content_type)
        
        # Step 3: Validasi ukuran
        validate_file_size(file_bytes)
        
        # Step 4: Deteksi tipe file dari magic bytes
        detected_ext, detected_mime = detect_file_type_by_magic_bytes(file_bytes)
        
        # Step 5: Verifikasi bahwa MIME type cocok dengan deteksi magic bytes
        if content_type != detected_mime:
            logger.warning(
                f"⚠️ [UPLOAD] MIME type mismatch! "
                f"Client: {content_type}, Magic Bytes: {detected_mime}"
            )
            # Bisa kita tolerir atau reject, untuk sekarang log saja
        
        logger.info(f"✅ [VALIDATION] File '{filename}' lulus semua validasi")
        return True, "Validasi berhasil"
        
    except UploadValidationError as e:
        logger.warning(f"⚠️ [VALIDATION] Validasi gagal: {str(e)}")
        return False, str(e)
    except Exception as e:
        logger.error(f"❌ [VALIDATION] Unexpected error: {str(e)}", exc_info=True)
        return False, f"Error validasi: {str(e)}"


def check_rate_limit(client_ip: str) -> bool:
    """
    Check rate limiting untuk client IP.
    Max 10 upload request per 5 menit.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    
    # Bersihkan request lama dari tracker
    rate_limit_tracker[client_ip] = [
        (ts, count) for ts, count in rate_limit_tracker[client_ip]
        if ts > window_start
    ]
    
    # Hitung total request dalam window
    total_requests = sum(count for _, count in rate_limit_tracker[client_ip])
    
    if total_requests >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(
            f"⚠️ [RATE LIMIT] IP {client_ip} exceed limit "
            f"({total_requests}/{RATE_LIMIT_MAX_REQUESTS} dalam {RATE_LIMIT_WINDOW_MINUTES} menit)"
        )
        return False
    
    # Increment counter
    rate_limit_tracker[client_ip].append((now, 1))
    logger.debug(f"📊 [RATE LIMIT] IP {client_ip}: {total_requests + 1} requests dalam window")
    return True
