from flask import Flask, render_template, request, Response
import psycopg2
from psycopg2.extras import RealDictCursor
import os, time, torch, easyocr, cv2, numpy as np, fitz
from werkzeug.utils import secure_filename

# >>> IMPORT OCR + EMBED PROCESSOR
from ocr.ocr_processor import process_pending_docs
from ocr.chunk_embed_processor import process_all_embeddings

# >>> IMPORT PARSERS
from parsers.parser_se import parse_se_document
# nanti tambahkan:
# from pinAi.parsers.parser_ik import parse_ik_document
# from pinAi.parsers.parser_prosedur import parse_prosedur_document
# from pinAi.parsers.parser_skep import parse_skep_document


# =============================
# INISIALISASI FLASK
# =============================
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["DOCUMENT_FOLDER"] = "static/documents"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["DOCUMENT_FOLDER"], exist_ok=True)

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
    id_jenis = request.form.get("jenis_dokumen")  # penting untuk parser
    tanggal = request.form.get("tanggal_dokumen")
    tempat = request.form.get("tempat_dokumen")
    file = request.files["file"]

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # ===========================================
    # SIMPAN PDF KE static/documents
    # ===========================================
    if filename.lower().endswith(".pdf"):
        dest = os.path.join(app.config["DOCUMENT_FOLDER"], filename)
        file.seek(0)
        file.save(dest)
        print(f"📄 File PDF disalin ke: {dest}")

    # OCR pada file
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
        message = f"✅ Dokumen {judul} disimpan (ID {dokumen_id}). Mulai proses..."
    except Exception as e:
        conn.rollback()
        message = f"❌ Gagal menyimpan dokumen: {str(e)}"
        cur.close()
        conn.close()
        return render_template("index.html", message=message, jenis_dokumen=get_jenis_dokumen())

    cur.close()
    conn.close()


    # 🔵 1. JALANKAN OCR PADA SEMUA HALAMAN PDF
    process_pending_docs()

    # 🔵 2. Ambil teks OCR hasil chunk
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT content FROM dokumen_chunk
        WHERE dokumen_id = %s
        ORDER BY chunk_id ASC
    """, (dokumen_id,))
    chunks = cur.fetchall()
    cur.close()
    conn.close()

    full_text = "\n".join([c["content"] for c in chunks])

    # ============================================================
    # 🔵 3. PANGGIL PARSER SESUAI JENIS DOKUMEN
    # ============================================================
    sections_output = []

    if id_jenis == "2":  # SE
        sections_output = parse_se_document(dokumen_id, full_text)
        print("🟦 Parser SE dijalankan.")

    # elif id_jenis == "1":
    #     parse_ik_document(dokumen_id, full_text)
    # elif id_jenis == "3":
    #     parse_prosedur_document(dokumen_id, full_text)
    # elif id_jenis == "4":
    #     parse_skep_document(dokumen_id, full_text)
    else:
        print(f"⚠️ Tidak ada parser untuk jenis dokumen id={id_jenis}")

    # ============================================================
    # 🔵 4. EMBEDDING
    # ============================================================
    process_all_embeddings()

    message += " ✅ OCR + Parsing + Embedding selesai!"

    return render_template("index.html",
                           message=message,
                           ocr_text=extracted_text,
                           jenis_dokumen=get_jenis_dokumen(),
                           sections=sections_output)


# =============================
# HELPER
# =============================
def get_jenis_dokumen():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, nama FROM jenis_dokumen ORDER BY nama;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# =============================
# MAIN APP
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
