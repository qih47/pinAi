import base64
import os
import uuid
import json
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
import logging
from datetime import datetime
import tempfile

from webui.backend.ocr.ocr_agent import extract_text_per_page
from database.db import DB_CONFIG


async def process_pdf_attachment_to_ocr(
    attachment, npp, session_id, get_embedding_func
):
    filename = attachment.get("name", f"upload_{uuid.uuid4()}.pdf")
    base64_data = attachment.get("data", "")
    file_id = attachment.get("file_id")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
        temp_path = tf.name
        try:
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]

            pdf_bytes = base64.b64decode(base64_data)
            tf.write(pdf_bytes)
            tf.flush()

            # 1. Jalankan OCR
            pages_content = extract_text_per_page(temp_path)

            if not pages_content:
                print("[WARNING] OCR balikin list kosong.")
                return ""

            all_text_for_chat = ""

            # KONEKSI KE DATABASE
            conn = psycopg2.connect(**DB_CONFIG)
            # Paksa koneksi untuk bisa membaca data yang baru di-commit transaksi lain
            conn.set_session(
                isolation_level=ISOLATION_LEVEL_READ_COMMITTED, autocommit=False
            )
            cur = conn.cursor()

            try:
                # --- VALIDASI ULANG DI DALAM KONEKSI INI ---
                final_session_id = None
                if session_id:
                    cur.execute(
                        "SELECT id FROM chat_sessions WHERE id = %s", (session_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        final_session_id = row[0]
                        print(
                            f"[DEBUG] Validasi DB: Session {final_session_id} ditemukan."
                        )
                    else:
                        print(
                            f"[WARNING] Session {session_id} tidak terlihat oleh koneksi ini. Menggunakan NULL."
                        )

                for i, content in enumerate(pages_content):
                    if not content.strip():
                        continue

                    embedding_vector = get_embedding_func(content)

                    metadata = {
                        "filename": filename,
                        "page": i + 1,
                        "method": "paddle_ocr_gpu",
                        "timestamp": datetime.now().isoformat(),
                    }

                    # INSERT
                    cur.execute(
                        """
                        INSERT INTO ai_document_chunks 
                        (session_id, file_id, npp, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            final_session_id,
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
            if os.path.exists(temp_path):
                os.remove(temp_path)
