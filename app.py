from flask import Flask, render_template, request, Response
import psycopg2
from psycopg2.extras import RealDictCursor
import os, time, torch, easyocr, cv2, numpy as np, fitz
from werkzeug.utils import secure_filename
from ocr_processor import process_pending_docs
from chunk_embed_processor import process_all_embeddings

# =============================
# INISIALISASI FLASK
# =============================
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =============================
# KONFIGURASI DATABASE
# =============================
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="ragdb",
        user="pindadai",
        password="Pindad123!"
    )

# =============================
# INISIALISASI EASY OCR
# =============================
gpu_available = torch.cuda.is_available()
device = torch.cuda.get_device_name(0) if gpu_available else "CPU"
print(f"✅ Device OCR aktif: {device}")
reader = easyocr.Reader(["en", "id"], gpu=gpu_available)

# =============================
# FUNGSI PREPROCESS
# =============================
def enhance_image_for_ocr(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        doc = fitz.open(file_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        image_path = file_path.replace(".pdf", ".png")
        pix.save(image_path)
        doc.close()
    else:
        image_path = file_path

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Gagal membaca file gambar: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    if mean_brightness < 128:
        gray = cv2.bitwise_not(gray)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

    processed_path = os.path.join(app.config["UPLOAD_FOLDER"], "processed_" + os.path.basename(image_path))
    cv2.imwrite(processed_path, denoised)
    return processed_path

# =============================
# ROUTE INDEX
# =============================
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", jenis_dokumen=get_jenis_dokumen())

# =============================
# ROUTE UPLOAD + PROSES OTOMATIS
# =============================
@app.route("/upload", methods=["POST"])
def upload():
    conn = get_db_connection()
    cur = conn.cursor()

    judul = request.form.get("judul_dokumen")
    nomor = request.form.get("nomor_dokumen")
    id_jenis = request.form.get("jenis_dokumen")
    tanggal = request.form.get("tanggal_dokumen")
    tempat = request.form.get("tempat_dokumen")
    file = request.files["file"]

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    processed_path = enhance_image_for_ocr(filepath)
    ocr_results = reader.readtext(processed_path, detail=0, paragraph=True)
    extracted_text = "\n".join(ocr_results)

    try:
        cur.execute("""
            INSERT INTO dokumen (judul, nomor, id_jenis, tanggal, tempat, filename, status_ocr)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            RETURNING id;
        """, (judul, nomor, id_jenis, tanggal, tempat, filename))
        dokumen_id = cur.fetchone()[0]
        conn.commit()
        message = f"✅ Dokumen {judul} disimpan (ID {dokumen_id}). Mulai proses OCR + Embedding..."
    except Exception as e:
        conn.rollback()
        message = f"❌ Gagal menyimpan dokumen: {str(e)}"
        cur.close()
        conn.close()
        return render_template("index.html", message=message, jenis_dokumen=get_jenis_dokumen())

    cur.close()
    conn.close()

    # === PROSES OTOMATIS ===
    process_pending_docs()
    process_all_embeddings()

    message += " ✅ Semua tahap selesai!"
    return render_template("index.html",
                           message=message,
                           ocr_text=extracted_text,
                           jenis_dokumen=get_jenis_dokumen())

# =============================
# HELPER
# =============================
def get_jenis_dokumen():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, nama FROM jenis_dokumen ORDER BY nama;")
    jenis_dokumen = cur.fetchall()
    cur.close()
    conn.close()
    return jenis_dokumen

# =============================
# MAIN APP
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
