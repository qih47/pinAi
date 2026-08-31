import os
import json
import base64
import logging
import asyncio
from typing import Tuple, List, Dict, Any, Optional

import fitz

from backend.app.core.database import get_peraturan_db

logger = logging.getLogger("CAKRA_PERATURAN")

PERATURAN_DIR = "/home/qisthi/pinAi/file_peraturan"
CACHE_DIR = "/home/qisthi/pinAi/backend/uploads/.ocr_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _process_pdf_sync(abs_path: str) -> Tuple[str, List[Dict[str, Any]], int]:
    """
    Process PDF synchronously (CPU bound).
    Returns (extracted_text, formatted_attachments_images).
    """
    import PyPDF2
    import fitz
    
    extracted = ""
    total_pages = 0
    try:
        doc = fitz.open(abs_path)
        total_pages = len(doc)
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            # Use sort=True or layout preservation techniques if available. get_text("text") in fitz is generally good for layouts.
            page_text = page.get_text("text")
            if page_text:
                extracted += page_text + "\n"
        doc.close()
    except Exception as e:
        logger.warning(f"[PERATURAN_SERVICE] Failed to read PDF {abs_path}: {e}")
        return "", [], 0

    extracted = extracted.strip()
    formatted_attachments = []
    
    # If PDF has text, we just return the text (no need to OCR/Image for LLM)
    if extracted:
        return extracted, [], total_pages
        
    # If PDF is scanned (empty text), we need to OCR and convert to images
    logger.info(f"[PERATURAN_SERVICE] Scanned PDF detected, running OCR + Vision extraction for: {abs_path}")
    
    filename = os.path.basename(abs_path)
    restored_pdf = os.path.join(CACHE_DIR, f"{filename}.restored.pdf")
    
    if not os.path.exists(restored_pdf):
        try:
            import ocrmypdf
            logger.info(f"[PERATURAN_SERVICE] Running OCRmyPDF on {filename}...")
            ocrmypdf.ocr(abs_path, restored_pdf, deskew=True, force_ocr=True, optimize=1)
        except Exception as e:
            logger.warning(f"[PERATURAN_SERVICE] ocrmypdf failed: {e}. Fallback to original PDF.")
            restored_pdf = abs_path
            
    # Convert restored PDF to images for VLM
    try:
        doc = fitz.open(restored_pdf)
        total_pages = len(doc)
        # Batasi halaman scan dengan DPI 150 untuk ketajaman visual maksimal
        for page_num in range(min(len(doc), 2)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            encoded = base64.b64encode(img_data).decode("utf-8")
            formatted_attachments.append({"base64": encoded, "type": "image"})
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Failed to convert PDF to image: {e}")
        
    return "", formatted_attachments, total_pages


def extract_pdf_pages_sync(abs_path: str, max_pages: int = 100) -> List[Dict[str, Any]]:
    """
    Ekstrak teks halaman per halaman secara cepat untuk Page-Level Cross-Document Reranking.
    Returns list of dict: {page_num, text, is_scan, total_pages}
    """
    results = []
    if not abs_path or not os.path.exists(abs_path):
        return results
        
    try:
        doc = fitz.open(abs_path)
        total = min(len(doc), max_pages)
        for page_idx in range(total):
            page = doc.load_page(page_idx)
            text = page.get_text("text").strip()
            clean_text = " ".join(text.split())
            is_scan = len(clean_text) < 40
            
            results.append({
                "page_num": page_idx + 1,
                "text": clean_text,
                "is_scan": is_scan,
                "total_pages": len(doc)
            })
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Error extracting pages from {abs_path}: {e}")
        
    return results


def _find_valid_pdf_file(gambar: Any, gambar2: Any, gambar3: Any) -> Optional[str]:
    """Mencari file PDF yang valid dari kolom attachment peraturan."""
    for file_name in [gambar, gambar2, gambar3]:
        if file_name and isinstance(file_name, str) and file_name.lower().endswith(".pdf"):
            abs_path = os.path.join(PERATURAN_DIR, file_name)
            if os.path.exists(abs_path):
                return abs_path
    return None


def _resolve_status_berlaku(id_berita: int, stataktif: str, dicabut_oleh: Dict[int, Any]) -> str:
    """Menentukan status berlaku regulasi berdasarkan tabel silsilah dan stataktif."""
    if id_berita in dicabut_oleh:
        pengganti_judul = dicabut_oleh[id_berita][1]
        return f"Tidak Berlaku (Digantikan oleh: {pengganti_judul})"
    if stataktif == "batal":
        return "Dicabut"
    elif stataktif == "obsolete":
        return "Tidak Berlaku"
    return "Berlaku"


async def _resolve_latest_active_via_cursor(
    cursor,
    doc_id: int,
    max_depth: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Traversal forward melalui rantai mencabut/linkper untuk menemukan
    regulasi penerus yang masih berlaku (stataktif bukan obsolete/batal).
    Menggunakan cursor MySQL yang sudah terbuka (shared) agar tidak
    membuka koneksi baru per dokumen.
    Mengembalikan dict {id, judul, noper} atau None jika tidak ditemukan.
    """
    visited = set()
    current_id = doc_id
    depth = 0

    while depth < max_depth:
        if current_id in visited:
            break  # Circular chain guard
        visited.add(current_id)

        await cursor.execute(
            "SELECT id_berita, judul, noper, stataktif, mencabut, linkper "
            "FROM berita WHERE id_berita = %s",
            (current_id,)
        )
        row = await cursor.fetchone()
        if not row:
            break

        r_id, r_judul, r_noper, r_stataktif, r_mencabut, r_linkper = row
        r_stataktif_norm = str(r_stataktif or "").strip().lower()

        # Jika dokumen ini masih aktif → ini adalah leaf node
        if r_stataktif_norm not in ("obsolete", "batal"):
            if r_id != doc_id:  # Jangan kembalikan diri sendiri
                return {"id": r_id, "judul": r_judul, "noper": r_noper or ""}
            break

        # Cari penerus dari mencabut atau linkper
        next_ids = []
        for field in [r_mencabut, r_linkper]:
            if field:
                for part in str(field).split("|"):
                    part = part.strip()
                    if part.isdigit():
                        next_ids.append(int(part))

        if not next_ids:
            break  # Tidak ada penerus — rantai putus

        current_id = next_ids[0]  # Ambil penerus pertama
        depth += 1

    return None


def _resolve_mencabut_text(mencabut_str: str, linkper_str: str, doc_map: Dict[int, Dict[str, Any]]) -> str:
    """Mengubah ID dokumen pada kolom mencabut/linkper menjadi teks deskriptif lengkap (No SKEP, Judul, Tanggal)."""
    parts = []
    seen = set()
    for s in [mencabut_str, linkper_str]:
        if not s:
            continue
        for item in str(s).split('|'):
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


async def search_and_ocr_by_judul(query_judul: Any) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Mencari metadata peraturan berdasarkan field `judul` di tabel `berita`.
    Berguna saat Call 1 memutuskan butuh pencarian persis berdasarkan judul.
    Sprint 4: LIMIT 3 untuk mendeteksi conflict jika ada beberapa versi.
    
    Returns: context_text, formatted_attachments, list_of_source_metadata
    """
    if not query_judul:
        return "", [], []
        
    query_judul_list = query_judul if isinstance(query_judul, list) else [query_judul]
    query_judul_list = [q for q in query_judul_list if q and q.strip()]
    if not query_judul_list:
        return "", [], []
        
    # Gabungkan semua query untuk pencarian FTS MySQL
    search_terms = " ".join([w for q in query_judul_list for w in q.strip().split() if len(w) > 2])
    
    logger.info(f"[PERATURAN_SERVICE] Searching title in DB: '{search_terms}'")
    
    try:
        async with get_peraturan_db() as conn:
            async with conn.cursor() as cur:
                # ── SPRINT 5: FULL-TEXT SEARCH & GENEALOGY ──
                if not search_terms:
                    return "", [], []
                
                sql = """
                    SELECT b.id_berita, b.noper, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.tanggal, b.stataktif, b.mencabut, b.linkper,
                           1.0 as score,
                           b.tag,
                           SUBSTRING(b.isi_berita, 1, 5000) as isi_snippet
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE b.judul LIKE %s OR b.tag LIKE %s OR b.noper LIKE %s
                    ORDER BY b.tanggal DESC LIMIT 15
                """
                search_pattern = "%" + "%".join(search_terms.strip().split()[:4]) + "%"
                await cur.execute(sql, (search_pattern, search_pattern, search_pattern))
                rows = await cur.fetchall()
                
                if not rows:
                    logger.info(f"[PERATURAN_SERVICE] No matching title found for '{search_terms}', trying individual keywords")
                    words = [w for w in search_terms.split() if len(w) >= 3]
                    if words:
                        first_word = f"%{words[0]}%"
                        await cur.execute(sql, (first_word, first_word, first_word))
                        rows = await cur.fetchall()
                
                if not rows:
                    return "", [], []
                    
                combined_context_text = ""
                all_formatted_attachments = []
                all_source_metadata = []

                loop = asyncio.get_running_loop()
                
                # ── GENEALOGY PARSING ──
                found_ids = {row[0] for row in rows}
                dicabut_oleh = {} # dict of id_berita -> (id_pengganti, judul_pengganti)
                
                for row in rows:
                    curr_id = row[0]
                    curr_judul = row[2]
                    mencabut_str = row[9] or ""
                    linkper_str = row[10] or ""
                    
                    all_replaced = []
                    if mencabut_str:
                        all_replaced.extend([x.strip() for x in mencabut_str.split('|') if x.strip()])
                    if linkper_str:
                        all_replaced.extend([x.strip() for x in linkper_str.split('|') if x.strip()])
                        
                    for rep_id_str in all_replaced:
                        if rep_id_str.isdigit():
                            rep_id = int(rep_id_str)
                            if rep_id in found_ids:
                                dicabut_oleh[rep_id] = (curr_id, curr_judul)
                
                # ── SPRINT 5: SEMANTIC RERANKING ──
                # Rerank 15 dokumen dari MySQL menggunakan AI CrossEncoder berdasarkan kecocokan judul dengan query_judul
                try:
                    from backend.app.services.rag.reranker_service import reranker_service
                    corpus_texts = [row[2] for row in rows]  # Rerank berdasarkan kolom judul
                    
                    # Hitung skor untuk setiap keyword, lalu ambil skor tertinggi
                    best_scores = [0.0] * len(corpus_texts)
                    for q_term in query_judul_list:
                        scores = await reranker_service.compute_scores(q_term, corpus_texts)
                        for i, s in enumerate(scores):
                            if s > best_scores[i]:
                                best_scores[i] = s
                    
                    # Gabungkan rows dengan skor Reranker
                    scored_rows = []
                    for i, r in enumerate(rows):
                        r_list = list(r)
                        r_list[11] = best_scores[i] # Ganti FTS score dengan best Reranker score
                        scored_rows.append((r_list, best_scores[i]))
                    
                    # Urutkan dari yang tertinggi
                    scored_rows.sort(key=lambda x: x[1], reverse=True)
                    
                    # Buang dokumen "sampah" yang skor rerankernya terlalu rendah (misal <= 0.505)
                    # Karena base score Sigmoid BGE sering kali bertengger di 0.5000 jika benar-benar tidak nyambung
                    scored_rows = [x for x in scored_rows if x[1] > 0.505]
                    
                    rows = [r[0] for r in scored_rows]
                except Exception as e:
                    logger.warning(f"[PERATURAN_SERVICE] Semantic Reranking gagal, fallback ke urutan FTS MySQL: {e}")

                parsed_count = 0
                for row in rows:
                    id_berita, noper, judul, gambar, gambar2, gambar3, nama_kategori, tanggal, stataktif, mencabut_str, linkper_str, score, _tag_val, _isi_val = row
                    logger.info(f"[PERATURAN_SERVICE] Found match: '{judul}' (FTS Score/Ranked: {score})")
                    
                    # Coba cari file yang valid dari ketiga kolom
                    valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
                    if not valid_file:
                        logger.warning(f"[PERATURAN_SERVICE] Match found but PDF file not exist in {PERATURAN_DIR}")
                        continue
                    
                    status_berlaku_str = _resolve_status_berlaku(id_berita, stataktif, dicabut_oleh)

                    # ── LINEAGE AWARENESS: Cari regulasi aktif terbaru via forward traversal ──
                    latest_active_info = None
                    if status_berlaku_str != "Berlaku":
                        try:
                            latest_active_info = await _resolve_latest_active_via_cursor(cur, id_berita)
                        except Exception as _la_err:
                            logger.warning(f"[PERATURAN_SERVICE] Lineage resolve failed for {id_berita}: {_la_err}")

                    meta_str = f"ID Dokumen: {id_berita}\nStatus Berlaku: {status_berlaku_str}\nTanggal Terbit: {tanggal}\nNomor Regulasi: {noper}\nMencabut: {mencabut_str if mencabut_str else '-'}\n"
                    if latest_active_info:
                        meta_str += (
                            f"Regulasi Aktif Saat Ini : [{latest_active_info['noper']}] "
                            f"{latest_active_info['judul']} (ID: {latest_active_info['id']})\n"
                            f"\u26a0\ufe0f PERINGATAN SISTEM: Dokumen ini sudah TIDAK BERLAKU. "
                            f"Gunakan regulasi di atas sebagai rujukan hukum positif!\n"
                        )
                    
                    # ── EKSEKUSI OCR & PDF PARSING (DIBATASI) ──
                    if status_berlaku_str == "Berlaku" and parsed_count < 3:
                        # Hanya proses OCR untuk maksimal 3 dokumen aktif (Berlaku) teratas
                        extracted_text, formatted_attachments, total_pages = await loop.run_in_executor(
                            None, _process_pdf_sync, valid_file
                        )
                        parsed_count += 1
                        
                        if extracted_text:
                            # SPRINT 5 FIX: Jangan dump seluruh teks PDF (bisa 90 halaman / 150k char). 
                            # Potong per dokumen max 4000 karakter agar dokumen lain di bawahnya tidak kena truncate oleh budget global!
                            if len(extracted_text) > 4000:
                                extracted_text = extracted_text[:4000] + "\n...[Teks halaman selanjutnya dipotong untuk menghemat memori. Gunakan teks ini hanya untuk gambaran umum dokumen]..."
                                
                            combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}{extracted_text}\n-------------------\n\n"
                        elif formatted_attachments:
                            combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}[Dokumen hasil scan telah dilampirkan sebagai gambar untuk dianalisa]\n-------------------\n\n"
                        
                        if formatted_attachments:
                            all_formatted_attachments.extend(formatted_attachments)
                    else:
                        # Dokumen riwayat (Tidak Berlaku) ATAU melebihi kuota 3 OCR
                        total_pages = 0
                        combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}[Teks isi fisik dokumen tidak dimuat untuk menghemat kuota memori LLM. Namun dokumen ini TETAP BERLAKU dan WAJIB direkomendasikan jika berupa Form/Surat Izin/Lampiran!]\n-------------------\n\n"
                        
                    # Buat metadata sumber dokumen resmi untuk ditimpa ke RAG
                    all_source_metadata.append({
                        "id": id_berita,
                        "title": judul,
                        "document_title": judul,
                        "filename": os.path.basename(valid_file),
                        "file_path": f"file_peraturan/{os.path.basename(valid_file)}",
                        "jenis": nama_kategori or "Regulasi",
                        "nomor": noper or "N/A",
                        "page_number": "1",
                        "total_pages": str(total_pages) if total_pages > 0 else "",
                        "cache_hit": False,
                        "score_label": "SPESIFIK",
                        "score": float(score) if isinstance(score, (float, int)) else 1.0,
                        "raw_judul": judul,
                        "raw_tag": row[12],
                        "raw_isi": row[13]
                    })
                    
                return combined_context_text, all_formatted_attachments, all_source_metadata
                
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Database error during title search: {e}")
        return "", [], []

