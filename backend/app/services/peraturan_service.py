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


async def search_and_ocr_by_judul(query_judul: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Mencari metadata peraturan berdasarkan field `judul` di tabel `berita`.
    Berguna saat Call 1 memutuskan butuh pencarian persis berdasarkan judul.
    Sprint 4: LIMIT 3 untuk mendeteksi conflict jika ada beberapa versi.
    
    Returns: context_text, formatted_attachments, list_of_source_metadata
    """
    if not query_judul or not query_judul.strip():
        return "", [], []
        
    logger.info(f"[PERATURAN_SERVICE] Searching title in DB: '{query_judul}'")
    
    try:
        async with get_peraturan_db() as conn:
            async with conn.cursor() as cur:
                # Cari berdasarkan judul
                search_pattern = "%" + "%".join(query_judul.strip().split()) + "%"
                
                sql = """
                    SELECT b.id_berita, b.noper, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori 
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE b.judul LIKE %s LIMIT 3
                """
                await cur.execute(sql, (search_pattern,))
                rows = await cur.fetchall()
                
                if not rows:
                    logger.info(f"[PERATURAN_SERVICE] No matching title found for '{query_judul}'")
                    return "", [], []
                    
                combined_context_text = ""
                all_formatted_attachments = []
                all_source_metadata = []

                loop = asyncio.get_running_loop()
                
                for row in rows:
                    id_berita, noper, judul, gambar, gambar2, gambar3, nama_kategori = row
                    logger.info(f"[PERATURAN_SERVICE] Found match: '{judul}'")
                    
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
                    
                    # Eksekusi sinkronus OCR & PDF Parsing di background thread agar tidak memblokir event loop
                    extracted_text, formatted_attachments, total_pages = await loop.run_in_executor(
                        None, _process_pdf_sync, valid_file
                    )
                    
                    if extracted_text:
                        combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{extracted_text}\n-------------------\n\n"
                    elif formatted_attachments:
                        combined_context_text += f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n[Dokumen hasil scan telah dilampirkan sebagai gambar untuk dianalisa]\n-------------------\n\n"
                    
                    if formatted_attachments:
                        all_formatted_attachments.extend(formatted_attachments)
                        
                    # Buat metadata sumber dokumen resmi untuk ditimpa ke RAG
                    all_source_metadata.append({
                        "id": id_berita,
                        "title": judul,
                        "document_title": judul,
                        "filename": os.path.basename(valid_file),
                        "jenis": nama_kategori or "Regulasi",
                        "nomor": noper or "N/A",
                        "page_number": str(total_pages),
                        "cache_hit": False,
                        "score_label": "SPESIFIK",
                        "score": 1.0 # Highest priority
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
