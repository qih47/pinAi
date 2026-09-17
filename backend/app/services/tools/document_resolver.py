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


# ─── Isolated Document Unified Resolver ───────────────────────────────────────
async def resolve_isolated_document(
    isolated_doc_id: Any,
    doc_title: Optional[str] = None,
    doc_nomor: Optional[str] = None,
    doc_filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolusi menyeluruh dokumen terisolasi (Context Isolation) dari PostgreSQL (dokumen & dokumen_chunk)
    dan MySQL (berita), lengkap dengan smart fallback ke nomor/judul jika record awal tidak memiliki berkas fisik.
    """
    from backend.app.core.database import get_db, get_peraturan_db

    clean_id = isolated_doc_id
    pg_doc_id = None
    mysql_doc_id = None
    final_title = (doc_title or "").strip()
    final_nomor = (doc_nomor or "").strip()
    final_tanggal = ""
    final_jenis = "Regulasi"
    final_filename = (doc_filename or "").strip()
    file_path = None
    chunk_count = 0

    if isinstance(clean_id, str) and clean_id.lower().endswith(".pdf"):
        final_filename = final_filename or clean_id

    # 1. Lookup ke PostgreSQL dokumen
    if clean_id or final_filename or final_title:
        try:
            async with get_db() as pg_conn:
                pg_select = """
                    SELECT d.id, d.judul, d.filename, COALESCE(d.nomor, '') as nomor,
                           COALESCE(d.tanggal::text, '') as tanggal, COALESCE(j.nama, 'Regulasi') as jenis
                    FROM dokumen d
                    LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                """
                doc_row = None
                if str(clean_id).isdigit():
                    doc_row = await pg_conn.fetchrow(f"{pg_select} WHERE d.id = $1", int(clean_id))
                if not doc_row and final_filename:
                    doc_row = await pg_conn.fetchrow(f"{pg_select} WHERE d.filename = $1 LIMIT 1", final_filename)
                if not doc_row and final_title:
                    doc_row = await pg_conn.fetchrow(f"{pg_select} WHERE d.judul ILIKE $1 LIMIT 1", f"%{final_title}%")

                if doc_row:
                    pg_doc_id = doc_row["id"]
                    final_title = final_title or doc_row["judul"] or ""
                    final_filename = final_filename or doc_row["filename"] or ""
                    final_nomor = final_nomor or doc_row["nomor"] or ""
                    final_tanggal = final_tanggal or doc_row["tanggal"] or ""
                    final_jenis = doc_row["jenis"] or final_jenis
        except Exception as e:
            logger.warning(f"[RESOLVER] PG lookup error: {e}")

    # 2. Lookup ke MySQL berita
    if clean_id or final_nomor or final_title or final_filename:
        try:
            async with get_peraturan_db() as conn:
                async with conn.cursor() as cur:
                    my_select = """
                        SELECT b.id_berita, b.judul,
                               COALESCE(NULLIF(b.gambar, ''), NULLIF(b.gambar2, ''), NULLIF(b.gambar3, ''), NULLIF(b.linkper, '')) AS filename,
                               COALESCE(b.noper, '') as nomor,
                               COALESCE(b.tanggal, '') as tanggal,
                               COALESCE(k.nama_kategori, 'Regulasi') as jenis
                        FROM berita b
                        LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    """
                    row = None
                    if str(clean_id).isdigit():
                        await cur.execute(f"{my_select} WHERE b.id_berita = %s", (int(clean_id),))
                        row = await cur.fetchone()
                    if not row and final_filename:
                        await cur.execute(f"{my_select} WHERE b.gambar = %s OR b.gambar2 = %s OR b.gambar3 = %s OR b.linkper = %s LIMIT 1", (final_filename, final_filename, final_filename, final_filename))
                        row = await cur.fetchone()
                    if not row and final_nomor:
                        await cur.execute(f"{my_select} WHERE b.noper = %s LIMIT 1", (final_nomor,))
                        row = await cur.fetchone()
                    if not row and final_title:
                        await cur.execute(f"{my_select} WHERE b.judul LIKE %s LIMIT 1", (f"%{final_title}%",))
                        row = await cur.fetchone()

                    if row:
                        mysql_doc_id = row[0]
                        final_title = final_title or row[1] or ""
                        # Jika filename awal belum ada atau file fisik dari filename awal tidak ada di disk, prioritaskan filename dari MySQL
                        mysql_fn = row[2] or ""
                        if not final_filename or not find_valid_pdf_file(final_filename):
                            if mysql_fn and find_valid_pdf_file(mysql_fn):
                                final_filename = mysql_fn
                        final_nomor = final_nomor or row[3] or ""
                        final_tanggal = final_tanggal or (str(row[4]) if row[4] else "")
                        final_jenis = final_jenis if final_jenis and final_jenis != "Regulasi" else (row[5] or final_jenis)
        except Exception as e:
            logger.warning(f"[RESOLVER] MySQL lookup error: {e}")

    # 3. Cari keberadaan file fisik di disk
    file_path = find_valid_pdf_file(final_filename)

    # 4. Hitung chunk count di PG dokumen_chunk & Sinkronkan pg_doc_id jika didapat dari MySQL/Filename
    try:
        async with get_db() as pg_conn:
            if (not pg_doc_id or chunk_count == 0) and (mysql_doc_id or final_filename):
                alt_pg = await pg_conn.fetchrow(
                    "SELECT id, filename FROM dokumen WHERE id = $1 OR filename = $2 LIMIT 1",
                    mysql_doc_id or 0, final_filename
                )
                if alt_pg:
                    pg_doc_id = alt_pg["id"]
                    if not file_path and alt_pg["filename"]:
                        cand_p = find_valid_pdf_file(alt_pg["filename"])
                        if cand_p:
                            file_path = cand_p
                            final_filename = alt_pg["filename"]

            if pg_doc_id:
                chunk_count = await pg_conn.fetchval(
                    "SELECT count(*) FROM dokumen_chunk WHERE dokumen_id = $1", 
                    pg_doc_id
                ) or 0
    except Exception as e:
        logger.warning(f"[RESOLVER] Error checking chunk count: {e}")

    # 5. Smart Fallback by Nomor / Judul jika file fisik masih belum ditemukan
    if not file_path or not os.path.exists(file_path):
        logger.info(f"[RESOLVER] File physical not found for id={clean_id} (filename='{final_filename}'). Attempting smart resolution by nomor='{final_nomor}' or title='{final_title}'...")

        # 5.1 Coba cari di MySQL berita berdasarkan nomor / judul untuk mencari record yang memiliki berkas fisik valid
        if final_nomor or final_title:
            try:
                async with get_peraturan_db() as conn:
                    async with conn.cursor() as cur:
                        my_query = """
                            SELECT b.id_berita, b.judul,
                                   COALESCE(NULLIF(b.gambar, ''), NULLIF(b.gambar2, ''), NULLIF(b.gambar3, ''), NULLIF(b.linkper, '')) AS filename,
                                   COALESCE(b.noper, '') as nomor,
                                   COALESCE(b.tanggal, '') as tanggal,
                                   COALESCE(k.nama_kategori, 'Regulasi') as jenis
                            FROM berita b
                            LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                            WHERE (b.noper = %s OR b.noper LIKE %s OR b.judul LIKE %s)
                              AND (b.gambar != '' OR b.gambar2 != '' OR b.gambar3 != '' OR b.linkper != '')
                            LIMIT 5
                        """
                        nomor_pattern = f"%{final_nomor}%" if final_nomor else "%"
                        title_pattern = f"%{final_title}%" if final_title else "%"
                        await cur.execute(my_query, (final_nomor or "", nomor_pattern, title_pattern))
                        alt_rows = await cur.fetchall()
                        for a_row in alt_rows:
                            cand_fn = a_row[2]
                            cand_path = find_valid_pdf_file(cand_fn)
                            if cand_path and os.path.exists(cand_path):
                                mysql_doc_id = a_row[0]
                                final_title = final_title or a_row[1]
                                final_filename = cand_fn
                                final_nomor = final_nomor or a_row[3]
                                final_tanggal = final_tanggal or (str(a_row[4]) if a_row[4] else "")
                                final_jenis = a_row[5] or final_jenis
                                file_path = cand_path
                                logger.info(f"[RESOLVER] ✅ Smart-resolved via MySQL: alt_id={mysql_doc_id}, file={cand_path}")
                                break
            except Exception as e:
                logger.warning(f"[RESOLVER] Error in MySQL smart fallback: {e}")

        # 5.2 Coba cari di PostgreSQL dokumen berdasarkan nomor / judul yang memiliki chunks di dokumen_chunk atau file fisik
        if (not file_path or not os.path.exists(file_path)) and (final_nomor or final_title):
            try:
                async with get_db() as pg_conn:
                    pg_query = """
                        SELECT d.id, d.judul, d.filename, COALESCE(d.nomor, '') as nomor,
                               COALESCE(d.tanggal::text, '') as tanggal, COALESCE(j.nama, 'Regulasi') as jenis,
                               count(c.chunk_id) as c_cnt
                        FROM dokumen d
                        LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                        JOIN dokumen_chunk c ON d.id = c.dokumen_id
                        WHERE (d.nomor ILIKE $1 OR d.judul ILIKE $2)
                        GROUP BY d.id, d.judul, d.filename, d.nomor, d.tanggal, j.nama
                        ORDER BY c_cnt DESC
                        LIMIT 1
                    """
                    nomor_pattern = f"%{final_nomor}%" if final_nomor else "%"
                    title_pattern = f"%{final_title}%" if final_title else "%"
                    alt_pg = await pg_conn.fetchrow(pg_query, nomor_pattern, title_pattern)
                    if alt_pg:
                        pg_doc_id = alt_pg["id"]
                        final_title = final_title or alt_pg["judul"]
                        final_filename = final_filename or alt_pg["filename"]
                        final_nomor = final_nomor or alt_pg["nomor"]
                        final_tanggal = final_tanggal or alt_pg["tanggal"]
                        final_jenis = alt_pg["jenis"] or final_jenis
                        chunk_count = alt_pg["c_cnt"]
                        cand_path = find_valid_pdf_file(final_filename)
                        if cand_path and os.path.exists(cand_path):
                            file_path = cand_path
                        logger.info(f"[RESOLVER] ✅ Smart-resolved via PG: alt_pg_id={pg_doc_id}, chunks={chunk_count}, file={file_path}")
            except Exception as e:
                logger.warning(f"[RESOLVER] Error in PG smart fallback: {e}")

    # Fallback title jika masih kosong
    if not final_title:
        final_title = final_filename or f"Dokumen {clean_id or ''}".strip()

    return {
        "doc_id": mysql_doc_id or pg_doc_id or clean_id,
        "pg_doc_id": pg_doc_id,
        "mysql_doc_id": mysql_doc_id,
        "title": final_title,
        "nomor": final_nomor,
        "tanggal": final_tanggal,
        "jenis": final_jenis,
        "filename": final_filename,
        "file_path": file_path,
        "has_chunks": chunk_count > 0,
        "chunk_count": chunk_count,
    }

