import requests
import json
import re
from pathlib import Path
import time
import psycopg2

# ================================
# FUNGSI AMBIL FILE TERBARU DARI DB
# ================================
def get_latest_koreksi_file(db_config=None):
    """
    Ambil nama file koreksi_file terbaru dari tabel history_file
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
                SELECT koreksi_file
                FROM history_file
                WHERE koreksi_file IS NOT NULL
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

def update_latest_clean_file(file_path, db_config=None):
    """
    Update kolom clean_file pada record ID terbaru di tabel history_file
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
                SET clean_file = %s
                WHERE id = (SELECT id FROM history_file ORDER BY created_time DESC LIMIT 1)
            """, (file_path,))
            conn.commit()
        conn.close()
        print(f"✅ Updated latest history_file record with clean_file: {file_path}")
    except Exception as e:
        print(f"❌ Failed to update clean_file in DB: {e}")

# OLLAMA CONFIGURATION
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:8b"

# BATCH PROMPT FOR TEXT CORRECTION - GENERAL RULES
BATCH_PROMPT = """Clean and correct the following OCR-extracted text from a formal document:

- Fix typos and obvious OCR errors.
- Remove page markers like "===== PAGE 1 =====".
- Preserve the original meaning and structure.
- Format the output as clean, professional document text.
- Do not add any comments, explanations, or extra content.

Corrected text only:
"""

def correct_text_with_ollama(text):
    """Correct text using Ollama AI"""
    if not text or len(text.strip()) == 0:
        return text
        
    try:
        # Check if Ollama is running
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code != 200:
                print("⚠️ Ollama not running, skipping AI correction")
                return text
        except:
            print("⚠️ Ollama not running, skipping AI correction")
            return text
        
        # Send entire text at once
        return _send_to_ollama(text)
            
    except Exception as e:
        print(f"⚠️ AI correction failed: {str(e)[:100]}")
        return text

def _send_to_ollama(text_chunk):
    """Send text chunk to Ollama"""
    full_prompt = BATCH_PROMPT + "\n" + text_chunk
    
    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": len(text_chunk) + 1000
        }
    }
    
    try:
        print(f"   📤 Sending {len(text_chunk)} characters to Ollama...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            corrected_text = result.get("response", "").strip()
            
            # Clean up response
            if "Teks yang perlu dikoreksi:" in corrected_text:
                corrected_text = corrected_text.split("Teks yang perlu dikoreksi:")[-1].strip()
            
            return corrected_text
        else:
            print(f"❌ Ollama API error: {response.status_code}")
            return text_chunk
            
    except Exception as e:
        print(f"❌ Error sending to Ollama: {str(e)[:100]}")
        return text_chunk

def clean_document_content(text):
    """Remove noise, page markers, headers, footers, and standalone page numbers"""
    lines = text.split('\n')
    cleaned_lines = []
    
    # Pola yang ingin dihapus
    noise_patterns = [
        r'^\s*={3,}\s*PAGE\s+\d+\s*={3,}\s*$',  # ===== PAGE 1 ====
        r'^\s*\d+\s*$',                          # baris hanya berisi "2", "3", dll
        r'^\s*(Head Office|Representative Office|UKAS)\s*$',  # noise khas
        r'^\s*\d{4}-\d{3}-\d{4}\s*$',           # kode seperti 2010-019-0000
        r'^\s*\d{4}-\d{4}\s*$',                 # kode seperti 1000-0000
        r'^\s*$',                               # skip empty for now (will re-add later)
    ]
    
    for line in lines:
        stripped = line.strip()
        
        # Skip jika cocok dengan pola noise
        skip = False
        for pattern in noise_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                skip = True
                break
        
        if not skip:
            cleaned_lines.append(line)  # pertahankan indentasi asli jika perlu
    
    # Gabungkan dan rapikan baris kosong berlebih
    cleaned_text = '\n'.join(cleaned_lines)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)  # max 2 baris kosong
    return cleaned_text.strip()

def process_entire_document(input_file_path, output_dir="./file_koreksi"):
    """Process entire document as one unit"""
    print(f"📄 Processing entire document: {input_file_path}")
    
    # Read input file
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    # Extract filename for output
    input_path = Path(input_file_path)
    filename = input_path.stem.replace('_paddleocr', '')
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    
    # Clean the document content
    print("🔄 Cleaning document content...")
    clean_content = clean_document_content(content)
    
    print(f"📊 Document size: {len(clean_content)} characters")
    
    # Apply AI correction to entire document
    print("🤖 Applying AI correction to entire document...")
    start_time = time.time()
    
    corrected_content = correct_text_with_ollama(clean_content)
    
    processing_time = time.time() - start_time
    print(f"✅ AI correction completed in {processing_time:.1f} seconds")
    
    final_output = corrected_content
    
    # Save corrected document
    timestamp = int(time.time())
    output_file = output_path / f"{filename}_full_corrected_{timestamp}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_output)
    
    print(f"\n✅ Corrected document saved: {output_file}")
    print(f"📊 Original size: {len(clean_content)} characters")
    print(f"📊 Corrected size: {len(corrected_content)} characters")
    
    return str(output_file)

def main():
    print("="*70)
    print("DOCUMENT CORRECTION TOOL - FULL DOCUMENT PROCESSING")
    print(f"AI Model: {MODEL_NAME}")
    print("="*70)
    print()
    
    # Ambil file OCR terbaru
    input_file = get_latest_koreksi_file()
    
    # Cek file
    if not input_file or not Path(input_file).exists():
        print(f"❌ File not found: {input_file}")
        outputs_dir = Path("./koreksi_file")
        if outputs_dir.exists():
            txt_files = list(outputs_dir.glob("*.txt"))
            if txt_files:
                # Gunakan file OCR pertama yang ada
                ocr_files = [f for f in txt_files if '_paddleocr_' in f.name]
                if ocr_files:
                    input_file = str(ocr_files[0])
                else:
                    input_file = str(txt_files[0])
                print(f"🔍 Using file: {input_file}")
            else:
                print("❌ No text files found in outputs folder")
                return
        else:
            print("❌ Outputs folder not found")
            return
    
    # Proses dokumen satu kali
    corrected_file = process_entire_document(input_file)
    
    # Update DB
    if corrected_file:
        update_latest_clean_file(corrected_file)

if __name__ == "__main__":
    main()