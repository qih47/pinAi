import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Depends, Form
from fastapi.responses import PlainTextResponse

from backend.app.core.config import settings
import base64
from backend.app.core.paths import get_account_session_dir
from backend.app.api.dependencies.auth import get_current_user_npp

import zipfile
import io
from fastapi.responses import PlainTextResponse, StreamingResponse

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


@router.get("/artifacts/download_all")
async def download_all_artifacts(
    session_id: str = Query(..., description="ID Sesi (Session UUID)"),
    current_user_npp: str = Depends(get_current_user_npp),
):
    """
    Mengunduh semua file artifact dalam suatu sesi sebagai file ZIP.
    """
    target_dir = get_account_session_dir(current_user_npp, session_id, "artifacts")
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Tidak ada artifact pada sesi ini.")

    zip_buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for f in target_dir.glob("*.*"):
            if f.is_file():
                zip_file.write(f, f.name)
                file_count += 1
                
    if file_count == 0:
        raise HTTPException(status_code=404, detail="Tidak ada file yang bisa didownload.")

    zip_buffer.seek(0)
    logger.info(f"[ARTIFACTS] Download All: session {session_id[:8]} ({file_count} files)")
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=artifacts_{session_id[:8]}.zip"}
    )


@router.post("/artifacts/download_b64")
async def download_b64_artifact(
    base64_data: str = Form(...),
    filename: str = Form(...),
    mime_type: str = Form(...)
):
    """
    Mengunduh data base64 sebagai file attachment.
    Ini berguna untuk mem-bypass pemblokiran browser terhadap 'blob:' atau 'data:'
    pada download HTTP non-localhost.
    """
    try:
        # Strip header if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
            
        file_bytes = base64.b64decode(base64_data)
        file_like = io.BytesIO(file_bytes)
        
        return StreamingResponse(
            file_like,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"[ARTIFACTS] Failed to decode base64 for {filename}: {e}")
        raise HTTPException(status_code=400, detail="Data base64 tidak valid.")
