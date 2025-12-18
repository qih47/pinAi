import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image, ImageFilter
import numpy as np
import cv2
from io import BytesIO

# ================================
# KONFIGURASI CROP (MM)
# ================================
CROP_LEFT_MM = 15
CROP_RIGHT_MM = 15
CROP_TOP_MM = 25
CROP_BOTTOM_MM = 25
# ================================

def enhance_image(pil_img: Image.Image) -> Image.Image:
    """Enhance image: sharpen + denoise"""
    # Convert ke OpenCV
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # Denoise (fastNlMeans)
    img = cv2.fastNlMeansDenoisingColored(img, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21)

    # Sharpen
    kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
    img = cv2.filter2D(img, -1, kernel)

    # Balik ke PIL
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img)

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
        rect = page.rect
        cropped_rect = fitz.Rect(
            rect.x0 + left,
            rect.y0 + top,
            rect.x1 - right,
            rect.y1 - bottom,
        )
        if cropped_rect.width <= 0 or cropped_rect.height <= 0:
            raise ValueError("⚠ Crop terlalu besar — halaman bisa hilang!")

        page.set_cropbox(cropped_rect)

        # Render page → pixmap
        pix = page.get_pixmap(dpi=300)

        # Convert pixmap → PIL
        mode = "RGB" if pix.alpha == 0 else "RGBA"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)

        # Enhance
        img = enhance_image(img)

        # Compress dan masukkan ke PDF baru
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

def main():
    input_path = "outputs/SE Seragam.pdf"
    if not Path(input_path).exists():
        print(f"❌ File tidak ditemukan: {input_path}")
        return

    filename = Path(input_path).stem
    output_folder = Path("outputs")
    output_folder.mkdir(exist_ok=True)
    output_path = output_folder / f"{filename}_enhanced.pdf"

    crop_and_enhance_pdf(
        input_pdf=input_path,
        output_pdf=str(output_path),
        crop_left_mm=CROP_LEFT_MM,
        crop_right_mm=CROP_RIGHT_MM,
        crop_top_mm=CROP_TOP_MM,
        crop_bottom_mm=CROP_BOTTOM_MM,
    )

if __name__ == "__main__":
    print("=" * 60)
    print(" PDF CROPPER + ENHANCE MODE")
    print("=" * 60)
    main()
