import os
import json
import base64
import logging
import asyncio
from typing import Tuple, List, Dict, Any, Optional

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
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Tingkatkan DPI ke 300 agar model Vision bisa membaca garis form/tabel dengan presisi tinggi
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            encoded = base64.b64encode(img_data).decode("utf-8")
            formatted_attachments.append({"base64": encoded, "type": "image"})
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Failed to convert PDF to image: {e}")
        
    return "", formatted_attachments, total_pages


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
                           MATCH(b.judul, b.isi_berita, b.tag) AGAINST (%s IN NATURAL LANGUAGE MODE) as score,
                           b.tag,
                           SUBSTRING(b.isi_berita, 1, 5000) as isi_snippet
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE MATCH(b.judul, b.isi_berita, b.tag) AGAINST (%s IN NATURAL LANGUAGE MODE)
                    ORDER BY score DESC, b.tanggal DESC LIMIT 15
                """
                await cur.execute(sql, (search_terms, search_terms))
                rows = await cur.fetchall()
                
                if not rows:
                    logger.info(f"[PERATURAN_SERVICE] No matching title found via FTS for '{search_terms}', falling back to LIKE")
                    fallback_sql = """
                        SELECT b.id_berita, b.noper, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.tanggal, b.stataktif, b.mencabut, b.linkper,
                               1.0 as score,
                               b.tag,
                               SUBSTRING(b.isi_berita, 1, 5000) as isi_snippet
                        FROM berita b
                        LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                        WHERE b.judul LIKE %s ORDER BY b.tanggal DESC LIMIT 15
                    """
                    search_pattern = "%" + "%".join(search_terms.strip().split()) + "%"
                    await cur.execute(fallback_sql, (search_pattern,))
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
                    valid_file = None
                    for file_name in [gambar, gambar2, gambar3]:
                        if file_name and isinstance(file_name, str) and file_name.lower().endswith(".pdf"):
                            abs_path = os.path.join(PERATURAN_DIR, file_name)
                            if os.path.exists(abs_path):
                                valid_file = abs_path
                                break
                                
                    if not valid_file:
                        logger.warning(f"[PERATURAN_SERVICE] Match found but PDF file not exist in {PERATURAN_DIR}")
                        continue
                    
                    # ── TENTUKAN STATUS BERLAKU LEBIH DULU (SILSILAH) ──
                    if id_berita in dicabut_oleh:
                        pengganti_judul = dicabut_oleh[id_berita][1]
                        status_berlaku_str = f"Tidak Berlaku (Digantikan oleh: {pengganti_judul})"
                    else:
                        status_berlaku_str = "Berlaku"
                        if stataktif == "batal":
                            status_berlaku_str = "Dicabut"
                        elif stataktif == "obsolete":
                            status_berlaku_str = "Tidak Berlaku"

                    meta_str = f"ID Dokumen: {id_berita}\nStatus Berlaku: {status_berlaku_str}\nTanggal Terbit: {tanggal}\nNomor Regulasi: {noper}\nMencabut: {mencabut_str if mencabut_str else '-'}\n"
                    
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
