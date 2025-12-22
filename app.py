from quart import Quart, render_template, request, session, jsonify
import fitz
import os
import subprocess
import re
import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor
import hashlib
from embeddings.chunk_skep import chunk_skep
from embeddings.chunk_se import chunk_se
from embeddings.chunk_ik import chunk_ik
from embeddings.chunk_prosedur import chunk_prosedur
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")
app = Quart(__name__)
app.config["UPLOAD_FOLDER"] = "./temp_uploads"
app.config["DB_DOC_FOLDER"] = "./db_doc"
app.config["OUTPUT_FOLDER"] = "./ocr_file"
app.secret_key = "pinAI-secret-key"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["DB_DOC_FOLDER"], exist_ok=True)
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

# Chunk SKEP
@app.route("/chunk_skep", methods=["POST"])
async def debug_skep():
    try:
        data = await request.get_json()
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Teks OCR kosong"}), 400

        sections = chunk_skep(text)
        preview = sections[:20]  # ambil 3 pertama untuk preview

        return jsonify({
            "doc_type": "SKEP",
            "chunk_count": len(sections),
            "preview_chunks": preview
        })
    except Exception as e:
        print(f"🚨 Error di /chunk_skep: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Chunk SE
@app.route("/chunk_se", methods=["POST"])
async def debug_se():
    try:
        data = await request.get_json()
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Teks OCR kosong"}), 400

        sections = chunk_se(text)
        preview = sections[:20]  # ambil 3 pertama untuk preview

        return jsonify({
            "doc_type": "SE",
            "chunk_count": len(sections),
            "preview_chunks": preview
        })
    except Exception as e:
        print(f"🚨 Error di /chunk_se: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
# Chunk IK
@app.route("/chunk_ik", methods=["POST"])
async def debug_ik():
    try:
        data = await request.get_json()
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Teks OCR kosong"}), 400

        sections = chunk_ik(text)
        preview = sections[:20]  # ambil 3 pertama untuk preview

        return jsonify({
            "doc_type": "IK",
            "chunk_count": len(sections),
            "preview_chunks": preview
        })
    except Exception as e:
        print(f"🚨 Error di /chunk_ik: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Prosedur
@app.route("/chunk_prosedur", methods=["POST"])
async def debug_prosedur():
    try:
        data = await request.get_json()
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Teks OCR kosong"}), 400

        sections = chunk_prosedur(text)
        preview = sections[:20]

        return jsonify({
            "doc_type": "PROSEDUR",
            "chunk_count": len(sections),
            "preview_chunks": preview
        })
    except Exception as e:
        print(f"🚨 Error di /chunk_prosedur: {str(e)}")
        return jsonify({"error": str(e)}), 500

# upload
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
            file_path = os.path.join(app.config["DB_DOC_FOLDER"], filename)
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
            if id_jenis == "1":  # SKEP
                from embeddings.chunk_skep import chunk_skep
                raw_sections = chunk_skep(ocr_text)

                # Ekstrak metadata untuk SKEP
                metadata = {
                    "doc_type": "SKEP",
                    "nomor": None,
                    "tanggal": None,
                    "tentang": None,
                    "judul": None
                }

                nomor_match = re.search(r'Nomor\s*[:：]\s*(Skep[/\d\w\s\-\.]+)', ocr_text, re.IGNORECASE)
                if nomor_match:
                    metadata["nomor"] = nomor_match.group(1).strip()
                    
                tanggal_match = re.search(r'(Ditetapkan di|Dikeluarkan di).*?\n.*?tanggal\s*[:：]?\s*([\d\s\w,\.]+)', ocr_text, re.IGNORECASE)
                if not tanggal_match:
                    tanggal_match = re.search(r'Pada tanggal\s*[:：]?\s*([\d\s\w,\.]+)', ocr_text, re.IGNORECASE)
                if tanggal_match:
                    metadata["tanggal"] = tanggal_match.group(1).strip()

                tentang_match = re.search(r'Tentang\s*\n\s*([^\n]+)', ocr_text, re.IGNORECASE)
                if tentang_match:
                    tentang_clean = tentang_match.group(1).strip()
                    metadata["tentang"] = tentang_clean
                    metadata["judul"] = tentang_clean

            elif id_jenis == "2":  # SE
                from embeddings.chunk_se import chunk_se
                raw_sections = chunk_se(ocr_text)
                
                # Konversi ke format dict
                sections_dict = []
                for i, content in enumerate(raw_sections):
                    sections_dict.append({
                        "type": "butir",
                        "title": f"Butir {i+1}",
                        "content": content,
                        "parent_title": None
                    })
                raw_sections = sections_dict

                # Ekstrak metadata untuk SE
                metadata = {
                    "doc_type": "SE",
                    "nomor": None,
                    "tanggal": None,
                    "tentang": None,
                    "judul": None
                }

                nomor_match = re.search(r'Nomor\s*[:：]\s*([SEse\d/\w\s\-\.]+)', ocr_text, re.IGNORECASE)
                if nomor_match:
                    metadata["nomor"] = nomor_match.group(1).strip()
                    
                tanggal_match = re.search(r'(Ditetapkan di|Dikeluarkan di).*?\n.*?tanggal\s*[:：]?\s*([\d\s\w,\.]+)', ocr_text, re.IGNORECASE)
                if not tanggal_match:
                    tanggal_match = re.search(r'Pada tanggal\s*[:：]?\s*([\d\s\w,\.]+)', ocr_text, re.IGNORECASE)
                if tanggal_match:
                    metadata["tanggal"] = tanggal_match.group(1).strip()

                tentang_match = re.search(r'Tentang\s*\n\s*([^\n]+)', ocr_text, re.IGNORECASE)
                if tentang_match:
                    tentang_clean = tentang_match.group(1).strip()
                    metadata["tentang"] = tentang_clean
                    metadata["judul"] = tentang_clean

            elif id_jenis == "3":  # IK (Instruksi Kerja)
                from embeddings.chunk_ik import chunk_ik
                raw_sections = chunk_ik(ocr_text)

                # Ekstrak metadata untuk IK
                metadata = {
                    "doc_type": "IK",
                    "nomor": None,
                    "tanggal": None,
                    "tentang": None,
                    "judul": None
                }

                # Nomor (cari pola seperti I-03-MI-555)
                nomor_match = re.search(r'(I[-\s]\d{2,3}[-\w\d]+)', ocr_text)
                if nomor_match:
                    metadata["nomor"] = nomor_match.group(1).strip()

                # Judul (ambil dari baris setelah INSTRUKSI KERJA)
                lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
                if lines:
                    for line in lines:
                        if "INSTRUKSI KERJA" in line.upper():
                            # Ambil baris berikutnya sebagai judul
                            idx = lines.index(line)
                            if idx + 1 < len(lines):
                                metadata["judul"] = lines[idx + 1]
                                metadata["tentang"] = lines[idx + 1]
                            break
                        
            elif id_jenis == "4":  # Prosedur
                from embeddings.chunk_prosedur import chunk_prosedur
                raw_sections = chunk_prosedur(ocr_text)

                # Ekstrak metadata untuk Prosedur
                metadata = {
                    "doc_type": "PROSEDUR",
                    "nomor": None,
                    "tanggal": None,
                    "tentang": None,
                    "judul": None
                }

                # Nomor (cari pola seperti P-11-PP-070)
                nomor_match = re.search(r'(P\s*[-–]\s*\d+\s*[-–]\s*[A-Z\d\s\-]+)', ocr_text)
                if nomor_match:
                    metadata["nomor"] = nomor_match.group(1).strip()

                # Judul (ambil dari baris pertama sebelum nomor)
                lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
                if lines:
                    for line in lines:
                        if "PROSEDUR" in line.upper():
                            # Ambil baris sebelumnya sebagai judul
                            idx = lines.index(line)
                            if idx > 0:
                                metadata["judul"] = lines[idx - 1]
                                metadata["tentang"] = lines[idx - 1]
                            break

            else:
                # Fallback untuk jenis lain
                raw_sections = [{
                    "type": "dokumen",
                    "title": "Dokumen Lengkap",
                    "content": ocr_text,
                    "parent_title": None
                }]
                metadata = {
                    "doc_type": "UNKNOWN",
                    "nomor": None,
                    "tanggal": None,
                    "tentang": None,
                    "judul": None
                }

            # Siapkan chunks_with_meta
            chunks_with_meta = []
            for i, sec in enumerate(raw_sections):
                chunk_meta = metadata.copy()
                chunk_meta.update({
                    "chunk_id": i + 1,
                    "content": sec["content"],
                    "section_type": sec["type"],
                    "section_title": sec["title"],
                    "parent_title": sec.get("parent_title")
                })
                chunks_with_meta.append(chunk_meta)

            # === SIMPAN KE DATABASE ===
            conn = get_db_connection()
            cur = conn.cursor()

            section_ids = {}
            temp_sections = []

            # Normalisasi function untuk konsistensi
            def normalize_title(title):
                return title.replace('–', '-').replace('—', '-').strip()

            for chunk in chunks_with_meta:
                content = chunk["content"]
                if not content.strip():
                    continue

                section_type = chunk.get("section_type", "bagian")
                section_title = chunk.get("section_title", f"Bagian {chunk['chunk_id']}")
                section_order = chunk["chunk_id"]
                parent_title = chunk.get("parent_title")

                # Normalisasi judul
                section_title_norm = normalize_title(section_title)
                parent_title_norm = normalize_title(parent_title) if parent_title else None

                cur.execute("""
                    INSERT INTO dokumen_section (
                        dokumen_id, section_type, section_title, content, section_order
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    dokumen_id,
                    section_type,
                    section_title_norm,
                    content,
                    section_order
                ))
                sec_id = cur.fetchone()[0]
                temp_sections.append((sec_id, parent_title_norm, section_title_norm))
                section_ids[section_title_norm] = sec_id

            # Update parent_id
            for sec_id, parent_title_norm, child_title in temp_sections:
                if parent_title_norm:
                    if parent_title_norm in section_ids:
                        parent_id = section_ids[parent_title_norm]
                        cur.execute("UPDATE dokumen_section SET parent_id = %s WHERE id = %s", (parent_id, sec_id))
                    else:
                        print(f"Warning: Parent '{parent_title_norm}' not found for section '{child_title}'")

            # Simpan ke dokumen_chunk (untuk RAG)
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)