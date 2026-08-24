import logging
import json
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.pipeline.system_prompts import build_attachment_system_prompt

logger = logging.getLogger("MODE_ATTACHMENT")

# Ekstensi file teks yang ditangani sebagai konten teks
TEXT_EXTENSIONS = {
    "txt", "csv", "md", "py", "js", "jsx", "ts", "tsx", "html", "css",
    "json", "yaml", "yml", "xml", "php", "java", "cpp", "c", "h",
    "sh", "bash", "dart", "swift", "go", "rs", "sql", "toml", "ini", "conf"
}

class ModeAttachment:
    """
    Mode Attachment: Bypasses Call 1 and RAG, focuses purely on the provided attachment.
    Menangani dua jenis attachment:
    1. File teks (txt, csv, code) → diinjeksi sebagai konten teks ke dalam prompt
    2. File gambar / PDF → diproses sebagai vision (base64 images)
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
        
        system_prompt = build_attachment_system_prompt(employee_name=employee_name)

        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        trimmed_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict

        if is_thinking:
            system_prompt = "<|think|\>\n" + system_prompt

        session_chunks = routing_data.get("_session_chunks_text", "") if routing_data else ""
        if session_chunks:
            system_prompt = session_chunks + "\n\n" + system_prompt

        # ── Klasifikasi Attachment: Teks vs Gambar ──────────────────────────────
        is_from_pdf = False
        images_base64 = []
        text_contents = []  # Konten teks dari file txt/csv/code

        if attachments:
            for att in attachments:
                if not isinstance(att, dict):
                    if isinstance(att, str):
                        images_base64.append(att)
                    continue

                # Deteksi PDF
                mime = att.get("mime_type", "")
                file_path = att.get("file_path", "")
                if mime == "application/pdf" or "pdf" in file_path.lower():
                    is_from_pdf = True

                # Deteksi file teks berdasarkan ekstensi atau mime type
                ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
                is_text_file = (
                    ext in TEXT_EXTENSIONS or
                    mime.startswith("text/") or
                    "csv" in mime or "json" in mime
                )

                if is_text_file and att.get("extracted_text"):
                    # File teks: ambil konten teks yang sudah di-extract
                    file_name = att.get("file_name", file_path.split("/")[-1])
                    content_text = att.get("extracted_text", "").strip()
                    text_contents.append(f"### File: {file_name}\n```\n{content_text}\n```")
                    logger.info(f"[MODE_ATTACHMENT] File teks terdeteksi: {file_name} ({len(content_text)} chars)")
                elif att.get("base64"):
                    images_base64.append(att["base64"])

        # ── Build Message yang Tepat ────────────────────────────────────────────
        # Gabungkan konten teks ke dalam user message jika ada
        augmented_user_message = user_message
        if text_contents:
            text_block = "\n\n".join(text_contents)
            augmented_user_message = (
                f"{user_message}\n\n"
                f"[KONTEN FILE TERLAMPIR]\n{text_block}"
            )
            logger.info(f"[MODE_ATTACHMENT] Menginjeksi {len(text_contents)} file teks ke dalam prompt")

        # (blok replace lama dihapus - sekarang ditangani langsung di stream_messages di bawah)

        stream_messages = [
            {"role": "system", "content": system_prompt},
            *trimmed_messages,
        ]
        
        # PENTING: user_message yang diterima dari orchestrator sudah berisi teks file yang diinjeksi
        # (baik via pipeline_orchestrator.py maupun via text_contents di atas).
        # Pastikan SELALU pesan user terakhir di stream_messages berisi augmented_user_message / user_message penuh.
        # Ini menangani kasus paste text dimana attachments array kosong tapi user_message sudah berisi kode.
        final_user_msg = augmented_user_message  # Sudah include text_contents jika ada
        replaced = False
        for i in range(len(stream_messages) - 1, -1, -1):
            if stream_messages[i]["role"] == "user":
                stream_messages[i] = {"role": "user", "content": final_user_msg}
                replaced = True
                break
        if not replaced:
            # Kalau tidak ada pesan user sama sekali (sesi baru), tambahkan
            stream_messages.append({"role": "user", "content": final_user_msg})
        
        logger.info(f"[MODE_ATTACHMENT] Final user msg length: {len(final_user_msg)} chars")

        # ── Proses Gambar (Vision) ──────────────────────────────────────────────
        if images_base64:
            import base64
            from io import BytesIO
            try:
                from PIL import Image
                processed_images = []
                for b64_str in images_base64:
                    if len(b64_str) * 0.75 > 2 * 1024 * 1024:
                        image_data = base64.b64decode(b64_str)
                        image = Image.open(BytesIO(image_data))
                        max_size = (1024, 1024)
                        image.thumbnail(max_size, Image.Resampling.LANCZOS)
                        buffered = BytesIO()
                        image.save(buffered, format="JPEG", quality=85)
                        processed_images.append(base64.b64encode(buffered.getvalue()).decode("utf-8"))
                    else:
                        processed_images.append(b64_str)
                
                for msg in reversed(stream_messages):
                    if msg["role"] == "user":
                        msg["images"] = processed_images
                        break
            except Exception as e:
                logger.error(f"[VISION] Gagal memproses gambar: {e}")

        # ── Token Budget & Context Window ───────────────────────────────────────
        # Karena pipeline_orchestrator.py MENGINJEKSI isi dokumen langsung ke user_message,
        # array `attachments` akan kosong untuk file teks.
        # Jadi kita kalkulasi token berdasarkan panjang actual dari user_message.
        
        # Cari pesan user terakhir untuk dihitung
        actual_user_msg = augmented_user_message
        for m in reversed(stream_messages):
            if m.get("role") == "user":
                actual_user_msg = m.get("content", "")
                break

        estimated_text_tokens = len(actual_user_msg) // 3
        
        # Jika panjang pesan user > 1000 char (berarti ada teks lampiran) atau text_contents terisi,
        # berikan context & budget besar
        has_large_text = estimated_text_tokens > 300 or bool(text_contents)

        num_ctx = 32768
        if is_from_pdf:
            token_budget = 1120
            num_predict_output = -1
        elif has_large_text:
            token_budget = None
            num_predict_output = -1
            logger.info(
                f"[MODE_ATTACHMENT] Text file mode | "
                f"estimated_tokens={estimated_text_tokens} | "
                f"num_ctx={num_ctx} | num_predict={num_predict_output} | token_budget=NONE (unlimited)"
            )
        else:
            token_budget = 280
            num_predict_output = -1

        temperature = 1.0  # Standard best practice Gemma 4
        target_model = getattr(settings, "MODEL_PERSONA", "gemma4:12b")

        # ── Observability ───────────────────────────────────────────────────────
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in messages_dict) // 4
        total_used = sys_tokens + hist_tokens + estimated_text_tokens

        session_uuid_to_use = session_uuid or (routing_data.get("_session_uuid") if routing_data else None)
        if session_uuid_to_use:
            from backend.app.services.chat.chat_history_service import chat_history_service
            obs_dict = {
                "msg": "Generating response for attachment",
                "attachment_type": "pdf" if is_from_pdf else ("text" if text_contents else "image"),
                "memory": {
                    "system_tokens": sys_tokens,
                    "history_tokens": hist_tokens,
                    "text_tokens": estimated_text_tokens,
                    "total_used": total_used,
                    "max_ctx": num_ctx,
                    "token_budget": token_budget
                }
            }
            await chat_history_service.save_agent_step(
                session_id=session_uuid_to_use,
                step_number=3,
                tool_called="CALL_2_ATTACHMENT",
                tool_input=f"Attachment analysis mode",
                observation=json.dumps(obs_dict)
            )

        yield format_sse(status="👁️ Memindai lampiran", event_type=SSEEventType.STATUS)

        try:
            async for chunk_line in stream_ollama_chat(
                model_name=target_model,
                messages=stream_messages,
                request=request,
                temperature=temperature,
                keep_alive=-1,
                num_ctx=num_ctx,
                num_predict=num_predict_output,
                is_thinking=is_thinking,
                token_budget=token_budget,
            ):
                try:
                    chunk_data = json.loads(chunk_line.strip())
                    yield chunk_line
                except json.JSONDecodeError:
                    yield chunk_line
        except Exception as e:
            logger.error(f"[MODE_ATTACHMENT] Execution error: {str(e)}", exc_info=True)
            yield format_sse(
                status=f"Terjadi kesalahan saat mengeksekusi Mode Attachment: {str(e)}",
                event_type=SSEEventType.STATUS
            )
