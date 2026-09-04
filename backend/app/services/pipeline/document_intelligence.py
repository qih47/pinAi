import logging
import json
import re
import os
import asyncio
import base64
import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor
import fitz
from PIL import Image
import io

from backend.app.services.rag.reranker_service import reranker_service

logger = logging.getLogger("DOCUMENT_INTELLIGENCE")

# Global In-Memory Cache for Document Pages and OCR
_DOC_CACHE: Dict[str, Dict[str, Any]] = {}

def get_document_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    return _DOC_CACHE.get(cache_key)

def set_document_cache(cache_key: str, text_map: List[Dict[str, Any]], images: List[str]):
    _DOC_CACHE[cache_key] = {
        "text_map": text_map,
        "images": images,
        "timestamp": datetime.datetime.now()
    }


class StructuralContinuityDetector:
    """
    Pendeteksi kontinuitas struktural antar halaman dokumen regulasi/hukum.
    Menganalisis tanda sambung (catchwords) di footer dan kelanjutan penomoran pasal/sub-bab.
    """
    @staticmethod
    def detect_catchword(text: str) -> bool:
        if not text:
            return False
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        if not lines:
            return False
        last_chunk = " ".join(lines[-3:])
        # Pola catchword standar SK Pindad/BUMN: /7) General..... atau /Pasal 5..... atau /b. Direksi.....
        if re.search(r'\/[0-9a-zA-Z\(\)\.\s\-]{2,}\.{2,}', last_chunk) or re.search(r'\/\s*[0-9a-zA-Z\(\)]+', last_chunk):
            return True
        return False

    @staticmethod
    def detect_unclosed_list_forward(text_curr: str, text_next: str) -> bool:
        if not text_curr or not text_next:
            return False
        curr_numbers = re.findall(r'(?:^|\n|\s)([0-9]{1,2})\)\s', text_curr)
        next_numbers = re.findall(r'(?:^|\n|\s)([0-9]{1,2})\)\s', text_next[:400])
        if curr_numbers and next_numbers:
            last_curr = int(curr_numbers[-1])
            first_next = int(next_numbers[0])
            if first_next == last_curr + 1:
                return True
        lines_curr = [line.strip() for line in text_curr.strip().split('\n') if line.strip()]
        if lines_curr:
            last_line = lines_curr[-1].lower()
            if last_line.endswith(',') or last_line.endswith(';') or last_line.endswith(' dan') or last_line.endswith(' serta'):
                return True
        return False

    @staticmethod
    def detect_unclosed_list_backward(text_curr: str, text_prev: str) -> bool:
        if not text_curr or not text_prev:
            return False
        first_curr_numbers = re.findall(r'(?:^|\n|\s)([0-9]{1,2})\)\s', text_curr[:400])
        prev_numbers = re.findall(r'(?:^|\n|\s)([0-9]{1,2})\)\s', text_prev)
        if first_curr_numbers and prev_numbers:
            first_curr = int(first_curr_numbers[0])
            last_prev = int(prev_numbers[-1])
            if first_curr > 1 and first_curr == last_prev + 1:
                return True
        return False


def extract_explicit_pages_from_query(query: str, total_pages: int) -> Set[int]:
    """Mengekstrak nomor halaman majemuk dari pertanyaan pengguna (contoh: 'halaman 3 dan 5')."""
    explicit_pages = set()
    page_matches = re.finditer(r'(?:halaman|hal\.?|page)\s*([0-9\s,\-dan&sampai]+)', query, re.IGNORECASE)
    for pm in page_matches:
        raw_part = pm.group(1)
        nums = re.findall(r'\b([0-9]+)\b', raw_part)
        for n in nums:
            p_idx = int(n) - 1
            if 0 <= p_idx < total_pages:
                explicit_pages.add(p_idx)
    return explicit_pages


