import fitz  # PyMuPDF
import warnings
import time
from pathlib import Path
import json
import torch
import numpy as np
import gc
import tempfile
import psycopg2
from PIL import Image
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

warnings.filterwarnings('ignore')


# ================================
# FUNGSI AMBIL FILE TERBARU DARI DB
# ================================
def get_latest_ocr_file(db_config=None):
    """
    Ambil nama file ocr_file terbaru dari tabel history_file
    db_config: dict {host, database, user, password}
    """
    if db_config is None:
        db_config = {
            "host": "localhost",
            "database": "ragdb",
            "user": "pindadai",
            "password": "Pindad123!"
        }
    
    try:
        conn = psycopg2.connect(**db_config)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ocr_file
                FROM history_file
                WHERE ocr_file IS NOT NULL
                ORDER BY created_time DESC
                LIMIT 1
            """)
            row = cur.fetchone()
        conn.close()
        if row:
            latest_file = Path(row[0])
            if latest_file.exists():
                print(f"📄 Found latest OCR file from DB: {latest_file}")
                return str(latest_file)
            else:
                print(f"⚠ File from DB not found on disk: {latest_file}")
                return None
        else:
            print("⚠ No OCR file found in DB")
            return None
    except Exception as e:
        print(f"❌ Failed to fetch latest OCR file from DB: {e}")
        return None

def update_latest_koreksi_file(file_path, db_config=None):
    """
    Update kolom koreksi_file pada record ID terbaru di tabel history_file
    """
    if db_config is None:
        db_config = {
            "host": "localhost",
            "database": "ragdb",
            "user": "pindadai",
            "password": "Pindad123!"
        }
    
    try:
        conn = psycopg2.connect(**db_config)
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE history_file
                SET koreksi_file = %s
                WHERE id = (SELECT id FROM history_file ORDER BY created_time DESC LIMIT 1)
            """, (file_path,))
            conn.commit()
        conn.close()
        print(f"✅ Updated latest history_file record with koreksi_file: {file_path}")
    except Exception as e:
        print(f"❌ Failed to update koreksi_file in DB: {e}")


