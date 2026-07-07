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

def _process_pdf_sync(abs_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Process PDF synchronously (CPU bound).
    Returns (extracted_text, formatted_attachments_images).
    """
    import PyPDF2
    import fitz
    
    extracted = ""
    try:
        with open(abs_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted += page_text + "\n"
    except Exception as e:
        logger.warning(f"[PERATURAN_SERVICE] Failed to read PDF {abs_path}: {e}")
        return "", []

    extracted = extracted.strip()
    formatted_attachments = []
    
    # If PDF has text, we just return the text (no need to OCR/Image for LLM)
    if extracted:
        return extracted, []
        
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
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            encoded = base64.b64encode(img_data).decode("utf-8")
            formatted_attachments.append({"base64": encoded, "type": "image"})
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Failed to convert PDF to image: {e}")
        
    return "", formatted_attachments


async def search_and_ocr_by_judul(query_judul: Optional[str]) -> Tuple[str, List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Cari judul di MySQL `berita`, jika ada ambil PDF-nya dan lakukan ekstraksi/OCR.
    Berjalan secara paralel di event loop via run_in_executor untuk tugas berat.
    Returns: context_text, formatted_attachments, source_metadata
    """
    if not query_judul or not query_judul.strip():
        return "", [], None
        
    logger.info(f"[PERATURAN_SERVICE] Searching title in DB: '{query_judul}'")
    
    try:
        async with get_peraturan_db() as conn:
            async with conn.cursor() as cur:
                # Cari berdasarkan judul
                # Ubah spasi menjadi wildcard '%' agar pencarian lebih fleksibel
                # Misal: "Work From Home WFH PT Pindad" menjadi "%Work%From%Home%WFH%PT%Pindad%"
                # Sehingga bisa match dengan "Pelaksanaan Work From Home (WFH) di PT Pindad"
                search_pattern = "%" + "%".join(query_judul.strip().split()) + "%"
                
                sql = """
                    SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori 
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE b.judul LIKE %s LIMIT 1
                """
                await cur.execute(sql, (search_pattern,))
                row = await cur.fetchone()
                
                if not row:
                    logger.info(f"[PERATURAN_SERVICE] No matching title found for '{query_judul}'")
                    return "", [], None
                    
                id_berita, judul, gambar, gambar2, gambar3, nama_kategori = row
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
                    return "", [], None
                
                # Eksekusi sinkronus OCR & PDF Parsing di background thread agar tidak memblokir event loop
                loop = asyncio.get_running_loop()
                extracted_text, formatted_attachments = await loop.run_in_executor(
                    None, _process_pdf_sync, valid_file
                )
                
                context_text = ""
                if extracted_text:
                    context_text = f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n{extracted_text}\n-------------------\n"
                elif formatted_attachments:
                    context_text = f"--- DOKUMEN SPESIFIK (JUDUL: {judul}) ---\n[Dokumen hasil scan telah dilampirkan sebagai gambar untuk dianalisa]\n-------------------\n"
                # Buat metadata sumber dokumen resmi untuk ditimpa ke RAG
                source_metadata = {
                    "id": id_berita,
                    "title": judul,
                    "document_title": judul,
                    "kategori": nama_kategori,
                    "file_path": valid_file,  # INI PATH YANG BENAR (pinAi/file_peraturan)
                    "score": 10.0, # Beri score sangat tinggi agar pasti terpilih
                    "similarity": 10.0,
                    "cache_hit": True,
                    "is_exact_match": True
                }
                    
                return context_text, formatted_attachments, source_metadata
                
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Database error during title search: {e}")
        return "", [], None

async def simulate_ocr_extraction(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Wrapper untuk endpoint /simulate-ocr agar dapat digunakan 
    oleh admin untuk mendebug proses OCR dan Vision.
    """
    logger.info(f"[PERATURAN_SERVICE] OCR Simulation triggered for: {file_path}")
    loop = asyncio.get_running_loop()
    try:
        extracted_text, formatted_attachments = await loop.run_in_executor(
            None, _process_pdf_sync, file_path
        )
        return extracted_text, formatted_attachments
    except Exception as e:
        logger.error(f"[PERATURAN_SERVICE] Simulation failed: {e}")
        raise e
