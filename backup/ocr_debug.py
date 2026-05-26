import fitz  # PyMuPDF
import warnings
import time
from pathlib import Path
import json
import numpy as np
import os
import gc
from PIL import Image, ImageEnhance

# Matikan warning yang gak penting
warnings.filterwarnings("ignore")
os.environ["FLAGS_allocator_strategy"] = "auto_growth" # Optimasi memori Paddle

class PDFExtractor:
    def __init__(self):
        self.paddleocr_reader = None
        self.init_paddleocr()

    def init_paddleocr(self):
        print("🔄 Initializing PaddleOCR (GPU/A40 Mode)...")
        try:
            # Karena lu udah sukses setup CUDA 11.8 di A40, kita aktifkan GPU
            from paddleocr import PaddleOCR
            self.paddleocr_reader = PaddleOCR(
                lang="id",
                use_angle_cls=True,
                use_gpu=True,  # Pake A40 lu bro!
                show_log=False,
                gpu_mem=2000    # Alokasi 2GB VRAM
            )
            print("✅ PaddleOCR initialized on GPU successfully")
        except Exception as e:
            print(f"❌ PaddleOCR initialization failed: {e}")
            self.paddleocr_reader = None

    def _enhance_image_quality(self, img_array):
        """Preprocessing gambar agar teks lebih tegas tanpa merusak pixel"""
        try:
            img_pil = Image.fromarray(img_array).convert("L")
            # Tingkatkan kontras dan ketajaman secukupnya
            img_pil = ImageEnhance.Contrast(img_pil).enhance(1.5)
            img_pil = ImageEnhance.Sharpness(img_pil).enhance(1.3)
            return np.array(img_pil)
        except Exception as e:
            print(f"   ⚠️ Enhancement failed: {e}")
            return img_array

    def extract_with_paddleocr_enhanced(self, pdf_path: str) -> dict:
        if not self.paddleocr_reader:
            return {"error": "PaddleOCR not initialized", "success": False}

        try:
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            results = {}
            total_time = 0

            print(f"Processing {total_pages} pages with GPU Acceleration...")

            for page_num in range(total_pages):
                start_time = time.time()
                page = doc.load_page(page_num)

                # DPI 300 sudah sangat cukup untuk OCR akurat
                dpi = 300
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # Convert to numpy (RGB format)
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
                
                # Enhance
                img_processed = self._enhance_image_quality(img_array)

                # OCR dengan struktur "Safe Parsing"
                try:
                    # Parameter det=True, rec=True adalah default
                    ocr_result = self.paddleocr_reader.ocr(img_processed, cls=True)
                except Exception as ocr_error:
                    print(f"   ❌ OCR Page {page_num + 1} failed: {ocr_error}")
                    ocr_result = None

                page_text_lines = []
                
                # LOGIKA PARSING ANTI-ERROR INDEX
                # PaddleOCR result biasanya: [ [[coords], [text, conf]], [...] ]
                if ocr_result and isinstance(ocr_result, list):
                    for line_result in ocr_result:
                        if line_result is None: continue # Skip jika deteksi kosong
                        
                        for box_info in line_result:
                            try:
                                # box_info[0] = koordinat kotak
                                # box_info[1] = (teks, confidence)
                                if len(box_info) >= 2:
                                    text_data = box_info[1]
                                    if isinstance(text_data, (list, tuple)) and len(text_data) >= 1:
                                        text = str(text_data[0]).strip()
                                        conf = text_data[1] if len(text_data) > 1 else 1.0
                                        
                                        if text and conf > 0.4:
                                            page_text_lines.append(text)
                            except (IndexError, TypeError):
                                continue

                page_text = "\n".join(page_text_lines)
                page_time = time.time() - start_time
                total_time += page_time

                results[page_num + 1] = {
                    "text": page_text,
                    "char_count": len(page_text),
                    "line_count": len(page_text_lines),
                    "processing_time": round(page_time, 2)
                }

                print(f"   ✅ Page {page_num + 1}: {len(page_text_lines)} lines, {page_time:.1f}s")

                # Paksa Cleanup Memori VRAM/RAM
                del img_array, pix
                gc.collect()

            doc.close()
            return {
                "success": True,
                "total_pages": total_pages,
                "total_processing_time": round(total_time, 2),
                "pages": results,
                "method": "PaddleOCR-GPU-Stable"
            }

        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return {"error": str(e), "success": False}

    def save_results(self, results: dict, output_dir: str = "./outputs") -> dict:
        Path(output_dir).mkdir(exist_ok=True, parents=True)
        filename = results.get("metadata", {}).get("filename", "output").replace(".pdf", "")
        timestamp = int(time.time())
        
        output_path = Path(output_dir) / f"{filename}_{timestamp}.txt"
        
        with open(output_path, "w", encoding="utf-8") as f:
            for page_num, data in results["paddleocr"]["pages"].items():
                f.write(f"\n--- PAGE {page_num} ---\n{data['text']}\n")
        
        print(f"📄 Results saved to: {output_path}")
        return {"text_file": str(output_path)}

def main():
    pdf_path = "./ocr_file/SE Seragam.pdf"
    if not Path(pdf_path).exists():
        print(f"❌ File not found: {pdf_path}")
        return

    extractor = PDFExtractor()
    start_time = time.time()
    
    ocr_data = extractor.extract_with_paddleocr_enhanced(pdf_path)
    
    results = {
        "paddleocr": ocr_data,
        "metadata": {"filename": Path(pdf_path).name}
    }
    
    if ocr_data.get("success"):
        extractor.save_results(results)
        print(f"\n🎉 Selesai dalam {time.time() - start_time:.1f} detik!")

if __name__ == "__main__":
    main()