"""
CAKRA AI — 5-Worker Synchronized Training Coordinator
=====================================================
Menjalankan 5 worker secara sinkron untuk setiap halaman/bagian dokumen:
- Worker 1: Standard Text RAG (Hierarchical Chunks + pgvector 1024)
- Worker 2: Synthetic Q&A Generator (UNLIMITED Q&A via Gemma-4 31B)
- Worker 3: Graph RAG (Knowledge Graph Entity & Relation Extraction)
- Worker 4: Vision RAG (Page Image Snapshot & Visual Features)
- Worker 5: LoRA Fine-Tuning (Instruction Tuning Dataset & Adapter Pipeline)
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
import httpx

from backend.app.core.database import embedding_to_pgvector_str
from backend.app.core.config import settings
from backend.app.services.rag.vector_service import VectorService
from .db_setup import get_ragdb_conn
from .page_parser import StitchedSection, BookPageReader

logger = logging.getLogger("CAKRA_WORKER_COORDINATOR")

class WorkerCoordinator:
    def __init__(self, ollama_url: Optional[str] = None, model_name: Optional[str] = None):
        self.ollama_url = (ollama_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or "gemma4:31b"
        self.vector_service = VectorService()
        # Timeout 600s: Unlimited Q&A generation bisa membutuhkan ~5-10 menit per spread
        self.http_client = httpx.AsyncClient(timeout=600.0)

        # Direktori penampung dataset LoRA & page image
        self.finetune_data_dir = "/home/qisthi/pinAi/data/finetune"
        self.pages_image_dir = "/home/qisthi/pinAi/backend/storage/doc_pages"
        os.makedirs(self.finetune_data_dir, exist_ok=True)
        os.makedirs(self.pages_image_dir, exist_ok=True)

    async def _call_ollama_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> str:
        """
        Helper memanggil Gemma-4 31B di Ollama (Mendukung Input Multimodal Images).
        Menjalankan query secara simultan/paralel tanpa antri semaphore karena kapasitas
        VRAM 48GB sangat leluasa menampung inferensi simultan gemma4:31b (24GB).
        num_predict=-1: Tidak membatasi panjang output — wajib untuk Unlimited Q&A.
        """
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_ctx": 16384,
                "num_predict": -1  # UNLIMITED output — jangan batasi Q&A generation
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if images:
            payload["images"] = images  # List of base64 encoded PNG strings

        try:
            resp = await self.http_client.post(f"{self.ollama_url}/api/generate", json=payload)
            if resp.status_code == 200:
                rdata = resp.json()
                done_reason = rdata.get("done_reason", "")
                response_text = rdata.get("response", "").strip()
                if done_reason == "length" and response_text:
                    logger.warning(
                        f"[OLLAMA_LENGTH_CUT] Response terpotong (done_reason=length) "
                        f"— seharusnya tidak terjadi dengan num_predict=-1. "
                        f"Response length: {len(response_text)} chars."
                    )
                return response_text
            logger.error(f"[OLLAMA_ERROR] Status {resp.status_code}: {resp.text[:200]}")
            return ""
        except Exception as e:
            logger.error(f"[OLLAMA_EXCEPTION] Gagal query model {self.model_name}: {e}")
            return ""

    # ── WORKER 1: TEXT RAG ───────────────────────────────────────────────────
    async def run_worker1_text_rag(
        self,
        dokumen_id: int,
        sections: List[StitchedSection],
        spread_images_b64: Optional[List[str]] = None,
        raw_text: str = "",
        spread_label: str = "",
        log_cb: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Menyimpan section & chunks ke dokumen_section dan dokumen_chunk dengan pgvector.
        Mendukung rentang halaman ('4-6') untuk pasal yang menyambung lintas halaman.
        Mendukung Dokumen Scan: Jika sections kosong dan terdapat citra bentangan halaman,
        Gemma-4 31B multimodal dipanggil langsung untuk OCR/ekstraksi teks komprehensif.
        """
        active_sections: List[StitchedSection] = list(sections or [])

        # Jika PDF adalah hasil scan (tidak ada text layer / sections kosong),
        # ekstrak teks secara multimodal via Gemma-4 31B
        has_content = any(s.content.strip() for s in active_sections) if active_sections else False
        if not has_content and spread_images_b64:
            if log_cb:
                log_cb("W1_TEXT", "INFO", f"Halaman {spread_label}: Dokumen scan (tanpa text layer). Mengekstrak teks via Gemma-4 31B multimodal...")

            ocr_prompt = f"""Kamu adalah OCR & Document Text Extractor presisi tinggi untuk Dokumen Regulasi PT Pindad.
Di hadapanmu terlampir citra bentangan 2 halaman (Halaman {spread_label or 'dokumen'}) hasil scan dokumen regulasi resmi PT Pindad.

TUGAS:
1. Transkripsikan SELURUH teks yang tertulis pada halaman ini secara lengkap dan akurat (verbatim).
2. Pertahankan struktur dokumen: JUDUL, BAB, Bagian, Pasal, Ayat, huruf/angka, dan tabel bila ada.
3. Jangan meringkas atau menghilangkan bagian teks regulasi apapun.

Keluarkan transkripsi teks regulasi lengkap:"""

            extracted_text = await self._call_ollama_generate(prompt=ocr_prompt, images=spread_images_b64)
            extracted_text = extracted_text.strip()

            if extracted_text:
                if log_cb:
                    log_cb("W1_TEXT", "INFO", f"  ✓ Berhasil mengekstrak {len(extracted_text)} karakter teks dari citra scan")
                p_start = int(spread_label.split("-")[0]) if spread_label and "-" in spread_label else (int(spread_label) if spread_label.isdigit() else 1)
                p_end = int(spread_label.split("-")[-1]) if spread_label and "-" in spread_label else (int(spread_label) if spread_label.isdigit() else 1)
                active_sections.append(StitchedSection(
                    dokumen_id=dokumen_id,
                    bab="DOKUMEN_SCAN",
                    pasal=f"Halaman {spread_label}" if spread_label else "Transkrip Halaman",
                    page_start=p_start,
                    page_end=p_end,
                    page_range=spread_label or str(p_start),
                    content=extracted_text,
                    is_cross_page="-" in spread_label,
                    section_type="PASAL"
                ))
            elif raw_text:
                active_sections.append(StitchedSection(
                    dokumen_id=dokumen_id,
                    bab="UMUM",
                    pasal="Teks Halaman",
                    page_start=1,
                    page_end=1,
                    page_range=spread_label or "1",
                    content=raw_text,
                    is_cross_page=False,
                    section_type="PASAL"
                ))

        if not active_sections or not any(s.content.strip() for s in active_sections):
            if log_cb:
                log_cb("W1_TEXT", "WARNING", f"Halaman {spread_label}: Tidak ada teks maupun citra yang dapat diekstrak.")
            return {"count": 0, "items": []}

        chunks_inserted = 0
        chunk_summaries: List[Dict[str, Any]] = []
        async with get_ragdb_conn() as conn:
            for sec_idx, sec in enumerate(active_sections):
                # 1. Simpan ke dokumen_section
                section_title = f"{sec.bab} - {sec.pasal}".strip(" -")
                sec_id = await conn.fetchval("""
                    INSERT INTO dokumen_section (dokumen_id, section_type, section_title, content, section_order)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, dokumen_id, sec.section_type, section_title, sec.content, sec.page_start)

                # 2. Chunking teks (jika teks sangat panjang, chunk per ~1000 char)
                content_len = len(sec.content)
                chunk_parts = []
                if content_len <= 1500:
                    chunk_parts.append(sec.content)
                else:
                    paragraphs = sec.content.split("\n")
                    curr_chunk = ""
                    for p in paragraphs:
                        if len(curr_chunk) + len(p) < 1200:
                            curr_chunk += p + "\n"
                        else:
                            if curr_chunk.strip():
                                chunk_parts.append(curr_chunk.strip())
                            curr_chunk = p + "\n"
                    if curr_chunk.strip():
                        chunk_parts.append(curr_chunk.strip())

                for idx, chunk_text in enumerate(chunk_parts):
                    emb = await self.vector_service.get_query_embedding(chunk_text)
                    emb_str = embedding_to_pgvector_str(emb) if emb else None

                    metadata = {
                        "bab": sec.bab,
                        "pasal": sec.pasal,
                        "page_start": sec.page_start,
                        "page_end": sec.page_end,
                        "page_range": sec.page_range,
                        "is_cross_page": sec.is_cross_page,
                        "chunk_index": idx
                    }

                    if emb_str:
                        await conn.execute("""
                            INSERT INTO dokumen_chunk (
                                dokumen_id, chunk_id, content, metadata, page_number,
                                section_id, embedding, embedding_model
                            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7::vector, 'mxbai-embed-large')
                        """, dokumen_id, idx + 1, chunk_text, json.dumps(metadata), sec.page_range, sec_id, emb_str)
                    else:
                        await conn.execute("""
                            INSERT INTO dokumen_chunk (
                                dokumen_id, chunk_id, content, metadata, page_number,
                                section_id, embedding_model
                            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, 'mxbai-embed-large')
                        """, dokumen_id, idx + 1, chunk_text, json.dumps(metadata), sec.page_range, sec_id)
                    chunks_inserted += 1

                    chunk_summaries.append({
                        "title": section_title or f"Pasal (Hal {sec.page_range})",
                        "preview": chunk_text[:280] + ("..." if len(chunk_text) > 280 else ""),
                        "char_count": len(chunk_text),
                        "page_range": sec.page_range,
                        "has_embedding": emb_str is not None
                    })

                    if log_cb and chunks_inserted <= 8:
                        lbl = (section_title or f"Pasal Hal {sec.page_range}")[:35]
                        log_cb("W1_TEXT", "INFO", f"  ✓ Chunk {chunks_inserted}: {lbl} ({len(chunk_text)} char) di-embed pgvector")

        if log_cb:
            log_cb("W1_TEXT", "SUCCESS", f"Selesai: {chunks_inserted} chunk berbobot vektor tersimpan di dokumen_chunk.")
        logger.info(f"✅ [WORKER_1_TEXT] Dokumen {dokumen_id}: Berhasil memasukkan {chunks_inserted} chunk teks.")
        return {"count": chunks_inserted, "items": chunk_summaries}

    # ── WORKER 2: SYNTHETIC Q&A (UNLIMITED & SPREAD-LEVEL MULTIMODAL) ────────
    async def run_worker2_synthetic_qa(
        self,
        dokumen_id: int,
        sections: List[StitchedSection],
        spread_images_b64: Optional[List[str]] = None,
        raw_text: str = "",
        spread_label: str = "",
        log_cb: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Menghasilkan Synthetic Q&A mendalam dari bentangan 2 halaman (two-page spread).
        Mengkonsolidasi seluruh pasal pada bentangan menjadi 1 analisis multimodal komprehensif ke Gemma-4 31B.
        UNLIMITED Q&A: Menggali sebanyak mungkin pasangan tanya jawab tanpa batasan 10 pertanyaan.
        """
        if not sections and not spread_images_b64 and not raw_text:
            return []

        page_range_str = spread_label or (f"{sections[0].page_start}-{sections[-1].page_end}" if sections else "1")
        
        if sections:
            combined_text = "\n\n".join([
                f"=== {sec.bab} | {sec.pasal} (Halaman {sec.page_range}) ===\n{sec.content}"
                for sec in sections
            ])
        elif raw_text:
            combined_text = raw_text
        else:
            combined_text = "Teks tertera langsung pada citra bentangan halaman."

        all_qa_pairs: List[Dict[str, Any]] = []

        if spread_images_b64:
            prompt = f"""Kamu adalah Pakar AI Dokumen Regulasi PT Pindad.
Di hadapanmu terlampir citra bentangan 2 halaman (kiri & kanan, Halaman {page_range_str}) dari dokumen regulasi resmi PT Pindad.

BACA DAN TELAAH LANGSUNG DARI CITRA DOKUMEN:
1. Teks regulasi asli dari setiap pasal yang termuat pada bentangan ini.
2. Tabel matriks, persentase angka, spesifikasi teknis, bagan alur, stempel pengesahan, dan tanda tangan pejabat.
3. Keterangan pasal dan ayat yang tertera pada kedua halaman bentangan.

KONTEKS TEKS TERDETEKSI:
{combined_text[:4000]}

TUGAS PENTING (UNLIMITED Q&A - TANPA BATAS KUOTA):
Buatkan daftar pertanyaan dan jawaban (Q&A) mendalam dan komprehensif sebanyak-banyaknya mengenai seluruh isi regulasi yang tertera pada bentangan Halaman {page_range_str} ini:
- Pertanyaan formal SOP dan kepatuhan hukum PT Pindad
- Pertanyaan detail data tabel, angka, bagan, atau matriks yang terlihat pada halaman
- Pertanyaan operasional sehari-hari karyawan pabrik/lapangan/kantor
- Skenario pelanggaran, sanksi, hak, kewajiban, dan definisi istilah teknis

ATURAN KUANTITAS:
- DILARANG membatasi pertanyaan (JANGAN hanya membuat 5 atau 10 pertanyaan). Buatlah sebanyak mungkin Q&A yang dapat digali secara faktual dari setiap pasal, ayat, tabel, dan ketentuan di halaman ini.
- Semakin komprehensif dan banyak variasi pertanyaan yang dibuat, semakin baik kualitas pelatihan AI.

FORMAT OUTPUT:
Keluarkan HANYA format JSON list murni seperti ini, tanpa markdown, teks pembuka, atau teks penutup:
[
  {{"question": "Pertanyaan 1...", "answer": "Jawaban lengkap dan presisi...", "pasal": "Pasal terkait"}},
  {{"question": "Pertanyaan 2...", "answer": "Jawaban...", "pasal": "Pasal terkait"}}
]
"""
        else:
            prompt = f"""Kamu adalah Pakar AI Dokumen Regulasi PT Pindad.
Pelajari dengan seksama teks regulasi Halaman {page_range_str} berikut:
{combined_text[:4000]}

TUGAS PENTING (UNLIMITED Q&A - TANPA BATAS KUOTA):
Buatkan daftar pertanyaan dan jawaban (Q&A) sebanyak-banyaknya mengenai isi regulasi di atas.
DILARANG membatasi jumlah (jangan dibatasi 10 pertanyaan). Gali setiap pasal, ayat, dan aturan menjadi Q&A sebanyak mungkin yang faktual.

FORMAT OUTPUT:
Keluarkan HANYA format JSON list murni:
[
  {{"question": "Pertanyaan 1...", "answer": "Jawaban lengkap sesuai isi teks...", "pasal": "Pasal terkait"}},
  {{"question": "Pertanyaan 2...", "answer": "Jawaban...", "pasal": "Pasal terkait"}}
]
"""

        if log_cb:
            img_info = f" ({len(spread_images_b64)} citra snapshot)" if spread_images_b64 else ""
            log_cb("W2_QA", "INFO", f"Mengirim citra bentangan Hal {page_range_str}{img_info} ke Gemma 31B...")

        llm_output = await self._call_ollama_generate(prompt, images=spread_images_b64)
        if not llm_output:
            if log_cb:
                log_cb("W2_QA", "WARNING", "Gemma 31B tidak mengembalikan respons teks.")
            return []

        # Parse JSON dari output LLM dengan multi-tier fallback
        qa_list = []
        try:
            start_bracket = llm_output.find("[")
            end_bracket = llm_output.rfind("]")
            if start_bracket != -1 and end_bracket != -1:
                json_str = llm_output[start_bracket:end_bracket+1]
                try:
                    qa_list = json.loads(json_str)
                except Exception:
                    import re
                    cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
                    qa_list = json.loads(cleaned)
        except Exception as parse_err:
            logger.warning(f"[WORKER_2_QA] Parse JSON gagal: {parse_err}, menggunakan regex...")
            import re
            pattern = r'["\']question["\']\s*:\s*["\'](.*?)["\']\s*,\s*["\']answer["\']\s*:\s*["\'](.*?)["\']'
            matches = re.findall(pattern, llm_output, re.DOTALL)
            for q_m, a_m in matches:
                if len(q_m.strip()) > 5:
                    qa_list.append({"question": q_m.strip(), "answer": a_m.strip(), "pasal": f"Hal {page_range_str}"})

        if not qa_list:
            lines = [l.strip() for l in llm_output.split("\n") if l.strip()]
            for l in lines:
                if l.startswith(("-", "*", "?")) or (len(l) > 3 and l[0].isdigit() and l[1] in [".", ")"]):
                    q_text = l.lstrip("-*?0123456789.) ").strip()
                    if len(q_text) > 8:
                        qa_list.append({"question": q_text, "answer": combined_text[:300], "pasal": f"Hal {page_range_str}"})

        if log_cb:
            log_cb("W2_QA", "INFO", f"Gemma 31B selesai: {len(qa_list)} Q&A sintetis diekstrak. Menyimpan ke pgvector...")

        # Simpan ke rag_document_questions
        async with get_ragdb_conn() as conn:
            for idx, qa in enumerate(qa_list):
                q = qa.get("question", "").strip()
                ans = qa.get("answer", "").strip()
                pasal_ref = qa.get("pasal") or f"Hal {page_range_str}"
                if not q:
                    continue

                emb = await self.vector_service.get_query_embedding(q)
                emb_str = embedding_to_pgvector_str(emb) if emb else None

                if emb_str:
                    await conn.execute("""
                        INSERT INTO rag_document_questions (
                            source_db, source_id, generated_question, answer, page_range, embedding
                        ) VALUES ('peraturan_db', $1, $2, $3, $4, $5::vector)
                    """, dokumen_id, q, ans, page_range_str, emb_str)
                else:
                    await conn.execute("""
                        INSERT INTO rag_document_questions (
                            source_db, source_id, generated_question, answer, page_range
                        ) VALUES ('peraturan_db', $1, $2, $3, $4)
                    """, dokumen_id, q, ans, page_range_str)

                all_qa_pairs.append({
                    "dokumen_id": dokumen_id,
                    "question": q,
                    "answer": ans,
                    "page_range": page_range_str,
                    "pasal": pasal_ref
                })

                if log_cb and (idx < 5 or idx == len(qa_list) - 1):
                    log_cb("W2_QA", "INFO", f"  ✓ Q{idx+1}: \"{q[:55]}...\"")

        if log_cb:
            log_cb("W2_QA", "SUCCESS", f"Selesai: {len(all_qa_pairs)} pasangan Q&A sintetis berhasil dibuat & di-embed.")
        logger.info(f"✅ [WORKER_2_QA] Dokumen {dokumen_id}: Berhasil membuat & menyimpan {len(all_qa_pairs)} pasangan Q&A sintetis.")
        return all_qa_pairs

    # ── WORKER 3: GRAPH RAG (SPREAD-LEVEL MULTIMODAL) ────────────────────────
    async def run_worker3_graph_rag(
        self,
        dokumen_id: int,
        sections: List[StitchedSection],
        spread_images_b64: Optional[List[str]] = None,
        raw_text: str = "",
        spread_label: str = "",
        log_cb: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Ekstraksi entitas (Divisi, Jabatan, Produk, Sanksi) dan relasi antar entitas ke knowledge_graph.
        Mengkonsolidasi seluruh bentangan 2 halaman menjadi 1 analisis grafik entitas ke Gemma-4 31B.
        """
        if not sections and not spread_images_b64 and not raw_text:
            return {"count": 0, "triplets": []}

        page_range_str = spread_label or (f"{sections[0].page_start}-{sections[-1].page_end}" if sections else "1")
        primary_page = sections[0].page_start if sections else 1
        
        if sections:
            combined_text = "\n\n".join([
                f"=== {sec.bab} | {sec.pasal} (Halaman {sec.page_range}) ===\n{sec.content}"
                for sec in sections
            ])
        elif raw_text:
            combined_text = raw_text
        else:
            combined_text = "Teks tertera langsung pada citra bentangan halaman."

        total_relations = 0
        all_triplets: List[Dict[str, Any]] = []

        if spread_images_b64:
            prompt = f"""Ekstrak seluruh entitas dan relasi dari citra bentangan 2 halaman regulasi PT Pindad yang dilampirkan (Halaman {page_range_str}):
Perhatikan divisi/jabatan penanggung jawab, organ manajemen (Direksi/Dewan Komisaris), produk pertahanan/industri, wewenang, dan sanksi.
Konteks teks:
{combined_text[:4000]}

Keluarkan HANYA JSON array dari relasi (Subject - Relation - Object):
[
  {{"source": "Nama Entitas 1", "source_type": "DIVISI/JABATAN/REGULASI", "relation": "MENGATUR/SANKSI_UNTUK/BERTANGGUNG_JAWAB", "target": "Nama Entitas 2", "target_type": "PRODUK/PASAL/KEWAJIBAN"}}
]
"""
        else:
            prompt = f"""Ekstrak entitas dan relasi dari teks peraturan PT Pindad berikut (Halaman {page_range_str}):
TEKS:
{combined_text[:4000]}

Keluarkan HANYA JSON array dari relasi (Subject - Relation - Object):
[
  {{"source": "Nama Entitas 1", "source_type": "DIVISI/JABATAN/REGULASI", "relation": "MENGATUR/SANKSI_UNTUK/BERTANGGUNG_JAWAB", "target": "Nama Entitas 2", "target_type": "PRODUK/PASAL/KEWAJIBAN"}}
]
"""

        if log_cb:
            log_cb("W3_GRAPH", "INFO", f"Menganalisis relasi entitas graf visual bentangan Hal {page_range_str} via Gemma 31B...")

        llm_output = await self._call_ollama_generate(prompt, images=spread_images_b64)
        if not llm_output:
            if log_cb:
                log_cb("W3_GRAPH", "WARNING", "Gemma 31B tidak mengembalikan relasi graf.")
            return {"count": 0, "triplets": []}

        relations = []
        try:
            start_b = llm_output.find("[")
            end_b = llm_output.rfind("]")
            if start_b != -1 and end_b != -1:
                json_str = llm_output[start_b:end_b+1]
                try:
                    relations = json.loads(json_str)
                except Exception:
                    import re
                    cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
                    relations = json.loads(cleaned)
        except Exception:
            relations = []

        if log_cb:
            log_cb("W3_GRAPH", "INFO", f"Gemma 31B selesai: {len(relations)} relasi entitas ditemukan. Menyimpan ke knowledge_graph...")

        async with get_ragdb_conn() as conn:
            for idx, rel in enumerate(relations):
                src = rel.get("source", "").strip()
                src_type = rel.get("source_type", "ENTITAS").strip()
                relation = rel.get("relation", "BERHUBUNGAN").strip()
                tgt = rel.get("target", "").strip()
                tgt_type = rel.get("target_type", "ENTITAS").strip()

                if not src or not tgt:
                    continue

                # Insert source node
                src_id = await conn.fetchval("""
                    INSERT INTO knowledge_graph_nodes (dokumen_id, page_number, page_range, entity_name, entity_type)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, dokumen_id, primary_page, page_range_str, src, src_type)

                # Insert target node
                tgt_id = await conn.fetchval("""
                    INSERT INTO knowledge_graph_nodes (dokumen_id, page_number, page_range, entity_name, entity_type)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, dokumen_id, primary_page, page_range_str, tgt, tgt_type)

                # Insert edge
                await conn.execute("""
                    INSERT INTO knowledge_graph_edges (source_node_id, target_node_id, relation_type, dokumen_id)
                    VALUES ($1, $2, $3, $4)
                """, src_id, tgt_id, relation, dokumen_id)
                total_relations += 1

                all_triplets.append({
                    "source": src,
                    "source_type": src_type,
                    "relation": relation,
                    "target": tgt,
                    "target_type": tgt_type,
                    "page_range": page_range_str
                })

                if log_cb and (idx < 5 or idx == len(relations) - 1):
                    log_cb("W3_GRAPH", "INFO", f"  ✓ ({src}) ──[{relation}]──> ({tgt})")

        if log_cb:
            log_cb("W3_GRAPH", "SUCCESS", f"Selesai: {total_relations} relasi entitas graf diekstrak & tersimpan di knowledge_graph.")
        logger.info(f"✅ [WORKER_3_GRAPH] Dokumen {dokumen_id}: Berhasil membangun {total_relations} relasi graph.")
        return {"count": total_relations, "triplets": all_triplets}

    # ── WORKER 4: VISION RAG (WORKFLOW, DIAGRAM, MERMAID & TABLE EXTRACTOR) ──
    async def run_worker4_vision_rag(
        self,
        dokumen_id: int,
        pages: Any,
        reader: BookPageReader,
        spread_images_b64: Optional[List[str]] = None,
        spread_label: str = "",
        raw_text: str = "",
        log_cb: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Merender snapshot gambar halaman untuk viewer UI dan melakukan ekstraksi visual cerdas:
        1. Menyimpan snapshot PNG 150 DPI ke disk (/backend/storage/doc_pages).
        2. Menganalisis citra bentangan halaman via Gemma-4 31B Multimodal:
           - Bagan Alir & Prosedur SOP -> Runtutan langkah + kode diagram Mermaid (graph TD).
           - Tabel Kompleks & Matriks -> Structured Markdown Table.
           - Cap Basah Kedinasan & Tanda Tangan Legalitas -> Status dokumen & pejabat pengesah.
        3. Menyimpan hasil ekstraksi visual ke dokumen_section & dokumen_chunk dengan pgvector embedding.
        """
        if isinstance(pages, int):
            page_list = [pages]
        elif isinstance(pages, (list, tuple)):
            page_list = list(pages)
        else:
            page_list = []

        # 1. Simpan gambar PNG ke disk untuk Two-Page Book Viewer UI
        doc_dir = os.path.join(self.pages_image_dir, str(dokumen_id))
        os.makedirs(doc_dir, exist_ok=True)
        saved_count = 0

        for p in page_list:
            img_bytes = reader.render_page_image(p, dpi=150)
            if not img_bytes:
                continue

            img_path = os.path.join(doc_dir, f"page_{p:03d}.png")
            try:
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                saved_count += 1
                if log_cb:
                    log_cb("W4_VISION", "SUCCESS", f"Snapshot PNG Hal {p} tersimpan (150 DPI) → /doc_pages/{dokumen_id}/page_{p:03d}.png")
            except Exception as e:
                logger.error(f"[WORKER_4_VISION] Gagal simpan gambar halaman {p}: {e}")

        # 2. Ekstraksi Visual Multimodal via Gemma-4 31B (Bagan Alur, Mermaid, Tabel Matriks, Cap Pengesahan)
        visual_items: List[Dict[str, Any]] = []
        if spread_images_b64:
            if log_cb:
                log_cb("W4_VISION", "INFO", f"Menganalisis visual diagram/workflow bentangan Hal {spread_label} via Gemma 31B...")

            prompt = f"""Kamu adalah Visual Document Analyst & Workflow Specialist untuk Regulasi & SOP PT Pindad.
Di hadapanmu terlampir citra bentangan 2 halaman (Halaman {spread_label or 'dokumen'}) dari dokumen regulasi/SOP resmi PT Pindad.

TUGAS UTAMA:
Analisis secara visual elemen grafis dan struktural pada bentangan halaman ini:
1. BAGAN ALUR & FLOWCHART PROSEDUR:
   - Jika ada bagan alur proses / flowchart / SOP / bagan kerja, rekonstruksikan:
     a. Runtutan langkah prosedural (Step 1, Step 2, dst) beserta divisi pelaksananya.
     b. Logika percabangan ('Ya'/'Tidak'/'Lolos'/'Gagal').
     c. Sintaks kode diagram MERMAID lengkap (misal: ```mermaid\\ngraph TD\\n...```).
2. TABEL KOMPLEKS & MATRIKS:
   - Jika ada tabel matriks, tabel tarif, atau tabel spesifikasi teknis, rekonstruksikan ke format Markdown Table terstruktur.
3. LEMBAR PENGESAHAN & CAP LEGALITAS:
   - Jika ada cap basah (stempel dinas), tanda tangan pejabat, atau status pengesahan (SALINAN SAH, RAHASIA, BERLAKU, DICABUT), catat nama pejabat dan statusnya.
4. JIKA HALAMAN INI MURNI TEKS BIASA:
   - Tidak ada flowchart, tidak ada tabel kompleks, tidak ada diagram proses, dan tidak ada cap khusus:
   - JAWAB HANYA DENGAN ARRAY KOSONG: []

Keluarkan HANYA JSON array berikut (tanpa pengantar markdown apapun di luar blok json):
[
  {{
    "type": "FLOWCHART",
    "title": "Nama Bagan Alur",
    "description": "Ringkasan proses alur kerja",
    "mermaid": "graph TD\\n  A[Langkah 1] --> B[Langkah 2]",
    "steps": ["1. Langkah 1 oleh Divisi X", "2. Langkah 2 verifikasi"]
  }},
  {{
    "type": "TABLE",
    "title": "Nama Tabel",
    "description": "Ringkasan isi tabel",
    "markdown_table": "| Kolom 1 | Kolom 2 |\\n|---|---|\\n| Nilai 1 | Nilai 2 |"
  }},
  {{
    "type": "LEGAL_STAMP",
    "title": "Pengesahan / Stempel Resmi",
    "signatory": "Nama & Jabatan Penandatangan",
    "stamp_status": "SALINAN SAH / RAHASIA / dll",
    "date": "Tanggal jika ada"
  }}
]
"""
            llm_output = await self._call_ollama_generate(prompt=prompt, images=spread_images_b64)
            llm_output = llm_output.strip()

            if llm_output and "TIDAK_ADA_ARTIFAK_VISUAL" not in llm_output:
                try:
                    start_b = llm_output.find("[")
                    end_b = llm_output.rfind("]")
                    if start_b != -1 and end_b != -1:
                        json_str = llm_output[start_b:end_b+1]
                        try:
                            parsed_list = json.loads(json_str)
                            if isinstance(parsed_list, list):
                                visual_items = parsed_list
                        except Exception:
                            import re
                            cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
                            parsed_list = json.loads(cleaned)
                            if isinstance(parsed_list, list):
                                visual_items = parsed_list
                except Exception as e:
                    logger.warning(f"[WORKER_4_VISION] Gagal parse JSON visual: {e}")

        # 3. Simpan artifak visual ke dokumen_section & dokumen_chunk dengan pgvector
        chunks_inserted = 0
        visual_summaries: List[Dict[str, Any]] = []

        valid_items = [it for it in visual_items if isinstance(it, dict) and it.get("type") not in ("NONE", "TIDAK_ADA", None)]

        if valid_items:
            p_start = int(spread_label.split("-")[0]) if spread_label and "-" in spread_label else (int(spread_label) if spread_label.isdigit() else 1)
            p_end = int(spread_label.split("-")[-1]) if spread_label and "-" in spread_label else p_start

            async with get_ragdb_conn() as conn:
                for v_idx, item in enumerate(valid_items):
                    v_type = item.get("type", "FLOWCHART")
                    v_title = item.get("title", f"Visual Artifak Hal {spread_label}")
                    v_desc = item.get("description", "")
                    v_mermaid = item.get("mermaid", "")
                    v_table = item.get("markdown_table", "")
                    v_steps = item.get("steps", [])

                    # Format konten terstruktur untuk chunking RAG
                    content_parts = [f"### [{v_type}] {v_title} (Halaman {spread_label})"]
                    if v_desc:
                        content_parts.append(f"Deskripsi: {v_desc}")
                    if v_mermaid:
                        content_parts.append(f"```mermaid\n{v_mermaid.strip()}\n```")
                    if v_steps:
                        content_parts.append("Tahapan Prosedural:\n" + "\n".join(f"- {s}" for s in v_steps))
                    if v_table:
                        content_parts.append(f"Tabel:\n{v_table.strip()}")
                    if v_type == "LEGAL_STAMP":
                        signatory = item.get("signatory", "")
                        status = item.get("stamp_status", "")
                        date = item.get("date", "")
                        content_parts.append(f"Penandatangan: {signatory} | Status: {status} | Tanggal: {date}")

                    full_chunk_text = "\n\n".join(content_parts)

                    # Simpan ke dokumen_section
                    sec_id = await conn.fetchval("""
                        INSERT INTO dokumen_section (dokumen_id, section_type, section_title, content, section_order)
                        VALUES ($1, 'VISUAL_WORKFLOW', $2, $3, $4)
                        RETURNING id
                    """, dokumen_id, v_title[:200], full_chunk_text, p_start)

                    # Embed chunk via mxbai-embed-large
                    emb = await self.vector_service.get_query_embedding(full_chunk_text)
                    emb_str = embedding_to_pgvector_str(emb) if emb else None

                    metadata = {
                        "type": "VISUAL_WORKFLOW",
                        "visual_type": v_type,
                        "title": v_title,
                        "has_mermaid": bool(v_mermaid),
                        "page_range": spread_label,
                        "page_start": p_start,
                        "page_end": p_end
                    }

                    if emb_str:
                        await conn.execute("""
                            INSERT INTO dokumen_chunk (
                                dokumen_id, chunk_id, content, metadata, page_number,
                                section_id, embedding, embedding_model
                            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7::vector, 'mxbai-embed-large')
                        """, dokumen_id, v_idx + 100, full_chunk_text, json.dumps(metadata), spread_label, sec_id, emb_str)
                    else:
                        await conn.execute("""
                            INSERT INTO dokumen_chunk (
                                dokumen_id, chunk_id, content, metadata, page_number,
                                section_id, embedding_model
                            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, 'mxbai-embed-large')
                        """, dokumen_id, v_idx + 100, full_chunk_text, json.dumps(metadata), spread_label, sec_id)

                    chunks_inserted += 1
                    summary_obj = {
                        "type": v_type,
                        "title": v_title,
                        "preview": full_chunk_text[:280] + ("..." if len(full_chunk_text) > 280 else ""),
                        "mermaid": v_mermaid,
                        "markdown_table": v_table,
                        "page_range": spread_label
                    }
                    visual_summaries.append(summary_obj)

                    if log_cb:
                        has_m = "Ya" if v_mermaid else "Tidak"
                        log_cb("W4_VISION", "SUCCESS", f"  ✓ [{v_type}] {v_title[:45]} di-embed pgvector (Mermaid: {has_m})")

            if log_cb:
                log_cb("W4_VISION", "SUCCESS", f"Selesai: {chunks_inserted} artifak visual (diagram/tabel/cap) tersimpan di dokumen_chunk.")
        else:
            if log_cb:
                log_cb("W4_VISION", "INFO", f"Halaman {spread_label}: Murni teks biasa, tidak ada diagram alur/tabel khusus.")

        logger.info(f"✅ [WORKER_4_VISION] Dokumen {dokumen_id}: {saved_count} snapshot PNG, {chunks_inserted} visual chunks.")
        return {
            "saved_images": saved_count,
            "visual_chunks": chunks_inserted,
            "items": visual_summaries
        }

    # ── WORKER 5: LORA & ROUTER FINE-TUNING DATASET ACCUMULATOR (UNLIMITED) ───
    async def run_worker5_lora_ingest(
        self,
        dokumen_id: int,
        qa_pairs: List[Dict[str, Any]],
        log_cb: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Mengakumulasi pasangan Q&A dari Worker 2 menjadi dataset latih (JSONL)
        secara SIMULTAN dan UNLIMITED:
        1. Call 2 Core: data/finetune/nightly_cakra_core.jsonl (Reasoning CoT & Respons Regulasi)
        2. Call 1 Router e4b: data/finetune/nightly_call1_router.jsonl (Intent Router Classification)
        Tidak ada batasan sampel 3000 — bertumbuh murni mengikuti seluruh halaman yang diproses.
        """
        if not qa_pairs:
            return {"count": 0, "samples": [], "router_count": 0}

        if log_cb:
            log_cb("W5_LORA", "INFO", f"Mengompilasi {len(qa_pairs)} Q&A ke dataset Call 1 Router e4b & Call 2 Core (Unlimited)...")

        os.makedirs(self.finetune_data_dir, exist_ok=True)
        core_file = os.path.join(self.finetune_data_dir, "nightly_cakra_core.jsonl")
        router_file = os.path.join(self.finetune_data_dir, "nightly_call1_router.jsonl")

        count_core = 0
        count_router = 0
        all_samples: List[Dict[str, Any]] = []

        try:
            # 1. Tulis ke Call 2 Core (ShareGPT dengan CoT Reasoning)
            with open(core_file, "a", encoding="utf-8") as f_core, \
                 open(router_file, "a", encoding="utf-8") as f_router:

                for idx, qa in enumerate(qa_pairs):
                    q_text = qa["question"].strip()
                    ans_text = qa["answer"].strip()
                    pasal_ref = qa.get("pasal", "Regulasi PT Pindad")
                    page_ref = qa.get("page_range", "-")

                    if not q_text or not ans_text:
                        continue

                    # Sample Call 2 Core (Alpaca / ShareGPT + CoT)
                    thought_cot = (
                        f"1. Analisis Pertanyaan: Pengguna menanyakan '{q_text}'.\n"
                        f"2. Dokumen Rujukan: Regulasi PT Pindad ({pasal_ref}, Halaman {page_ref}).\n"
                        f"3. Resolusi Regulasi: {ans_text[:200]}...\n"
                        f"4. Format Respon: Sajikan jawaban lugas, profesional, mengutip dasar pasal/ketentuan resmi."
                    )
                    assistant_core_msg = (
                        f"<think>\n{thought_cot}\n</think>\n\n"
                        f"{ans_text}\n\n"
                        f"*(Dasar Rujukan: {pasal_ref}, Halaman {page_ref})*"
                    )

                    sample_core = {
                        "conversations": [
                            {
                                "from": "system",
                                "value": (
                                    "Kamu adalah CAKRA AI, asisten kecerdasan buatan berdaulat PT PINDAD. "
                                    "Sebelum menjawab, lakukan penalaran terstruktur di dalam tag <think>...</think> "
                                    "lalu sajikan jawaban profesional, akurat, to-the-point berdasar regulasi resmi."
                                )
                            },
                            {
                                "from": "human",
                                "value": q_text
                            },
                            {
                                "from": "gpt",
                                "value": assistant_core_msg
                            }
                        ]
                    }
                    f_core.write(json.dumps(sample_core, ensure_ascii=False) + "\n")
                    count_core += 1
                    all_samples.append(sample_core)

                    # 2. Sample Call 1 Router e4b (Deterministik JSON Routing)
                    # Query regulasi otomatis terklasifikasi ke need_rag: true dengan mode DOCUMENTS
                    router_target = {
                        "active_topic": "Regulasi & Kebijakan PT PINDAD",
                        "key_subject": pasal_ref,
                        "need_rag": True,
                        "rag_reason": f"Menanyakan regulasi internal PT Pindad ({pasal_ref})",
                        "queries": [q_text, pasal_ref],
                        "is_chitchat": False,
                        "is_ambiguous": False,
                        "pronoun": "formal_saya_anda",
                        "tone_hint": "direct_concise"
                    }
                    sample_router = {
                        "conversations": [
                            {
                                "from": "system",
                                "value": (
                                    "Kamu adalah model klasifikasi dan router intent presisi tinggi untuk CAKRA AI PT Pindad. "
                                    "Tugasmu adalah menganalisis query pengguna dan mengeluarkan keputusan routing JSON deterministik."
                                )
                            },
                            {
                                "from": "human",
                                "value": q_text
                            },
                            {
                                "from": "gpt",
                                "value": json.dumps(router_target, ensure_ascii=False)
                            }
                        ]
                    }
                    f_router.write(json.dumps(sample_router, ensure_ascii=False) + "\n")
                    count_router += 1

                    if log_cb and (idx < 2 or idx == len(qa_pairs) - 1):
                        log_cb("W5_LORA", "INFO", f"  ✓ Sampel {idx+1}: Core CoT & Router e4b pair tersimpan")

            if log_cb:
                log_cb("W5_LORA", "SUCCESS", f"Selesai: +{count_core} Core CoT & +{count_router} Router e4b data latih tersimpan (Unlimited).")
            logger.info(f"🎯 [WORKER_5_LORA] Berhasil menambahkan {count_core} sampel ke {core_file} dan {count_router} sampel ke {router_file}")
            return {"count": count_core, "router_count": count_router, "samples": all_samples[:5]}
        except Exception as e:
            logger.error(f"[WORKER_5_LORA] Gagal menulis dataset LoRA/Router: {e}")
            return {"count": 0, "router_count": 0, "samples": []}

    async def close(self):
        await self.http_client.aclose()
