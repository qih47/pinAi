import base64
import os
import uuid
import json
import psycopg2
import logging
from datetime import datetime
import tempfile

from webui.backend.ocr.ocr_agent import (
    extract_text_per_page,
)  # Fungsi PaddleOCR yang kita buat sebelumnya

# Pastikan DB_CONFIG diimport atau didefinisikan di sini
from database.db import DB_CONFIG


async def process_pdf_attachment_to_ocr(attachment, npp, session_id, get_embedding_func):
    filename = attachment.get("name", f"upload_{uuid.uuid4()}.pdf")
    base64_data = attachment.get("data", "")
    file_id = attachment.get("file_id")

    # Gunakan context manager untuk file sementara
    # Ini menjamin file ter-create dan path-nya valid
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
        temp_path = tf.name
        try:
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]

            pdf_bytes = base64.b64decode(base64_data)
            tf.write(pdf_bytes)
            tf.flush() # Pastikan data beneran ketulis ke disk
            
            print(f"[DEBUG] File PDF beneran ada di: {temp_path}")
            print(f"[DEBUG] Ukuran file: {os.path.getsize(temp_path)} bytes")

            # 1. Jalankan OCR
            # Pastikan fungsi ini SUDAH tidak pakai CUDA_VISIBLE_DEVICES="-1"
            pages_content = extract_text_per_page(temp_path)
            
            if not pages_content:
                print("[WARNING] OCR balikin list kosong. Cek log ocr_agent!")
                return ""

            all_text_for_chat = ""
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()

            try:
                for i, content in enumerate(pages_content):
                    if not content.strip():
                        continue

                    # 2. Vektorisasi
                    embedding_vector = get_embedding_func(content)
                    
                    # Pastikan format vector bener (PostgreSQL pgvector biasanya butuh list/array)
                    # Jika kolom embedding lu tipe 'vector', json.dumps(list) sudah benar.

                    metadata = {
                        "filename": filename,
                        "page": i + 1,
                        "method": "paddle_ocr_gpu",
                        "timestamp": datetime.now().isoformat(),
                    }

                    cur.execute(
                        """
                        INSERT INTO ai_document_chunks 
                        (session_id, file_id, npp, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session_id,
                            file_id if file_id else 0,
                            npp,
                            content,
                            json.dumps(embedding_vector),
                            json.dumps(metadata),
                        ),
                    )
                    all_text_for_chat += f"\n[Halaman {i + 1}]: {content}\n"

                conn.commit()
                print(f"[*] Berhasil simpan {len(pages_content)} halaman ke database.")

            except Exception as db_e:
                conn.rollback()
                print(f"[ERROR] DB Error: {db_e}")
                raise db_e
            finally:
                cur.close()
                conn.close()

            return all_text_for_chat

        except Exception as e:
            print(f"[CRITICAL] Gagal proses OCR: {e}")
            import traceback
            traceback.print_exc()
            return ""
        finally:
            # Hapus file temp setelah selesai
            if os.path.exists(temp_path):
                os.remove(temp_path)
                print(f"[DEBUG] File temp dihapus: {temp_path}")