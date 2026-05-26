import fitz
import base64
import requests
from pathlib import Path
from PIL import Image
import io
import time
import psycopg2

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

# ==============================
# KONFIGURASI
# ==============================
PDF_DIR = Path("ocr_file")
OUTPUT_DIR = Path("file_koreksi")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3-vl:8b"

OUTPUT_DIR.mkdir(exist_ok=True)

PROMPT = (
    "You are an OCR engine.\n"
    "Extract ALL readable text from this document image.\n"
    "Preserve paragraphs and line breaks.\n"
    "Do NOT summarize.\n"
    "Do NOT explain.\n"
    "Return only the extracted text."
)

# ==============================
# UTIL
# ==============================
def image_to_base64(img: Image.Image) -> str:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def call_qwen_vl(image_b64: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": PROMPT,
        "stream": False,
        "images": [image_b64],
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=600)
    response.raise_for_status()
    return response.json().get("response", "")


# ==============================
# CORE
# ==============================
def extract_pdf(pdf_path: Path) -> str:
    print(f"\n📄 Processing: {pdf_path.name}")
    doc = fitz.open(pdf_path)

    collected_text = []

    for idx in range(doc.page_count):
        page = doc.load_page(idx)

        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        print(f"   🖼️ Page {idx + 1}/{doc.page_count} → Qwen3-VL")

        start = time.time()
        text = call_qwen_vl(image_to_base64(img))
        elapsed = time.time() - start

        print(f"      ✓ Done ({elapsed:.1f}s)")

        collected_text.append(f"\n===== PAGE {idx + 1} =====\n")
        collected_text.append(text.strip())

    doc.close()
    return "\n".join(collected_text)

# ==============================
# MAIN
# ==============================
def main():
    pdf_path = get_latest_ocr_file()  # Ini string atau None

    if not pdf_path:
        print("❌ No OCR file found in history_file DB. Exiting...")
        return

    print(f"📄 Processing: {pdf_path}")
    try:
        text = extract_pdf(Path(pdf_path))  # Pastikan jadi Path object

        output_file = OUTPUT_DIR / f"{Path(pdf_path).stem}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"\n✅ Saved: {output_file}\n")

        # Opsional: simpan path hasil ke DB
        update_latest_koreksi_file(str(output_file))

    except Exception as e:
        print(f"❌ Gagal memproses {pdf_path}: {e}")


if __name__ == "__main__":
    main()
