"""
CAKRA AI — Document Resolver
==============================
Resolver metadata dan path fisik dokumen regulasi PT Pindad.
Merupakan konsolidasi dari helper functions di peraturan_service.py.

Di Step 1, file ini berdiri sendiri (tidak menggantikan kode lama).
Step 4 nanti akan menghubungkan ini ke peraturan_service.py.
"""

import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("CAKRA_DOCUMENT_RESOLVER")

PERATURAN_DIR = "/home/qisthi/pinAi/file_peraturan"


# ─── PDF File Resolver ───────────────────────────────────────────────────────
def find_valid_pdf_file(
    gambar: Any = None,
    gambar2: Any = None,
    gambar3: Any = None,
    db_file_path: Optional[str] = None
) -> Optional[str]:
    """
    Mencari file PDF yang valid dari kolom attachment regulasi atau path database.
    Memeriksa db_file_path → gambar → gambar2 → gambar3 di berbagai direktori valid.

    Returns:
        Path absolut ke file PDF yang ditemukan, atau None.
    """
    from backend.app.core.paths import BASE_DIR, FILE_PERATURAN_DIR, UPLOAD_DIR, DOCUMENTS_DIR

    candidate_dirs = [
        FILE_PERATURAN_DIR,
        PERATURAN_DIR,
        DOCUMENTS_DIR,
        UPLOAD_DIR,
        os.path.join(BASE_DIR, "file_peraturan"),
        BASE_DIR,
    ]

    if db_file_path and isinstance(db_file_path, str):
        if os.path.exists(db_file_path) and os.path.isfile(db_file_path):
            return db_file_path
        relative_path = os.path.join(BASE_DIR, db_file_path.lstrip("/"))
        if os.path.exists(relative_path) and os.path.isfile(relative_path):
            return relative_path

    for file_name in [gambar, gambar2, gambar3]:
        if file_name and isinstance(file_name, str):
            clean_name = os.path.basename(file_name.strip())
            for d in candidate_dirs:
                if not d:
                    continue
                p = os.path.join(d, clean_name)
                if os.path.exists(p) and os.path.isfile(p):
                    logger.debug(f"[RESOLVER] PDF ditemukan: {p}")
                    return p
    logger.debug("[RESOLVER] Tidak ada PDF valid di attachment regulasi.")
    return None



# ─── Status Berlaku Resolver ─────────────────────────────────────────────────
def resolve_status_berlaku(
    id_berita: int,
    stataktif: str,
    dicabut_oleh: Dict[int, Any],
) -> str:
    """
    Menentukan string status berlaku regulasi.

    Identik dengan _resolve_status_berlaku() di peraturan_service.py.

    Args:
        id_berita: ID regulasi yang dicek.
        stataktif: Nilai kolom stataktif dari DB ('batal', 'obsolete', atau aktif).
        dicabut_oleh: Dict {id_berita: (id_pengganti, judul_pengganti)} dari query silsilah.

    Returns:
        String status: "Berlaku" | "Dicabut" | "Tidak Berlaku" | "Tidak Berlaku (Digantikan oleh: ...)"
    """
    if id_berita in dicabut_oleh:
        pengganti_judul = dicabut_oleh[id_berita][1]
        return f"Tidak Berlaku (Digantikan oleh: {pengganti_judul})"
    stataktif_norm = str(stataktif or "").strip().lower()
    if stataktif_norm == "batal":
        return "Dicabut"
    elif stataktif_norm == "obsolete":
        return "Tidak Berlaku"
    return "Berlaku"


# ─── Mencabut Text Resolver ──────────────────────────────────────────────────
def resolve_mencabut_text(
    mencabut_str: str,
    linkper_str: str,
    doc_map: Dict[int, Dict[str, Any]],
) -> str:
    """
    Mengubah ID dokumen pada kolom mencabut/linkper menjadi teks deskriptif.

    Identik dengan _resolve_mencabut_text() di peraturan_service.py.

    Args:
        mencabut_str: String berisi ID yang dipisah '|' dari kolom mencabut.
        linkper_str: String berisi ID yang dipisah '|' dari kolom linkper.
        doc_map: Dict {id: {judul, noper, tanggal}} dari query batch.

    Returns:
        String deskriptif, contoh: "SK-001 - Judul Dok (2023-01-01); SK-002 - Judul Lain"
    """
    parts = []
    seen: set = set()

    for s in [mencabut_str, linkper_str]:
        if not s:
            continue
        for item in str(s).split("|"):
            item = item.strip()
            if not item:
                continue
            if item.isdigit():
                doc_id = int(item)
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                if doc_id in doc_map:
                    noper = str(doc_map[doc_id].get("noper") or "").strip()
                    judul = str(doc_map[doc_id].get("judul") or "").strip()
                    tgl = str(doc_map[doc_id].get("tanggal") or "").strip()[:10]
                    tgl_str = f" ({tgl})" if tgl and tgl not in ("0000-00-00", "None") else ""
                    if noper and judul:
                        parts.append(f"{noper} - {judul}{tgl_str}")
                    elif judul:
                        parts.append(f"{judul}{tgl_str}")
                    elif noper:
                        parts.append(f"{noper}{tgl_str}")
                    else:
                        parts.append(f"Dokumen ID #{doc_id}")
                else:
                    parts.append(f"Dokumen ID #{doc_id}")
            elif item not in seen:
                seen.add(item)
                parts.append(item)

    return "; ".join(parts) if parts else "-"


# ─── Path Helper ─────────────────────────────────────────────────────────────
def get_peraturan_abs_path(filename: str) -> Optional[str]:
    """
    Resolusi path absolut file regulasi dari nama file saja.

    Returns:
        Path absolut jika file ada, None jika tidak.
    """
    if not filename:
        return None
    abs_path = os.path.join(PERATURAN_DIR, filename)
    return abs_path if os.path.exists(abs_path) else None