async def simulate_ocr_extraction(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Wrapper untuk endpoint /simulate-ocr agar dapat digunakan 
    oleh admin untuk mendebug proses OCR dan Vision.
    """
    logger.info(f"[PERATURAN_SERVICE] OCR Simulation triggered for: {file_path}")
    loop = asyncio.get_running_loop()
    try:
        extracted_text, formatted_attachments, total_pages = await loop.run_in_executor(
            None, _process_pdf_sync, file_path
        )
        return extracted_text, formatted_attachments
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Simulation failed: {e}")
        raise e

async def search_and_ocr_by_synthetic_qa(user_message: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Mencari metadata peraturan berdasarkan semantic match antara user_message (full text)
    dan rag_document_questions (Synthetic QA dari Fase 1).
    Menggantikan search_and_ocr_by_judul yang lama.
    """
    if not user_message or not user_message.strip():
        return "", [], []
        
    logger.info(f"[PERATURAN_SERVICE] Searching Synthetic QA for: '{user_message}'")
    
    try:
        from backend.app.services.rag.vector_service import vector_service
        from backend.app.core.database import get_db
        
        # 1. Embed the user's full message
        query_embedding = await vector_service.get_query_embedding(user_message)
        if not query_embedding:
            return "", [], []
            
        # Convert list to string for pgvector: '[0.1, 0.2, ...]'
        embedding_str = str(query_embedding)
            
        # 2. Search pgvector table for top matching source_ids
        async with get_db() as conn_pg:
            pg_sql = """
                SELECT source_id, 1 - (embedding <=> $1::vector) as similarity
                FROM rag_document_questions
                ORDER BY embedding <=> $1::vector
                LIMIT 30
            """
            records = await conn_pg.fetch(pg_sql, embedding_str)
            
        if not records:
            return "", [], []
            
        unique_source_ids = []
        source_scores = {}
        for r in records:
            s_id = r["source_id"]
            if s_id not in source_scores:
                source_scores[s_id] = r["similarity"]
                unique_source_ids.append(s_id)
            if len(unique_source_ids) >= 15:
                break
                
        if not unique_source_ids:
            return "", [], []
            
        # 3. Fetch metadata from MySQL (berita) for these source_ids
        async with get_peraturan_db() as conn_my:
            async with conn_my.cursor() as cur:
                format_strings = ','.join(['%s'] * len(unique_source_ids))
                sql = f"""
                    SELECT b.id_berita, b.noper, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.tanggal, b.stataktif, b.mencabut, b.linkper,
                           1.0 as dummy_score,
                           b.tag,
                           SUBSTRING(b.isi_berita, 1, 5000) as isi_snippet
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE b.id_berita IN ({format_strings})
                """
                await cur.execute(sql, tuple(unique_source_ids))
                raw_rows = await cur.fetchall()
                
                if not raw_rows:
                    return "", [], []
                    
                rows_dict = {row[0]: list(row) for row in raw_rows}
                rows = []
                for s_id in unique_source_ids:
                    if s_id in rows_dict:
                        row_data = rows_dict[s_id]
                        row_data[11] = source_scores[s_id] # Replace score
                        rows.append(tuple(row_data))
                
                # Threshold untuk Cosine Similarity model mxbai-embed-large
                # Nilai 0.75-0.79 biasanya masih nyasar/random. True match ada di > 0.80
                rows = [r for r in rows if r[11] >= 0.80]
                if not rows:
                    return "", [], []
                    
                combined_context_text = ""
                all_formatted_attachments = []
                all_source_metadata = []

                loop = asyncio.get_running_loop()
                
                found_ids = {row[0] for row in rows}
                dicabut_oleh = {}
                
                for row in rows:
                    curr_id = row[0]
                    curr_judul = row[2]
                    mencabut_str = row[9] or ""
                    linkper_str = row[10] or ""
                    
                    all_replaced = []
                    if mencabut_str:
                        all_replaced.extend([x.strip() for x in mencabut_str.split('|') if x.strip()])
                    if linkper_str:
                        all_replaced.extend([x.strip() for x in linkper_str.split('|') if x.strip()])
                        
                    for rep_id_str in all_replaced:
                        if rep_id_str.isdigit():
                            rep_id = int(rep_id_str)
                            if rep_id in found_ids:
                                dicabut_oleh[rep_id] = (curr_id, curr_judul)
                
                parsed_count = 0
                for row in rows:
                    id_berita, noper, judul, gambar, gambar2, gambar3, nama_kategori, tanggal, stataktif, mencabut_str, linkper_str, score, _tag_val, _isi_val = row
                    logger.info(f"[PERATURAN_SERVICE_SYNTHETIC] Found match: '{judul}' (Score: {score:.4f})")
                    
                    valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
                    if not valid_file:
                        continue
                        
                    # total_pages hanya untuk metadata display — tidak perlu buka file (blocking)
                    total_pages = 0
                    
                    status_berlaku_str = _resolve_status_berlaku(id_berita, stataktif, dicabut_oleh)

                    # ── LINEAGE AWARENESS: Cari regulasi aktif terbaru via forward traversal ──
                    latest_active_info = None
                    if status_berlaku_str != "Berlaku":
                        try:
                            latest_active_info = await _resolve_latest_active_via_cursor(cur, id_berita)
                        except Exception as _la_err:
                            logger.warning(f"[PERATURAN_SERVICE_SYNTHETIC] Lineage resolve failed for {id_berita}: {_la_err}")

                    meta_str = f"ID Dokumen: {id_berita}\nStatus Berlaku: {status_berlaku_str}\nTanggal Terbit: {tanggal}\nNomor Regulasi: {noper}\nMencabut: {mencabut_str if mencabut_str else '-'}\n"
                    if latest_active_info:
                        meta_str += (
                            f"Regulasi Aktif Saat Ini : [{latest_active_info['noper']}] "
                            f"{latest_active_info['judul']} (ID: {latest_active_info['id']})\n"
                            f"\u26a0\ufe0f PERINGATAN SISTEM: Dokumen ini sudah TIDAK BERLAKU. "
                            f"Gunakan regulasi di atas sebagai rujukan hukum positif!\n"
                        )
                    
                    if status_berlaku_str == "Berlaku" and parsed_count < 3:
                        extracted_text, formatted_attachments, _ = await loop.run_in_executor(
                            None, _process_pdf_sync, valid_file
                        )
                        parsed_count += 1
                        
                        if extracted_text:
                            if len(extracted_text) > 4000:
                                extracted_text = extracted_text[:4000] + "\n...[Teks halaman selanjutnya dipotong untuk menghemat memori. Gunakan teks ini hanya untuk gambaran umum dokumen]..."
                                
                            combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}{extracted_text}\n-------------------\n\n"
                        elif formatted_attachments:
                            combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}[Dokumen hasil scan telah dilampirkan sebagai gambar untuk dianalisa]\n-------------------\n\n"
                        
                        if formatted_attachments:
                            all_formatted_attachments.extend(formatted_attachments)
                    else:
                        combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}[Teks isi fisik dokumen tidak dimuat untuk menghemat kuota memori LLM. Namun dokumen ini TETAP BERLAKU dan WAJIB direkomendasikan jika berupa Form/Surat Izin/Lampiran!]\n-------------------\n\n"
                        
                    all_source_metadata.append({
                        "id": id_berita,
                        "title": judul,
                        "document_title": judul,
                        "filename": os.path.basename(valid_file),
                        "file_path": f"file_peraturan/{os.path.basename(valid_file)}",
                        "jenis": nama_kategori or "Regulasi",
                        "nomor": noper or "N/A",
                        "page_number": "1",
                        "total_pages": str(total_pages) if total_pages > 0 else "",
                        "cache_hit": False,
                        "score_label": "SYNTHETIC_QA",
                        "score": float(score) if isinstance(score, (float, int)) else 1.0,
                        "raw_judul": judul,
                        "raw_tag": _tag_val,
                        "raw_isi": _isi_val
                    })
                    
                return combined_context_text, all_formatted_attachments, all_source_metadata
                
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE_SYNTHETIC] Error during Synthetic QA search: {e}")
        return "", [], []

