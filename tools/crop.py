import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image
import numpy as np
import cv2
from io import BytesIO
import psycopg2  # untuk PostgreSQL

# ================================
# KONFIGURASI CROP (MM)
# ================================
CROP_LEFT_MM = 10
CROP_RIGHT_MM = 10
CROP_TOP_MM = 15
CROP_BOTTOM_MM = 15
# ================================

# ================================
# KONFIGURASI DATABASE
# ================================
def get_db_connection():
    return psycopg2.connect(
        host="localhost", database="ragdb", user="pindadai", password="Pindad123!"
    )

def save_history(ocr_file: str, koreksi_file=None, clean_file=None):
    """Simpan nama file ke tabel history_file"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO history_file (ocr_file, koreksi_file, clean_file)
                VALUES (%s, %s, %s)
            """, (ocr_file, koreksi_file, clean_file))
            conn.commit()
    print(f"📌 Nama file disimpan ke database: {ocr_file}")

# ================================
# FUNGSI ENHANCE IMAGE
# ================================
def enhance_image(pil_img: Image.Image) -> Image.Image:
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    img = cv2.fastNlMeansDenoisingColored(img, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21)
    kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
    img = cv2.filter2D(img, -1, kernel)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img)

# ================================
# FUNGSI CROP + ENHANCE PDF
# ================================
def crop_and_enhance_pdf(input_pdf: str, output_pdf: str,
                         crop_left_mm=0, crop_right_mm=0,
                         crop_top_mm=0, crop_bottom_mm=0):

    mm_to_pt = 72 / 25.4
    left = crop_left_mm * mm_to_pt
    right = crop_right_mm * mm_to_pt
    top = crop_top_mm * mm_to_pt
    bottom = crop_bottom_mm * mm_to_pt

    print("Processing PDF (crop + enhance)...")
    original = fitz.open(input_pdf)
    out_doc = fitz.open()

    for page_num, page in enumerate(original, start=1):
        # 🔑 Gunakan mediabox sebagai acuan sebenarnya
        media_rect = page.mediabox

        # Hitung cropped_rect dari mediabox
        cropped_rect = fitz.Rect(
            media_rect.x0 + left,
            media_rect.y0 + top,
            media_rect.x1 - right,
            media_rect.y1 - bottom,
        )

        # 🔒 Clamp ke dalam mediabox (pastikan tidak keluar)
        cropped_rect = cropped_rect & media_rect  # intersect operator

        if cropped_rect.width <= 10 or cropped_rect.height <= 10:
            print(f"   ⚠ Page {page_num}: Crop terlalu besar, gunakan mediabox penuh")
            cropped_rect = media_rect

        # Set cropbox (aman karena sudah di-clamp)
        page.set_cropbox(cropped_rect)

        # Render ke gambar
        pix = page.get_pixmap(dpi=300)
        mode = "RGB" if pix.alpha == 0 else "RGBA"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        img = enhance_image(img)

        # Simpan ke PDF baru
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        img_bytes = buf.getvalue()
        buf.close()

        img_pdf = fitz.open()
        img_page = img_pdf.new_page(width=img.width, height=img.height)
        img_page.insert_image(img_page.rect, stream=img_bytes)
        out_doc.insert_pdf(img_pdf)
        img_pdf.close()
        print(f"   Page {page_num} processed ({img.width}x{img.height})")

    original.close()
    out_doc.save(output_pdf, deflate=True)
    out_doc.close()
    print(f"✅ PDF berhasil diproses dan disimpan: {output_pdf}")

    save_history(str(output_pdf))

# ================================
# MAIN
# ================================
def main():
    input_folder = Path("temp_uploads")
    pdf_files = list(input_folder.glob("*.pdf"))

    if not pdf_files:
        print("❌ Tidak ada file PDF di folder temp_uploads")
        return

    input_path = pdf_files[0]
    print(f"📄 Memotong file PDF: {input_path.name}")

    filename = input_path.stem
    output_folder = Path("ocr_file")
    output_folder.mkdir(exist_ok=True)
    output_path = output_folder / f"{filename}.pdf"

    crop_and_enhance_pdf(
        input_pdf=str(input_path),
        output_pdf=str(output_path),
        crop_left_mm=CROP_LEFT_MM,
        crop_right_mm=CROP_RIGHT_MM,
        crop_top_mm=CROP_TOP_MM,
        crop_bottom_mm=CROP_BOTTOM_MM,
    )

if __name__ == "__main__":
    print("=" * 40)
    print(" PDF CROPPER + ENHANCE MODE")
    print("=" * 40)
    main()
