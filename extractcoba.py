import os
import pdfplumber
import easyocr
import numpy as np
from PIL import Image
import re
import torch
import requests
import time
import pymupdf  # Added from test.py
from typing import List
from pathlib import Path
import logging

# Setup logging seperti test.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_cuda_availability():
    """Cek ketersediaan CUDA - DIAMBIL DARI test.py"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"✅ CUDA tersedia: {gpu_name} ({gpu_memory:.1f} GB)")
        return True, device
    else:
        logger.info("❌ CUDA tidak tersedia, menggunakan CPU")
        return False, device

def detect_pdf_type(filepath: str):
    """Deteksi tipe PDF: text-based vs image-based - DIAMBIL DARI test.py"""
    logger.info("🔍 Starting PDF type detection")
    try:
        with pymupdf.open(filepath) as doc:
            total_text_len = 0
            total_images = 0
            total_pages = len(doc)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                page_text = page.get_text("text").strip()
                total_text_len += len(page_text)
                images = page.get_images()
                total_images += len(images)
                logger.info(f"📄 Page {page_num + 1}: {len(page_text)} chars, {len(images)} images")
            
            avg_text_per_page = total_text_len / total_pages if total_pages > 0 else 0
            is_scanned = avg_text_per_page < 100 or total_images > total_pages * 2
            
            pdf_type = "scanned" if is_scanned else "text-based"
            confidence = True if (is_scanned and total_images > 0) or (not is_scanned and avg_text_per_page > 200) else False
            
            logger.info(f"📊 PDF Type: {pdf_type}, Confidence: {confidence}, Avg chars per page: {avg_text_per_page:.1f}, Total images: {total_images}")
            return pdf_type, confidence
        
    except Exception as e:
        logger.error(f"❌ Error detecting PDF type: {e}")
        return "unknown", False

def extract_page_with_ocr_retry(page, page_num: int, reader):
    """OCR retry dengan multiple attempts - DIAMBIL DARI test.py"""
    logger.info(f"🔍 Starting OCR retry for page {page_num}")
    
    ocr_attempts = [
        {"dpi": 300, "paragraph": True, "min_size": 10},
        {"dpi": 400, "paragraph": False, "min_size": 5},
        {"dpi": 300, "paragraph": True, "text_threshold": 0.5},
    ]
    
    best_ocr_text = ""
    
    for attempt_num, params in enumerate(ocr_attempts, 1):
        try:
            logger.info(f"  📸 OCR Attempt {attempt_num} for page {page_num} with params: {params}")
            
            pix = page.get_pixmap(dpi=params["dpi"])
            img_data = pix.tobytes("png")
            
            ocr_result = reader.readtext(
                img_data,
                detail=0,
                paragraph=params.get("paragraph", True),
                min_size=params.get("min_size", 10),
                text_threshold=params.get("text_threshold", 0.7),
                canvas_size=4000
            )
            
            current_ocr_text = "\n".join([text for text in ocr_result if text.strip()])
            
            logger.info(f"  📊 Attempt {attempt_num}: {len(current_ocr_text)} chars")
            
            if len(current_ocr_text) > len(best_ocr_text):
                best_ocr_text = current_ocr_text
                
            if len(current_ocr_text) > 200:
                logger.info(f"  ✅ Attempt {attempt_num} sufficient, stopping retries")
                break
                
        except Exception as e:
            logger.error(f"  ❌ OCR Attempt {attempt_num} failed: {e}")
            continue
    
    return best_ocr_text

def extract_text_comprehensive(filepath: str, pdf_type: str, reader):
    """Ekstrak text dengan auto-retry OCR - DIAMBIL DARI test.py"""
    logger.info(f"📑 Comprehensive text extraction for {pdf_type} PDF")
    
    all_text = ""
    problematic_pages = []
    
    try:
        with pymupdf.open(filepath) as doc:
            total_pages = len(doc)
            logger.info(f"📄 Processing {total_pages} pages")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                logger.info(f"🔄 Processing page {page_num + 1}")
                
                normal_text = page.get_text("text").strip()
                
                if len(normal_text) > 100:
                    page_content = f"=== PAGE {page_num + 1} ===\n{normal_text}"
                    all_text += page_content + "\n\n"
                    logger.info(f"✅ Page {page_num + 1}: {len(normal_text)} chars")
                    
                else:
                    logger.warning(f"⚠️ Page {page_num + 1}: insufficient text ({len(normal_text)} chars) - SWITCHING TO OCR")
                    problematic_pages.append(page_num + 1)
                    
                    ocr_text = extract_page_with_ocr_retry(page, page_num + 1, reader)
                    
                    if ocr_text and len(ocr_text) > 50:
                        page_content = f"=== PAGE {page_num + 1} (OCR) ===\n{ocr_text}"
                        all_text += page_content + "\n\n"
                        logger.info(f"✅ Page {page_num + 1} OCR success: {len(ocr_text)} chars")
                    else:
                        fallback_text = normal_text if normal_text else "[LOW QUALITY TEXT - NEEDS MANUAL REVIEW]"
                        page_content = f"=== PAGE {page_num + 1} (LOW QUALITY) ===\n{fallback_text}"
                        all_text += page_content + "\n\n"
                        logger.warning(f"⚠️ Page {page_num + 1} OCR also failed, using low quality text")
        
        if problematic_pages:
            logger.info(f"📊 Extraction summary: {total_pages - len(problematic_pages)} pages normal, {len(problematic_pages)} pages used OCR: {problematic_pages}")
        else:
            logger.info(f"📊 Extraction summary: All {total_pages} pages extracted normally")
            
        return all_text.strip()
        
    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        return f"=== EXTRACTION ERROR ===\n{str(e)}"

def clean_text_advanced(text: str):
    """Advanced text cleaning yang menjaga struktur - DIAMBIL DARI test.py"""
    logger.info("🧹 Cleaning text while preserving structure")
    original_len = len(text)
    
    text = re.sub(r'=== PAGE \d+ ===', '\n=== PAGE \\g<0> ===\n', text)
    
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    replacements = {
        r'\bPT\s+Pindad\b': 'PT Pindad',
        r'\bPindad\s+\(Persero\)': 'Pindad (Persero)',
        r'\bSkep\b': 'SKEP',
        r'\bSE\s*\/': 'SE/',
        r'\bSKEP\s*\/': 'SKEP/',
        r'(\d)\s*\/\s*([A-Z])': '\\1/\\2',
        r'(\w)\1{2,}': lambda m: m.group(0)[0],
    }
    
    for pattern, replacement in replacements.items():
        if callable(replacement):
            text = re.sub(pattern, replacement, text)
        else:
            text = re.sub(pattern, replacement, text)
    
    text = re.sub(r'(?<=\n)(\d+\.)\s*([A-Z])', '\\1 \\2', text)
    text = re.sub(r'(?<=\n)([a-z]\.)\s*([A-Z])', '\\1 \\2', text)
    
    cleaned_len = len(text)
    logger.info(f"✅ Text cleaning completed: {original_len} → {cleaned_len} chars (structure preserved)")
    return text.strip()

def validate_text_quality(text: str):
    """Validasi kualitas extracted text - DIAMBIL DARI test.py"""
    logger.info("🔎 Validating text quality")
    issues = []
    
    if not text or len(text.strip()) == 0:
        logger.error("❌ Empty text")
        return False, ["Empty text"]
    
    if len(text.strip()) < 100:
        issues.append("Text too short")
        logger.warning(f"⚠️ Text too short: {len(text.strip())} chars")
    
    weird_chars = re.findall(r'[^\w\s.,!?;:()\-@#$%&*+/=]', text)
    weird_ratio = len(weird_chars) / len(text) if text else 0
    if weird_ratio > 0.1:
        issues.append("Too many unusual characters")
        logger.warning(f"⚠️ Too many unusual characters: {weird_ratio:.2%}")
    
    newline_ratio = text.count('\n') / len(text) if text else 0
    if newline_ratio > 0.1:
        issues.append("Poor formatting")
        logger.warning(f"⚠️ Poor formatting: newline ratio {newline_ratio:.2%}")
    
    is_valid = len(issues) == 0
    logger.info(f"✅ Text quality validation: {'PASS' if is_valid else 'FAIL'} - Issues: {issues}")
    return is_valid, issues

def correct_text_batch(chunks: List[str]):
    """Koreksi text dalam batch untuk efisiensi - DIAMBIL DARI test.py"""
    logger.info(f"🔧 Starting text correction for {len(chunks)} chunks")
    corrected_chunks = []
    
    for i in range(0, len(chunks), 2):
        batch = chunks[i:i+2]
        batch_num = (i // 2) + 1
        logger.info(f"🔄 Processing correction batch {batch_num}: chunks {i+1}-{i+len(batch)}")
        
        batch_prompt = """Perbaiki teks berikut dengan aturan:
1. Benarkan ejaan dan typo
2. Benarkan kalimat yang sama jangan sampai ada duplikat
3. KOREKSI KHUSUS KATA:
   - Kata yang kurang huruf seperti "Finger Pint" harusnya "Finger Print"
   - Kata yang hurufnya berubah jadi angka atau simbol seperti "tD Card" harusnya "ID Card" atau "Parki/" harusnya "Parkir" dan kata lain yang sejenis
4. KOREKSI KHUSUS FORMAT NOMOR SURAT:
   - SURAT EDARAN (SE): format "SE/1/P/BD/IV/2016" → koreksi "SE/1/P/BDllVl2016" jadi "SE/1/P/BD/IV/2016"
   - SURAT KEPUTUSAN (SKEP): format "SKEP/1/P/BD/IV/2016" 
   - INSTRUKSI KERJA (IK): format "I-03-MI-555" atau "IK-03-MI-555"
   - PROSEDUR: format "P-11-PP-070"
5. Aturan detail format:
   - SE/NOMOR/P/BD/BULAN_ROMawi/TAHUN
   - SKEP/NOMOR/P/BD/BULAN_ROMawi/TAHUN  
   - I-NOMOR-BAGIAN-NOMOR_BELAKANG atau IK-NOMOR-BAGIAN-NOMOR_BELAKANG
   - P-NOMOR-BAGIAN-NOMOR_BELAKANG
