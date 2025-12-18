import requests
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

# STRICT PROMPT IN [INST] FORMAT FOR QWEN3
BATCH_PROMPT = """[INST] Strictly correct the following OCR output into a clean, official corporate letter. Follow these rules exactly:

1. Fix all typos, spacing, punctuation, and capitalization.
2. Remove ONLY: page markers (e.g. "===== PAGE 1 ====="), lines of dots ("....."), and garbage like "UKAS", "2010-019-0000", "D(PE", "PT RINDAD".
3. NEVER delete real content: keep all articles, clauses, dates, names, signatures, and "Tembusan" list.
4. NEVER add any sentence, explanation, prefix, or suffix.
5. Output ONLY the corrected text — nothing before, nothing after.

Now process this text: [/INST]
"""

def correct_text_with_ollama(text):
    """Correct text using Ollama AI — full text, no chunking"""
    if not text or len(text.strip()) == 0:
        return text

    # Cek Ollama
    try:
        requests.get("http://localhost:11434/api/tags", timeout=5)
    except:
        print("⚠️ Ollama not running, skipping AI correction")
        return text

    if len(text) > 25000:
        print(f"⚠️ Text too long ({len(text)} chars). Truncating to 25K.")
        text = text[:25000]

    return _send_to_ollama(text)

def _send_to_ollama(text_chunk):
    full_prompt = BATCH_PROMPT + "\n\n" + text_chunk
    
    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 3000  # Cukup untuk output penuh
        }
    }
    
    try:
        print(f"   📤 Sending {len(text_chunk)} characters to Ollama...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=600)
        if response.status_code == 200:
            corrected = response.json().get("response", "").strip()
            return corrected
        else:
            print(f"❌ Ollama error: {response.status_code}")
            return text_chunk
    except Exception as e:
        print(f"❌ Ollama request failed: {str(e)[:100]}")
        return text_chunk

def strip_ai_artifacts(text):
    """Remove AI preambles like 'Here is the corrected version:'"""
    lines = text.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not re.match(
            r'^(Here is|I have|The corrected|Output:|Return only|Below is|Sure,|Certainly|As an AI)',
            stripped,
            re.IGNORECASE
        ):
            start_idx = i
            break
    return '\n'.join(lines[start_idx:]).strip()

def clean_document_content(text):
    """Hanya hapus PAGE markers dan baris kosong berlebih"""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^\s*={3,}\s*PAGE\s+\d+\s*={3,}\s*$', stripped, re.IGNORECASE):
            continue
        cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    return cleaned_text.strip()

def process_entire_document(input_file_path, output_dir="./file_koreksi"):
    """Process entire document as one unit"""
    print(f"📄 Processing entire document: {input_file_path}")
    
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    input_path = Path(input_file_path)
    filename = input_path.stem.replace('_paddleocr', '')
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    
    print("🔄 Cleaning document content...")
    clean_content = clean_document_content(content)
    print(f"📊 Document size: {len(clean_content)} characters")
    
    print("🤖 Applying AI correction to entire document...")
    start_time = time.time()
    corrected_content = correct_text_with_ollama(clean_content)
    corrected_content = strip_ai_artifacts(corrected_content)  # <-- CLEAN AI COMMENT
    processing_time = time.time() - start_time
    print(f"✅ AI correction completed in {processing_time:.1f} seconds")
    
    # Save
    timestamp = int(time.time())
    output_file = output_path / f"{filename}_full_corrected_{timestamp}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(corrected_content)
    
    print(f"\n✅ Corrected document saved: {output_file}")
    print(f"📊 Original size: {len(clean_content)} chars")
    print(f"📊 Corrected size: {len(corrected_content)} chars")
    
    return str(output_file)

def main():
    print("="*70)
    print("DOCUMENT CORRECTION TOOL - FULL DOCUMENT PROCESSING")
    print(f"AI Model: {MODEL_NAME}")
    print("="*70)
    print()
    
    input_file = get_latest_koreksi_file()
    
    if not input_file or not Path(input_file).exists():
        print(f"❌ File not found: {input_file}")
        outputs_dir = Path("./koreksi_file")
        if outputs_dir.exists():
            txt_files = list(outputs_dir.glob("*.txt"))
            if txt_files:
                ocr_files = [f for f in txt_files if '_paddleocr_' in f.name]
                input_file = str(ocr_files[0]) if ocr_files else str(txt_files[0])
                print(f"🔍 Using file: {input_file}")
            else:
                print("❌ No text files found in outputs folder")
                return
        else:
            print("❌ Outputs folder not found")
            return
    
    corrected_file = process_entire_document(input_file)
    if corrected_file:
        update_latest_clean_file(corrected_file)

if __name__ == "__main__":
    main()