class PDFExtractor:
    def __init__(self):
        """
        PDF extractor menggunakan DocTR OCR (auto GPU/CPU detection).
        """
        self.model = None
        self.device = None
        self.temp_dir = None
        self.init_doctr()

    def init_doctr(self):
        """Initialize DocTR OCR model"""
        print("🔄 Initializing DocTR OCR Engine...")
        try:
            # Auto detect device
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"   Detected device: {self.device.upper()}")
            
            # Initialize model
            self.model = ocr_predictor(
                det_arch='db_resnet50',     # Detector architecture
                reco_arch='crnn_vgg16_bn',  # Recognizer architecture
                pretrained=True,
                assume_straight_pages=True  # Assume straight pages, faster
            ).to(self.device)
            
            # Set to evaluation mode
            self.model.eval()
            
            # Create temp directory for images
            self.temp_dir = tempfile.mkdtemp(prefix="doctr_")
            
            print(f"✅ DocTR OCR initialized successfully")
            print(f"   Detector: db_resnet50, Recognizer: crnn_vgg16_bn")
            print(f"   Temp dir: {self.temp_dir}")
            
        except Exception as e:
            print(f"❌ DocTR initialization failed: {e}")
            print("   Please install: pip install python-doctr[tf] or python-doctr[torch]")
            self.model = None

    def _render_page_to_image(self, page, dpi=1200):
        """Render PDF page to numpy array"""
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convert to numpy array
        img_array = np.frombuffer(pix.samples, dtype=np.uint8)
        img_array = img_array.reshape(pix.height, pix.width, pix.n)
        
        # Handle alpha channel
        if pix.n == 4:
            # RGBA to RGB
            img_array = img_array[:, :, :3]
        
        # Cleanup
        del pix
        gc.collect()
        
        return img_array

    def _preprocess_image(self, img_array):
        """Preprocess image for better OCR accuracy"""
        try:
            if len(img_array.shape) == 2:
                # Grayscale to RGB
                img_array = np.stack([img_array] * 3, axis=-1)
            elif img_array.shape[2] == 4:
                # RGBA to RGB
                img_array = img_array[:, :, :3]
            elif img_array.shape[2] == 1:
                # Single channel to RGB
                img_array = np.stack([img_array[:, :, 0]] * 3, axis=-1)
            
            # Resize if too large
            max_size = 2000
            height, width = img_array.shape[:2]
            if max(height, width) > max_size:
                ratio = max_size / max(height, width)
                new_height = int(height * ratio)
                new_width = int(width * ratio)
                img_pil = Image.fromarray(img_array)
                img_pil = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
                img_array = np.array(img_pil)
            
            return img_array
            
        except Exception as e:
            print(f"   ⚠️ Image preprocessing failed: {e}")
            return img_array

    def _save_image_temp(self, img_array, page_num):
        """Save image to temporary file for DocTR"""
        try:
            img_pil = Image.fromarray(img_array)
            temp_path = Path(self.temp_dir) / f"page_{page_num:03d}.png"
            img_pil.save(temp_path, format='PNG', optimize=True)
            return str(temp_path)
        except Exception as e:
            print(f"   ⚠️ Failed to save temp image: {e}")
            return None

    def extract_with_doctr(self, pdf_path: str) -> dict:
        """Extract text from PDF using DocTR OCR"""
        if not self.model:
            return {"error": "DocTR model not initialized", "success": False}

        try:
            # Open PDF file
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            results = {}
            
            print(f"📄 Processing {total_pages} pages using DocTR OCR...")
            print(f"   Device: {self.device.upper()}, DPI: 300")

            # Save all pages as temporary image files
            print("   Step 1: Rendering and saving pages as images...")
            temp_files = []
            render_times = []
            
            for page_num in range(total_pages):
                start_render = time.time()
                page = doc.load_page(page_num)
                
                # Render page to image
                img_array = self._render_page_to_image(page, dpi=1200)
                
                # Preprocess image
                img_array = self._preprocess_image(img_array)
                
                # Save to temporary file
                temp_path = self._save_image_temp(img_array, page_num + 1)
                if temp_path:
                    temp_files.append(temp_path)
                
                render_time = time.time() - start_render
                render_times.append(render_time)
                
                if (page_num + 1) % 5 == 0 or (page_num + 1) == total_pages:
                    print(f"      Rendered {page_num + 1}/{total_pages} pages...")
            
            doc.close()
            
            if not temp_files:
                return {"error": "Failed to create image files", "success": False}
            
            avg_render_time = sum(render_times) / len(render_times) if render_times else 0
            print(f"   ✓ All pages saved as images (avg: {avg_render_time:.2f}s per page)")
            print(f"   Temp files: {len(temp_files)} files")
            
            # Method 1: Try batch processing first
            print("   Step 2: Running DocTR OCR (batch mode)...")
            start_ocr = time.time()
            
            try:
                # Use file paths for DocTR
                doc_file = DocumentFile.from_images(temp_files)
                
                # Run OCR inference
                with torch.no_grad():
                    doctr_result = self.model(doc_file)
                
                inference_time = time.time() - start_ocr
                print(f"   ✓ DocTR inference completed in {inference_time:.1f}s")
                
                # Extract and format results
                print("   Step 3: Extracting text from results...")
                total_time = inference_time + sum(render_times)
                
                for idx, page_result in enumerate(doctr_result.pages):
                    page_text = ""
                    
                    # Extract text from DocTR results
                    if hasattr(page_result, 'blocks'):
                        for block in page_result.blocks:
                            if hasattr(block, 'lines'):
                                for line in block.lines:
                                    if hasattr(line, 'words'):
                                        line_text = " ".join([word.value for word in line.words if hasattr(word, 'value')])
                                        page_text += line_text + "\n"
                    
                    page_text = page_text.strip()
                    lines = page_text.split("\n") if page_text else []
                    
                    page_time = render_times[idx] + (inference_time / total_pages)
                    
                    results[idx + 1] = {
                        "text": page_text,
                        "char_count": len(page_text),
                        "word_count": len(page_text.split()),
                        "line_count": len(lines),
                        "processing_time": round(page_time, 2),
                        "render_time": round(render_times[idx], 2),
                        "dpi_used": 1200,
                        "enhancement": "DocTR-Batch",
                        "confidence": "N/A"
                    }
                    
                    if (idx + 1) % 5 == 0 or (idx + 1) == total_pages:
                        print(f"      Processed {idx + 1}/{total_pages} pages...")
                
            except Exception as batch_error:
                print(f"   ❌ Batch processing failed: {batch_error}")
                print("   Trying individual page processing...")
                results = self._extract_pages_individually(temp_files, render_times)
            
            # Calculate statistics
            total_chars = sum(p["char_count"] for p in results.values())
            total_words = sum(p["word_count"] for p in results.values())
            total_lines = sum(p["line_count"] for p in results.values())
            total_time = sum(p.get("processing_time", 0) for p in results.values())

            return {
                "success": True,
                "total_pages": total_pages,
                "total_processing_time": round(total_time, 2),
                "avg_time_per_page": round(total_time / total_pages, 2) if total_pages > 0 else 0,
                "render_time_total": round(sum(render_times), 2),
                "total_characters": total_chars,
                "total_words": total_words,
                "total_lines": total_lines,
                "pages": results,
                "method": "DocTR-OCR",
                "config": {
                    "dpi": 1200,
                    "device": self.device,
                    "detector": "db_resnet50",
                    "recognizer": "crnn_vgg16_bn",
                    "processing_mode": "Batch" if len(results) > 0 and "Batch" in str(results[1].get("enhancement", "")) else "Individual"
                }
            }

        except Exception as e:
            print(f"❌ OCR extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "success": False}

    def _extract_pages_individually(self, temp_files, render_times):
        """Fallback method: Process pages individually"""
        print("   Using individual page processing...")
        results = {}
        
        for idx, temp_path in enumerate(temp_files):
            start_time = time.time()
            page_num = idx + 1
            
            try:
                # Process single image
                doc_file = DocumentFile.from_images([temp_path])
                with torch.no_grad():
                    page_result = self.model(doc_file)
                
                # Extract text
                page_text = ""
                if page_result.pages:
                    page_data = page_result.pages[0]
                    if hasattr(page_data, 'blocks'):
                        for block in page_data.blocks:
                            if hasattr(block, 'lines'):
                                for line in block.lines:
                                    if hasattr(line, 'words'):
                                        line_text = " ".join([word.value for word in line.words])
                                        page_text += line_text + "\n"
                
                page_text = page_text.strip()
                
            except Exception as page_error:
                print(f"   ⚠️ Page {page_num} failed: {page_error}")
                page_text = ""
            
            lines = page_text.split("\n") if page_text else []
            page_time = time.time() - start_time
            
            results[page_num] = {
                "text": page_text,
                "char_count": len(page_text),
                "word_count": len(page_text.split()),
                "line_count": len(lines),
                "processing_time": round(page_time, 2),
                "render_time": round(render_times[idx], 2),
                "dpi_used": 1200,
                "enhancement": "DocTR-Individual"
            }
            
            print(f"      Page {page_num}: {len(lines)} lines, {len(page_text)} chars")
        
        return results

    def save_results(self, results: dict, output_dir: str = "./outputs") -> dict:
        """Save OCR results to files in outputs/ folder"""
        # Ensure outputs directory exists
        Path(output_dir).mkdir(exist_ok=True, parents=True)
        
        # Get filename from metadata
        metadata = results.get("metadata", {})
        filename = metadata.get("filename", "output")
        if isinstance(filename, str):
            filename = Path(filename).stem
        else:
            filename = "doctr_output"
        
        timestamp = int(time.time())
        saved_files = {}

        # Check if we have OCR results
        ocr_result = results.get("paddleocr", {})
        if not ocr_result.get("success"):
            # Try direct result
            ocr_result = results
        
        if ocr_result.get("success"):
            # Save text file
            text_content = f"DocTR OCR Results\n"
            text_content += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            text_content += f"Method: {ocr_result.get('method', 'DocTR-OCR')}\n"
            text_content += f"Device: {ocr_result.get('config', {}).get('device', 'CPU')}\n"
            text_content += f"Total Pages: {ocr_result.get('total_pages', 0)}\n"
            text_content += f"Total Time: {ocr_result.get('total_processing_time', 0)}s\n"
            text_content += "=" * 60 + "\n\n"

            for page_num in sorted(ocr_result.get("pages", {}).keys()):
                page_data = ocr_result["pages"][page_num]
                text_content += f"\n{'='*60}\n"
                text_content += f"PAGE {page_num}\n"
                text_content += f"{'='*60}\n\n"
                text_content += page_data.get("text", "")
                text_content += f"\n\n[Chars: {page_data.get('char_count', 0)} | "
                text_content += f"Words: {page_data.get('word_count', 0)} | "
                text_content += f"Lines: {page_data.get('line_count', 0)} | "
                text_content += f"Time: {page_data.get('processing_time', 0)}s | "
                text_content += f"DPI: {page_data.get('dpi_used', 1200)}]\n"

            text_file = Path(output_dir) / f"{filename}_doctr_{timestamp}.txt"
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(text_content)
            print(f"📄 DocTR text saved to outputs/: {text_file.name}")
            saved_files["text"] = str(text_file)

        # Save JSON results
        json_file = Path(output_dir) / f"{filename}_doctr_results_{timestamp}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"📊 JSON results saved to outputs/: {json_file.name}")
        saved_files["json"] = str(json_file)

        # Cleanup temp directory
        if hasattr(self, 'temp_dir') and self.temp_dir:
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                print(f"🧹 Cleaned up temp directory: {self.temp_dir}")
            except:
                pass

        return saved_files


def main():
    """Main function"""
    # Try multiple possible PDF paths
    # Cek DB dulu
    pdf_path = get_latest_ocr_file()

    # Jika tidak ada file di DB, hentikan program dengan log
    if not pdf_path:
        print("❌ No OCR file found in history_file DB. Exiting...")
        return

    print("="*70)
    print("PDF OCR EXTRACTION TOOL - DOCTR OCR")
    print("="*70)
    print(f"📄 Processing: {pdf_path}")
    
    # Initialize extractor
    extractor = PDFExtractor()
    
    if not extractor.model:
        print("❌ Failed to initialize DocTR model. Exiting...")
        return
    
    # Extract text
    start_time = time.time()
    
    # Get OCR results
    ocr_results = extractor.extract_with_doctr(pdf_path)
    
    # Create complete results structure
    results = {
        "paddleocr": ocr_results,  # Keep key name compatible
        "metadata": {
            "filename": Path(pdf_path).name,
            "extraction_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input_file": pdf_path,
            "tool": "DocTR OCR Extractor v1.0"
        }
    }
    
    total_time = time.time() - start_time
    
    print("\n" + "="*70)
    print("EXTRACTION SUMMARY")
    print("="*70)
    
    if ocr_results.get("success"):
        print(f"✅ SUCCESS: Processed {ocr_results.get('total_pages', 0)} pages")
        print(f"⏱️  Total time: {total_time:.1f}s")
        
        if 'avg_time_per_page' in ocr_results:
            print(f"   Average per page: {ocr_results['avg_time_per_page']:.1f}s")
        
        print(f"📊 Total characters: {ocr_results.get('total_characters', 0):,}")
        print(f"📊 Total words: {ocr_results.get('total_words', 0):,}")
        
        if 'render_time_total' in ocr_results:
            print(f"🖼️  Rendering time: {ocr_results['render_time_total']:.1f}s")
        
        # Save results to file_koreksi folder
        saved_files = extractor.save_results(results, output_dir="./file_koreksi")

        # Ambil path file koreksi (misal text file)
        koreksi_file_path = saved_files.get("text")
        if koreksi_file_path:
            # Update DB
            update_latest_koreksi_file(koreksi_file_path)
        
        print(f"\n💾 Files saved to 'outputs/' folder:")
        for key, path in saved_files.items():
            if path:
                print(f"   • {Path(path).name}")
        
        # Show full path of first file
        if saved_files.get("text"):
            print(f"\n📁 Full path: {saved_files['text']}")
                
    else:
        print(f"❌ FAILED: {ocr_results.get('error', 'Unknown error')}")
    
    print("="*70)


if __name__ == "__main__":
    # Show installation instructions
    print("📦 Required installation:")
    print("   pip install python-doctr[tf]   # for TensorFlow")
    print("   pip install python-doctr[torch] # for PyTorch (recommended)")
    print("   pip install PyMuPDF pillow torch")
    print()
    
    # Ensure outputs directory exists
    Path("./outputs").mkdir(exist_ok=True)
    
    # Run main program
    main()