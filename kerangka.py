from quart import Quart, render_template, request, session, jsonify
import fitz
import os
import subprocess
import asyncio
import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor
import hashlib
from tools.document_chunker import chunk_document
from tools.document_chunker import detect_document_type
from tools.document_chunker import chunk_skep
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")
app = Quart(__name__)
app.config["UPLOAD_FOLDER"] = "./temp_uploads"
app.config["OUTPUT_FOLDER"] = "./ocr_file"
app.secret_key = "pinAI-secret-key"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)


# =============================
# KONFIGURASI DATABASE
# =============================
def get_db_connection():
    return psycopg2.connect(
        host="localhost", database="ragdb", user="pindadai", password="Pindad123!"
    )


def get_jenis_dokumen():
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, nama FROM jenis_dokumen ORDER BY nama;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

def get_pdf_page_count(pdf_path):
    doc = fitz.open(pdf_path)
    count = doc.page_count
    doc.close()
    return count
# ==============================
# ROUTES
# ==============================
@app.route("/")
async def index():
    return await render_template("index.html", jenis_dokumen=get_jenis_dokumen())


@app.post("/proses_crop")
async def proses_crop():
    files = await request.files
    uploaded_file = files.get("file")

    if not uploaded_file:
        return jsonify({"error": "Tidak ada file PDF yang diupload"}), 400

    # Simpan file original
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], uploaded_file.filename)
    await uploaded_file.save(filepath)

    session["uploaded_filepath"] = filepath

    # Jalankan crop.py
    try:
        crop_result = subprocess.run(
            ["python3", "tools/crop.py", filepath],
            capture_output=True,
            text=True,
            check=True,
        )
        log_crop = crop_result.stdout
    except subprocess.CalledProcessError as e:
        log_crop = e.stdout + "\n" + e.stderr

    # HAPUS FILE INPUT setelah crop
    if os.path.exists(filepath):
        os.remove(filepath)

    return jsonify({
        "status": "crop_done",
        "log": log_crop
    })


@app.post("/proses_ocr")
async def proses_ocr():
    try:
        ocr_result = subprocess.run(
            ["python3", "ocr/doc_ocr_processor.py"],
            capture_output=True,
            text=True,
            check=True,
        )
        log_ocr = ocr_result.stdout
    except subprocess.CalledProcessError as e:
        log_ocr = e.stdout + "\n" + e.stderr

    return jsonify({
        "status": "ocr_done",
        "log": log_ocr
    })

