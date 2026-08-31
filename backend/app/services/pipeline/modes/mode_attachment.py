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
from backend.app.services.pipeline.system_prompts import build_attachment_system_prompt
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
        "bedah seluruh", "analisis dokumen ini"
    ]
    return any(kw in q for kw in summary_keywords)

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
        
        yield format_sse(status="👁️ Memindai file lampiran", event_type=SSEEventType.STATUS)
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

        # ── 2. Penanganan Khusus Lampiran PDF dengan Document Intelligence ───────
        final_extracted_text = ""
        final_base64_images = []
        selected_pages = []
        total_pages = 0

        if pdf_file_path and os.path.exists(pdf_file_path):
            yield format_sse(status="⚙️ Memindai & mengekstrak konten PDF...", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.02)

            cache_key = session_uuid or pdf_file_path
            text_map, all_base64_images, total_pages = await extract_and_ocr_document_async(pdf_file_path, cache_key=cache_key)

            is_summary = is_summary_intent(user_message)
            logger.info(f"[MODE_ATTACHMENT] PDF detected ({total_pages} pages). Intent: {'SUMMARY' if is_summary else 'TARGETED_QA'}")

            if is_summary:
                # Mode Rangkuman Dokumen Utuh
                yield format_sse(status=f"📑 Merangkum seluruh {total_pages} halaman dokumen...", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.05)

                if total_pages <= 40:
                    # Single-Pass Full Context
                    doc_builder = []
                    for item in text_map:
                        p_idx = item.get("page_num", 0)
                        p_text = item.get("text", "").strip()
                        doc_builder.append(f"--- TEKS HALAMAN {p_idx+1} ---\n{p_text}")
                    final_extracted_text = "\n\n".join(doc_builder)
                    final_base64_images = [] # Text sudah diekstrak lengkap lewat OCR paralel
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
                yield format_sse(status=f"🔍 Menganalisis klausul terkait pada {total_pages} halaman...", event_type=SSEEventType.STATUS)
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
                yield format_sse(status=f"📌 Ditemukan Klausul pada Halaman {halaman_str}!", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.1)

        # ── 3. Susun Prompt & Context ───────────────────────────────────────────
        system_prompt = build_attachment_system_prompt(employee_name=employee_name)
        if is_thinking:
            system_prompt = "<|think|\>\n" + system_prompt

        session_chunks = routing_data.get("_session_chunks_text", "") if routing_data else ""
        if session_chunks:
            system_prompt = session_chunks + "\n\n" + system_prompt

        # Gabungkan teks yang diekstrak ke dalam pesan user
        augmented_user_message = user_message
        if final_extracted_text:
            pdf_name = os.path.basename(pdf_file_path) if pdf_file_path else "dokumen.pdf"
            augmented_user_message = (
                f"{user_message}\n\n"
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

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict

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
