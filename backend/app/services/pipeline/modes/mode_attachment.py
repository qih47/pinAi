import logging
import json
import os
import asyncio
import base64
import datetime
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.core.paths import get_abs_path, UPLOAD_DIR, BASE_DIR
from backend.app.services.pipeline.system_prompts import (
    build_attachment_system_prompt,
    build_doc_audit_system_prompt
)
from backend.app.services.pipeline.document_intelligence import (
    extract_and_ocr_document_async,
    two_stage_rerank_cluster_async,
    extract_explicit_pages_from_query
)

logger = logging.getLogger("MODE_ATTACHMENT")

# Ekstensi file teks yang ditangani sebagai konten teks
TEXT_EXTENSIONS = {
    "txt", "csv", "md", "py", "js", "jsx", "ts", "tsx", "html", "css",
    "json", "yaml", "yml", "xml", "php", "java", "cpp", "c", "h",
    "sh", "bash", "dart", "swift", "go", "rs", "sql", "toml", "ini", "conf"
}

def is_summary_intent(query: str) -> bool:
    q = (query or "").lower().strip()
    if not q or len(q) < 5:
        return True
    summary_keywords = [
        "rangkum", "ringkas", "summary", "summarize", "ikhtisar", "garis besar",
        "jelaskan seluruh", "baca seluruh", "review seluruh", "apa isi dokumen ini",
        "keseluruhan", "secara umum", "overview", "sinopsis", "poin-poin penting",
        "bedah seluruh", "analisis dokumen ini", "mengenai apa", "tentang apa",
        "membahas apa", "menjelaskan apa", "menceritakan apa", "isi dari dokumen",
        "isi dokumen", "apa isinya", "apa isiannya", "dokumen apa ini", "dokumen ini apa",
        "apa yang dibahas", "topik dokumen"
    ]
    return any(kw in q for kw in summary_keywords)

def is_audit_intent(query: str) -> bool:
    q = (query or "").lower().strip()
    audit_keywords = [
        "koreksi", "periksa kesalahan", "typo", "kesalahan penulisan",
        "audit", "proofread", "proofreading", "cek ejaan", "tata bahasa",
        "tinjau berkas", "tinjau dokumen", "evaluasi berkas", "evaluasi dokumen",
        "cek kata demi kata", "cek penulisan", "koreksi typo", "periksa typo",
        "cek dokumen ini", "periksa berkas ini", "periksa dokumen ini",
        "koreksi dokumen ini", "audit dokumen", "cek bahasa", "koreksi berkas",
        "cek pasal", "koreksi alur", "periksa penulisan"
    ]
    return any(kw in q for kw in audit_keywords)

def is_continuation_intent(query: str) -> bool:
    q = (query or "").lower().strip()
    continuation_keywords = [
        "lanjut", "lanjutkan", "next", "teruskan", "halaman berikutnya",
        "batch selanjutnya", "halaman selanjutnya", "lanjut audit", "lanjutkan audit",
        "lanjut koreksi", "lanjutkan koreksi", "lanjut periksa", "lanjutkan periksa",
        "sambung", "sambungkan", "halaman setelahnya"
    ]
    if q in ["lanjut", "lanjutkan", "next", "gas", "ok lanjut", "oke lanjut", "teruskan"]:
        return True
    return any(kw in q for kw in continuation_keywords)

