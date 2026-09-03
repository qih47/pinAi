"""
CAKRA AI — Artifact Generator
===============================
Generator dan penyimpan file fisik hasil AI ke folder artifacts/ sesi.
Konsolidasi dari _write_file_to_disk() dan _sanitize_filename() di mode_generate_file.py.

Di Step 1 ini berdiri sendiri.
Step 5 akan menghubungkan ModeGenerateFile ke sini.
"""

import os
import re
import logging
import asyncio
import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("CAKRA_ARTIFACT_GENERATOR")

# Format MIME yang didukung untuk deteksi otomatis
_MIME_MAP = {
    ".py": "text/x-python",
    ".js": "application/javascript",
    ".ts": "application/typescript",
    ".jsx": "text/jsx",
    ".tsx": "text/tsx",
    ".html": "text/html",
    ".css": "text/css",
    ".json": "application/json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf",
    ".sh": "text/x-sh",
    ".sql": "text/x-sql",
    ".xml": "text/xml",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".csv": "text/csv",
}


# ─── Filename Sanitizer ───────────────────────────────────────────────────────
def sanitize_filename(filename: str) -> str:
    """
    Membersihkan nama file dari karakter berbahaya.
    Identik dengan _sanitize_filename() di mode_generate_file.py.
    """
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    filename = re.sub(r'\s+', '_', filename.strip())
    return filename[:100] if filename else "output_file.txt"


# ─── Main Writer ─────────────────────────────────────────────────────────────
async def write_artifact(
    filename: str,
    content: str,
    npp: str,
    session_id: str,
    artifacts_base_dir: Optional[str] = None,
) -> Path:
    """
    Tulis file artefak ke disk secara async.

    Identik dengan _write_file_to_disk() di mode_generate_file.py,
    tetapi dengan path yang lebih fleksibel.

    Args:
        filename: Nama file (akan disanitasi).
        content: Isi file sebagai string.
        npp: NPP pengguna.
        session_id: ID sesi aktif.
        artifacts_base_dir: Override folder artifacts. Default: accounts/{npp}/{session}/artifacts/

    Returns:
        Path absolut ke file yang ditulis.
    """
    safe_fn = sanitize_filename(filename)

    if artifacts_base_dir:
        target_dir = Path(artifacts_base_dir)
    else:
        from backend.app.core.paths import get_account_session_dir
        target_dir = get_account_session_dir(npp, session_id, "artifacts")

    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / safe_fn

    def _write():
        output_path.write_text(content, encoding="utf-8")

    await asyncio.to_thread(_write)
    logger.info(f"[ARTIFACT_GEN] ✅ Ditulis: {output_path}")

    # Catat ke manifest Brain sesi secara otomatis
    try:
        from backend.app.services.session.session_brain_service import SessionBrainService
        brain = SessionBrainService(npp, session_id)
        size_bytes = len(content.encode("utf-8"))
        rel_path = f"accounts/{npp}/{session_id}/brain/artifacts/{safe_fn}"
        brain.save_artifact_manifest(safe_fn, rel_path, size_bytes)
    except Exception as e:
        logger.warning(f"[ARTIFACT_GEN] Gagal update manifest brain: {e}")

    return output_path


# ─── MIME Helper ─────────────────────────────────────────────────────────────
def get_mime_type(filename: str) -> str:
    """Deteksi MIME type dari ekstensi file."""
    ext = Path(filename).suffix.lower()
    return _MIME_MAP.get(ext, "text/plain")


# ─── Relative Path Helper ─────────────────────────────────────────────────────
def get_relative_artifact_path(npp: str, session_id: str, filename: str) -> str:
    """
    Hasilkan path relatif artefak untuk disimpan di metadata/DB.
    Format: accounts/{npp}/{session}/brain/artifacts/{filename}
    """
    safe_npp = re.sub(r'[^\w\-]', '_', str(npp))
    safe_session = re.sub(r'[^\w\-]', '_', str(session_id))
    safe_fn = sanitize_filename(filename)
    return f"accounts/{safe_npp}/{safe_session}/brain/artifacts/{safe_fn}"