def expand_tri_window_context(seed_pages: List[int], text_map: List[Dict[str, Any]], total_pages: int) -> List[int]:
    """
    Ekspansi jendela struktural Tri-Window [p-1, p, p+1] untuk menghubungkan pasal yang terpotong.
    Setiap seed page selalu mengambil halaman sebelum (p-1) dan sesudah (p+1) agar alur kalimat,
    pasal, ayat, dan tabel tidak terputus di tengah jalan.
    """
    if not seed_pages or not text_map:
        return seed_pages or []
        
    expanded_cluster = set()
    for p in seed_pages:
        if p < 0 or p >= total_pages:
            continue
        # 1. Halaman inti (seed)
        expanded_cluster.add(p)
        
        # 2. Tri-Window KIRI (Backward): Selalu ambil halaman sebelum (p - 1)
        if p > 0:
            prev_p = p - 1
            expanded_cluster.add(prev_p)
            
            # Deep Extension jika terdeteksi list/catchword menyambung lebih jauh ke p-2
            if prev_p > 0:
                text_prev = text_map[prev_p]["text"] if prev_p < len(text_map) else ""
                text_prev2 = text_map[prev_p - 1]["text"] if (prev_p - 1) < len(text_map) else ""
                if StructuralContinuityDetector.detect_unclosed_list_backward(text_prev, text_prev2) or StructuralContinuityDetector.detect_catchword(text_prev2):
                    expanded_cluster.add(prev_p - 1)
                    logger.info(f"[DOC_INTEL] 🔗 Deep Linked LEFT: Page {prev_p} into cluster")

        # 3. Tri-Window KANAN (Forward): Selalu ambil halaman sesudah (p + 1)
        if p + 1 < total_pages:
            next_p = p + 1
            expanded_cluster.add(next_p)
            
            # Deep Extension jika terdeteksi list/catchword menyambung lebih jauh ke p+2
            if next_p + 1 < total_pages:
                text_next = text_map[next_p]["text"] if next_p < len(text_map) else ""
                text_next2 = text_map[next_p + 1]["text"] if (next_p + 1) < len(text_map) else ""
                if StructuralContinuityDetector.detect_unclosed_list_forward(text_next, text_next2) or StructuralContinuityDetector.detect_catchword(text_next):
                    expanded_cluster.add(next_p + 1)
                    logger.info(f"[DOC_INTEL] 🔗 Deep Linked RIGHT: Page {next_p + 2} into cluster")
                
    # 4. Gap-filling: Jika ada celah 1 halaman bolong di antara halaman yang terpilih, sambungkan!
    sorted_pages = sorted(list(expanded_cluster))
    bridged_cluster = set(sorted_pages)
    for i in range(len(sorted_pages) - 1):
        if sorted_pages[i + 1] - sorted_pages[i] == 2:
            gap_page = sorted_pages[i] + 1
            bridged_cluster.add(gap_page)
            logger.info(f"[DOC_INTEL] 🌉 Gap-filling bridged Page {gap_page + 1} between Page {sorted_pages[i] + 1} and Page {sorted_pages[i + 1] + 1}")

    result = sorted(list(bridged_cluster))
    # Batasi maksimal 18 halaman per dokumen agar hemat token dan responsif
    if len(result) > 18:
        result = result[:18]
        
    return result