@app.route("/get_latest_ocr_text")
async def get_latest_ocr_text():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT koreksi_file
            FROM history_file
            WHERE koreksi_file IS NOT NULL
            ORDER BY created_time DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row or not row[0]:
            return jsonify({"error": "Tidak ada file OCR ditemukan"}), 404

        ocr_file_path = row[0]
        if not os.path.exists(ocr_file_path):
            return jsonify({"error": "File OCR tidak ditemukan di disk"}), 404

        with open(ocr_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify({
            "filename": os.path.basename(ocr_file_path),
            "content": content
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# SIMPAN HADIL EDIT
@app.post("/save_edited_ocr")
async def save_edited_ocr():
    data = await request.get_json()
    content = data.get("content", "").strip()

    if not content:
        return jsonify({"error": "Teks kosong"}), 400

    try:
        # Ambil PATH FILE KOREKSI dari DB (kolom: koreksi_file)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT koreksi_file FROM history_file
            WHERE koreksi_file IS NOT NULL
            ORDER BY created_time DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row or not row[0]:
            return jsonify({"error": "Tidak ada file koreksi aktif di database"}), 404

        koreksi_file_path = row[0]

        # Pastikan folder ada
        os.makedirs(os.path.dirname(koreksi_file_path), exist_ok=True)

        # Simpan ke file koreksi (file yang memang sedang ditampilkan)
        with open(koreksi_file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({
            "status": "success",
            "message": f"Berhasil simpan ke: {os.path.basename(koreksi_file_path)}"
        })

    except Exception as e:
        print(f"❌ Error saat simpan file koreksi: {e}")
        return jsonify({"error": str(e)}), 500

# Upload
@app.post("/upload")
async def upload_document():
    try:
        form = await request.form
        files = await request.files
        file = files.get("file")

        # Ambil data dari form
        judul = form.get("judul_dokumen", "").strip()
        nomor = form.get("nomor_dokumen", "").strip()
        id_jenis = form.get("jenis_dokumen", "").strip()
        tanggal = form.get("tanggal_dokumen", "").strip()
        tempat = form.get("tempat_dokumen", "").strip()
        ocr_text = form.get("ocr_text", "").strip()

        if not judul or not id_jenis or not ocr_text:
            return jsonify({"error": "Data wajib tidak lengkap"}), 400

        # Simpan file asli (opsional)
        filename = None
        page_count = 0
        if file:
            filename = file.filename
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            await file.save(file_path)
            try:
                page_count = get_pdf_page_count(file_path)
            except:
                page_count = 0

        # === 1. Simpan ke tabel `dokumen` ===
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO dokumen (
                judul, nomor, id_jenis, tanggal, tempat,
                filename, clean_text, status_ocr,
                ocr_text_length, last_processed, ocr_page_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'rag_ready', %s, NOW(), %s)
            RETURNING id
        """, (
            judul,
            nomor,
            int(id_jenis) if id_jenis.isdigit() else None,
            tanggal or None,
            tempat,
            filename,
            ocr_text,
            len(ocr_text),
            page_count
        ))
        dokumen_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # === 2. Parse & simpan ke `dokumen_section` dan `dokumen_chunk` ===
        try:
            chunks_with_meta = chunk_document(ocr_text)  # list of dict

            conn = get_db_connection()
            cur = conn.cursor()

            # Step 1: Insert semua section, simpan mapping title -> id
            section_ids = {}  # { (section_title, section_order): id }
            temp_sections = []

            for chunk in chunks_with_meta:
                content = chunk["content"]
                if not content.strip():
                    continue

                section_type = chunk.get("section_type", "bagian")
                section_title = chunk.get("section_title", f"Bagian {chunk['chunk_id']}")
                section_order = chunk["chunk_id"]
                parent_title = chunk.get("parent_title")  # ← ini penting!

                cur.execute("""
                    INSERT INTO dokumen_section (
                        dokumen_id, section_type, section_title, content, section_order
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (dokumen_id, section_type, section_title, content, section_order))
                sec_id = cur.fetchone()[0]

                temp_sections.append((sec_id, parent_title, section_title, section_order))
                section_ids[(section_title, section_order)] = sec_id

            # Step 2: Update parent_id jika parent_title ada
            for sec_id, parent_title, child_title, order in temp_sections:
                if parent_title:
                    # Cari ID parent berdasarkan parent_title
                    cur.execute("""
                        SELECT id FROM dokumen_section
                        WHERE dokumen_id = %s AND section_title = %s
                    """, (dokumen_id, parent_title))
                    parent_row = cur.fetchone()
                    if parent_row:
                        cur.execute("UPDATE dokumen_section SET parent_id = %s WHERE id = %s", (parent_row[0], sec_id))

            # Step 3: Simpan ke dokumen_chunk (flat, untuk RAG)
            for chunk in chunks_with_meta:
                content = chunk["content"]
                if not content.strip():
                    continue

                text_hash = hashlib.md5(content.encode()).hexdigest()
                embedding = EMBEDDING_MODEL.encode(content).tolist()

                cur.execute("""
                    INSERT INTO dokumen_chunk (
                        dokumen_id, chunk_id, content, metadata,
                        embedding, embedding_model, chunk_size, text_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    dokumen_id,
                    chunk["chunk_id"],
                    content,
                    Json(chunk),
                    embedding,
                    "BAAI/bge-m3",
                    len(content),
                    text_hash
                ))

            conn.commit()
            cur.close()
            conn.close()

        except Exception as chunk_err:
            print(f"⚠️ Error saat chunking/embedding: {chunk_err}")
            # Opsional: update status_ocr = 'cleaned' jika gagal chunking
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE dokumen SET status_ocr = 'cleaned' WHERE id = %s", (dokumen_id,))
            conn.commit()
            cur.close()
            conn.close()

        return jsonify({"status": "success"})

    except Exception as e:
        print(f"❌ Error simpan dokumen: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/debug_chunks", methods=["POST"])
def debug_chunks():
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Teks OCR kosong"}), 400

        doc_type = detect_document_type(text)
        if doc_type == "SKEP":
            # Ambil output mentah dari chunk_skep()
            raw_chunks = chunk_skep(text)
            # Ambil 3 chunk pertama untuk preview
            preview = raw_chunks[:3]
            return jsonify({
                "doc_type": doc_type,
                "chunk_count": len(raw_chunks),
                "preview_chunks": preview
            })
        else:
            # Untuk SE/IK/Prosedur, pakai chunk_document
            chunks = chunk_document(text)
            preview = chunks[:3]
            return jsonify({
                "doc_type": doc_type,
                "chunk_count": len(chunks),
                "preview_chunks": preview
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
