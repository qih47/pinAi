import os
import json
import re
import pdfplumber
import fitz
import easyocr
import requests
from sentence_transformers import SentenceTransformer
from pathlib import Path
import time
from typing import List, Dict, Tuple
import numpy as np
import torch
from quart import Quart, request, jsonify, send_file, render_template_string
import asyncio
import logging

# =====================================================
# CONFIG & LOGGING
# =====================================================
# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TEMP_DIR = Path("./tmp")
TEMP_DIR.mkdir(exist_ok=True)

# Gunakan CPU atau GPU dengan memory management
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

try:
    embedder = SentenceTransformer("BAAI/bge-m3", device=device)
    logger.info("✅ Embedding model loaded successfully")
except Exception as e:
    logger.error(f"❌ Failed to load embedding model: {e}")
    raise

try:
    ocr_reader = easyocr.Reader(["id", "en"], gpu=(device == "cuda"))
    logger.info("✅ OCR model loaded successfully")
except Exception as e:
    logger.error(f"❌ Failed to load OCR model: {e}")
    raise

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:8b"

app = Quart(__name__)

# =====================================================
# HTML TEMPLATE (sama seperti sebelumnya)
# =====================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Processing Tool</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .upload-area {
            border: 2px dashed #ccc;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin: 20px 0;
            background: #fafafa;
            cursor: pointer;
        }
        .upload-area:hover {
            border-color: #007bff;
            background: #f0f8ff;
        }
        .upload-area.dragover {
            border-color: #007bff;
            background: #e3f2fd;
        }
        .btn {
            background: #007bff;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px;
        }
        .btn:hover {
            background: #0056b3;
        }
        .btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
        .progress {
            width: 100%;
            height: 20px;
            background: #f0f0f0;
            border-radius: 10px;
            margin: 20px 0;
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            background: #007bff;
            width: 0%;
            transition: width 0.3s;
        }
        .log-container {
            background: #1e1e1e;
            color: #00ff00;
            padding: 15px;
            border-radius: 5px;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            margin: 20px 0;
        }
        .result {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }
        .error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }
        .download-links {
            margin: 15px 0;
        }
        .download-links a {
            display: block;
            background: #28a745;
            color: white;
            padding: 10px 15px;
            text-decoration: none;
            border-radius: 5px;
            margin: 5px 0;
        }
        .download-links a:hover {
            background: #218838;
        }
        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📄 PDF Processing Tool</h1>
        <p>Upload file PDF untuk diproses menjadi chunks dengan embedding</p>
        
        <div class="upload-area" id="uploadArea">
            <input type="file" id="fileInput" accept=".pdf" style="display: none;">
            <div>
                <h3>📁 Klik atau drop file PDF di sini</h3>
                <p>Format yang didukung: PDF</p>
                <button class="btn" onclick="document.getElementById('fileInput').click()">
                    Pilih File PDF
                </button>
            </div>
        </div>

        <div id="fileInfo" class="hidden"></div>

        <div id="progressSection" class="hidden">
            <h3>🔄 Sedang Memproses...</h3>
            <div class="progress">
                <div class="progress-bar" id="progressBar"></div>
            </div>
            <div class="log-container" id="logContainer">
                <div>Log akan muncul di sini...</div>
            </div>
        </div>

        <div id="resultSection" class="hidden">
            <h3>✅ Proses Selesai!</h3>
            <div class="result">
                <div id="resultContent"></div>
            </div>
        </div>

        <div id="errorSection" class="hidden">
            <h3>❌ Terjadi Error</h3>
            <div class="error">
                <div id="errorContent"></div>
            </div>
        </div>

        <div style="text-align: center; margin-top: 20px;">
            <a href="/logs" class="btn" style="background: #6c757d; display: inline-block;">View Logs</a>
            <a href="/status" class="btn" style="background: #6c757d; display: inline-block;">Status</a>
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');
        const fileInfo = document.getElementById('fileInfo');
        const progressSection = document.getElementById('progressSection');
        const resultSection = document.getElementById('resultSection');
        const errorSection = document.getElementById('errorSection');
        const progressBar = document.getElementById('progressBar');
        const logContainer = document.getElementById('logContainer');
        const resultContent = document.getElementById('resultContent');
        const errorContent = document.getElementById('errorContent');

        // Drag and drop functionality
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });

        function handleFileSelect(file) {
            if (file.type !== 'application/pdf') {
                alert('Hanya file PDF yang didukung!');
                return;
            }

            fileInfo.innerHTML = `<strong>File terpilih:</strong> ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
            fileInfo.classList.remove('hidden');

            // Reset UI
            progressSection.classList.remove('hidden');
            resultSection.classList.add('hidden');
            errorSection.classList.add('hidden');
            progressBar.style.width = '0%';
            logContainer.innerHTML = '<div>Memulai proses...</div>';

            uploadFile(file);
        }

        function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);

            fetch('/process', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showResult(data);
                } else {
                    showError(data.error || 'Terjadi kesalahan');
                }
            })
            .catch(error => {
                showError('Error: ' + error.message);
            });
        }

        function showResult(data) {
            progressSection.classList.add('hidden');
            resultSection.classList.remove('hidden');
            
            const results = data.results;
            let html = `
                <h4>📊 Hasil Processing</h4>
                <p><strong>File:</strong> ${results.filename}</p>
                <p><strong>Tipe PDF:</strong> ${results.pdf_type}</p>
                <p><strong>Total Chunks:</strong> ${results.total_chunks}</p>
                <p><strong>Waktu Processing:</strong> ${data.processing_time}</p>
                
                <div class="download-links">
                    <h5>📥 Download Hasil:</h5>
                    <a href="${results.download_links.json_result}" target="_blank">
                        📄 Download JSON Result (Embeddings)
                    </a>
                    <a href="${results.download_links.preview}" target="_blank">
                        📝 Download Preview (Teks Lengkap)
                    </a>
                    <a href="${results.download_links.full_chunks}" target="_blank">
                        📋 Download Full Chunks (Text Only)
                    </a>
                    <a href="${results.download_links.corrected_full}" target="_blank">
                        📝 Download Full Corrected Text
                    </a>
                </div>
            `;

            if (results.sample_chunk) {
                html += `
                    <h5>👀 Sample Chunk #1:</h5>
                    <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin: 10px 0;">
                        <strong>Original (${results.sample_chunk.original_length} chars):</strong><br>
                        <pre style="white-space: pre-wrap; font-size: 11px; max-height: 200px; overflow-y: auto;">${results.sample_chunk.original_full}</pre>
                        <strong>Corrected (${results.sample_chunk.corrected_length} chars):</strong><br>
                        <pre style="white-space: pre-wrap; font-size: 11px; max-height: 200px; overflow-y: auto;">${results.sample_chunk.corrected_full}</pre>
                    </div>
                `;
            }

            resultContent.innerHTML = html;
        }

        function showError(message) {
            progressSection.classList.add('hidden');
            errorSection.classList.remove('hidden');
            errorContent.innerHTML = message;
        }

        // Real-time log updates (simple version)
        function updateLogs() {
            fetch('/logs')
                .then(response => response.json())
                .then(data => {
                    if (data.logs) {
                        logContainer.innerHTML = '<div>' + data.logs.replace(/\\n/g, '<br>') + '</div>';
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }
                });
        }

        // Update logs every 2 seconds during processing
        setInterval(updateLogs, 2000);
    </script>
</body>
</html>
"""

# =====================================================
# FIXED UTILITIES - PERBAIKAN ERROR "document closed"
# =====================================================
def detect_pdf_type(filepath: str) -> Tuple[str, bool]:
    """Deteksi tipe PDF: text-based vs image-based dengan confidence."""
    logger.info("🔍 Starting PDF type detection")
    try:
        # Gunakan context manager untuk handle PDF dengan benar
        with fitz.open(filepath) as doc:
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
            
            # Heuristic: jika rata2 text per page < 100 chars atau banyak gambar → scanned
            avg_text_per_page = total_text_len / total_pages if total_pages > 0 else 0
            is_scanned = avg_text_per_page < 100 or total_images > total_pages * 2
            
            pdf_type = "scanned" if is_scanned else "text-based"
            confidence = True if (is_scanned and total_images > 0) or (not is_scanned and avg_text_per_page > 200) else False
            
            logger.info(f"📊 PDF Type: {pdf_type}, Confidence: {confidence}, Avg chars per page: {avg_text_per_page:.1f}, Total images: {total_images}")
            return pdf_type, confidence
        
    except Exception as e:
        logger.error(f"❌ Error detecting PDF type: {e}")
        # Fallback: coba dengan pdfplumber
        try:
            logger.info("🔄 Trying fallback with pdfplumber...")
            with pdfplumber.open(filepath) as pdf:
                total_text_len = 0
                total_pages = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    total_text_len += len(page_text.strip())
                    logger.info(f"📄 Page {page_num + 1} (pdfplumber): {len(page_text)} chars")
                
                avg_text_per_page = total_text_len / total_pages if total_pages > 0 else 0
                is_scanned = avg_text_per_page < 100
                pdf_type = "scanned" if is_scanned else "text-based"
                confidence = avg_text_per_page > 200 if not is_scanned else False
                
                logger.info(f"📊 PDF Type (fallback): {pdf_type}, Confidence: {confidence}, Avg chars per page: {avg_text_per_page:.1f}")
                return pdf_type, confidence
                
        except Exception as e2:
            logger.error(f"❌ Fallback also failed: {e2}")
            return "unknown", False

# HAPUS fungsi extract_text_optimized yang lama
# DAN GANTI DENGAN:

def extract_text_comprehensive(filepath: str, pdf_type: str) -> str:
    """Ekstrak text dengan auto-retry OCR untuk halaman yang bermasalah."""
    logger.info(f"📑 Comprehensive text extraction for {pdf_type} PDF")
    
    all_text = ""
    problematic_pages = []
    
    try:
        with fitz.open(filepath) as doc:
            total_pages = len(doc)
            logger.info(f"📄 Processing {total_pages} pages")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                logger.info(f"🔄 Processing page {page_num + 1}")
                
                # Try normal text extraction first
                normal_text = page.get_text("text").strip()
                
                # Check if text extraction is sufficient
                if len(normal_text) > 100:  # Jika dapat text yang cukup
                    page_content = f"=== PAGE {page_num + 1} ===\n{normal_text}"
                    all_text += page_content + "\n\n"
                    logger.info(f"✅ Page {page_num + 1}: {len(normal_text)} chars")
                    
                else:  # Text tidak cukup - STOP dan retry dengan OCR
                    logger.warning(f"⚠️ Page {page_num + 1}: insufficient text ({len(normal_text)} chars) - SWITCHING TO OCR")
                    problematic_pages.append(page_num + 1)
                    
                    # Retry dengan OCR untuk halaman ini
                    ocr_text = extract_page_with_ocr_retry(page, page_num + 1)
                    
                    if ocr_text and len(ocr_text) > 50:
                        page_content = f"=== PAGE {page_num + 1} (OCR) ===\n{ocr_text}"
                        all_text += page_content + "\n\n"
                        logger.info(f"✅ Page {page_num + 1} OCR success: {len(ocr_text)} chars")
                    else:
                        # Jika OCR juga gagal, gunakan text yang ada + warning
                        fallback_text = normal_text if normal_text else "[LOW QUALITY TEXT - NEEDS MANUAL REVIEW]"
                        page_content = f"=== PAGE {page_num + 1} (LOW QUALITY) ===\n{fallback_text}"
                        all_text += page_content + "\n\n"
                        logger.warning(f"⚠️ Page {page_num + 1} OCR also failed, using low quality text")
        
        # Log summary
        if problematic_pages:
            logger.info(f"📊 Extraction summary: {total_pages - len(problematic_pages)} pages normal, {len(problematic_pages)} pages used OCR: {problematic_pages}")
        else:
            logger.info(f"📊 Extraction summary: All {total_pages} pages extracted normally")
            
        return all_text.strip()
        
    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        return f"=== EXTRACTION ERROR ===\n{str(e)}"

def extract_page_with_ocr_retry(page, page_num: int) -> str:
    """OCR retry dengan multiple attempts dan parameter optimized."""
    logger.info(f"🔍 Starting OCR retry for page {page_num}")
    
    ocr_attempts = [
        {"dpi": 300, "paragraph": True, "min_size": 10},  # Attempt 1: Standard
        {"dpi": 400, "paragraph": False, "min_size": 5},  # Attempt 2: Higher DPI
        {"dpi": 300, "paragraph": True, "text_threshold": 0.5},  # Attempt 3: Lower threshold
    ]
    
    best_ocr_text = ""
    
    for attempt_num, params in enumerate(ocr_attempts, 1):
        try:
            logger.info(f"  📸 OCR Attempt {attempt_num} for page {page_num} with params: {params}")
            
            pix = page.get_pixmap(dpi=params["dpi"])
            img_data = pix.tobytes("png")
            
            # OCR dengan parameter yang berbeda-beda
            ocr_result = ocr_reader.readtext(
                img_data,
                detail=0,
                paragraph=params.get("paragraph", True),
                min_size=params.get("min_size", 10),
                text_threshold=params.get("text_threshold", 0.7),
                canvas_size=4000
            )
            
            current_ocr_text = "\n".join([text for text in ocr_result if text.strip()])
            
            logger.info(f"  📊 Attempt {attempt_num}: {len(current_ocr_text)} chars")
            
            # Update best result jika lebih baik
            if len(current_ocr_text) > len(best_ocr_text):
                best_ocr_text = current_ocr_text
                
            # Jika sudah dapat text yang cukup, stop attempts
            if len(current_ocr_text) > 200:
                logger.info(f"  ✅ Attempt {attempt_num} sufficient, stopping retries")
                break
                
        except Exception as e:
            logger.error(f"  ❌ OCR Attempt {attempt_num} failed: {e}")
            continue
    
    return best_ocr_text

def extract_with_pdfplumber_fallback(filepath: str) -> str:
    """Fallback extraction menggunakan pdfplumber dengan OCR integration."""
    logger.info("🔄 Using pdfplumber + OCR fallback extraction")
    
    all_text = ""
    try:
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages):
                logger.info(f"📄 pdfplumber processing page {page_num + 1}")
                
                # Try pdfplumber extraction first
                pdfplumber_text = page.extract_text() or ""
                
                if len(pdfplumber_text) > 100:
                    all_text += f"=== PAGE {page_num + 1} ===\n{pdfplumber_text.strip()}\n\n"
                    logger.info(f"✅ Page {page_num + 1} (pdfplumber): {len(pdfplumber_text)} chars")
                else:
                    logger.warning(f"⚠️ Page {page_num + 1} (pdfplumber): insufficient text ({len(pdfplumber_text)} chars)")
                    
                    # Fallback: convert page to image and OCR
                    try:
                        # Convert pdfplumber page to image
                        im = page.to_image(resolution=300)
                        img_array = np.array(im.original)
                        
                        # OCR the image
                        ocr_result = ocr_reader.readtext(img_array, detail=0, paragraph=True)
                        ocr_text = "\n".join(ocr_result)
                        
                        if ocr_text and len(ocr_text) > 50:
                            all_text += f"=== PAGE {page_num + 1} (OCR) ===\n{ocr_text}\n\n"
                            logger.info(f"✅ Page {page_num + 1} OCR via pdfplumber: {len(ocr_text)} chars")
                        else:
                            all_text += f"=== PAGE {page_num + 1} (LOW QUALITY) ===\n{pdfplumber_text if pdfplumber_text else '[NO TEXT DETECTED]'}\n\n"
                            logger.warning(f"⚠️ Page {page_num + 1} all methods failed")
                            
                    except Exception as e:
                        logger.error(f"❌ Page {page_num + 1} pdfplumber OCR failed: {e}")
                        all_text += f"=== PAGE {page_num + 1} (ERROR) ===\n[EXTRACTION FAILED: {str(e)}]\n\n"
        
        return all_text.strip()
        
    except Exception as e:
        logger.error(f"❌ pdfplumber fallback failed: {e}")
        return f"=== EXTRACTION ERROR ===\n{str(e)}"

# HAPUS fungsi chunk_text_semantic yang lama
# DAN GANTI DENGAN 3 FUNGSI BARU:

def chunk_text_by_pages_and_sections(text: str, max_chunk_size: int = 800) -> List[str]:
    """Chunking berdasarkan halaman dengan handling untuk empty pages."""
    logger.info("✂️ Starting page-based chunking")
    
    chunks = []
    
    # Split by pages first
    pages = re.split(r'=== PAGE \d+ ===', text)
    pages = [page.strip() for page in pages if page.strip()]
    
    logger.info(f"📄 Found {len(pages)} pages in document")
    
    valid_pages = []
    for page_num, page_content in enumerate(pages, 1):
        # Skip pages with no content
        if page_content.strip() and page_content != "[NO TEXT CONTENT]":
            valid_pages.append((page_num, page_content))
        else:
            logger.warning(f"⚠️ Page {page_num}: skipping empty content")
    
    for idx, (page_num, page_content) in enumerate(valid_pages):
        logger.info(f"📋 Processing page {page_num}: {len(page_content)} chars")
        
        # Skip if content is just error message
        if page_content.startswith("[NO TEXT CONTENT]") or page_content.startswith("=== ERROR"):
            continue
            
        # Jika page kecil, bisa digabung dengan page berikutnya
        if len(page_content) < 300 and idx < len(valid_pages) - 1:
            next_page_num, next_page_content = valid_pages[idx + 1]
            combined = f"=== PAGE {page_num}-{next_page_num} ===\n{page_content}\n\n{next_page_content}"
            
            if len(combined) < max_chunk_size:
                chunks.append(combined)
                logger.info(f"✅ Combined pages {page_num} and {next_page_num}")
                continue  # Skip next page since already combined
        
        # Jika page besar, split internal
        if len(page_content) > max_chunk_size:
            logger.info(f"🔄 Splitting large page {page_num}")
            page_chunks = split_large_page(page_content, page_num, max_chunk_size)
            chunks.extend(page_chunks)
        else:
            chunks.append(f"=== PAGE {page_num} ===\n{page_content}")
            logger.info(f"✅ Created chunk for page {page_num}")
    
    # Jika tidak ada chunks yang berhasil, return minimal content
    if not chunks:
        logger.warning("⚠️ No valid chunks created, creating fallback chunk")
        chunks.append("=== DOCUMENT CONTENT ===\n" + "\n".join([f"Page {num}: {content[:100]}..." for num, content in valid_pages[:3]]))
    
    logger.info(f"✅ Page-based chunking completed: {len(chunks)} chunks")
    return chunks

def split_large_page(page_content: str, page_num: int, max_chunk_size: int) -> List[str]:
    """Split halaman besar menjadi beberapa chunks."""
    chunks = []
    current_chunk = f"=== PAGE {page_num} ===\n"
    current_size = len(current_chunk)
    
    # Split by paragraphs first
    paragraphs = [p.strip() for p in page_content.split('\n\n') if p.strip()]
    
    for i, para in enumerate(paragraphs):
        para_with_newline = f"{para}\n\n"
        
        if current_size + len(para_with_newline) > max_chunk_size and current_size > len(f"=== PAGE {page_num} ===\n"):
            # Save current chunk and start new one
            chunks.append(current_chunk.strip())
            current_chunk = f"=== PAGE {page_num} (Lanjutan) ===\n{para}\n\n"
            current_size = len(current_chunk)
        else:
            current_chunk += para_with_newline
            current_size += len(para_with_newline)
    
    if current_chunk.strip() and current_chunk != f"=== PAGE {page_num} ===\n":
        chunks.append(current_chunk.strip())
    
    return chunks

def validate_text_quality(text: str) -> Tuple[bool, List[str]]:
    """Validasi kualitas extracted text."""
    logger.info("🔎 Validating text quality")
    issues = []
    
    if not text or len(text.strip()) == 0:
        logger.error("❌ Empty text")
        return False, ["Empty text"]
    
    if len(text.strip()) < 100:
        issues.append("Text too short")
        logger.warning(f"⚠️ Text too short: {len(text.strip())} chars")
    
    # Cek karakter aneh (OCR artifacts)
    weird_chars = re.findall(r'[^\w\s.,!?;:()\-@#$%&*+/=]', text)
    weird_ratio = len(weird_chars) / len(text) if text else 0
    if weird_ratio > 0.1:  # >10% weird chars
        issues.append("Too many unusual characters")
        logger.warning(f"⚠️ Too many unusual characters: {weird_ratio:.2%}")
    
    # Cek ratio whitespace
    newline_ratio = text.count('\n') / len(text) if text else 0
    if newline_ratio > 0.1:
        issues.append("Poor formatting")
        logger.warning(f"⚠️ Poor formatting: newline ratio {newline_ratio:.2%}")
    
    is_valid = len(issues) == 0
    logger.info(f"✅ Text quality validation: {'PASS' if is_valid else 'FAIL'} - Issues: {issues}")
    return is_valid, issues

def clean_text_advanced(text: str) -> str:
    """Advanced text cleaning yang menjaga struktur."""
    logger.info("🧹 Cleaning text while preserving structure")
    original_len = len(text)
    
    # Pertahankan struktur page markers
    text = re.sub(r'=== PAGE \d+ ===', '\n=== PAGE \\g<0> ===\n', text)
    
    # Normalize whitespace tapi jaga paragraph breaks
    text = re.sub(r'[ \t]+', ' ', text)  # Normalize spaces
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Normalize multiple newlines
    
    # Fix common OCR errors dengan preservasi struktur
    replacements = {
        r'\bPT\s+Pindad\b': 'PT Pindad',
        r'\bPindad\s+\(Persero\)': 'Pindad (Persero)',
        r'\bSkep\b': 'SKEP',
        r'\bSE\s*\/': 'SE/',
        r'\bSKEP\s*\/': 'SKEP/',
        r'(\d)\s*\/\s*([A-Z])': '\\1/\\2',  # Fix spasi dalam nomor surat
        r'(\w)\1{2,}': lambda m: m.group(0)[0],  # Remove repeated chars
    }
    
    for pattern, replacement in replacements.items():
        if callable(replacement):
            text = re.sub(pattern, replacement, text)
        else:
            text = re.sub(pattern, replacement, text)
    
    # Restore important document structure
    text = re.sub(r'(?<=\n)(\d+\.)\s*([A-Z])', '\\1 \\2', text)  # Restore numbering
    text = re.sub(r'(?<=\n)([a-z]\.)\s*([A-Z])', '\\1 \\2', text)  # Restore sub-numbering
    
    cleaned_len = len(text)
    logger.info(f"✅ Text cleaning completed: {original_len} → {cleaned_len} chars (structure preserved)")
    return text.strip()

def clean_extraction_results(text: str) -> str:
    """Bersihkan hasil extraction dari duplikat dan artifact."""
    logger.info("🧹 Cleaning extraction results")
    
    # Remove duplicate page markers
    text = re.sub(r'=== PAGE \d+ ===\s*=== PAGE \d+ ===', '=== PAGE \\g<0> ===', text)
    
    # Remove empty page markers
    text = re.sub(r'=== PAGE \d+ ===\s*$', '', text, flags=re.MULTILINE)
    
    # Fix common OCR typos
    corrections = {
        r'\bPTNDAD\b': 'PT PINDAD',
        r'\bONDAD\b': 'PINDAD', 
        r'\bw\.prndad\.com\b': 'www.pindad.com',
        r'\bPFPAPA5\b': 'PINDAD',
        r'\bnindé\b': 'PINDAD',
        r'\bIembusan\b': 'Tembusan',
        r'QIRLY': '',
        r'ABRAHAMMOSE': 'ABRAHAM MOSE'
    }
    
    for wrong, correct in corrections.items():
        text = re.sub(wrong, correct, text)
    
    return text

# =====================================================
# TEXT CORRECTION FUNCTIONS (WITHOUT <think> TAGS)
# =====================================================
def correct_text_batch(chunks: List[str]) -> List[str]:
    """Koreksi text dalam batch untuk efisiensi - tanpa tag <think>."""
    logger.info(f"🔧 Starting text correction for {len(chunks)} chunks")
    corrected_chunks = []
    
    for i in range(0, len(chunks), 2):  # Batch size 2
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
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": batch_prompt,
                    "temperature": 0,
                    "stream": False
                },
                timeout=120
            )
            processing_time = time.time() - start_time
            
            corrected_batch = response.json().get("response", "").strip()
            logger.info(f"✅ Ollama response received for batch {batch_num} in {processing_time:.1f}s")
            
            # Clean response - remove any <think> tags or thinking process
            corrected_batch = re.sub(r'<think>.*?</think>', '', corrected_batch, flags=re.DOTALL)
            corrected_batch = re.sub(r'\(thinking.*?\)', '', corrected_batch, flags=re.DOTALL)
            corrected_batch = re.sub(r'Thinking:.*?(?=\n\n|\n[A-Z])', '', corrected_batch, flags=re.DOTALL)
            
            # Simple split by number (asumsi format terjaga)
            corrected_parts = re.split(r'Teks \d+:', corrected_batch)
            corrected_parts = [re.sub(r'^\s*\d+\.?\s*', '', p.strip()) for p in corrected_parts if p.strip()]
            
            # Jika jumlah parts tidak sesuai, gunakan fallback
            if len(corrected_parts) != len(batch):
                logger.warning(f"⚠️ Part count mismatch: expected {len(batch)}, got {len(corrected_parts)}")
                if corrected_parts:
                    # Distribute available parts
                    for j in range(len(batch)):
                        if j < len(corrected_parts):
                            corrected_chunks.append(corrected_parts[j])
                        else:
                            corrected_chunks.append(batch[j])  # Fallback ke original
                else:
                    corrected_chunks.extend(batch)  # Fallback semua ke original
            else:
                corrected_chunks.extend(corrected_parts[:len(batch)])
            
            logger.info(f"✅ Batch {batch_num} correction completed: {len(corrected_parts)} parts")
            
        except Exception as e:
            logger.error(f"❌ Error in correction batch {batch_num}: {e}")
            # Fallback ke original chunks
            corrected_chunks.extend(batch)
            logger.info(f"🔄 Using original chunks as fallback for batch {batch_num}")
    
    logger.info(f"✅ Text correction completed: {len(corrected_chunks)} chunks corrected")
    return corrected_chunks

def embed_chunks_batch_optimized(chunks: List[str], batch_size: int = 8) -> List[List[float]]:
    """Embedding dalam batch dengan memory management."""
    logger.info(f"🧮 Starting embedding for {len(chunks)} chunks (batch_size: {batch_size})")
    all_embeddings = []
    
    # Clear GPU cache sebelum memulai
    if device == "cuda":
        torch.cuda.empty_cache()
        logger.info("🧹 GPU cache cleared")
    
    # Process dalam batch kecil
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        logger.info(f"🔄 Processing embedding batch {batch_num}: chunks {i+1}-{i+len(batch_chunks)}")
        
        try:
            # Encode dengan optimasi memory
            start_time = time.time()
            batch_embeddings = embedder.encode(
                batch_chunks,
                normalize_embeddings=True,
                batch_size=2,  # Smaller batch size untuk embedding
                show_progress_bar=False,
                convert_to_tensor=False
            )
            processing_time = time.time() - start_time
            
            all_embeddings.extend(batch_embeddings.tolist())
            logger.info(f"✅ Embedding batch {batch_num} completed in {processing_time:.1f}s: {len(batch_embeddings)} vectors")
            
            # Clear cache setelah setiap batch
            if device == "cuda":
                torch.cuda.empty_cache()
                
        except Exception as e:
            logger.error(f"❌ Error embedding batch {batch_num}: {e}")
            # Fallback: skip embedding untuk batch ini
            for chunk_idx in range(len(batch_chunks)):
                all_embeddings.append([0.0] * 1024)  # Default vector size
            logger.info(f"🔄 Using zero vectors as fallback for batch {batch_num}")
    
    logger.info(f"✅ Embedding completed: {len(all_embeddings)} total vectors")
    return all_embeddings

# =====================================================
# QUART ROUTES - WITH DYNAMIC CHUNKING
# =====================================================
@app.route('/')
async def index():
    """Serve HTML interface"""
    return await render_template_string(HTML_TEMPLATE)

@app.route('/status')
async def status():
    return jsonify({
        "status": "running",
        "device": device,
        "models_loaded": {
            "embedding": True,
            "ocr": True
        }
    })

@app.route('/process', methods=['POST'])
async def process_pdf():
    start_time = time.time()
    logger.info("🚀 Starting PDF processing request")
    
    try:
        if 'file' not in await request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = (await request.files)['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "File must be a PDF"}), 400

        # Save uploaded file
        safe_name = re.sub(r'[^\w\-_]', '_', file.filename.replace(".pdf", ""))
        timestamp = int(time.time())
        input_path = TEMP_DIR / f"upload_{safe_name}_{timestamp}.pdf"
        await file.save(input_path)
        
        logger.info(f"📄 File uploaded: {file.filename} -> {input_path}")
        
        # Step 1: Deteksi tipe PDF (FIXED)
        logger.info("Step 1: PDF type detection")
        pdf_type, confidence = detect_pdf_type(str(input_path))
        
        # Step 2: Ekstrak text dengan retry mechanism
        logger.info("Step 2: Text extraction")
        max_retries = 2
        raw_text = ""

        for retry_count in range(max_retries + 1):
            try:
                if retry_count == 0:
                    # First attempt: normal extraction
                    raw_text = extract_text_comprehensive(str(input_path), pdf_type)
                else:
                    # Retry: use fallback method
                    logger.warning(f"🔄 Retry attempt {retry_count} with fallback method")
                    raw_text = extract_with_pdfplumber_fallback(str(input_path))
                
                # Check if extraction produced meaningful content
                if raw_text and len(raw_text.strip()) > 500:  # Minimum 500 chars
                    logger.info(f"✅ Extraction successful on attempt {retry_count + 1}")
                    break
                else:
                    logger.warning(f"⚠️ Attempt {retry_count + 1} produced insufficient text: {len(raw_text.strip())} chars")
                    
            except Exception as e:
                logger.error(f"❌ Attempt {retry_count + 1} failed: {e}")
                if retry_count == max_retries:
                    raise e  # Re-raise if all retries failed

        if not raw_text or len(raw_text.strip()) < 100:
            logger.error("❌ All extraction methods failed")
            return jsonify({"error": "Failed to extract text from PDF after multiple attempts"}), 500
        
        # Step 2.5: Clean extraction results
        logger.info("Step 2.5: Cleaning extraction results")
        raw_text = clean_extraction_results(raw_text)
        
        # Step 3: Validasi kualitas
        logger.info("Step 3: Text quality validation")
        is_valid, issues = validate_text_quality(raw_text)
        
        # Step 4: Cleaning
        logger.info("Step 4: Text cleaning")
        cleaned_text = clean_text_advanced(raw_text)
        
        # Step 5: Chunking - GUNAKAN YANG BARU  
        logger.info("Step 5: Text chunking")
        chunks = chunk_text_by_pages_and_sections(cleaned_text, max_chunk_size=800)  # <- FUNGSI BARU
        
        # Step 6: Koreksi teks (tanpa <think> tags)
        corrected_chunks = chunks
        if len(chunks) > 0:
            logger.info("Step 6: Text correction")
            corrected_chunks = correct_text_batch(chunks)
        
        # Step 7: Embedding
        logger.info("Step 7: Embedding generation")
        # Adaptive batch size berdasarkan jumlah chunks
        if len(corrected_chunks) > 20:
            embedding_batch_size = 2
        elif len(corrected_chunks) > 10:
            embedding_batch_size = 4
        else:
            embedding_batch_size = len(corrected_chunks)
        
        embeddings = embed_chunks_batch_optimized(corrected_chunks, batch_size=embedding_batch_size)
        
        # Step 8: Prepare results
        logger.info("Step 8: Preparing results")
        results = []
        for i, (chunk, corrected, embedding) in enumerate(zip(chunks, corrected_chunks, embeddings)):
            results.append({
                "chunk_id": i + 1,
                "original": chunk,
                "corrected": corrected,
                "embedding": embedding,
                "pdf_type": pdf_type,
                "quality_issues": issues if i == 0 else []
            })

        # Step 9: Save results
        logger.info("Step 9: Saving results")
        output_filename = f"result_{safe_name}_{timestamp}.json"
        output_path = TEMP_DIR / output_filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "filename": file.filename,
                    "pdf_type": pdf_type,
                    "total_chunks": len(chunks),
                    "processing_time": int(time.time()),
                    "total_processing_time": time.time() - start_time,
                    "quality_check": {
                        "is_valid": is_valid,
                        "issues": issues
                    }
                },
                "chunks": results
            }, f, indent=2, ensure_ascii=False)

        # Step 10: Buat file preview dengan FULL TEXT
        logger.info("Step 10: Creating preview files")
        
        # File 1: Preview dengan semua chunks lengkap
        preview_filename = f"preview_{safe_name}_{timestamp}.txt"
        preview_path = TEMP_DIR / preview_filename
        
        preview_content = "=== PREVIEW CHUNKS YANG BERHASIL DIPROSES ===\n\n"
        for i, chunk_data in enumerate(results):
            preview_content += f"--- CHUNK {i+1} (Original: {len(chunk_data['original'])} chars, Corrected: {len(chunk_data['corrected'])} chars) ---\n"
            preview_content += "ORIGINAL (Full Text):\n"
            preview_content += f"{chunk_data['original']}\n\n"
            preview_content += "CORRECTED (Full Text):\n"
            preview_content += f"{chunk_data['corrected']}\n\n"
            preview_content += f"Embedding length: {len(chunk_data['embedding'])} vectors\n"
            preview_content += "="*80 + "\n\n"
        
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(preview_content)

        # File 2: Hanya corrected chunks full text
        full_chunks_filename = f"full_chunks_{safe_name}_{timestamp}.txt"
        full_chunks_path = TEMP_DIR / full_chunks_filename
        
        full_chunks_content = "=== FULL CORRECTED CHUNKS (UNTUK ANALISIS KATA PER KATA) ===\n\n"
        for i, chunk_data in enumerate(results):
            full_chunks_content += f"--- CHUNK {i+1} ({len(chunk_data['corrected'])} chars) ---\n"
            full_chunks_content += f"{chunk_data['corrected']}\n\n"
            full_chunks_content += "="*80 + "\n\n"
        
        with open(full_chunks_path, "w", encoding="utf-8") as f:
            f.write(full_chunks_content)

        # File 3: Full corrected text tanpa chunking (untuk analisis lengkap)
        corrected_full_filename = f"corrected_full_{safe_name}_{timestamp}.txt"
        corrected_full_path = TEMP_DIR / corrected_full_filename
        
        corrected_full_content = "=== FULL CORRECTED TEXT (TANPA CHUNKING) ===\n\n"
        corrected_full_content += "\n\n".join([chunk_data['corrected'] for chunk_data in results])
        
        with open(corrected_full_path, "w", encoding="utf-8") as f:
            f.write(corrected_full_content)

        total_time = time.time() - start_time
        logger.info(f"🎉 PDF processing completed in {total_time:.1f} seconds")
        
        # Return response dengan link download
        base_url = request.host_url.rstrip('/')
        
        return jsonify({
            "status": "success",
            "processing_time": f"{total_time:.1f}s",
            "results": {
                "filename": file.filename,
                "pdf_type": pdf_type,
                "total_chunks": len(chunks),
                "text_quality": {
                    "is_valid": is_valid,
                    "issues": issues
                },
                "download_links": {
                    "json_result": f"{base_url}/download/{output_filename}",
                    "preview": f"{base_url}/download/{preview_filename}",
                    "full_chunks": f"{base_url}/download/{full_chunks_filename}",
                    "corrected_full": f"{base_url}/download/{corrected_full_filename}"
                },
                "sample_chunk": {
                    "chunk_id": results[0]["chunk_id"] if results else None,
                    "original_full": results[0]["original"] if results else None,
                    "corrected_full": results[0]["corrected"] if results else None,
                    "original_length": len(results[0]["original"]) if results else 0,
                    "corrected_length": len(results[0]["corrected"]) if results else 0
                }
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error processing PDF: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
async def download_file(filename):
    """Endpoint untuk download hasil file"""
    file_path = TEMP_DIR / filename
    
    # Security check - hanya boleh download file result, preview, full_chunks, dan corrected_full
    if not filename.startswith(('result_', 'preview_', 'full_chunks_', 'corrected_full_')):
        return jsonify({"error": "Access denied"}), 403
    
    if file_path.exists():
        logger.info(f"📥 Downloading file: {filename}")
        return await send_file(
            file_path, 
            as_attachment=True,
            attachment_filename=filename
        )
    else:
        logger.error(f"❌ File not found: {filename}")
        return jsonify({"error": "File not found"}), 404

@app.route('/logs')
async def view_logs():
    """Endpoint untuk melihat logs"""
    try:
        with open('pdf_processing.log', 'r') as f:
            logs = f.read()
        return jsonify({"logs": logs})
    except FileNotFoundError:
        return jsonify({"logs": "No logs found"})

if __name__ == '__main__':
    logger.info("🚀 Starting Quart PDF Processing Server with Web Interface")
    app.run(host='0.0.0.0', port=5000, debug=True)