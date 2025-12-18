import fitz
from typing import Dict, List, Union

def analisa_pdf(path: str) -> Dict[str, Union[int, List[Dict], str]]:
    """
    Menganalisis PDF untuk menghitung rasio teks dan gambar per halaman.
    
    Args:
        path: Path ke file PDF
        
    Returns:
        Dictionary dengan informasi analisis atau error jika gagal
    """
    try:
        if not isinstance(path, str) or not path.lower().endswith('.pdf'):
            return {"pages": 0, "page_detail": [], "error": "Path harus berupa string dan file PDF"}
        
        doc = fitz.open(path)
        total_pages = doc.page_count
        pages_info = []
        
        for i in range(total_pages):
            page = doc.load_page(i)
            rect = page.rect
            
            width_mm = round(rect.width * 0.352778, 2)
            height_mm = round(rect.height * 0.352778, 2)
            page_area = rect.width * rect.height

            text_blocks = page.get_text("blocks")
            text_area = sum((block[2] - block[0]) * (block[3] - block[1])
                            for block in text_blocks if block[2] > block[0] and block[3] > block[1])

            image_area = 0
            for img in page.get_images(full=True):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n > 0:
                    image_area += pix.width * pix.height
                pix = None

            total_content = text_area + image_area
            if total_content > 0:
                text_ratio = min(round((text_area / page_area) * 100, 2), 100)
                image_ratio = min(round((image_area / page_area) * 100, 2), max(0, 100 - text_ratio))
            else:
                text_ratio = 0
                image_ratio = 0

            pages_info.append({
                "page": i + 1,
                "width_mm": width_mm,
                "height_mm": height_mm,
                "text_ratio": text_ratio,
                "image_ratio": image_ratio
            })

        return {
            "pages": total_pages,
            "page_detail": pages_info
        }

    except Exception as e:
        return {"pages": 0, "page_detail": [], "error": f"Error: {str(e)}"}