class ModeAttachment:
    """
    Mode Attachment: Memproses file yang diunggah pengguna (PDF, Gambar, Teks/Kode).
    Dilengkapi Dual-Intent Routing:
    1. Targeted Clause QA: Two-Stage Tri-Window Context Retrieval & Structural Continuity.
    2. Full Document Summarization: Single-Pass Context Assembly (<= 40 hal) / Skeleton Map-Reduce (> 40 hal).
    """
    async def execute(
        self,
        user_message: str,
        chat_history: List[ChatMessageSchema],
        is_thinking: bool,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_isolation: Optional[Dict[str, Any]] = None,
        routing_data: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        employee_name: str = "Pegawai",
        current_user_npp: Optional[str] = None,
        session_uuid: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        logger.info("[MODE_ATTACHMENT] Starting execution")
        
        yield format_sse(status="👁️ Memindai file lampiran", status_key="SCANNING_ATTACHMENT", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.02)

        # ── 1. Ekstraksi Path File Lampiran ─────────────────────────────────────
        pdf_file_path = None
        text_contents = []
        direct_images_b64 = []

        if attachments:
            for att in attachments:
                if isinstance(att, str):
                    direct_images_b64.append(att)
                    continue
                if not isinstance(att, dict):
                    continue

                mime = att.get("mime_type", "")
                file_path = att.get("file_path", "")
                if not file_path:
                    file_path = att.get("path", "")
                
                # Resolve physical path
                abs_path = None
                if file_path:
                    if os.path.isabs(file_path) and os.path.exists(file_path):
                        abs_path = file_path
                    else:
                        cand1 = os.path.join(UPLOAD_DIR, os.path.basename(file_path))
                        cand2 = get_abs_path(file_path)
                        if os.path.exists(cand1):
                            abs_path = cand1
                        elif os.path.exists(cand2):
                            abs_path = cand2

                if abs_path and (mime == "application/pdf" or abs_path.lower().endswith(".pdf")):
                    pdf_file_path = abs_path
                elif abs_path and any(abs_path.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]):
                    try:
                        with open(abs_path, "rb") as img_f:
                            direct_images_b64.append(base64.b64encode(img_f.read()).decode("utf-8"))
                    except Exception as e:
                        logger.error(f"[MODE_ATTACHMENT] Error reading image {abs_path}: {e}")
                elif att.get("base64"):
                    direct_images_b64.append(att["base64"])
                elif att.get("extracted_text"):
                    file_name = att.get("file_name", os.path.basename(file_path or "dokumen.txt"))
                    text_contents.append(f"### File: {file_name}\n```\n{att.get('extracted_text', '').strip()}\n```")

        # Inisialisasi SessionBrain jika ada session_uuid & current_user_npp
        brain = None
        if session_uuid and current_user_npp:
            from backend.app.services.session.session_brain_service import SessionBrainService
            brain = SessionBrainService(current_user_npp, session_uuid)

        active_audit = brain.get_active_audit() if brain else None

        # Jika pengguna tidak melampirkan file fisik di turn ini (misal mengetik "Lanjut") tapi ada audit aktif
        if not pdf_file_path and active_audit:
            cand = active_audit.get("pdf_file_path")
            if cand and os.path.exists(cand):
                pdf_file_path = cand

        # ── 2. Penanganan Khusus Lampiran PDF dengan Document Intelligence ───────
        final_extracted_text = ""
        final_base64_images = []
        selected_pages = []
        total_pages = 0
        is_audit_mode = False
        is_continuation = False
        is_summary = False
        audit_start_page = 1
        audit_end_page = 1
        audit_is_last = True
        audit_next_start = None
        audit_next_end = None

        if pdf_file_path and os.path.exists(pdf_file_path):
            doc_id_key = str(os.path.basename(pdf_file_path))
            text_map = None
            all_base64_images = None
            total_pages = 0

            if brain:
                cached_brain = brain.get_document(doc_id_key)
                if cached_brain and "text_map" in cached_brain:
                    yield format_sse(status="🧠 Dari memori sesi", status_key="BRAIN_HIT", event_type=SSEEventType.STATUS)
                    await asyncio.sleep(0.01)
                    text_map = cached_brain["text_map"]
                    all_base64_images = cached_brain.get("images", [])
                    total_pages = cached_brain.get("total_pages", len(text_map))

            if text_map is None:
                yield format_sse(status="📄 Memuat dokumen", status_key="DOC_LOADING", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)
                cache_key = session_uuid or pdf_file_path
                text_map, all_base64_images, total_pages = await extract_and_ocr_document_async(pdf_file_path, cache_key=cache_key)

                if brain:
                    await brain.save_document(doc_id_key, {
                        "title": os.path.basename(pdf_file_path),
                        "text_map": text_map,
                        "images": all_base64_images,
                        "total_pages": total_pages,
                    })
                    yield format_sse(status="💾 Menyimpan ke memori", status_key="BRAIN_SAVE", event_type=SSEEventType.STATUS)
                    await asyncio.sleep(0.01)

            # ── Deteksi Intent: Audit / Proofreader vs Ringkasan vs Targeted QA ───
            explicit_pages = extract_explicit_pages_from_query(user_message, total_pages)
            is_continuation = is_continuation_intent(user_message) and (
                active_audit is not None or "audit" in user_message.lower() or "koreksi" in user_message.lower()
            )

            # Jika user meminta audit lanjutan (contoh: tombol widget "Lanjut audit Halaman 16-18")
            # atau audit dengan rentang halaman eksplisit (contoh: "Audit halaman 1-5"):
            # Ini adalah MODE AUDIT penuh, bukan Targeted QA biasa.
            is_audit_with_explicit_range = (
                is_audit_intent(user_message) and (
                    is_continuation or "lanjut" in user_message.lower() or len(explicit_pages) > 1 or active_audit is not None
                )
            )

            if is_continuation or is_audit_with_explicit_range:
                is_audit = True
            elif explicit_pages and len(explicit_pages) == 1:
                # User menanyakan 1 halaman spesifik secara eksplisit (contoh: "Halaman 4: apa ada typo?", "Tanya Halaman 4")
                # Alihkan ke Targeted QA agar cepat dan fokus hanya pada 1 halaman tersebut
                is_audit = False
            else:
                is_audit = is_audit_intent(user_message)

            is_summary = is_summary_intent(user_message) and not is_audit and not explicit_pages

            logger.info(f"[MODE_ATTACHMENT] PDF detected ({total_pages} pages). Intent: {'AUDIT_PROOFREAD' if is_audit else ('SUMMARY' if is_summary else 'TARGETED_QA')}")

            if is_audit:
                # ── Mode Chunked Audit & Proofreader (Multi-Turn Batching) ──
                is_audit_mode = True
                BATCH_SIZE = 5

                if explicit_pages and (is_continuation or is_audit_with_explicit_range):
                    # Gunakan rentang halaman yang tertera di pesan (contoh: "Lanjut audit Halaman 16-18")
                    start_idx = min(explicit_pages)
                    end_idx = min(max(explicit_pages) + 1, total_pages)
                elif is_continuation and active_audit:
                    start_idx = active_audit.get("current_end", 0)
                    end_idx = min(start_idx + BATCH_SIZE, total_pages)
                else:
                    start_idx = 0
                    end_idx = min(start_idx + BATCH_SIZE, total_pages)

                if start_idx >= total_pages:
                    start_idx = 0  # Reset jika sudah habis
                    end_idx = min(start_idx + BATCH_SIZE, total_pages)

                audit_start_page = start_idx + 1
                audit_end_page = end_idx
                audit_is_last = (end_idx >= total_pages)
                audit_next_start = (end_idx + 1) if not audit_is_last else None
                audit_next_end = min(end_idx + BATCH_SIZE, total_pages) if not audit_is_last else None

                yield format_sse(
                    status=f"📑 Mengaudit Dokumen: Halaman {audit_start_page}–{audit_end_page} dari {total_pages} Halaman",
                    status_key="AUDITING_PAGES",
                    event_type=SSEEventType.STATUS
                )
                await asyncio.sleep(0.05)

                doc_builder = []
                for p in range(start_idx, end_idx):
                    if p < len(text_map):
                        item = text_map[p]
                        p_num = item.get("page_num", p) + 1
                        p_text = item.get("text", "").strip()
                        doc_builder.append(f"=== TEKS DOKUMEN HALAMAN {p_num} ===\n{p_text}")
                final_extracted_text = "\n\n".join(doc_builder)

                if all_base64_images and len(all_base64_images) > start_idx:
                    final_base64_images = all_base64_images[start_idx:end_idx]

                # Simpan metadata audit ke SessionBrain
                if brain:
                    if audit_is_last:
                        brain.clear_active_audit()
                    else:
                        await brain.save_active_audit({
                            "doc_id": doc_id_key,
                            "pdf_file_path": pdf_file_path or "",
                            "file_name": os.path.basename(pdf_file_path or "dokumen.pdf"),
                            "current_start": audit_start_page,
                            "current_end": audit_end_page,
                            "current_batch_label": f"{audit_start_page}-{audit_end_page}",
                            "total_pages": total_pages,
                            "batch_size": BATCH_SIZE
                        })

            elif is_summary:
                # Mode Rangkuman Dokumen Utuh
                yield format_sse(status=f"📑 Merangkum seluruh {total_pages} halaman dokumen", status_key="SUMMARIZING_PAGES", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.05)

                if total_pages <= 40:
                    # Single-Pass Full Context
                    doc_builder = []
                    for item in text_map:
                        p_idx = item.get("page_num", 0)
                        p_text = item.get("text", "").strip()
                        doc_builder.append(f"--- TEKS HALAMAN {p_idx+1} ---\n{p_text}")
                    final_extracted_text = "\n\n".join(doc_builder)
                    final_base64_images = []
                else:
                    # Map-Reduce / Skeleton mode untuk dokumen raksasa (> 40 halaman)
                    doc_builder = []
                    for item in text_map[:60]:
                        p_idx = item.get("page_num", 0)
                        p_text = item.get("text", "").strip()
                        lines = p_text.splitlines()[:15]
                        doc_builder.append(f"--- OUTLINE HALAMAN {p_idx+1} ---\n" + "\n".join(lines))
                    final_extracted_text = "\n\n".join(doc_builder)
                    final_base64_images = []
            else:
                # Mode Targeted QA (Two-Stage Context-Aware Retrieval)
                yield format_sse(status=f"🔍 Menganalisis klausul terkait pada {total_pages} halaman", status_key="ANALYZING_CLAUSES_PAGES", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.05)

                explicit_pages = extract_explicit_pages_from_query(user_message, total_pages)
                selected_pages, final_base64_images, final_extracted_text = await two_stage_rerank_cluster_async(
                    user_message=user_message,
                    text_map=text_map,
                    all_base64_images=all_base64_images,
                    total_pages=total_pages,
                    explicit_pages=explicit_pages,
                    top_k_seeds=4
                )

                halaman_str = ", ".join([str(p+1) for p in selected_pages])
                yield format_sse(status=f"📌 Ditemukan Klausul pada Halaman {halaman_str}!", status_key="FOUND_CLAUSE_PAGE", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.1)

        # ── 3. Susun Prompt & Context ───────────────────────────────────────────
        if is_audit_mode:
            pdf_name = os.path.basename(pdf_file_path) if pdf_file_path else "Dokumen Kedinasan"
            system_prompt = build_doc_audit_system_prompt(
                employee_name=employee_name,
                filename=pdf_name,
                start_page=audit_start_page,
                end_page=audit_end_page,
                total_pages=total_pages,
                is_last_batch=audit_is_last,
                next_start=audit_next_start,
                next_end=audit_next_end,
                is_thinking=is_thinking
            )
        else:
            system_prompt = build_attachment_system_prompt(employee_name=employee_name)

        if is_thinking:
            system_prompt = "<|think|\>\n" + system_prompt

        session_chunks = routing_data.get("_session_chunks_text", "") if routing_data else ""
        if session_chunks:
            system_prompt = session_chunks + "\n\n" + system_prompt

        # Gabungkan teks yang diekstrak ke dalam pesan user
        augmented_user_message = user_message
        if is_audit_mode:
            pdf_name = os.path.basename(pdf_file_path) if pdf_file_path else "dokumen.pdf"
            augmented_user_message = (
                f"Lakukan audit ejaan, typo, tata bahasa, dan struktur format untuk Halaman {audit_start_page} s/d {audit_end_page} dari dokumen '{pdf_name}'.\n\n"
                f"[KONTEN DOKUMEN BATCH HALAMAN {audit_start_page}–{audit_end_page} (Total {total_pages} Halaman)]:\n"
                f"{final_extracted_text}"
            )
        elif final_extracted_text:
            pdf_name = os.path.basename(pdf_file_path) if pdf_file_path else "dokumen.pdf"
            augmented_user_message = (
                f"PERHATIAN: Pengguna melampirkan dokumen baru '{pdf_name}'. Jawablah HANYA berdasarkan konten dokumen lampiran baru ini. Abaikan topik, peraturan, nomor halaman, atau audit dari riwayat percakapan sebelumnya.\n\n"
                f"Pertanyaan Pengguna: {user_message}\n\n"
                f"[KONTEN DOKUMEN PDF LAMPIRAN: '{pdf_name}' (Total {total_pages} Halaman)]:\n"
                f"{final_extracted_text}"
            )

        elif text_contents:
            text_block = "\n\n".join(text_contents)
            # Smart context budgeting to comfortably fit within 16k context window (max ~42k chars text)
            if len(text_block) > 42000:
                text_block = text_block[:42000] + "\n\n...[Teks lampiran panjang diringkas ke batas optimal 16K context]..."
            augmented_user_message = (
                f"{user_message}\n\n"
                f"[KONTEN FILE TERLAMPIR]\n{text_block}"
            )

        # Jika pengguna mengunggah dokumen baru (bukan lanjutan audit/multi-turn pada dokumen yang sama),
        # bersihkan riwayat chat sebelumnya agar tidak terjadi kontaminasi silang dokumen/topik lain
        if not is_continuation and (is_audit_mode or is_summary or (pdf_file_path and len(attachments or []) > 0)):
            trimmed_messages = []
            logger.info("[MODE_ATTACHMENT] 🛡️ Anti-contamination active: cleared previous history for fresh attachment")
        else:
            messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
            trimmed_messages = messages_dict[-4:] if len(messages_dict) > 4 else messages_dict

        # Build stream messages
        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]

        user_payload = {"role": "user", "content": augmented_user_message}
        
        # Masukkan gambar visual (baik dari PDF pages maupun direct images)
        all_imgs = final_base64_images + direct_images_b64
        if all_imgs:
            user_payload["images"] = all_imgs[:4]

        # Gantikan atau tambahkan pesan user terakhir
        replaced = False
        for i in range(len(stream_messages) - 1, -1, -1):
            if stream_messages[i]["role"] == "user":
                stream_messages[i] = user_payload
                replaced = True
                break
        if not replaced:
            stream_messages.append(user_payload)

        # ── 4. Fixed 16K Token Budget (Zero VRAM Eviction / Zero Reload) ───────────
        # Mengunci num_ctx di 16384 persis sama dengan seluruh mode lainnya
        num_ctx = 16384
        logger.info(f"[MODE_ATTACHMENT] Fixed 16K context size locked: {num_ctx}")
        target_model = getattr(settings, "MODEL_PERSONA", "gemma4:31b")

        yield format_sse(status="", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        buffer = ""
        try:
            async for chunk_line in stream_ollama_chat(
                model_name=target_model,
                messages=stream_messages,
                request=request,
                temperature=0.7,
                num_ctx=num_ctx,
                num_predict=8192,
                is_thinking=is_thinking,
                stream_speed=0.01,
                employee_name=employee_name
            ):
                buffer += chunk_line
                yield chunk_line
        except Exception as e:
            logger.error(f"[MODE_ATTACHMENT] Execution error: {str(e)}", exc_info=True)
            yield format_sse(
                chunk=f"\n\n[SYSTEM ERROR]: Terjadi kesalahan saat memproses lampiran: {str(e)}",
                event_type=SSEEventType.ERROR
            )
