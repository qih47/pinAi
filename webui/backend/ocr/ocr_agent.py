import os

# Force CPU mode globally for Paddle
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import numpy as np
import cv2

# Pastikan use_gpu=True jika ingin pakai A40
ocr = PaddleOCR(use_angle_cls=True, lang='id', use_gpu=True)


def preprocess_image(img):
    """Preprocessing untuk OCR: output HARUS 3-channel (H, W, 3)"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=8)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    # Konversi kembali ke 3-channel
    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)


def extract_text_per_page(pdf_path):
    # Log untuk memastikan file bisa dibaca
    if not os.path.exists(pdf_path):
        print(f"❌ PDF Path GAK ADA: {pdf_path}")
        return []

    try:
        # pdf2image butuh poppler
        pages = convert_from_path(pdf_path, dpi=200)
        full_text_list = []

        for i, page in enumerate(pages):
            img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
            processed_img = preprocess_image(img)

            result = ocr.ocr(processed_img)

            page_content = []
            if result and isinstance(result, list) and len(result) > 0 and result[0]:
                for line in result[0]:
                    if not line or len(line) < 2:
                        continue
                    try:
                        text = str(line[1][0]).strip()
                        confidence = float(line[1][1])
                        if text and confidence >= 0.3:
                            page_content.append(text)
                    except (IndexError, ValueError, TypeError):
                        continue

            text_halaman = " ".join(page_content)
            full_text_list.append(text_halaman)
            print(
                f"[*] Halaman {i + 1}: {len(page_content)} baris | Contoh: {text_halaman[:50]}..."
            )

        return full_text_list

    except Exception as e:
        print(f"[CRITICAL ERROR] extract_text_per_page Gagal: {e}")
        import traceback

        traceback.print_exc()
        return []
