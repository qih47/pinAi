import logging
import json
import os
import asyncio
import base64
import datetime
import time
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
    "sh", "bat", "sql", "log", "env", "ini", "conf", "toml"
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

def is_deep_diff_intent(query: str) -> bool:
    q = (query or "").lower().strip()
    deep_keywords = [
        "menyeluruh", "detail", "rinci", "rincian", "per pasal", "per klausul", 
        "klausul", "baris demi baris", "line by line", "audit", "inspeksi", "diff",
        "perbedaan kata", "redline", "red line", "bandingkan menyeluruh", 
        "bandingkan detail", "secara mendalam", "secara rinci", "secara detail",
        "komparasi mendalam", "komparasi menyeluruh", "periksa perbedaan",
        "sandingkan pasal", "penyandingan pasal", "sandingkan dokumen"
    ]
    return any(kw in q for kw in deep_keywords)

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
        t_pre_start = time.time()
        logger.info("[MODE_ATTACHMENT] Starting execution")
        
        yield format_sse(status="👁️ Memindai file lampiran", status_key="SCANNING_ATTACHMENT", event_type=SSEEventType.STATUS)

        # ── 1. Ekstraksi Path File Lampiran ─────────────────────────────────────
        pdf_file_path = None
        pdf_file_paths = []
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
                    pdf_file_paths.append(abs_path)
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
                if cand not in pdf_file_paths:
                    pdf_file_paths.append(cand)

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
        summary_start_page = 1
        summary_end_page = 1
        multi_pdf_context = None

        # ── Jalur Khusus: Multi-PDF Komparasi & Diskusi Lintas Berkas (>= 2 PDF) ───
        if len(pdf_file_paths) >= 2:
            yield format_sse(status=f"📑 Membaca {len(pdf_file_paths)} berkas PDF", status_key="DOC_LOADING", event_type=SSEEventType.STATUS)
            from backend.app.services.chat.chat_history_service import chat_history_service
            from backend.app.services.ambient.brain_organizer import brain_asset_organizer
            from backend.app.services.ambient.asset_diff_engine import asset_diff_engine

            extracted_docs = []
            for p_path in pdf_file_paths:
                p_name = os.path.basename(p_path)
                t_map = None
                imgs = []
                p_total = 0
                if brain:
                    cached_brain = brain.get_document(p_name)
                    if cached_brain and "text_map" in cached_brain:
                        t_map = cached_brain["text_map"]
                        imgs = cached_brain.get("images", [])
                        p_total = cached_brain.get("total_pages", len(t_map))
                
                if t_map is None:
                    t_map, imgs, p_total = await extract_and_ocr_document_async(p_path, cache_key=p_path)
                    if brain:
                        await brain.save_document(p_name, {
                            "title": p_name,
                            "text_map": t_map,
                            "images": imgs,
                            "total_pages": p_total
                        })

                full_text_parts = []
                if isinstance(t_map, list):
                    for idx, item in enumerate(t_map):
                        if isinstance(item, dict):
                            p_num = item.get("page_num", idx + 1)
                            p_txt = item.get("text", "")
                        else:
                            p_num = idx + 1
                            p_txt = str(item)
                        full_text_parts.append(f"--- Hal. {p_num} ---\n{p_txt}")
                elif isinstance(t_map, dict):
                    for pg, val in sorted(t_map.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else str(x[0])):
                        p_txt = val.get("text", str(val)) if isinstance(val, dict) else str(val)
                        full_text_parts.append(f"--- Hal. {pg} ---\n{p_txt}")
                elif isinstance(t_map, str):
                    full_text_parts.append(t_map)

                full_text = "\n\n".join(full_text_parts)
                extracted_docs.append({
                    "title": p_name,
                    "path": p_path,
                    "text": full_text,
                    "total_pages": p_total,
                    "images": imgs[:2] if imgs else []
                })

                # Daftarkan ke ai_document_chunks untuk multi-turn discussion di sesi ini
                if session_uuid and current_user_npp:
                    profile = brain_asset_organizer.profile_asset(
                        content=full_text,
                        metadata={
                            "source": "pdf_attachment",
                            "title": p_name,
                            "type": "document",
                            "total_pages": p_total
                        }
                    )
                    asyncio.create_task(chat_history_service.save_document_chunk(
                        session_uuid=session_uuid,
                        npp=current_user_npp,
                        content=full_text[:30000],
                        file_id=None,
                        chunk_metadata=profile
                    ))

            doc_1 = extracted_docs[0]
            doc_2 = extracted_docs[1]
            is_deep = is_deep_diff_intent(user_message)

            doc_blocks = []
            for idx, d in enumerate(extracted_docs, 1):
                d_text = d["text"][:22000] + ("\n...[teks diringkas untuk efisiensi context]..." if len(d["text"]) > 22000 else "")
                doc_blocks.append(f"=== [DOKUMEN {idx}: '{d['title']}' ({d['total_pages']} Halaman)] ===\n{d_text}")

            if is_deep:
                # ── Kondisi 2: Deep Diff Inspector (Sub-cabang Khusus Mandiri) ──
                yield format_sse(status="⚖️ Menjalankan inspeksi komparasi naskah", status_key="COMPUTING_DIFF", event_type=SSEEventType.STATUS)
                yield format_sse(status="🔍 Menganalisis perbedaan klausul & baris", status_key="AUDITING_CLAUSES", event_type=SSEEventType.STATUS)

                from backend.app.core.paths import get_account_session_dir
                scratch_dir = get_account_session_dir(current_user_npp or "guest", session_uuid or "default", "scratch")
                os.makedirs(scratch_dir, exist_ok=True)

                ts = int(time.time() * 1000)
                f1_path = os.path.join(scratch_dir, f"doc1_{ts}.txt")
                f2_path = os.path.join(scratch_dir, f"doc2_{ts}.txt")
                raw_diff = ""

                try:
                    with open(f1_path, "w", encoding="utf-8") as f1, open(f2_path, "w", encoding="utf-8") as f2:
                        f1.write(doc_1["text"])
                        f2.write(doc_2["text"])

                    proc = await asyncio.create_subprocess_exec(
                        "diff", "-u", "-w", f1_path, f2_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(scratch_dir)
                    )
                    stdout_b, _ = await proc.communicate()
                    raw_diff = stdout_b.decode("utf-8", errors="replace").strip()
                except Exception as e_diff:
                    logger.warning(f"[MODE_ATTACHMENT] Native diff fallback to difflib: {e_diff}")
                    import difflib
                    raw_diff = "\n".join(difflib.unified_diff(
                        doc_1["text"].splitlines(),
                        doc_2["text"].splitlines(),
                        fromfile=doc_1["title"],
                        tofile=doc_2["title"],
                        lineterm=""
                    ))
                finally:
                    for p in (f1_path, f2_path):
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except Exception:
                                pass

                # Perbaiki header diff agar menggunakan nama dokumen bersih
                if raw_diff:
                    raw_diff = raw_diff.replace(f1_path, doc_1["title"]).replace(f2_path, doc_2["title"])
                else:
                    raw_diff = "--- Tidak ditemukan perbedaan teks signifikan antara kedua naskah dokumen ---"

                diff_filename = f"Komparasi_{os.path.splitext(doc_1['title'])[0]}_vs_{os.path.splitext(doc_2['title'])[0]}.diff"
                diff_payload = {
                    "filename": diff_filename,
                    "diff_text": raw_diff[:35000] if len(raw_diff) > 35000 else raw_diff,
                    "stats": {
                        "doc1": doc_1["title"],
                        "doc2": doc_2["title"],
                        "total_diff_lines": len(raw_diff.splitlines())
                    }
                }
                diff_widget = f"\n\n```document_diff\n{json.dumps(diff_payload, ensure_ascii=False)}\n```\n\n"
                yield format_sse(chunk=diff_widget, event_type=SSEEventType.CHUNK)

                multi_pdf_context = (
                    f"HASIL INSPEKSI PERBEDAAN TEKS SECARA MENYELURUH (UNIFIED DIFF):\n"
                    f"{raw_diff[:15000]}\n\n"
                    f"Pertanyaan / Instruksi Pengguna:\n{user_message}\n\n"
                    f"INSTRUKSI RESPON ANALISIS KOMPARASI:\n"
                    f"1. Awali dengan ikhtisar perbedaan substansial antara Dokumen 1 ('{doc_1['title']}') dan Dokumen 2 ('{doc_2['title']}').\n"
                    f"2. Sajikan tabel komparasi detail perubahan pasal/klausul (Kolom: Nomor/Pasal/Klausul, Naskah Dokumen 1, Naskah Dokumen 2, Analisis Perubahan & Implikasi).\n"
                    f"3. Berikan sintesis eksekutif apakah revisi menguntungkan atau mengandung risiko kepatuhan/operasional.\n\n"
                    f"{chr(10).join(doc_blocks)}"
                )
            else:
                # ── Kondisi 1: Fast-Path Comparison (Direct Markdown Table, Tanpa Blok Diff) ──
                yield format_sse(status="⚖️ Mengkomparasi kedua dokumen", status_key="COMPUTING_DIFF", event_type=SSEEventType.STATUS)

                cross_delta = asset_diff_engine.compute_cross_asset_diff(
                    asset_a={"title": doc_1["title"], "content": doc_1["text"], "type": "document"},
                    asset_b={"title": doc_2["title"], "content": doc_2["text"], "type": "document"}
                )

                multi_pdf_context = (
                    f"{cross_delta.summary_text}\n\n"
                    f"Pertanyaan / Instruksi Pengguna:\n{user_message}\n\n"
                    f"INSTRUKSI RESPON KOMPARASI:\n"
                    f"1. Rangkum perbedaan pokok antara Dokumen 1 ('{doc_1['title']}') dan Dokumen 2 ('{doc_2['title']}') secara jelas dan lugas.\n"
                    f"2. Sajikan tabel perbandingan pokok (Topik/Aspek, Dokumen 1, Dokumen 2, Catatan Utama).\n"
                    f"3. Tarik kesimpulan ringkas untuk membantu pengambilan keputusan.\n\n"
                    f"{chr(10).join(doc_blocks)}"
                )

            for d in extracted_docs:
                for b64 in d["images"]:
                    direct_images_b64.append(b64)

        elif pdf_file_path and os.path.exists(pdf_file_path):
            doc_id_key = str(os.path.basename(pdf_file_path))
            text_map = None
            all_base64_images = None
            total_pages = 0

            if brain:
                cached_brain = brain.get_document(doc_id_key)
                if cached_brain and "text_map" in cached_brain:
                    yield format_sse(status="🧠 Dari memori sesi", status_key="BRAIN_HIT", event_type=SSEEventType.STATUS)
                    text_map = cached_brain["text_map"]
                    all_base64_images = cached_brain.get("images", [])
                    total_pages = cached_brain.get("total_pages", len(text_map))

            if text_map is None:
                yield format_sse(status="📄 Memuat dokumen", status_key="DOC_LOADING", event_type=SSEEventType.STATUS)
                cache_key = pdf_file_path
                text_map, all_base64_images, total_pages = await extract_and_ocr_document_async(pdf_file_path, cache_key=cache_key)

                if brain:
                    await brain.save_document(doc_id_key, {
                        "title": os.path.basename(pdf_file_path),
                        "text_map": text_map,
                        "images": all_base64_images,
                        "total_pages": total_pages,
                    })
                    yield format_sse(status="💾 Menyimpan ke memori", status_key="BRAIN_SAVE", event_type=SSEEventType.STATUS)

            # ── Deteksi Intent: Audit / Proofreader vs Ringkasan vs Targeted QA ───
            explicit_pages = extract_explicit_pages_from_query(user_message, total_pages)
            is_cont = is_continuation_intent(user_message)
            active_mode = (active_audit.get("mode") if active_audit else "") or ""

            # Pemisahan mutlak: Jika ada sesi aktif di Session Brain dan user mengetik 'lanjut'
            if is_cont and active_mode == "summary":
                is_summary = True
                is_audit = False
                is_continuation = True
            elif is_cont and (active_mode == "audit" or "audit" in user_message.lower() or "koreksi" in user_message.lower()):
                is_audit = True
                is_summary = False
                is_continuation = True
            elif is_summary_intent(user_message) and not explicit_pages:
                is_summary = True
                is_audit = False
                is_continuation = False
            elif explicit_pages and len(explicit_pages) == 1:
                # 1 halaman spesifik secara eksplisit -> Targeted QA
                is_audit = False
                is_summary = False
                is_continuation = False
            elif is_audit_intent(user_message) or (is_cont and active_audit is not None):
                is_audit = True
                is_summary = False
                is_continuation = is_cont
            else:
                is_audit = False
                is_summary = False
                is_continuation = False

            logger.info(f"[MODE_ATTACHMENT] PDF detected ({total_pages} pages). Intent: {'AUDIT_PROOFREAD' if is_audit else ('SUMMARY' if is_summary else 'TARGETED_QA')} | Active Mode: {active_mode or 'None'} | Continuation: {is_continuation}")

            if is_audit:
                # ── Mode Chunked Audit & Proofreader (Dynamic Vision Batching up to 20 Pages) ──
                is_audit_mode = True
                MAX_AUDIT_BATCH = 20
                BATCH_SIZE = min(MAX_AUDIT_BATCH, total_pages)

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

                batch_type_desc = "Semua" if (start_idx == 0 and audit_is_last) else f"Halaman {audit_start_page}–{audit_end_page}"
                yield format_sse(
                    status=f"📑 Mengaudit Dokumen: {batch_type_desc} dari {total_pages} Halaman (Full Vision)",
                    status_key="AUDITING_PAGES",
                    event_type=SSEEventType.STATUS
                )

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
                        asyncio.create_task(brain.save_active_audit({
                            "doc_id": doc_id_key,
                            "pdf_file_path": pdf_file_path or "",
                            "file_name": os.path.basename(pdf_file_path or "dokumen.pdf"),
                            "current_start": audit_start_page,
                            "current_end": audit_end_page,
                            "current_batch_label": f"{audit_start_page}-{audit_end_page}",
                            "total_pages": total_pages,
                            "batch_size": BATCH_SIZE,
                            "mode": "audit"
                        }))

            elif is_summary:
                # ── Mode Rangkuman Dokumen Utuh (Safe Branching: Full Multimodal Vision) ──
                MAX_SUMMARY_VISION_BATCH = 20

                if total_pages <= MAX_SUMMARY_VISION_BATCH:
                    # Sub-kasus B1: Single-Pass Full Multimodal Vision (<= 20 Halaman)
                    yield format_sse(
                        status=f"📑 Merangkum seluruh {total_pages} halaman dokumen (Full Multimodal Vision)",
                        status_key="SUMMARIZING_PAGES",
                        event_type=SSEEventType.STATUS
                    )

                    doc_builder = []
                    for item in text_map:
                        p_idx = item.get("page_num", 0)
                        p_text = item.get("text", "").strip()
                        doc_builder.append(f"--- TEKS HALAMAN {p_idx+1} ---\n{p_text}")
                    final_extracted_text = "\n\n".join(doc_builder)
                    final_base64_images = all_base64_images[:total_pages] if all_base64_images else []
                    summary_start_page = 1
                    summary_end_page = total_pages
                    summary_is_last = True
                    summary_next_start = None
                    summary_next_end = None
                else:
                    # Sub-kasus B2: Multi-Turn Dynamic Vision Batching (> 20 Halaman)
                    if is_continuation and active_audit and active_audit.get("mode") == "summary":
                        start_idx = active_audit.get("current_end", 0)
                        end_idx = min(start_idx + MAX_SUMMARY_VISION_BATCH, total_pages)
                    else:
                        start_idx = 0
                        end_idx = min(MAX_SUMMARY_VISION_BATCH, total_pages)

                    if start_idx >= total_pages:
                        start_idx = 0
                        end_idx = min(MAX_SUMMARY_VISION_BATCH, total_pages)

                    summary_start_page = start_idx + 1
                    summary_end_page = end_idx
                    summary_is_last = (end_idx >= total_pages)
                    summary_next_start = (end_idx + 1) if not summary_is_last else None
                    summary_next_end = min(end_idx + MAX_SUMMARY_VISION_BATCH, total_pages) if not summary_is_last else None

                    yield format_sse(
                        status=f"📑 Merangkum Halaman {summary_start_page}–{summary_end_page} dari {total_pages} Halaman (Multimodal Vision)",
                        status_key="SUMMARIZING_PAGES",
                        event_type=SSEEventType.STATUS
                    )

                    doc_builder = []
                    for p in range(start_idx, end_idx):
                        if p < len(text_map):
                            item = text_map[p]
                            p_num = item.get("page_num", p) + 1
                            p_text = item.get("text", "").strip()
                            doc_builder.append(f"--- TEKS HALAMAN {p_num} ---\n{p_text}")
                    final_extracted_text = "\n\n".join(doc_builder)
                    final_base64_images = all_base64_images[start_idx:end_idx] if all_base64_images else []

                    if brain:
                        if summary_is_last:
                            brain.clear_active_audit()
                        else:
                            asyncio.create_task(brain.save_active_audit({
                                "doc_id": doc_id_key,
                                "pdf_file_path": pdf_file_path or "",
                                "file_name": os.path.basename(pdf_file_path or "dokumen.pdf"),
                                "current_start": summary_start_page,
                                "current_end": summary_end_page,
                                "current_batch_label": f"{summary_start_page}-{summary_end_page}",
                                "total_pages": total_pages,
                                "batch_size": MAX_SUMMARY_VISION_BATCH,
                                "mode": "summary"
                            }))
            else:
                # Mode Targeted QA (Two-Stage Context-Aware Retrieval)
                yield format_sse(status=f"🔍 Menganalisis klausul terkait pada {total_pages} halaman", status_key="ANALYZING_CLAUSES_PAGES", event_type=SSEEventType.STATUS)

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
        if multi_pdf_context:
            augmented_user_message = multi_pdf_context
        elif is_audit_mode:
            pdf_name = os.path.basename(pdf_file_path) if pdf_file_path else "dokumen.pdf"
            augmented_user_message = (
                f"Lakukan audit ejaan, typo, tata bahasa, dan struktur format untuk Halaman {audit_start_page} s/d {audit_end_page} dari dokumen '{pdf_name}'.\n\n"
                f"[KONTEN DOKUMEN BATCH HALAMAN {audit_start_page}–{audit_end_page} (Total {total_pages} Halaman)]:\n"
                f"{final_extracted_text}"
            )
        elif is_summary:
            pdf_name = os.path.basename(pdf_file_path) if pdf_file_path else "dokumen.pdf"
            if total_pages <= 20:
                augmented_user_message = (
                    f"Rangkumlah dokumen '{pdf_name}' (Total {total_pages} Halaman) secara komprehensif, eksekutif, dan mendalam.\n\n"
                    f"PENTING: Seluruh {total_pages} halaman dokumen telah dilampirkan langsung dalam format visual resolusi tinggi (image). "
                    f"Bacalah visual gambar dokumen asli untuk menyerap teks, bagan, tabel, stempel, dan tanda tangan dengan akurat tanpa kesalahan OCR.\n"
                    f"Awali responsmu dengan gaya aktif dan ramah menyapa pegawai: 'Baik {employee_name}, mari kita rangkum dokumen '{pdf_name}' ({total_pages} Halaman)...'\n\n"
                    f"Pertanyaan / Instruksi Pengguna: {user_message}\n\n"
                    f"[PANDUAN KONTINUITAS TEKS DOKUMEN]:\n"
                    f"{final_extracted_text}"
                )
            else:
                summary_label = f"Halaman {summary_start_page}–{summary_end_page}"
                last_notice = (
                    "\n\nIni adalah bagian terakhir dokumen! Setelah memaparkan intisari bagian ini, "
                    "kamu WAJIB menyajikan 'Kesimpulan & Sintesis Eksekutif Menyeluruh' dari seluruh dokumen (Halaman 1 s/d "
                    f"{total_pages}) yang merangkum substansi pokok, poin-poin krusial, dan implikasi penting secara utuh!"
                    if summary_is_last else
                    f"\n\nCatatan: Dokumen memiliki total {total_pages} halaman. "
                    f"Di akhir jawabanmu, beri ajakan ramah dan jelas kepada pengguna untuk melanjutkan (contoh: ketik 'Lanjut' untuk merangkum Halaman {summary_next_start}–{summary_next_end})."
                )
                opener_guidance = (
                    f"Awali responsmu dengan menyatakan: 'Melanjutkan rangkuman dokumen '{pdf_name}' untuk bagian {summary_label} dari total {total_pages} halaman...'"
                    if is_continuation else
                    f"Awali responsmu dengan menyatakan: 'Baik {employee_name}, mari kita rangkum dokumen '{pdf_name}' (Total {total_pages} Halaman). Karena dokumen ini cukup panjang, saya menganalisis visual resolusi tinggi untuk {summary_label} terlebih dahulu...'"
                )
                augmented_user_message = (
                    f"Tugas: Buat rangkuman substansial dokumen '{pdf_name}' untuk bagian {summary_label} dari total {total_pages} Halaman.{last_notice}\n\n"
                    f"GAYA BAHASA: {opener_guidance}\n"
                    f"PENTING: Visual gambar halaman {summary_label} telah dilampirkan langsung dalam format visual resolusi tinggi (image). "
                    f"Bacalah visual gambar dokumen asli secara teliti (tabel, stempel, klausul penting).\n\n"
                    f"Pertanyaan / Instruksi Pengguna: {user_message}\n\n"
                    f"[PANDUAN KONTINUITAS TEKS HALAMAN {summary_label}]:\n"
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
            # Smart context budgeting to comfortably fit within 32k context window (max ~55k chars text)
            if len(text_block) > 55000:
                text_block = text_block[:55000] + "\n\n...[Teks lampiran panjang diringkas ke batas optimal 32K context]..."
            augmented_user_message = (
                f"{user_message}\n\n"
                f"[KONTEN FILE TERLAMPIR]\n{text_block}"
            )

        elif len(direct_images_b64) >= 2 and not final_extracted_text:
            # Jalur khusus: Komparasi Visual Dua Gambar (Multimodal Visual Diffing)
            augmented_user_message = (
                f"{user_message}\n\n"
                f"[PANDUAN KOMPARASI MULTIMODAL DUA GAMBAR]:\n"
                f"Pengguna melampirkan {len(direct_images_b64)} gambar visual untuk dianalisis dan dikomparasikan.\n"
                f"Gambar 1 adalah kondisi awal/baseline, dan Gambar 2 adalah kondisi revisi/terbaru.\n"
                f"Analisis perbedaan visual secara seksama:\n"
                f"1. Objek, elemen UI, atau komponen apa yang baru ditambahkan di Gambar 2?\n"
                f"2. Objek apa yang diubah warnanya, posisinya, ukurannya, atau dihapus?\n"
                f"3. Berikan rangkuman komparasi visual tersebut secara sistematis, faktual, dan jelas."
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
            # Safe branching: mode audit atau summary diperbolehkan hingga 20 gambar visual (sesuai limit-mm-per-prompt=20)
            # Mode Targeted QA dibatasi hingga 8 gambar untuk efisiensi
            max_img_allow = 20 if (is_audit_mode or is_summary) else 8
            user_payload["images"] = all_imgs[:max_img_allow]

        # Gantikan atau tambahkan pesan user terakhir
        replaced = False
        for i in range(len(stream_messages) - 1, -1, -1):
            if stream_messages[i]["role"] == "user":
                stream_messages[i] = user_payload
                replaced = True
                break
        if not replaced:
            stream_messages.append(user_payload)

        # ── 4. Fixed 32K Token Budget (Zero VRAM Eviction / Zero Reload) ───────────
        # Mengunci num_ctx di 32768 persis sama dengan seluruh mode lainnya
        num_ctx = getattr(settings, "NUM_CTX_CORE", 32768)
        logger.info(f"[MODE_ATTACHMENT] Fixed 32K context size locked: {num_ctx}")
        target_model = getattr(settings, "MODEL_PERSONA", "gemma4:31b")

        t_pre_elapsed = (time.time() - t_pre_start) * 1000
        logger.info(f"[TIMING_BENCHMARK] [PRE_RESPONDER_ATTACHMENT] Done in {t_pre_elapsed:.2f}ms | Starting Responder stream")

        # ── Dynamic Progress Status Carousel Selama Menunggu TTFT LLM Prefill ──
        status_steps = []
        if is_summary and total_pages > 0:
            batch_count = summary_end_page - summary_start_page + 1
            status_steps = [
                (1.1, f"📑 Memproses {batch_count} halaman (Hal. {summary_start_page}–{summary_end_page} dari {total_pages} hal)", "PROCESSING_ATTACHMENT_PAGES"),
                (1.3, "👁️ Menganalisis visual multimodal & tata letak dokumen", "ANALYZING_MULTIMODAL_LAYOUT"),
                (1.3, "🧠 Mengekstraksi substansi penting & poin dokumen", "EXTRACTING_SUBSTANCE"),
                (1.5, "✍️ Menyusun analisis & rangkuman jawaban", "DRAFTING_SYNTHESIS")
            ]
        elif is_audit_mode and total_pages > 0:
            batch_count = audit_end_page - audit_start_page + 1
            status_steps = [
                (1.1, f"📑 Mengaudit {batch_count} halaman (Hal. {audit_start_page}–{audit_end_page} dari {total_pages} hal)", "AUDITING_PAGES"),
                (1.3, "👁️ Memindai klausul & tata letak dokumen", "SCANNING_REDTEAM_CLAUSES"),
                (1.3, "⚖️ Menguji kepatuhan skenario & mitigasi risiko", "ANALYZING_COMPLIANCE_SCENARIO"),
                (1.5, "✍️ Menyusun catatan audit & rekomendasi", "DRAFTING_RESPONSE")
            ]
        elif selected_pages:
            status_steps = [
                (1.1, f"🔍 Menganalisis klausul pada {len(selected_pages)} halaman terpilih", "ANALYZING_CLAUSES_PAGES"),
                (1.3, "👁️ Membaca konteks multimodal & referensi", "ANALYZING_MULTIMODAL_LAYOUT"),
                (1.5, "✍️ Menyusun jawaban komprehensif", "DRAFTING_RESPONSE")
            ]
        else:
            img_c = len(all_imgs) if all_imgs else 1
            status_steps = [
                (1.1, f"👁️ Memproses {img_c} berkas visual lampiran", "SCANNING_ATTACHMENT"),
                (1.3, "🧠 Menganalisis konteks visual & teks dokumen", "ANALYZING_MULTIMODAL_LAYOUT"),
                (1.5, "✍️ Menyusun jawaban", "DRAFTING_RESPONSE")
            ]

        # Antrean async untuk mengirim status progresif secara real-time tanpa memblokir stream
        status_queue = asyncio.Queue()
        stop_ticker = asyncio.Event()

        async def ticker_worker():
            try:
                for delay, status_text, status_key in status_steps:
                    if stop_ticker.is_set():
                        break
                    await status_queue.put(("status", format_sse(status=status_text, status_key=status_key, event_type=SSEEventType.STATUS)))
                    try:
                        await asyncio.wait_for(stop_ticker.wait(), timeout=delay)
                        break
                    except asyncio.TimeoutError:
                        continue
            except asyncio.CancelledError:
                pass
            except Exception as e_tick:
                logger.debug(f"[MODE_ATTACHMENT] Ticker worker exception: {e_tick}")

        async def stream_worker():
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
                    if not stop_ticker.is_set():
                        stop_ticker.set()
                        # Bersihkan status begitu token streaming pertama tiba
                        await status_queue.put(("clear_status", format_sse(status="", event_type=SSEEventType.STATUS)))
                    await status_queue.put(("chunk", chunk_line))
            except Exception as err:
                await status_queue.put(("error", err))
            finally:
                if not stop_ticker.is_set():
                    stop_ticker.set()
                await status_queue.put(("eof", None))

        ticker_task = asyncio.create_task(ticker_worker())
        stream_task = asyncio.create_task(stream_worker())

        buffer = ""
        try:
            while True:
                item_type, data = await status_queue.get()
                if item_type == "eof":
                    break
                elif item_type == "error":
                    raise data
                elif item_type == "chunk":
                    buffer += data
                    yield data
                elif item_type in ("status", "clear_status"):
                    yield data
        except Exception as e:
            logger.error(f"[MODE_ATTACHMENT] Execution error: {str(e)}", exc_info=True)
            yield format_sse(
                chunk=f"\n\n[SYSTEM ERROR]: Terjadi kesalahan saat memproses lampiran: {str(e)}",
                event_type=SSEEventType.ERROR
            )
        finally:
            stop_ticker.set()
            if not ticker_task.done():
                ticker_task.cancel()
            if not stream_task.done():
                stream_task.cancel()
