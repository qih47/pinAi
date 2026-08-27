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
                    valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
                    if not valid_file:
                        logger.warning(f"[PERATURAN_SERVICE] Match found but PDF file not exist in {PERATURAN_DIR}")
                        continue
                    
                    status_berlaku_str = _resolve_status_berlaku(id_berita, stataktif, dicabut_oleh)

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

                    meta_str = f"ID Dokumen: {id_berita}\nStatus Berlaku: {status_berlaku_str}\nTanggal Terbit: {tanggal}\nNomor Regulasi: {noper}\nMencabut: {mencabut_str if mencabut_str else '-'}\n"
                    
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
                    
        # 2. Fetch from MySQL FTS (Menggunakan query_judul_list untuk filter wadah/judul regulasi)
        if query_judul_list:
            async with get_peraturan_db() as conn_my:
                async with conn_my.cursor() as cur:
                    for query_judul in query_judul_list:
                        safe_judul = "".join([c for c in query_judul[:200] if c.isalnum() or c.isspace()]).strip()
                        words = [w for w in safe_judul.split() if len(w) > 2]
                        if not words: continue
                        
                        match_str = " ".join(words)
                        sql_fts = f"""
                            SELECT id_berita
                            FROM berita 
                            WHERE MATCH(judul, tag, isi_berita) AGAINST (%s IN NATURAL LANGUAGE MODE)
                            ORDER BY MATCH(judul, tag, isi_berita) AGAINST (%s IN NATURAL LANGUAGE MODE) DESC
                            LIMIT 10
                        """
                        await cur.execute(sql_fts, (match_str, match_str))
                        rows = await cur.fetchall()
                        for row in rows:
                            candidate_ids.add(row[0])
                            
                        if len(words) == 1 and len(words[0]) <= 5:
                            like_str = f"%{words[0]}%"
                            sql_like = """
                                SELECT id_berita
                                FROM berita
                                WHERE judul LIKE %s OR tag LIKE %s
                                LIMIT 10
                            """
                            await cur.execute(sql_like, (like_str, like_str))
                            rows_like = await cur.fetchall()
                            for row in rows_like:
                                candidate_ids.add(row[0])
                                
        if not candidate_ids:
            return []
            
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
            return []
            
        rows = [list(r) for r in raw_rows]
        corpus_texts = [f"{r[2]} - Tag: {r[12]}" for r in rows]
        
        # Scoring awal judul/tag kandidat: gunakan kombinasi query judul dan substansi
        effective_rerank_query = f"{semantic_search_query} {' '.join(query_judul_list or [])}".strip()
        scores = await reranker_service.compute_scores(effective_rerank_query, corpus_texts)
        
        # Target Document Match Boost: Prioritaskan dokumen yang diminta secara spesifik (misal: PKB, SOP, dll)
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

        scored_rows = []
        for i, r in enumerate(rows):
            doc_title_lower = str(r[2] or "").lower()
            doc_noper_lower = str(r[1] or "").lower()
            doc_tag_lower = str(r[12] or "").lower()
            
            base_score = float(scores[i])
            has_primary_match = any(t in doc_title_lower or t in doc_noper_lower or t in doc_tag_lower for t in explicit_primary_types)
            has_general_match = any(t in doc_title_lower or t in doc_noper_lower or t in doc_tag_lower for t in general_target_tokens)
            
            # Dokumen induk (PKB/SOP) yang diminta user mendapat prioritas utama (+0.45), dokumen pendukung topik (+0.20)
            boost = 0.0
            if has_primary_match:
                boost += 0.45
            elif has_general_match:
                boost += 0.20
                
            final_score = base_score + boost
            r[11] = final_score
            scored_rows.append(r)
            
        scored_rows.sort(key=lambda x: x[11], reverse=True)
        scored_rows = [x for x in scored_rows if x[11] > 0.40]
        
        if not scored_rows:
            return []
            
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
                        
        candidate_docs = []
        for row in scored_rows:
            id_berita, noper, judul, gambar, gambar2, gambar3, nama_kategori, tanggal, stataktif, mencabut_str, linkper_str, score, _tag_val, _isi_val = row
            valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
            status_berlaku_str = _resolve_status_berlaku(id_berita, stataktif, dicabut_oleh)
            
            candidate_docs.append({
                "id": id_berita,
                "id_berita": id_berita,
                "judul": judul,
                "title": judul,
                "document_title": judul,
                "noper": noper or "N/A",
                "nomor": noper or "N/A",
                "tanggal": str(tanggal) if tanggal else "",
                "stataktif": stataktif,
                "status_berlaku": status_berlaku_str,
                "mencabut": mencabut_str or "-",
                "score": float(score),
                "jenis": nama_kategori or "Regulasi",
                "valid_file": valid_file,
                "filename": os.path.basename(valid_file) if valid_file else None,
                "file_path": f"file_peraturan/{os.path.basename(valid_file)}" if valid_file else None,
                "raw_tag": _tag_val,
                "raw_isi": _isi_val
            })
            
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
                        
                        match_str = " ".join(words)
                        
                        # Coba FTS dulu
                        sql_fts = f"""
                            SELECT id_berita
                            FROM berita 
                            WHERE MATCH(judul, tag, isi_berita) AGAINST (%s IN NATURAL LANGUAGE MODE)
                            ORDER BY MATCH(judul, tag, isi_berita) AGAINST (%s IN NATURAL LANGUAGE MODE) DESC
                            LIMIT 10
                        """
                        await cur.execute(sql_fts, (match_str, match_str))
                        rows = await cur.fetchall()
                        for row in rows:
                            candidate_ids.add(row[0])
                            
                        # SPRINT 5: Fallback LIKE untuk menangkap singkatan pendek (misal "PKB", "SOP") yang sering diabaikan FTS MySQL
                        if len(words) == 1 and len(words[0]) <= 5:
                            like_str = f"%{words[0]}%"
                            sql_like = """
                                SELECT id_berita
                                FROM berita
                                WHERE judul LIKE %s OR tag LIKE %s
                                LIMIT 10
                            """
                            await cur.execute(sql_like, (like_str, like_str))
                            rows_like = await cur.fetchall()
                            for row in rows_like:
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

            meta_str = f"ID Dokumen: {id_berita}\nStatus Berlaku: {status_berlaku_str}\nTanggal Terbit: {tanggal}\nNomor Regulasi: {noper}\nMencabut: {mencabut_str if mencabut_str else '-'}\n"
            
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
