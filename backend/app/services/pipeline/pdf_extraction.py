import logging
from typing import Dict, Any, List

logger = logging.getLogger("CAKRA_PIPELINE")

async def extract_pdf_text(file_paths: List[str]) -> Dict[str, Any]:
    import fitz  # pymupdf

    all_text = []
    page_count = 0

    for path in file_paths:
        try:
            doc = fitz.open(path)
            page_count += len(doc)
            for page in doc:
                text = page.get_text().strip()
                if text:
                    all_text.append(text)
            doc.close()
        except Exception as e:
            logger.warning(f"⚠️ [PDF] pymupdf gagal untuk {path}: {e} → skip")

    extracted = "\n\n".join(all_text).strip()

    if not extracted:
        logger.info("📸 [PDF] Teks kosong → fallback ke MiniCPM-V OCR...")
        try:
            from backend.app.services.vision.vision_service import extract_text_from_files
            result = await extract_text_from_files(file_paths)
            extracted = result.get("extracted_text", "")
            page_count = result.get("page_count", page_count)
        except Exception as e:
            logger.error(f"❌ [PDF] Vision fallback gagal: {e}")

    logger.info(
        f"✅ [PDF] Ekstraksi selesai | {page_count} halaman | {len(extracted)} chars"
    )
    return {"status": "success", "extracted_text": extracted, "page_count": page_count}
