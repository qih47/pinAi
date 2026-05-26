import os
import re
import cv2
import numpy as np
import logging
from paddleocr import PaddleOCR
from pdf2image import convert_from_path

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCR_AGENT")

# Inisialisasi PaddleOCR dengan dukungan GPU A40
ocr = PaddleOCR(
    use_angle_cls=True,
    lang="id",
    use_gpu=True,
    show_log=False,
    rec_char_type="en",  # Memperkuat karakter latin
    det_db_thresh=0.3,  # Lebih sensitif deteksi kotak teks
    det_db_box_thresh=0.5,
)


def clean_ocr_text(text):
    """
    Logic koreksi otomatis untuk menangani halusinasi OCR.
    Ditambah logika pembersihan karakter miring (italic).
    """
    if not text:
        return ""

    # 1. FIX KARAKTER SAMPAH AKIBAT TEKS MIRING (Robust Regex)
    # Menghapus simbol /, |, \ yang terjepit di antara huruf (biasanya salah baca italic)
    text = re.sub(r"([a-zA-Z])[/|\\I1i]([a-zA-Z])", r"\1\2", text)

    # 2. FIX BULAN ROMAWI
    text = re.sub(r"/XL/(20\d{2})", r"/XI/\1", text)
    text = re.sub(r"/X L/(20\d{2})", r"/XI/\1", text)

    # 3. DICTIONARY KOREKSI (Typo Alien & Common Mistakes)
    corrections = {
        "uep": "per",
        "wnan": "tuan",
        "pepu!d": "pindad",
        "e!ax": "kerja",
        "ueyeunbsuaa": "menggunakan",
        "ynanas": "seluruh",
        "otasied": "pindad",
        "sipel": "sipil",
        "kepada yth": "kepada yang terhormat",
        "dinatas": "dinas",
        "pnindad": "pindad",
        "pindar": "pindad",
        "ptnindad": "pindad",
        "perusahaab": "perusahaan",
        "perusabaan": "perusahaan",
        "dengtan": "dengan",
        "yangber": "yang ber",
        "kerjaper": "kerja per",
        "laimya": "lainnya",
        "tahun20": "tahun 20",
        "alamatnyad": "alamatnya di",
        "nomorab": "nomor ab",
        "dalamrangka": "dalam rangka",
        "keperluan": "keperluan",
        "mekanikal": "mekanikal",
        "elektrikal": "elektrikal",
        "industri": "industri",
        "tamggal": "tanggal",
        "jamkerja": "jam kerja",
        "menggubakan": "menggunakan",
        "menggunakab": "menggunakan",
        "haridi": "hari di",
        "dilakukab": "dilakukan",
        "tujuan—": "tujuan:",
        "pt. pindad (persero)": "PT Pindad (Persero)",
        "pemeriksaab": "pemeriksaan",
        "dokumeh": "dokumen",
        "merupakab": "merupakan",
        "diharaokan": "diharapkan",
        "studikasus": "studi kasus",
        "ketentuaa": "ketentuan",
        "sesuaidengan": "sesuai dengan",
        "keamanan": "keamanan",
        "keselamatab": "keselamatan",
        "kerjanyaa": "kerjanya",
        "pindad ": "pindad ",
        "ruangab": "ruangan",
        "kipndad": "pindad",
    }

    for wrong, right in corrections.items():
        pattern = re.compile(re.escape(wrong), re.IGNORECASE)
        text = pattern.sub(right, text)

    # 4. CLEANING KARAKTER & SYMBOL SAMPAH
    text = re.sub(r"[\\_~«»]", "", text)

    # 5. FIX SPASI BERLEBIH & HURUF JOMBLO
    text = re.sub(r"(?<=\b\w)\s(?=\w\b)", "", text)

    # Clean multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def preprocess_image(img):
    """
    Meningkatkan kontras dan meluruskan teks (Deskewing)
    supaya teks miring tidak terbaca sebagai simbol sampah.
    """
    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Denoising
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # 3. DESKEWING (Meluruskan posisi teks)
    # Sangat penting supaya OCR tidak bingung sumbu vertikal huruf italic
    coords = np.column_stack(np.where(denoised > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = denoised.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        denoised, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )

    # 4. Adaptive Thresholding
    thresh = cv2.adaptiveThreshold(
        rotated, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)


def extract_text_per_page(pdf_path):
    if not os.path.exists(pdf_path):
        logger.error(f"File PDF tidak ditemukan: {pdf_path}")
        return []

    try:
        # DPI 300 adalah sweet spot untuk karakter miring
        pages = convert_from_path(pdf_path, dpi=300)
        full_text_list = []

        for i, page in enumerate(pages):
            img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

            # Pre-processing (Termasuk Deskewing)
            processed_img = preprocess_image(img)

            # Jalankan PaddleOCR
            result = ocr.ocr(processed_img, cls=True)

            page_content = []
            if result and result[0]:
                for line in result[0]:
                    try:
                        raw_text = str(line[1][0]).strip()
                        confidence = float(line[1][1])

                        # Confidence diperketat dikit ke 0.45 biar sampah gak masuk
                        if raw_text and confidence >= 0.45:
                            cleaned_line = clean_ocr_text(raw_text)
                            if cleaned_line:
                                page_content.append(cleaned_line)
                    except:
                        continue

            text_halaman = " ".join(page_content)
            text_halaman = clean_ocr_text(text_halaman)

            full_text_list.append(text_halaman)
            logger.info(f"Halaman {i + 1} diproses. Baris valid: {len(page_content)}")

        return full_text_list

    except Exception as e:
        logger.critical(f"Gagal ekstrak PDF: {str(e)}")
        import traceback

        traceback.print_exc()
        return []