async def get_candidate_documents_metadata(
    user_message: str, 
    query_judul_list: List[str], 
    rag_queries: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Mengambil daftar dokumen kandidat terbaik dari MySQL (Lexical Wadah) & pgvector (Semantic Isi) yang lolos scoring BGE.
    Mengembalikan metadata lengkap dan path valid_file untuk diproses secara progresif.
    """
    if not user_message or not user_message.strip():
        return []
        
    try:
        from backend.app.services.rag.vector_service import vector_service
        from backend.app.core.database import get_db
        from backend.app.services.rag.reranker_service import reranker_service
        
        candidate_ids = set()
        
        # 0. Tentukan semantic query murni (substansi isi/pertanyaan)
        # Jika rag_queries tersedia dari Call 1, gunakan rag_queries karena merepresentasikan substansi isi tanpa noise
        clean_semantic_queries = [q.strip() for q in (rag_queries or []) if q and q.strip()]
        semantic_search_query = " ".join(clean_semantic_queries) if clean_semantic_queries else user_message
        
        # 1. Fetch from pgvector Semantic QA (Menggunakan semantic_search_query murni)
        query_embedding = await vector_service.get_query_embedding(semantic_search_query)
        if query_embedding:
            embedding_str = str(query_embedding)
            async with get_db() as conn_pg:
                pg_sql = """
                    SELECT source_id, 1 - (embedding <=> $1::vector) as similarity
                    FROM rag_document_questions
                    ORDER BY embedding <=> $1::vector
                    LIMIT 20
                """
                records = await conn_pg.fetch(pg_sql, embedding_str)
                for r in records:
                    candidate_ids.add(r["source_id"])
                    
        # 2. Fetch from MySQL (Opsi C: Full-phrase match priority sebelum per-kata)
        import re
        
        # ── STEP 2A: Full-phrase match dari query_judul_list (digabung sebagai satu frasa judul) ──
        # Ini mencegah mismatch urutan kata saat per-kata di-split dan dicocokkan dengan LIKE %a%b%c%
        # Contoh: ["PT Pindad", "Persero", "Organisasi"] → gabung jadi "Organisasi dan Tata Kerja PT Pindad Persero"
        # dan lakukan fuzzy phrase match langsung ke judul DB.
        if query_judul_list:
            async with get_peraturan_db() as conn_my:
                async with conn_my.cursor() as cur:
                    for q in query_judul_list:
                        if not q or not isinstance(q, str) or not q.strip():
                            continue
                        words_q = [w for w in re.findall(r'\b\w{2,}\b', q.lower()) if w not in {"yang", "dan", "atau", "untuk", "dari", "pada", "dalam", "dengan", "ke", "di", "ini", "itu", "persero", "pt"}]
                        if not words_q:
                            continue
                        
                        # Coba berbagai kombinasi urutan untuk mengatasi order mismatch:
                        # Kombinasi 1: urutan asli 4 kata pertama
                        phrase_like_fwd = f"%{'%'.join(words_q[:4])}%"
                        await cur.execute("SELECT id_berita FROM berita WHERE judul LIKE %s OR tag LIKE %s LIMIT 15", (phrase_like_fwd, phrase_like_fwd))
                        for row in await cur.fetchall():
                            candidate_ids.add(row[0])
                        
                        # Kombinasi 2: reverse order (untuk mengatasi kasus judul DB urutannya berbeda)
                        phrase_like_rev = f"%{'%'.join(words_q[:4][::-1])}%"
                        await cur.execute("SELECT id_berita FROM berita WHERE judul LIKE %s OR tag LIKE %s LIMIT 15", (phrase_like_rev, phrase_like_rev))
                        for row in await cur.fetchall():
                            candidate_ids.add(row[0])
                        
                        # Per-kata individual sebagai fallback coverage
                        for w in words_q:
                            if len(w) >= 3:
                                w_like = f"%{w}%"
                                await cur.execute("SELECT id_berita FROM berita WHERE judul LIKE %s OR tag LIKE %s OR noper LIKE %s LIMIT 10", (w_like, w_like, w_like))
                                for row in await cur.fetchall():
                                    candidate_ids.add(row[0])
        
        # ── STEP 2B: Fallback dari rag_queries dan user_message ──
        search_terms_set = set()
        if rag_queries:
            for q in rag_queries:
                if q and isinstance(q, str) and q.strip():
                    search_terms_set.add(q.strip())
        if user_message and user_message.strip():
            search_terms_set.add(user_message.strip())

        async with get_peraturan_db() as conn_my:
            async with conn_my.cursor() as cur:
                for term in search_terms_set:
                    words = [w for w in re.findall(r'\b\w{2,}\b', term.lower()) if w not in {"yang", "dan", "atau", "untuk", "dari", "pada", "dalam", "dengan", "ke", "di", "ini", "itu"}]
                    if not words: 
                        continue
                    
                    # Contiguous multi-word match
                    phrase_like = f"%{'%'.join(words[:4])}%"
                    await cur.execute("SELECT id_berita FROM berita WHERE judul LIKE %s OR tag LIKE %s LIMIT 15", (phrase_like, phrase_like))
                    for row in await cur.fetchall():
                        candidate_ids.add(row[0])
                    
                    # Individual keywords match
                    for w in words:
                        if len(w) >= 3:
                            w_like = f"%{w}%"
                            await cur.execute("SELECT id_berita FROM berita WHERE judul LIKE %s OR tag LIKE %s OR noper LIKE %s LIMIT 10", (w_like, w_like, w_like))
                            for row in await cur.fetchall():
                                candidate_ids.add(row[0])
                                
        if not candidate_ids:
            return []
            
        async with get_peraturan_db() as conn_my:
            async with conn_my.cursor() as cur:
                format_strings = ','.join(['%s'] * len(candidate_ids))
                sql = f"""
                    SELECT b.id_berita, b.noper, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori,
                           COALESCE(NULLIF(b.tanggal, '0000-00-00'), NULLIF(b.tgl_tetap, '0000-00-00'), NULLIF(b.tgl_edit, '0000-00-00'), NULLIF(b.tgl_obs, '0000-00-00')) as tanggal,
                           b.stataktif, b.mencabut, b.linkper,
                           1.0 as dummy_score,
                           b.tag,
                           SUBSTRING(b.isi_berita, 1, 5000) as isi_snippet,
                           b.tgl_obs,
                           b.tgl_tetap
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE b.id_berita IN ({format_strings})
                """
                await cur.execute(sql, tuple(candidate_ids))
                raw_rows = await cur.fetchall()
                
        if not raw_rows:
            return []
            
        # ── GENEALOGY EXPANSION: Telusuri seluruh mata rantai mencabut/linkper ─────────
        # Otomatis tarik dokumen yang direferensikan dalam mencabut / linkper (hingga 3 hop)
        # sehingga riwayat regulasi masa lalu lengkap (judul, noper, tanggal, dll).
        fetched_ids = set(candidate_ids)
        current_rows = list(raw_rows)
        
        for _hop in range(3):
            needed_ids = set()
            for r in current_rows:
                m_str = r[9] or ""
                l_str = r[10] or ""
                for s in [m_str, l_str]:
                    for item in str(s).split('|'):
                        item = item.strip()
                        if item.isdigit():
                            ref_id = int(item)
                            if ref_id not in fetched_ids:
                                needed_ids.add(ref_id)
            if not needed_ids:
                break
                
            async with get_peraturan_db() as conn_my:
                async with conn_my.cursor() as cur:
                    fmt = ','.join(['%s'] * len(needed_ids))
                    sql_ref = f"""
                        SELECT b.id_berita, b.noper, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori,
                               COALESCE(NULLIF(b.tanggal, '0000-00-00'), NULLIF(b.tgl_tetap, '0000-00-00'), NULLIF(b.tgl_edit, '0000-00-00'), NULLIF(b.tgl_obs, '0000-00-00')) as tanggal,
                               b.stataktif, b.mencabut, b.linkper,
                               0.35 as dummy_score,
                               b.tag,
                               SUBSTRING(b.isi_berita, 1, 5000) as isi_snippet,
                               b.tgl_obs,
                               b.tgl_tetap
                        FROM berita b
                        LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                        WHERE b.id_berita IN ({fmt})
                    """
                    await cur.execute(sql_ref, tuple(needed_ids))
                    ref_rows = await cur.fetchall()
                    for ref_r in ref_rows:
                        current_rows.append(ref_r)
                        fetched_ids.add(ref_r[0])
                        
        all_rows = [list(r) for r in current_rows]
        
        # Peta dokumen lengkap untuk resolusi teks silsilah
        doc_map = {
            r[0]: {
                "noper": r[1] or "",
                "judul": r[2] or "",
                "tanggal": str(r[7] or "")
            }
            for r in all_rows
        }
        
        # ── PRE-SPLIT: Primary (Aktif + Top 30 Terkini) vs Supplementary (Sisanya) ──
        # Dokumen Aktif/Berlaku (stataktif kosong/null/aktif) SELALU masuk Primary berapapun tahunnya!
        # Dokumen Obsolete/Batal diurutkan berdasarkan tanggal terbaru untuk mengisi sisa kuota 30.
        active_rows = []
        inactive_rows = []
        for r in all_rows:
            stat_val = str(r[8] or "").strip().lower()
            if stat_val in ("obsolete", "batal"):
                inactive_rows.append(r)
            else:
                active_rows.append(r)
                
        # Urutkan inactive_rows by effective tanggal DESC
        inactive_rows.sort(key=lambda x: str(x[7] or ""), reverse=True)
        
        primary_quota = 30
        remaining_slots = max(0, primary_quota - len(active_rows))
        primary_inactive = inactive_rows[:remaining_slots]
        supplementary_inactive = inactive_rows[remaining_slots:]
        
        primary_rows = active_rows + primary_inactive
        
        # Scoring awal judul/tag kandidat Primary via BGE CrossEncoder
        corpus_texts = [f"{r[2]} - Tag: {r[12]}" for r in primary_rows]
        
        long_judul_phrases = [q.strip() for q in (query_judul_list or []) if q and len(q.strip().split()) > 3]
        if long_judul_phrases:
            effective_rerank_query = " ".join(long_judul_phrases[:2]).strip()
            logger.info(f"[PERATURAN_SERVICE_CANDIDATES] Rerank query: long_judul_phrases = '{effective_rerank_query}'")
        elif semantic_search_query.strip():
            effective_rerank_query = semantic_search_query.strip()
            logger.info(f"[PERATURAN_SERVICE_CANDIDATES] Rerank query: semantic_search_query = '{effective_rerank_query}'")
        else:
            effective_rerank_query = user_message.strip()
            logger.info(f"[PERATURAN_SERVICE_CANDIDATES] Rerank query: user_message fallback = '{effective_rerank_query}'")
            
        scores = await reranker_service.compute_scores(effective_rerank_query, corpus_texts)
        
        # ── PRE-SCORING: Genealogy Resolution ─────────────────────────────────────────
        pre_found_ids = {r[0] for r in all_rows}
        pre_dicabut_oleh: Dict[int, Any] = {}
        for r in all_rows:
            curr_id = r[0]
            curr_judul = r[2]
            mencabut_str_pre = r[9] or ""
            linkper_str_pre = r[10] or ""
            all_replaced_pre = []
            if mencabut_str_pre:
                all_replaced_pre.extend([x.strip() for x in mencabut_str_pre.split('|') if x.strip()])
            if linkper_str_pre:
                all_replaced_pre.extend([x.strip() for x in linkper_str_pre.split('|') if x.strip()])
            for rep_id_str in all_replaced_pre:
                if rep_id_str.isdigit():
                    rep_id = int(rep_id_str)
                    if rep_id in pre_found_ids:
                        pre_dicabut_oleh[rep_id] = (curr_id, curr_judul)
        
        # ── TARGET DOCUMENT MATCH BOOST: PKB/SOP/SKEP type match ─────────────────────
        explicit_primary_types = set()
        user_lower = user_message.lower()
        for kw in ["pkb", "perjanjian kerja bersama", "sop", "skep", "surat keputusan", "surat edaran", "instruksi kerja"]:
            if kw in user_lower or any(kw in str(q).lower() for q in (query_judul_list or [])):
                explicit_primary_types.add(kw)
        
        general_target_tokens = set()
        for q in (query_judul_list or []):
            if q and len(q.strip()) >= 3:
                q_clean = q.strip().lower()
                if q_clean not in explicit_primary_types:
                    general_target_tokens.add(q_clean)

        # ── RECENCY BOOST: Tahun lebih baru = boost lebih besar ───────────────────────
        import datetime
        current_year = datetime.datetime.now().year
        
        def _recency_boost(tanggal_val: Any) -> float:
            """Hitung recency boost berdasarkan tahun terbit. Max +0.30 untuk tahun ini."""
            try:
                if tanggal_val is None:
                    return 0.0
                tanggal_str = str(tanggal_val).strip()
                if not tanggal_str or tanggal_str in ("0000-00-00", "None"):
                    return 0.0
                year = int(tanggal_str[:4])
                age = current_year - year
                if age <= 0:
                    return 0.30
                elif age == 1:
                    return 0.20
                elif age == 2:
                    return 0.10
                elif age == 3:
                    return 0.05
                else:
                    return 0.0
            except (ValueError, TypeError):
                return 0.0

        scored_primary_rows = []
        for i, r in enumerate(primary_rows):
            doc_id = r[0]
            doc_title_lower = str(r[2] or "").lower()
            doc_noper_lower = str(r[1] or "").lower()
            doc_tag_lower = str(r[12] or "").lower()
            doc_stataktif = str(r[8] or "").lower()
            doc_tanggal = r[7]
            
            base_score = float(scores[i])
            
            # Resolve status berlaku untuk scoring
            status_berlaku_str_pre = _resolve_status_berlaku(doc_id, r[8], pre_dicabut_oleh)
            is_berlaku = (status_berlaku_str_pre == "Berlaku")
            
            boost = 0.0
            
            # 1. STATUS BERLAKU BOOST: +0.50 jika masih aktif berlaku (PRIORITAS TERTINGGI)
            if is_berlaku:
                boost += 0.50
            elif doc_stataktif in ["obsolete", "batal"] or "tidak berlaku" in status_berlaku_str_pre.lower() or "dicabut" in status_berlaku_str_pre.lower():
                boost -= 0.10  # Penalti ringan dokumen sudah dicabut/obsolete
            
            # 2. RECENCY BOOST: Dokumen lebih baru naik peringkat (max +0.30)
            boost += _recency_boost(doc_tanggal)
            
            # 3. DOCUMENT TYPE MATCH BOOST: PKB/SOP/SKEP match (+0.45), topik umum (+0.20)
            has_primary_match = any(t in doc_title_lower or t in doc_noper_lower or t in doc_tag_lower for t in explicit_primary_types)
            has_general_match = any(t in doc_title_lower or t in doc_noper_lower or t in doc_tag_lower for t in general_target_tokens)
            
            if has_primary_match:
                boost += 0.45
            elif has_general_match:
                boost += 0.20
                
            final_score = base_score + boost
            r[11] = final_score
            scored_primary_rows.append(r)
            
        scored_primary_rows.sort(key=lambda x: x[11], reverse=True)
        scored_primary_rows = [x for x in scored_primary_rows if x[11] > 0.40]
        
        # ── GENEALOGY FINAL: Re-resolve dengan seluruh candidate ──────────────────────
        all_candidate_rows = scored_primary_rows + supplementary_inactive
        if not all_candidate_rows:
            return []
            
        found_ids = {row[0] for row in all_candidate_rows}
        dicabut_oleh = {}
        for row in all_candidate_rows:
            curr_id = row[0]
            curr_judul = row[2]
            mencabut_str = row[9] or ""
            linkper_str = row[10] or ""
            all_replaced = []
            if mencabut_str:
                all_replaced.extend([x.strip() for x in mencabut_str.split('|') if x.strip()])
            if linkper_str:
                all_replaced.extend([x.strip() for x in linkper_str.split('|') if x.strip()])
            for rep_id_str in all_replaced:
                if rep_id_str.isdigit():
                    rep_id = int(rep_id_str)
                    if rep_id in found_ids:
                        dicabut_oleh[rep_id] = (curr_id, curr_judul)
                        
        candidate_docs = []
        
        # ── LINEAGE AWARENESS: Buka satu koneksi untuk semua forward traversal ──
        async with get_peraturan_db() as _lineage_conn:
            async with _lineage_conn.cursor() as _lineage_cur:

                # 1. Masukkan Primary Candidates (sudah di-score)
                for row in scored_primary_rows:
                    id_berita, noper, judul, gambar, gambar2, gambar3, nama_kategori, tanggal, stataktif, mencabut_str, linkper_str, score, _tag_val, _isi_val, tgl_obs_val, tgl_tetap_val = row
                    valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
                    status_berlaku_str = _resolve_status_berlaku(id_berita, stataktif, dicabut_oleh)
                    mencabut_display = _resolve_mencabut_text(mencabut_str, linkper_str, doc_map)

                    latest_active_info = None
                    if status_berlaku_str != "Berlaku":
                        try:
                            latest_active_info = await _resolve_latest_active_via_cursor(_lineage_cur, id_berita)
                        except Exception as _la_err:
                            logger.warning(f"[PERATURAN_SERVICE_CANDIDATES] Lineage resolve failed for {id_berita}: {_la_err}")

                    tgl_clean = str(tanggal) if tanggal and str(tanggal) not in ('0000-00-00', 'None') else ""
                    obs_clean = str(tgl_obs_val) if tgl_obs_val and str(tgl_obs_val) not in ('0000-00-00', 'None') else ""
                    tetap_clean = str(tgl_tetap_val) if tgl_tetap_val and str(tgl_tetap_val) not in ('0000-00-00', 'None') else ""

                    candidate_docs.append({
                        "id": id_berita,
                        "id_berita": id_berita,
                        "judul": judul,
                        "title": judul,
                        "document_title": judul,
                        "noper": noper or "N/A",
                        "nomor": noper or "N/A",
                        "tanggal": tgl_clean,
                        "tgl_obs": obs_clean,
                        "tgl_tetap": tetap_clean,
                        "stataktif": stataktif,
                        "status_berlaku": status_berlaku_str,
                        "mencabut": mencabut_display,
                        "score": float(score),
                        "jenis": nama_kategori or "Regulasi",
                        "valid_file": valid_file,
                        "filename": os.path.basename(valid_file) if valid_file else None,
                        "file_path": f"file_peraturan/{os.path.basename(valid_file)}" if valid_file else None,
                        "raw_tag": _tag_val,
                        "raw_isi": _isi_val,
                        "is_supplementary": False,
                        "latest_active": latest_active_info,
                    })

                # 2. Masukkan Supplementary Candidates (metadata ringkas saja untuk referensi)
                for row in supplementary_inactive:
                    id_berita, noper, judul, gambar, gambar2, gambar3, nama_kategori, tanggal, stataktif, mencabut_str, linkper_str, _score, _tag_val, _isi_val, tgl_obs_val, tgl_tetap_val = row
                    valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
                    status_berlaku_str = _resolve_status_berlaku(id_berita, stataktif, dicabut_oleh)
                    mencabut_display = _resolve_mencabut_text(mencabut_str, linkper_str, doc_map)

                    latest_active_info = None
                    if status_berlaku_str != "Berlaku":
                        try:
                            latest_active_info = await _resolve_latest_active_via_cursor(_lineage_cur, id_berita)
                        except Exception as _la_err:
                            logger.warning(f"[PERATURAN_SERVICE_CANDIDATES] Lineage resolve failed (supp) for {id_berita}: {_la_err}")

                    tgl_clean = str(tanggal) if tanggal and str(tanggal) not in ('0000-00-00', 'None') else ""
                    obs_clean = str(tgl_obs_val) if tgl_obs_val and str(tgl_obs_val) not in ('0000-00-00', 'None') else ""
                    tetap_clean = str(tgl_tetap_val) if tgl_tetap_val and str(tgl_tetap_val) not in ('0000-00-00', 'None') else ""

                    candidate_docs.append({
                        "id": id_berita,
                        "id_berita": id_berita,
                        "judul": judul,
                        "title": judul,
                        "document_title": judul,
                        "noper": noper or "N/A",
                        "nomor": noper or "N/A",
                        "tanggal": tgl_clean,
                        "tgl_obs": obs_clean,
                        "tgl_tetap": tetap_clean,
                        "stataktif": stataktif,
                        "status_berlaku": status_berlaku_str,
                        "mencabut": mencabut_display,
                        "score": 0.35,
                        "jenis": nama_kategori or "Regulasi",
                        "valid_file": valid_file,
                        "filename": os.path.basename(valid_file) if valid_file else None,
                        "file_path": f"file_peraturan/{os.path.basename(valid_file)}" if valid_file else None,
                        "raw_tag": _tag_val,
                        "raw_isi": _isi_val,
                        "is_supplementary": True,
                        "latest_active": latest_active_info,
                    })
            
        logger.info(
            f"[PERATURAN_SERVICE_CANDIDATES] Final ranking (Primary: {len(scored_primary_rows)}, Supplementary: {len(supplementary_inactive)}):\n" +
            "\n".join([f"  Rank #{i+1}: [{d['status_berlaku']}] {d['tanggal'][:4] if d['tanggal'] else '????'} | score={d['score']:.3f} | supp={d['is_supplementary']} | {d['judul'][:55]}" for i, d in enumerate(candidate_docs[:10])])
        )
            
        return candidate_docs
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE_CANDIDATES] Error fetching candidates: {e}")
        return []



async def hybrid_document_search(user_message: str, query_judul_list: List[str]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fase 3: Late Fusion Reranking.
    Menggabungkan kandidat dari FTS MySQL & pgvector Synthetic QA, 
    Lalu di-Rerank secara serentak menggunakan BGE CrossEncoder.
    """
    if not user_message or not user_message.strip():
        return "", [], []
        
    logger.info(f"[PERATURAN_SERVICE_HYBRID] Starting Late Fusion for: '{user_message}'")
    
    try:
        from backend.app.services.rag.vector_service import vector_service
        from backend.app.core.database import get_db
        
        candidate_ids = set()
        
        # 1. Fetch from pgvector Semantic QA
        query_embedding = await vector_service.get_query_embedding(user_message)
        if query_embedding:
            embedding_str = str(query_embedding)
            async with get_db() as conn_pg:
                pg_sql = """
                    SELECT source_id, 1 - (embedding <=> $1::vector) as similarity
                    FROM rag_document_questions
                    ORDER BY embedding <=> $1::vector
                    LIMIT 20
                """
                records = await conn_pg.fetch(pg_sql, embedding_str)
                for r in records:
                    candidate_ids.add(r["source_id"])
                    
        # 2. Fetch from MySQL FTS
        if query_judul_list:
            async with get_peraturan_db() as conn_my:
                async with conn_my.cursor() as cur:
                    for query_judul in query_judul_list:
                        safe_judul = "".join([c for c in query_judul[:200] if c.isalnum() or c.isspace()]).strip()
                        words = [w for w in safe_judul.split() if len(w) > 2]
                        if not words: continue
                        
                        phrase_like = f"%{'%'.join(words[:4])}%"
                        await cur.execute("SELECT id_berita FROM berita WHERE judul LIKE %s OR tag LIKE %s LIMIT 15", (phrase_like, phrase_like))
                        for row in await cur.fetchall():
                            candidate_ids.add(row[0])
                            
                        for w in words:
                            if len(w) >= 3:
                                w_like = f"%{w}%"
                                await cur.execute("SELECT id_berita FROM berita WHERE judul LIKE %s OR tag LIKE %s OR noper LIKE %s LIMIT 10", (w_like, w_like, w_like))
                                for row in await cur.fetchall():
                                    candidate_ids.add(row[0])
                            
        if not candidate_ids:
            logger.info("[PERATURAN_SERVICE_HYBRID] No candidates found from any path.")
            return "", [], []
            
        logger.info(f"[PERATURAN_SERVICE_HYBRID] Pooled {len(candidate_ids)} unique candidates. Fetching metadata...")
        
        # 3. Fetch metadata for all candidates
        async with get_peraturan_db() as conn_my:
            async with conn_my.cursor() as cur:
                format_strings = ','.join(['%s'] * len(candidate_ids))
                sql = f"""
                    SELECT b.id_berita, b.noper, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.tanggal, b.stataktif, b.mencabut, b.linkper,
                           1.0 as dummy_score,
                           b.tag,
                           SUBSTRING(b.isi_berita, 1, 5000) as isi_snippet
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE b.id_berita IN ({format_strings})
                """
                await cur.execute(sql, tuple(candidate_ids))
                raw_rows = await cur.fetchall()
                
        if not raw_rows:
            return "", [], []
            
        rows = [list(r) for r in raw_rows]
        
        # 4. Rerank candidates using BGE CrossEncoder
        from backend.app.services.rag.reranker_service import reranker_service
        # Corpus text for reranker: Judul + Tag
        corpus_texts = [f"{r[2]} - Tag: {r[12]}" for r in rows]
        
        scores = await reranker_service.compute_scores(user_message, corpus_texts)
        
        scored_rows = []
        for i, r in enumerate(rows):
            r[11] = float(scores[i])
            scored_rows.append(r)
            
        # Urutkan dan Filter (BGE Sigmoid > 0.45 = Relevant)
        scored_rows.sort(key=lambda x: x[11], reverse=True)
        scored_rows = [x for x in scored_rows if x[11] > 0.45]
        
        if not scored_rows:
            logger.info("[PERATURAN_SERVICE_HYBRID] All candidates dropped by Reranker (Score <= 0.45).")
            return "", [], []
            
        logger.info(f"[PERATURAN_SERVICE_HYBRID] {len(scored_rows)} candidates passed Reranker.")
        
        # 5. Eksekusi OCR dan Pengolahan Silsilah Dokumen
        combined_context_text = ""
        all_formatted_attachments = []
        all_source_metadata = []

        loop = asyncio.get_running_loop()
        
        found_ids = {row[0] for row in scored_rows}
        dicabut_oleh = {}
        
        for row in scored_rows:
            curr_id = row[0]
            curr_judul = row[2]
            mencabut_str = row[9] or ""
            linkper_str = row[10] or ""
            
            all_replaced = []
            if mencabut_str:
                all_replaced.extend([x.strip() for x in mencabut_str.split('|') if x.strip()])
            if linkper_str:
                all_replaced.extend([x.strip() for x in linkper_str.split('|') if x.strip()])
                
            for rep_id_str in all_replaced:
                if rep_id_str.isdigit():
                    rep_id = int(rep_id_str)
                    if rep_id in found_ids:
                        dicabut_oleh[rep_id] = (curr_id, curr_judul)
        
        parsed_count = 0
        for row in scored_rows:
            id_berita, noper, judul, gambar, gambar2, gambar3, nama_kategori, tanggal, stataktif, mencabut_str, linkper_str, score, _tag_val, _isi_val = row
            logger.info(f"[PERATURAN_SERVICE_HYBRID] Selected Top Match: '{judul}' (BGE Score: {score:.4f})")
            
            valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
            if not valid_file:
                logger.warning(f"[PERATURAN_SERVICE_HYBRID] PDF not exist in {PERATURAN_DIR}")
                continue
                
            # total_pages hanya untuk metadata display — tidak perlu buka file (blocking)
            total_pages = 0

            status_berlaku_str = _resolve_status_berlaku(id_berita, stataktif, dicabut_oleh)

            # ── LINEAGE AWARENESS: Buka cursor sementara untuk forward traversal ──
            latest_active_info = None
            if status_berlaku_str != "Berlaku":
                try:
                    async with get_peraturan_db() as _hyb_conn:
                        async with _hyb_conn.cursor() as _hyb_cur:
                            latest_active_info = await _resolve_latest_active_via_cursor(_hyb_cur, id_berita)
                except Exception as _la_err:
                    logger.warning(f"[PERATURAN_SERVICE_HYBRID] Lineage resolve failed for {id_berita}: {_la_err}")

            meta_str = f"ID Dokumen: {id_berita}\nStatus Berlaku: {status_berlaku_str}\nTanggal Terbit: {tanggal}\nNomor Regulasi: {noper}\nMencabut: {mencabut_str if mencabut_str else '-'}\n"
            if latest_active_info:
                meta_str += (
                    f"Regulasi Aktif Saat Ini : [{latest_active_info['noper']}] "
                    f"{latest_active_info['judul']} (ID: {latest_active_info['id']})\n"
                    f"\u26a0\ufe0f PERINGATAN SISTEM: Dokumen ini sudah TIDAK BERLAKU. "
                    f"Gunakan regulasi di atas sebagai rujukan hukum positif!\n"
                )
            
            if status_berlaku_str == "Berlaku" and parsed_count < 3:
                extracted_text, formatted_attachments, _ = await loop.run_in_executor(
                    None, _process_pdf_sync, valid_file
                )
                parsed_count += 1
                
                if extracted_text:
                    if len(extracted_text) > 4000:
                        extracted_text = extracted_text[:4000] + "\n...[Teks halaman selanjutnya dipotong untuk menghemat memori. Gunakan teks ini hanya untuk gambaran umum dokumen]..."
                        
                    combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}{extracted_text}\n-------------------\n\n"
                elif formatted_attachments:
                    combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}[Dokumen hasil scan telah dilampirkan sebagai gambar untuk dianalisa]\n-------------------\n\n"
                    all_formatted_attachments.extend(formatted_attachments[:1])
            else:
                combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{meta_str}[Teks isi fisik dokumen tidak dimuat untuk menghemat kuota memori LLM. Namun dokumen ini TETAP BERLAKU dan WAJIB direkomendasikan jika berupa Form/Surat Izin/Lampiran!]\n-------------------\n\n"
                
            all_source_metadata.append({
                "id": id_berita,
                "title": judul,
                "document_title": judul,
                "filename": os.path.basename(valid_file),
                "file_path": f"file_peraturan/{os.path.basename(valid_file)}",
                "jenis": nama_kategori or "Regulasi",
                "nomor": noper or "N/A",
                "page_number": "1",
                "total_pages": str(total_pages) if total_pages > 0 else "",
                "cache_hit": False,
                "score_label": "HYBRID_RERANKER",
                "score": score,
                "raw_judul": judul,
                "raw_tag": _tag_val,
                "raw_isi": _isi_val
            })
            
        return combined_context_text, all_formatted_attachments, all_source_metadata
        
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE_HYBRID] Error during Hybrid Search: {e}")
        return "", [], []
