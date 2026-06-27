import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse

from backend.app.core.config import settings
from backend.app.core.paths import get_account_session_dir
from backend.app.api.dependencies.auth import get_current_user_npp

router = APIRouter()
logger = logging.getLogger("CAKRA_ARTIFACTS")

# Maksimum ukuran file yang boleh dibaca (5MB)
_MAX_READ_SIZE = 5 * 1024 * 1024


@router.get("/artifacts/read", response_class=PlainTextResponse)
async def read_artifact_file(
    filename: str = Query(..., description="Nama file artifact yang ingin dibaca"),
    session_id: str = Query(..., description="ID Sesi (Session UUID) tempat artifact ini dibuat"),
    current_user_npp: str = Depends(get_current_user_npp),
):
    """
    Baca konten file yang sudah di-generate oleh Interceptor-Analyst Pipeline.

    Security:
    - Hanya baca dari direktori session-scoped user yang bersangkutan (tidak ada path traversal)
    - Sanitasi nama file: hanya basename yang dipakai
    - Limit ukuran file maksimal 5MB
    """
    # Sanitasi: hanya ambil basename
    safe_name = Path(filename).name
    if not safe_name or safe_name.startswith(".") or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")

    target_dir = get_account_session_dir(current_user_npp, session_id, "artifacts")
    target = target_dir / safe_name

    # Verifikasi file berada di dalam direktori yang diizinkan
    try:
        target.resolve().relative_to(target_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Akses file ditolak.")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{safe_name}' tidak ditemukan.")

    file_size = target.stat().st_size
    if file_size > _MAX_READ_SIZE:
        raise HTTPException(status_code=413, detail=f"File terlalu besar ({file_size // 1024} KB).")

    content = target.read_text(encoding="utf-8", errors="replace")
    logger.info(f"[ARTIFACTS] Read: {safe_name} ({file_size} bytes)")
    return PlainTextResponse(content=content, media_type="text/plain; charset=utf-8")
