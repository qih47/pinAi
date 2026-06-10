"""
Vision Preprocessing Service untuk Sequential Pipeline Layer 0
Menangani OCR/image extraction dari PDF dan gambar
"""

import os
import base64
import logging
from typing import List, Dict, Optional
from io import BytesIO
from pathlib import Path

logger = logging.getLogger("CAKRA_VISION_SERVICE")


async def extract_text_from_files(file_paths: List[str]) -> Dict[str, str]:
    """
    Layer 0: Vision Preprocessor
    Ekstraksi teks dari semua file (gambar/PDF) secara parallel
    
    Args:
        file_paths: List path ke file di UPLOAD_DIR
        
    Returns:
        {
            "extracted_text": "Gabungan seluruh hasil OCR",
            "file_count": 2,
            "page_count": 5,
            "status": "success|partial|failed"
        }
    """
    extracted_texts = []
    total_pages = 0
    
    try:
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.warning(f"⚠️ File not found: {file_path}")
                continue
            
            filename = os.path.basename(file_path)
            
            if filename.lower().endswith('.pdf'):
                logger.info(f"📄 Processing PDF: {filename}")
                pdf_text, page_count = await _extract_from_pdf(file_path)
                extracted_texts.append(pdf_text)
                total_pages += page_count
                logger.info(f"📑 PDF processed: {page_count} pages extracted")
                
            elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                logger.info(f"📸 Processing Image: {filename}")
                image_text = await _extract_from_image(file_path)
                extracted_texts.append(image_text)
                total_pages += 1
            else:
                logger.warning(f"⚠️ Unsupported file format: {filename}")
                continue
        
        combined_text = "\n---\n".join(extracted_texts) if extracted_texts else "[No text extracted]"
        
        return {
            "extracted_text": combined_text,
            "file_count": len(file_paths),
            "page_count": total_pages,
            "status": "success" if extracted_texts else "empty"
        }
        
    except Exception as e:
        logger.error(f"❌ Vision extraction error: {str(e)}")
        return {
            "extracted_text": "[File processing failed]",
            "file_count": len(file_paths),
            "page_count": 0,
            "status": "failed"
        }


async def _extract_from_pdf(pdf_path: str) -> tuple[str, int]:
    """
    Extract text dari PDF menggunakan pdf2image + pytesseract (atau langsung text layer)
    """
    try:
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError:
            logger.error("Missing pdf2image or pytesseract. Using fallback.")
            return "[PDF processing requires pdf2image + pytesseract]", 0
        
        logger.info(f"🔄 Converting PDF to images...")
        images = convert_from_path(pdf_path, dpi=200)
        logger.info(f"✅ PDF converted to {len(images)} images")
        
        extracted_texts = []
        for idx, image in enumerate(images):
            logger.info(f"📖 OCR page {idx + 1}/{len(images)}...")
            text = pytesseract.image_to_string(image, lang='ind+eng')
            extracted_texts.append(f"\n[PAGE {idx + 1}]\n{text}\n")
        
        combined = "\n".join(extracted_texts)
        return combined, len(images)
        
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        return "[PDF extraction failed]", 0


async def _extract_from_image(image_path: str) -> str:
    """
    Extract text dari gambar menggunakan pytesseract
    """
    try:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.error("Missing pytesseract or PIL. Using fallback.")
            return "[Image processing requires pytesseract + PIL]"
        
        logger.info(f"📸 Opening image: {image_path}")
        image = Image.open(image_path)
        
        logger.info(f"🔄 Running OCR on image...")
        text = pytesseract.image_to_string(image, lang='ind+eng')
        
        return text if text.strip() else "[No text detected in image]"
        
    except Exception as e:
        logger.error(f"Image extraction error: {str(e)}")
        return "[Image extraction failed]"


async def prepare_vision_messages(
    file_paths: List[str],
    user_message: str
) -> Dict:
    """
    Siapkan format pesan untuk vision model (MiniCPM-V)
    dengan base64 encoded images/PDF pages
    
    Returns:
        {
            "extracted_text": "...",
            "base64_images": ["..."],
            "page_count": 5
        }
    """
    base64_images = []
    total_pages = 0
    
    try:
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue
            
            filename = os.path.basename(file_path)
            
            if filename.lower().endswith('.pdf'):
                logger.info(f"📄 Preparing PDF for vision: {filename}")
                
                try:
                    from pdf2image import convert_from_path
                except ImportError:
                    logger.error("pdf2image not installed")
                    continue
                
                images = convert_from_path(file_path, dpi=200)
                
                for page_idx, page_image in enumerate(images):
                    buffer = BytesIO()
                    page_image.save(buffer, format="PNG")
                    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    base64_images.append(img_b64)
                    total_pages += 1
                    logger.info(f"✅ PDF page {page_idx + 1} encoded to base64")
                
            elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                logger.info(f"📸 Preparing image for vision: {filename}")
                
                with open(file_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
                    base64_images.append(img_b64)
                    total_pages += 1
                    logger.info(f"✅ Image encoded to base64")
        
        return {
            "base64_images": base64_images,
            "page_count": total_pages,
            "user_message": user_message,
            "status": "success" if base64_images else "empty"
        }
        
    except Exception as e:
        logger.error(f"❌ Vision preparation error: {str(e)}")
        return {
            "base64_images": [],
            "page_count": 0,
            "user_message": user_message,
            "status": "failed"
        }
