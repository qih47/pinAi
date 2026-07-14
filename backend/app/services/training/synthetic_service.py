import asyncio
import logging
from typing import List, Dict, Any
from backend.app.core.database import get_db, get_peraturan_db, embedding_to_pgvector_str
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.rag.vector_service import VectorService
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_SYNTHETIC_TRAINING")

class SyntheticTrainingService:
    @staticmethod
    async def get_source_docs() -> List[Dict[str, Any]]:
        """
        Fetches documents from qa_peraturan_db (berita) and cross-checks with rag_document_questions.
        Returns list with is_synthetic_embedded flag.
        """
        try:
            mysql_docs = []
            async with get_peraturan_db() as conn_mysql:
                async with conn_mysql.cursor() as cur:
                    await cur.execute("""
                        SELECT id_berita, judul, noper, tanggal, gambar, id_kategori
                        FROM berita
                        ORDER BY id_berita DESC
                    """)
                    columns = [col[0] for col in cur.description]
                    rows = await cur.fetchall()
                    for row in rows:
                        mysql_docs.append(dict(zip(columns, row)))

            synthetic_ids = set()
            async with get_db() as conn_pg:
                pg_synth_rows = await conn_pg.fetch("SELECT DISTINCT source_id FROM rag_document_questions WHERE source_db = 'peraturan_db'")
                synthetic_ids = {row['source_id'] for row in pg_synth_rows}

            result = []
            for doc in mysql_docs:
                doc_id = doc['id_berita']
                result.append({
                    "id": doc_id,
                    "judul": doc['judul'],
                    "noper": doc['noper'],
                    "tanggal": doc['tanggal'].isoformat() if hasattr(doc['tanggal'], 'isoformat') else str(doc['tanggal']) if doc['tanggal'] else None,
                    "kategori_id": doc['id_kategori'],
                    "file_name": doc['gambar'],
                    "is_synthetic_embedded": doc_id in synthetic_ids
                })

            return result
        except Exception as e:
            logger.error(f"Failed to fetch synthetic source docs: {e}")
            raise RuntimeError(f"Database error: {e}")

    @staticmethod
    async def run_synthetic_pipeline(job_id: str, dokumen_id: int, request):
        """
        Generates and embeds synthetic questions for a document.
        Updates job progress in training_jobs table directly to avoid touching job_manager.py
        """
        async def update_progress(status: str, progress: int, log_msg: str):
            async with get_db() as conn:
                await conn.execute("""
                    UPDATE training_jobs 
                    SET status = $1, progress = $2, logs = CONCAT(logs, '\n[', NOW()::text, '] ', $3::text), updated_at = NOW()
                    WHERE job_id = $4::uuid
                """, status, progress, log_msg, job_id)
                logger.debug(f"[SYNTHETIC_JOB] {job_id}: {progress}% - {log_msg}")

        try:
            await update_progress("RUNNING", 10, "Fetching document metadata from MySQL (peraturan_db)...")
            
            doc_data = None
            async with get_peraturan_db() as conn_mysql:
                async with conn_mysql.cursor() as cur:
                    await cur.execute("SELECT judul, tag, isi_berita FROM berita WHERE id_berita = %s", (dokumen_id,))
                    row = await cur.fetchone()
                    if row:
                        doc_data = {"judul": row[0], "tag": row[1], "isi_berita": row[2]}
            
            if not doc_data:
                raise ValueError(f"Document ID {dokumen_id} not found in MySQL")
                
            await update_progress("RUNNING", 30, f"Generating synthetic queries using LLM for '{doc_data['judul'][:30]}...'")
            
            prompt = f"""Kamu adalah ahli sistem pencarian RAG (Retrieval-Augmented Generation).
Berdasarkan metadata dokumen Surat Keputusan / Peraturan berikut:
JUDUL: {doc_data['judul']}
TAG: {doc_data['tag']}
ISI/RINGKASAN: {doc_data['isi_berita']}

TUGAS:
Buatkan daftar pertanyaan sebanyak-banyaknya (sebanyak mungkin) yang mungkin ditanyakan oleh pengguna (karyawan) jika mereka mencari informasi yang ada di dalam dokumen ini. 
Gunakan berbagai variasi bahasa: baku, santai, slang kantoran, disingkat, atau bahkan menggunakan bahasa gaul.

PENTING:
Hanya keluarkan daftar pertanyaan. Setiap pertanyaan harus berada di baris baru dan diawali dengan tanda strip (-). Jangan berikan teks pembuka atau penutup sama sekali.
"""
            
            questions = []
            full_response = ""
            model_name = settings.MODEL_PERSONA
            async for chunk in stream_ollama_chat(model_name, [{"role": "user", "content": prompt}], request):
                full_response += chunk
                
            for line in full_response.split('\n'):
                line = line.strip()
                if line.startswith("-") or line.startswith("*") or (len(line) > 3 and line[0].isdigit() and line[1] in [".", ")"]):
                    q = line.lstrip("-*0123456789.) ").strip()
                    if q and len(q) > 4:
                        questions.append(q)
                        
            if not questions:
                questions = [f"Apa isi dari {doc_data['judul']}?"]
                
            await update_progress("RUNNING", 60, f"Generated {len(questions)} synthetic queries. Embedding vectors...")
            
            vector_service = VectorService()
            async with get_db() as conn_pg:
                for i, q in enumerate(questions):
                    if i % 5 == 0:
                        progress = 60 + int((i/max(1, len(questions)))*30)
                        await update_progress("RUNNING", progress, f"Embedding query {i+1}/{len(questions)}...")
                    
                    emb = await vector_service.get_query_embedding(q)
                    if emb:
                        emb_str = embedding_to_pgvector_str(emb)
                        await conn_pg.execute("""
                            INSERT INTO rag_document_questions (source_db, source_id, generated_question, embedding)
                            VALUES ('peraturan_db', $1, $2, $3::vector)
                        """, dokumen_id, q, emb_str)
                        
            await update_progress("DONE", 100, "Synthetic queries saved successfully.")
        except Exception as e:
            logger.error(f"❌ [SYNTHETIC_JOB] Job {job_id} failed: {str(e)}")
            await update_progress("FAILED", 0, f"Error: {str(e)}")

    @staticmethod
    async def run_batch_synthetic_pipeline(job_id: str, request):
        """
        Runs synthetic Q&A generation for ALL unenrolled documents in a single job.
        """
        async def update_progress(status: str, progress: int, log_msg: str):
            async with get_db() as conn:
                await conn.execute("""
                    UPDATE training_jobs 
                    SET status = $1, progress = $2, logs = CONCAT(logs, '\n[', NOW()::text, '] ', $3::text), updated_at = NOW()
                    WHERE job_id = $4::uuid
                """, status, progress, log_msg, job_id)
                
        try:
            await update_progress("RUNNING", 5, "Memulai proses Batch Training. Mengambil semua dokumen yang belum di-embed...")
            docs = await SyntheticTrainingService.get_source_docs()
            missing_docs = [doc for doc in docs if not doc.get("is_synthetic_embedded", False)]
            
            if not missing_docs:
                await update_progress("DONE", 100, "Semua dokumen sudah memiliki Synthetic Q&A. Tidak ada yang perlu diproses.")
                return
                
            total = len(missing_docs)
            await update_progress("RUNNING", 10, f"Ditemukan {total} dokumen yang akan diproses secara batch...")
            
            vector_service = VectorService()
            model_name = settings.MODEL_PERSONA
            
            # Helper for LLM and Vector
            for idx, doc in enumerate(missing_docs):
                progress = 10 + int((idx / total) * 85)
                await update_progress("RUNNING", progress, f"Memproses dokumen {idx+1}/{total} (ID: {doc['id']}) - {doc['judul'][:30]}...")
                
                # Fetch full metadata
                doc_data = None
                async with get_peraturan_db() as conn_mysql:
                    async with conn_mysql.cursor() as cur:
                        await cur.execute("SELECT judul, tag, isi_berita FROM berita WHERE id_berita = %s", (doc['id'],))
                        row = await cur.fetchone()
                        if row:
                            doc_data = {"judul": row[0], "tag": row[1], "isi_berita": row[2]}
                            
                if not doc_data:
                    continue
                    
                prompt = f"""Kamu adalah ahli sistem pencarian RAG.
Berdasarkan metadata dokumen berikut:
JUDUL: {doc_data['judul']}
TAG: {doc_data['tag']}
ISI/RINGKASAN: {doc_data['isi_berita']}

Buatkan daftar pertanyaan sebanyak-banyaknya yang mungkin ditanyakan oleh karyawan tentang dokumen ini.
PENTING:
Hanya keluarkan daftar pertanyaan. Setiap pertanyaan harus berada di baris baru dan diawali dengan tanda strip (-). Jangan berikan teks pembuka atau penutup sama sekali.
"""
                
                import json
                questions = []
                full_response = ""
                async for chunk_str in stream_ollama_chat(model_name, [{"role": "user", "content": prompt}], request):
                    try:
                        data = json.loads(chunk_str)
                        if "chunk" in data:
                            full_response += data["chunk"]
                    except:
                        pass
                    
                for line in full_response.split('\n'):
                    line = line.strip()
                    if line.startswith("-") or line.startswith("*") or (len(line) > 3 and line[0].isdigit() and line[1] in [".", ")"]):
                        q = line.lstrip("-*0123456789.) ").strip()
                        if q and len(q) > 4:
                            questions.append(q)
                            
                if not questions:
                    questions = [f"Apa isi dari {doc_data['judul']}?"]
                    
                async with get_db() as conn_pg:
                    for q in questions:
                        emb = await vector_service.get_query_embedding(q)
                        if emb:
                            emb_str = embedding_to_pgvector_str(emb)
                            await conn_pg.execute("""
                                INSERT INTO rag_document_questions (source_db, source_id, generated_question, embedding)
                                VALUES ('peraturan_db', $1, $2, $3::vector)
                            """, doc['id'], q, emb_str)
                            
            await update_progress("DONE", 100, f"Berhasil menyelesaikan batch training untuk {total} dokumen!")
            
        except Exception as e:
            logger.error(f"❌ [SYNTHETIC_BATCH] Failed: {str(e)}")
            await update_progress("FAILED", 0, f"Error: {str(e)}")

synthetic_training_service = SyntheticTrainingService()
