import logging
from typing import Dict, Any, List

logger = logging.getLogger("CAKRA_PIPELINE")

async def extract_pdf_text(file_paths: List[str]) -> Dict[str, Any]:
    """
    Ekstrak teks PDF secara backward-compatible menggunakan Unified Extractor.
    Mempertahankan format dict return yang sama: {status, extracted_text, page_count}.
    """
    from backend.app.services.tools.unified_extractor import extract_document

    all_text = []
    total_pages = 0

    for path in file_paths:
        try:
            doc = await extract_document(path)
            total_pages += doc.total_pages
            if doc.full_text:
                all_text.append(doc.full_text)
        except Exception as e:
            logger.warning(f"⚠️ [PDF] Unified extractor gagal untuk {path}: {e} → coba fallback pymupdf...")
            try:
                import fitz
                d = fitz.open(path)
                total_pages += len(d)
                for page in d:
                    t = page.get_text().strip()
                    if t:
                        all_text.append(t)
                d.close()
            except Exception as fe:
                logger.error(f"❌ [PDF] Fallback pymupdf juga gagal untuk {path}: {fe}")

    extracted = "\n\n".join(all_text).strip()
    logger.info(
        f"✅ [PDF] Ekstraksi selesai via Unified Extractor | {total_pages} halaman | {len(extracted)} chars"
    )
    return {"status": "success", "extracted_text": extracted, "page_count": total_pages}

