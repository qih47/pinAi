from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTRect, LTFigure

def extract_text_per_page_text_only(path: str) -> dict:
    try:
        pages_text = {}
        
        for i, page_layout in enumerate(extract_pages(path), 1):
            page_text = []
            
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    # Extract text dengan formatting
                    text = element.get_text().strip()
                    if text:
                        page_text.append(text)
                
                # Bisa handle gambar, tabel, dll
                elif isinstance(element, LTFigure):
                    # Handle figures/embedded objects
                    pass
            
            pages_text[i] = "\n".join(page_text)
        
        return pages_text
        
    except Exception as e:
        return {"error": str(e)}