def process_single_page_threadsafe(file_path: str, page_num: int, render_images: bool = False) -> Tuple[Dict[str, Any], str]:
    """Worker thread-safe: ekstrak teks digital secara instan, dan OCR hanya jika scan."""
    import pytesseract
    doc_thread = fitz.open(file_path)
    page = doc_thread.load_page(page_num)
    
    # 1. Ekstrak teks digital langsung (super cepat ~1ms, zero CPU load)
    text = page.get_text("text").strip()
    encoded = ""
    
    # 2. Render image hanya jika diminta secara eksplisit
    if render_images:
        pix = page.get_pixmap(dpi=120)
        encoded = base64.b64encode(pix.tobytes("png")).decode("utf-8")

    # 3. OCR fallback HANYA jika halaman berupa scan / gambar (< 40 karakter digital)
    if len(text) < 40:
        try:
            import os
            os.environ["OMP_THREAD_LIMIT"] = "1"
            pix_ocr = page.get_pixmap(dpi=120)
            img = Image.open(io.BytesIO(pix_ocr.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img, lang='ind+eng')
            if ocr_text and ocr_text.strip():
                text = ocr_text.strip()
        except Exception as _ocr_err:
            logger.warning(f"[DOC_INTEL] OCR fallback failed for page {page_num+1}: {_ocr_err}")

    doc_thread.close()
    return {"page_num": page_num, "text": text}, encoded


async def extract_and_ocr_document_async(
    file_path: str,
    cache_key: Optional[str] = None,
    render_images: bool = False
) -> Tuple[List[Dict[str, Any]], List[str], int]:
    """
    Mengekstrak teks dokumen PDF secara efisien (dual L1/L2 cache).
    Secara default render_images=False agar tidak membebani CPU/RAM server.
    """
    key_to_use = cache_key or file_path
    cached = get_document_cache(key_to_use)
    if cached:
        logger.info(f"[DOC_INTEL] 🚀 Cache Hit for document: {file_path}")
        return cached["text_map"], cached["images"], len(cached["text_map"])

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document file not found at: {file_path}")

    # Coba via Unified Extractor (dual-layer cache)
    try:
        from backend.app.services.tools.unified_extractor import extract_document
        doc_obj = await extract_document(file_path, cache_key=key_to_use, render_images=render_images)
        t_map = doc_obj.to_text_map()
        imgs = doc_obj.base64_images
        set_document_cache(key_to_use, t_map, imgs)
        logger.info(f"[DOC_INTEL] ✅ Ekstraksi selesai via Unified Extractor ({doc_obj.total_pages} hal, {doc_obj.extraction_seconds:.2f}s)")
        return t_map, imgs, doc_obj.total_pages
    except Exception as ue_err:
        logger.warning(f"[DOC_INTEL] Unified Extractor fallback: {ue_err} → menjalankan fallback lokal...")

    doc = fitz.open(file_path)
    total_pages = len(doc)
    doc.close()

    def run_parallel_extraction():
        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = [executor.submit(process_single_page_threadsafe, file_path, p, render_images) for p in range(total_pages)]
            results = [t.result() for t in tasks]
        t_map = [r[0] for r in results]
        imgs = [r[1] for r in results]
        return t_map, imgs

    start_time = datetime.datetime.now()
    text_map, all_base64_images = await asyncio.to_thread(run_parallel_extraction)
    duration = (datetime.datetime.now() - start_time).total_seconds()
    logger.info(f"[DOC_INTEL] ✅ Selesai proses ekstraksi {total_pages} halaman dalam {duration:.2f}s.")

    set_document_cache(key_to_use, text_map, all_base64_images)
    return text_map, all_base64_images, total_pages



async def two_stage_rerank_cluster_async(
    user_message: str,
    text_map: List[Dict[str, Any]],
    all_base64_images: Optional[List[str]] = None,
    total_pages: Optional[int] = None,
    explicit_pages: Optional[Set[int]] = None,
    top_k_seeds: int = 4,
    all_images: Optional[List[str]] = None,
    **kwargs: Any
) -> Tuple[List[int], List[str], str]:
    """
    Menjalankan Two-Stage Context-Aware Reranking & Structural Continuity Engine:
    1. Stage 1: BM25 + BGE Reranker untuk menemukan Top Seed Pages.
    2. Stage 2: Tri-Window Expansion [p-1, p, p+1] + Structural Continuity Validation.
    Mengembalikan (selected_pages, final_base64_images, final_extracted_text).
    """
    images_list = all_base64_images if all_base64_images is not None else (all_images or [])
    if total_pages is None:
        total_pages = len(text_map) if text_map else (len(images_list) if images_list else 1)

    corpus_texts = [item["text"] if item["text"] else "[FULL IMAGE SCAN]" for item in text_map]
    
    # 1. BGE Reranker Scores
    bge_scores = await reranker_service.compute_scores(user_message, corpus_texts)
    
    # 2. Keyword & Bigram Matching
    stopwords = {
        "yang", "itu", "ini", "dan", "di", "ke", "dari", "pada", "untuk", "dengan", "adalah", 
        "apa", "apakah", "siapa", "mengapa", "bagaimana", "kapan", "dimana", "ada", "ya", "sih",
        "dong", "kan", "bukannya", "tidak", "bukan", "atau", "juga", "sudah", "akan", "telah",
        "bisa", "dapat", "tentang", "mengenai", "dalam", "atas", "oleh", "secara", "seperti"
    }
    raw_words = re.findall(r'\b[a-zA-Z0-9_\-]{3,}\b', user_message.lower())
    keywords = [w for w in raw_words if w not in stopwords]
    
    phrases = []
    words_list = user_message.lower().split()
    for i in range(len(words_list) - 1):
        pair = f"{words_list[i]} {words_list[i+1]}"
        if len(pair) > 5:
            phrases.append(pair)
            
    page_scores = []
    for idx, item in enumerate(text_map):
        page_text_lower = item["text"].lower()
        kw_hits = sum(1 for kw in keywords if kw in page_text_lower)
        phrase_hits = sum(2 for ph in phrases if ph in page_text_lower)
        total_kw_score = (kw_hits * 0.2) + (phrase_hits * 0.4)
        b_score = float(bge_scores[idx]) if idx < len(bge_scores) else 0.0
        hybrid_score = (b_score * 0.5) + min(1.0, total_kw_score) * 0.5
        page_scores.append({
            "page_num": item["page_num"],
            "text": item["text"],
            "bge_score": b_score,
            "kw_score": total_kw_score,
            "score": hybrid_score
        })
        
    page_scores.sort(key=lambda x: x["score"], reverse=True)
    
    # Stage 1: Seed Selection
    if explicit_pages:
        seed_pages = sorted(list(explicit_pages))
        logger.info(f"[DOC_INTEL] 🎯 Explicit Seeds: {[p+1 for p in seed_pages]}")
    else:
        top_k = min(top_k_seeds, total_pages)
        seed_pages = [p["page_num"] for p in page_scores[:top_k]]
        logger.info(f"[DOC_INTEL] 🎯 Stage 1 Seeds: {[p+1 for p in seed_pages]}")

    # Stage 2: Tri-Window Structural & Semantic Boundary Analysis
    selected_pages = expand_tri_window_context(seed_pages, text_map, total_pages)
    logger.info(f"[DOC_INTEL] 📑 Final Connected Pages: {[p+1 for p in selected_pages]}")
    
    final_base64_images = [images_list[p] for p in selected_pages if p < len(images_list)]
    
    extracted_texts_list = []
    for p in selected_pages:
        t = text_map[p]["text"]
        if t.strip():
            extracted_texts_list.append(f"--- TEKS / KONTEN HALAMAN {p+1} ---\n{t}\n")
        else:
            extracted_texts_list.append(f"--- HALAMAN {p+1} (BAGAN/DIAGRAM STRUKTUR) ---\n[Halaman ini berupa diagram/bagan visual yang terlampir pada gambar]\n")
            
    final_extracted_text = "\n".join(extracted_texts_list)
    return selected_pages, final_base64_images, final_extracted_text
