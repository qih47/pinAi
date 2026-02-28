import fitz  # PyMuPDF
import base64
from PIL import Image
import io
import tempfile
import os
from typing import Optional
from backend.utils.embedding_utils import embedding_manager


class OCRService:
    @staticmethod
    async def process_pdf_attachment_to_ocr(attachment: dict, npp: Optional[str] = None, 
                                          session_id: Optional[int] = None, 
                                          get_embedding_func=None) -> str:
        """
        Process PDF attachment for OCR - simplified version
        This is a placeholder implementation that would integrate with the OCR processor mentioned in the original code
        """
        try:
            # Extract base64 data from attachment
            data = attachment.get("data", "")
            if "," in data:
                # Remove data URL prefix if present
                data = data.split(",", 1)[1]
            
            # Decode base64 data
            pdf_bytes = base64.b64decode(data)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(pdf_bytes)
                temp_pdf_path = temp_pdf.name
            
            # Process PDF with PyMuPDF
            doc = fitz.open(temp_pdf_path)
            extracted_text = ""
            
            # Extract text from first few pages (to avoid performance issues)
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                extracted_text += page.get_text() + "\n"
            
            doc.close()
            
            # Clean up temp file
            os.unlink(temp_pdf_path)
            
            return extracted_text.strip() if extracted_text.strip() else "[PDF tidak mengandung teks]"
            
        except Exception as e:
            print(f"OCR Processing Error: {e}")
            return f"[Ekstraksi gagal: {str(e)}]"
    
    @staticmethod
    async def extract_with_qwen3_vl(filepath: str, filetype: str) -> str:
        """Extract text using vision model - placeholder implementation"""
        try:
            if filetype == "pdf":
                doc = fitz.open(filepath)
                text = "\n".join([page.get_text() for page in doc])
                doc.close()
                return text.strip() if text.strip() else "[PDF tidak mengandung teks]"
            
            elif filetype in ["png", "jpg", "jpeg"]:
                # Use PIL for image processing
                image = Image.open(filepath)
                # In a real implementation, we would use pytesseract or similar
                # For now, return a placeholder
                return f"[Gambar {filetype.upper()} diupload]"
            
            elif filetype == "txt":
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read().strip()
            
            else:
                return f"[File {filetype.upper()} diupload]"
                
        except Exception as e:
            return f"[Ekstraksi gagal: {str(e)}]"
    
    @staticmethod
    async def generate_summary(text: str) -> str:
        """Generate summary of text - placeholder implementation"""
        try:
            # In a real implementation, this would call an AI model
            # For now, return a simple truncation
            if len(text) <= 150:
                return text
            else:
                # Return first 150 characters followed by ...
                return text[:150] + "..."
        except:
            return "Ringkasan tidak tersedia."