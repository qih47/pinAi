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

# Force CPU mode jika diperlukan, tapi lu bilang pake A40 kan? 
# Pastikan use_gpu=True untuk performa maksimal di server
ocr = PaddleOCR(use_angle_cls=True, lang='id', use_gpu=True, show_log=False)

def clean_ocr_text(text):
    """
    Logic koreksi otomatis untuk menangani halusinasi OCR
    """
    if not text:
        return ""

    # 1. FIX BULAN ROMAWI: XL (40) gak ada, biasanya salah baca dari XI (11) atau XII (12)
    # Kita koreksi pola /XL/ tahun menjadi /XI/ tahun (atau XII tergantung mayoritas dokumen)
    text = re.sub(r'/XL/(20\d{2})', r'/XI/\1', text)
    text = re.sub(r'/X L/(20\d{2})', r'/XI/\1', text)

    # 2. FIX TYPO ALIEN: Berdasarkan contoh error lu tadi
    corrections = {
        "uep": "per",
        "wnan": "tuan",
        "pepu!d": "pindad",
        "e!ax": "kerja",
        "ueyeunbsuaa": "menggunakan",
        "ynanas": "seluruh",
        "otasied": "pindad", # OCR sering salah baca 'pindad' jadi 'otasied' kalau font miring

        # Tambahan dictionary kemungkinan kesalahan ocr
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
        "saudara/i": "saudara/i",
        "tahun20": "tahun 20",
        "alamatnyad": "alamatnya di",
        "nomorab": "nomor ab",
        "dalamrangka": "dalam rangka",
        "keperluan": "keperluan",
        "mekanikal": "mekanikal",
        "elektrikal": "elektrikal",
        "industri": "industri",
        "maksuda": "maksud",
        "sesua": "sesuai",
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
        "kipndad": "pindad"
    }
    
    # Gunakan regex untuk replace kata (case insensitive)
    for wrong, right in corrections.items():
        pattern = re.compile(re.escape(wrong), re.IGNORECASE)
        text = pattern.sub(right, text)

    # 3. CLEANING KARAKTER: Hapus noise garis atau simbol yang sering muncul di scan lecek
    text = re.sub(r'[|\\_~«»]', '', text)
    
    # 4. FIX SPASI BERLEBIH: Gabungin huruf jomblo (misal: "P e r a t u r a n")
    text = re.sub(r'(?<=\b\w)\s(?=\w\b)', '', text)
    
    # Clean multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def preprocess_image(img):
    """
    Meningkatkan kontras dan ketajaman sebelum masuk ke OCR
    """
    # Convert ke grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Denoising (ngilangin bintik-bintik scan)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    
    # Adaptive Thresholding (bikin teks item putih tegas)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Balikin ke 3-channel karena PaddleOCR butuh format BGR
    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

def extract_text_per_page(pdf_path):
    if not os.path.exists(pdf_path):
        logger.error(f"File PDF tidak ditemukan: {pdf_path}")
        return []

    try:
        # Convert PDF ke Image (DPI 200 cukup imbang antara speed & akurasi)
        pages = convert_from_path(pdf_path, dpi=200)
        full_text_list = []

        for i, page in enumerate(pages):
            # Convert PIL ke OpenCV format
            img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
            
            # Pre-processing
            processed_img = preprocess_image(img)

            # Jalankan PaddleOCR
            result = ocr.ocr(processed_img, cls=True)

            page_content = []
            if result and result[0]:
                for line in result[0]:
                    try:
                        raw_text = str(line[1][0]).strip()
                        confidence = float(line[1][1])

                        # Hanya ambil teks dengan confidence di atas 0.4 biar gak banyak sampah
                        if raw_text and confidence >= 0.4:
                            # Langsung koreksi tiap baris
                            cleaned_line = clean_ocr_text(raw_text)
                            if cleaned_line:
                                page_content.append(cleaned_line)
                    except:
                        continue

            # Gabungkan baris jadi satu paragraf halaman
            text_halaman = " ".join(page_content)
            
            # Final cleaning untuk satu halaman
            text_halaman = clean_ocr_text(text_halaman)
            
            full_text_list.append(text_halaman)
            logger.info(f"Halaman {i + 1} diproses. Baris: {len(page_content)}")

        return full_text_list

    except Exception as e:
        logger.critical(f"Gagal ekstrak PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return []