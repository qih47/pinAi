import os
import datetime
import fitz  # PyMuPDF
import psycopg2
from psycopg2.extras import RealDictCursor
import easyocr

# ==============================
# KONFIGURASI
# ==============================
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!"
}

UPLOAD_DIR = "static/uploads"
OUTPUT_DIR = "static/ocr_pages"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==============================
# KONEKSI DATABASE
# ==============================
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# ==============================
# AMBIL DOKUMEN PENDING
# ==============================
def get_pending_docs(limit=5):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, filename
        FROM dokumen
        WHERE status_ocr = 'pending'
        ORDER BY created_at ASC
        LIMIT %s;
    """, (limit,))
    docs = cur.fetchall()
    cur.close()
    conn.close()
    return docs

# ==============================
# KONVERSI PDF → GAMBAR
# ==============================
def convert_pdf_to_images(pdf_path, output_dir):
    """Convert setiap halaman PDF menjadi PNG"""
    doc = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # resolusi 2x
        img_name = f"{os.path.basename(pdf_path)}_page_{i+1}.png"
        img_path = os.path.join(output_dir, img_name)
        pix.save(img_path)
        images.append(img_path)
    doc.close()
    return images

# ==============================
# OCR PROCESS
# ==============================
reader = easyocr.Reader(["id", "en"], gpu=True)
print("✅ EasyOCR initialized with GPU support")

def run_ocr_on_images(doc_id, image_paths):
    """Jalankan OCR dan simpan hasil ke database"""
    conn = get_db_connection()
    cur = conn.cursor()

    all_text = []
    for idx, img_path in enumerate(image_paths, start=1):
        print(f"🔍 OCR halaman {idx}/{len(image_paths)} : {img_path}")
        try:
            results = reader.readtext(img_path, detail=0, paragraph=True)
            text = "\n".join(results).strip()
            all_text.append(text)

            # Simpan per halaman ke dokumen_chunk
            cur.execute("""
                INSERT INTO dokumen_chunk (dokumen_id, chunk_id, content, created_at)
                VALUES (%s, %s, %s, %s)
            """, (doc_id, idx, text, datetime.datetime.now()))

        except Exception as e:
            print(f"⚠️ Gagal OCR halaman {idx}: {e}")

    # Update status dokumen
    total_text = "\n".join(all_text)
    cur.execute("""
        UPDATE dokumen
        SET status_ocr = 'done',
            last_processed = NOW(),
            ocr_page_count = %s,
            ocr_text_length = %s
        WHERE id = %s
    """, (len(image_paths), len(total_text), doc_id))

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ OCR selesai untuk dokumen ID {doc_id} — {len(image_paths)} halaman")

# ==============================
# PROSES DOKUMEN PENDING (dipanggil dari app.py)
# ==============================
def process_pending_docs(limit=5):
    docs = get_pending_docs(limit)
    if not docs:
        print("⚠️ Tidak ada dokumen pending.")
        return

    for doc in docs:
        file_path = os.path.join(UPLOAD_DIR, doc["filename"])
        if not os.path.exists(file_path):
            print(f"❌ File tidak ditemukan: {file_path}")
            continue

        print(f"\n📄 Memproses dokumen ID {doc['id']} → {doc['filename']}")
        try:
            image_paths = convert_pdf_to_images(file_path, OUTPUT_DIR)
            print(f"🖼️ Konversi selesai ({len(image_paths)} halaman). Memulai OCR...")
            run_ocr_on_images(doc["id"], image_paths)
        except Exception as e:
            print(f"❌ Gagal proses dokumen ID {doc['id']}: {e}")

    print("✅ Semua proses OCR selesai.")

# ==============================
# MAIN STANDALONE MODE
# ==============================
if __name__ == "__main__":
    print("🚀 Memulai OCR Processor...")
    process_pending_docs()
    print("\n🏁 Semua proses OCR selesai.")