6. Jangan ubah makna konten
7. Pertahankan format asli dokumen 
8. HANYA kembalikan teks yang sudah dikoreksi, tanpa komentar tambahan

Contoh koreksi:
- "SE/1/P/BDllVl2016" → "SE/1/P/BD/IV/2016"
- "SKEP/1/P/BDllVl2016" → "SKEP/1/P/BD/IV/2016" 
- "SE/2/P/BD/X/2017" → biarkan seperti itu (sudah benar)
- "I-03-MI-555" → biarkan seperti itu
- "IK-03-MI-555" → biarkan seperti itu
- "P–11–PP–070" → "P-11-PP-070" (normalisasi hyphen)

Teks yang perlu dikoreksi:
"""
        
        for j, chunk in enumerate(batch):
            batch_prompt += f"Teks {j+1}:\n{chunk}\n\n"
        
        batch_prompt += "Hasil perbaikan (hanya teks yang sudah dikoreksi, tanpa komentar):"
        
        try:
            logger.info(f"📡 Sending request to Ollama for batch {batch_num}")
            start_time = time.time()
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen3:8b",
                    "prompt": batch_prompt,
                    "temperature": 0,
                    "stream": False
                },
                timeout=120
            )
            processing_time = time.time() - start_time
            
            corrected_batch = response.json().get("response", "").strip()
            logger.info(f"✅ Ollama response received for batch {batch_num} in {processing_time:.1f}s")
            
            corrected_batch = re.sub(r'<think>.*?</think>', '', corrected_batch, flags=re.DOTALL)
            corrected_batch = re.sub(r'\(thinking.*?\)', '', corrected_batch, flags=re.DOTALL)
            corrected_batch = re.sub(r'Thinking:.*?(?=\n\n|\n[A-Z])', '', corrected_batch, flags=re.DOTALL)
            
            corrected_parts = re.split(r'Teks \d+:', corrected_batch)
            corrected_parts = [re.sub(r'^\s*\d+\.?\s*', '', p.strip()) for p in corrected_parts if p.strip()]
            
            if len(corrected_parts) != len(batch):
                logger.warning(f"⚠️ Part count mismatch: expected {len(batch)}, got {len(corrected_parts)}")
                if corrected_parts:
                    for j in range(len(batch)):
                        if j < len(corrected_parts):
                            corrected_chunks.append(corrected_parts[j])
                        else:
                            corrected_chunks.append(batch[j])
                else:
                    corrected_chunks.extend(batch)
            else:
                corrected_chunks.extend(corrected_parts[:len(batch)])
            
            logger.info(f"✅ Batch {batch_num} correction completed: {len(corrected_parts)} parts")
            
        except Exception as e:
            logger.error(f"❌ Error in correction batch {batch_num}: {e}")
            corrected_chunks.extend(batch)
            logger.info(f"🔄 Using original chunks as fallback for batch {batch_num}")
    
    logger.info(f"✅ Text correction completed: {len(corrected_chunks)} chunks corrected")
    return corrected_chunks

def chunk_text_by_pages_and_sections(text: str, max_chunk_size: int = 800):
    """Chunking berdasarkan halaman dengan handling untuk empty pages - DIAMBIL DARI test.py"""
    logger.info("✂️ Starting page-based chunking")
    
    chunks = []
    
    pages = re.split(r'=== PAGE \d+ ===', text)
    pages = [page.strip() for page in pages if page.strip()]
    
    logger.info(f"📄 Found {len(pages)} pages in document")
    
    valid_pages = []
    for page_num, page_content in enumerate(pages, 1):
        if page_content.strip() and page_content != "[NO TEXT CONTENT]":
            valid_pages.append((page_num, page_content))
        else:
            logger.warning(f"⚠️ Page {page_num}: skipping empty content")
    
    for idx, (page_num, page_content) in enumerate(valid_pages):
        logger.info(f"📋 Processing page {page_num}: {len(page_content)} chars")
        
        if page_content.startswith("[NO TEXT CONTENT]") or page_content.startswith("=== ERROR"):
            continue
            
        if len(page_content) < 300 and idx < len(valid_pages) - 1:
            next_page_num, next_page_content = valid_pages[idx + 1]
            combined = f"=== PAGE {page_num}-{next_page_num} ===\n{page_content}\n\n{next_page_content}"
            
            if len(combined) < max_chunk_size:
                chunks.append(combined)
                logger.info(f"✅ Combined pages {page_num} and {next_page_num}")
                continue
        
        if len(page_content) > max_chunk_size:
            logger.info(f"🔄 Splitting large page {page_num}")
            page_chunks = split_large_page(page_content, page_num, max_chunk_size)
            chunks.extend(page_chunks)
        else:
            chunks.append(f"=== PAGE {page_num} ===\n{page_content}")
            logger.info(f"✅ Created chunk for page {page_num}")
    
    if not chunks:
        logger.warning("⚠️ No valid chunks created, creating fallback chunk")
        chunks.append("=== DOCUMENT CONTENT ===\n" + "\n".join([f"Page {num}: {content[:100]}..." for num, content in valid_pages[:3]]))
    
    logger.info(f"✅ Page-based chunking completed: {len(chunks)} chunks")
    return chunks

def split_large_page(page_content: str, page_num: int, max_chunk_size: int):
    """Split halaman besar menjadi beberapa chunks - DIAMBIL DARI test.py"""
    chunks = []
    current_chunk = f"=== PAGE {page_num} ===\n"
    current_size = len(current_chunk)
    
    paragraphs = [p.strip() for p in page_content.split('\n\n') if p.strip()]
    
    for i, para in enumerate(paragraphs):
        para_with_newline = f"{para}\n\n"
        
        if current_size + len(para_with_newline) > max_chunk_size and current_size > len(f"=== PAGE {page_num} ===\n"):
            chunks.append(current_chunk.strip())
            current_chunk = f"=== PAGE {page_num} (Lanjutan) ===\n{para}\n\n"
            current_size = len(current_chunk)
        else:
            current_chunk += para_with_newline
            current_size += len(para_with_newline)
    
    if current_chunk.strip() and current_chunk != f"=== PAGE {page_num} ===\n":
        chunks.append(current_chunk.strip())
    
    return chunks

def extract_pdf_universal(pdf_path, txt_path):
    """
    Ekstrak PDF dengan approach dari test.py
    """
    print("🚀 Memulai ekstraksi PDF dengan metode test.py...")
    
    # Cek CUDA
    use_cuda, device = check_cuda_availability()
    
    # Inisialisasi OCR
    print("⏳ Menginisialisasi OCR...")
    reader = easyocr.Reader(['id', 'en'], gpu=use_cuda)
    
    try:
        # Step 1: Deteksi tipe PDF
        print("🔍 Mendeteksi tipe PDF...")
        pdf_type, confidence = detect_pdf_type(pdf_path)
        
        # Step 2: Ekstrak text comprehensive
        print("📑 Mengekstrak teks...")
        raw_text = extract_text_comprehensive(pdf_path, pdf_type, reader)
        
        if not raw_text or len(raw_text.strip()) < 100:
            print("❌ Gagal mengekstrak teks dari PDF")
            return False
        
        # Step 3: Validasi kualitas
        print("🔎 Memvalidasi kualitas teks...")
        is_valid, issues = validate_text_quality(raw_text)
        
        # Step 4: Cleaning advanced
        print("🧹 Membersihkan teks...")
        cleaned_text = clean_text_advanced(raw_text)
        
        # Step 5: Chunking
        print("✂️ Membuat chunks...")
        chunks = chunk_text_by_pages_and_sections(cleaned_text, max_chunk_size=800)
        
        # Step 6: Koreksi teks (opsional)
        use_llm = input("\n🤖 Gunakan LLM untuk koreksi teks? (y/n): ").lower() == 'y'
        if use_llm and chunks:
            print("🔧 Mengoreksi teks dengan LLM...")
            corrected_chunks = correct_text_batch(chunks)
            final_text = "\n\n".join(corrected_chunks)
        else:
            final_text = "\n\n".join(chunks)
        
        # Simpan hasil
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\n{'='*60}")
        print("📊 HASIL EKSTRAKSI (Metode test.py)")
        print(f"{'='*60}")
        print(f"📄 Tipe PDF: {pdf_type}")
        print(f"📄 Total Halaman: {len(chunks)} chunks")
        print(f"🔤 Total Karakter: {len(final_text):,}")
        print(f"📁 File Output: {txt_path}")
        print(f"✅ Kualitas Teks: {'Baik' if is_valid else 'Perlu Review'}")
        if issues:
            print(f"⚠️  Masalah: {', '.join(issues)}")
        print(f"🔧 LLM Correction: {'Ya' if use_llm else 'Tidak'}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_pdf_content(pdf_path):
    """
    Analisis konten PDF menggunakan deteksi tipe dari test.py
    """
    print("\n🔍 Menganalisis struktur PDF...")
    
    try:
        pdf_type, confidence = detect_pdf_type(pdf_path)
        print(f"📄 Tipe PDF: {pdf_type} (Confidence: {confidence})")
        
        with pymupdf.open(pdf_path) as doc:
            total_pages = len(doc)
            print(f"📄 Jumlah halaman: {total_pages}")
                    
    except Exception as e:
        print(f"   ❌ Error analisis: {e}")

def main():
    print("🚀 PDF to TXT Extractor (Menggunakan fungsi dari test.py)")
    print("=" * 50)
    print("Fitur: Comprehensive extraction + Advanced cleaning + Optional LLM correction")
    print("=" * 50)
    
    # Input PDF
    pdf_path = input("\n📁 Masukkan path PDF: ").strip()
    
    if not os.path.exists(pdf_path):
        print("❌ File tidak ditemukan!")
        return
    
    # Analisis PDF
    analyze_pdf_content(pdf_path)
    
    # Output path
    base_name = os.path.splitext(pdf_path)[0]
    txt_path = f"{base_name}_EXTRACTED.txt"
    
    # Process
    print(f"\n🎯 Memproses {os.path.basename(pdf_path)}...")
    success = extract_pdf_universal(pdf_path, txt_path)
    
    if success:
        print(f"\n✅ EKSTRAKSI SELESAI!")
        
        # Preview hasil
        preview = input("\n👀 Tampilkan preview? (y/n): ").lower()
        if preview == 'y':
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"\n{'='*60}")
                print("PREVIEW (600 karakter pertama):")
                print(f"{'='*60}")
                print(content[:600] + "..." if len(content) > 600 else content)
                        
    else:
        print("❌ Gagal memproses PDF")

if __name__ == "__main__":
    main()