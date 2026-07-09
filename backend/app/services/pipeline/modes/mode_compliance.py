import logging
import json
import os
import asyncio
import base64
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.modes.mode_utils import detect_precheck
from backend.app.services.pipeline.prompts.compliance_prompts import build_response_prompt_compliance
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.paths import get_abs_path, BASE_DIR
from backend.app.core.database import get_peraturan_db
from backend.app.core.config import settings

logger = logging.getLogger("MODE_COMPLIANCE")

class ModeCompliance:
    """
    Mode Compliance: Sandbox Uji Kepatuhan.
    Membaca dokumen PDF (teks/scan) secara iteratif (Sliding Window per 20 halaman).
    Jika jawaban tidak ada (dijawab 'KOSONG' oleh LLM), maju ke 20 halaman berikutnya.
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
        
        logger.info("[MODE_COMPLIANCE] Starting Compliance Mode Execution")
        isolated_doc_id = context_isolation.get("isolated_doc_id")
        
        yield format_sse(status="🎯 Menginisialisasi Mode Uji Kepatuhan...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        # 1. Fetch Filename from Database
        filename = None
        try:
            async with get_peraturan_db() as conn:
                async with conn.cursor() as cur:
                    query = """
                        SELECT COALESCE(NULLIF(gambar, ''), NULLIF(gambar2, ''), NULLIF(gambar3, '')) AS filename 
                        FROM berita 
                        WHERE id_berita = %s
                    """
                    await cur.execute(query, (isolated_doc_id,))
                    row = await cur.fetchone()
                    if row and row[0]:
                        filename = row[0]
        except Exception as e:
            logger.error(f"[MODE_FOCUS] DB Error: {e}")
                
        if not filename:
            error_msg = "Maaf, file dokumen untuk ID tersebut tidak ditemukan di database."
            yield format_sse(error_msg, "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            return

        # 2. Resolve File Path (pinAi/file_peraturan)
        file_path = os.path.join(str(BASE_DIR), "file_peraturan", filename)
        logger.info(f"[MODE_FOCUS] Target file: {file_path}")

        if not os.path.exists(file_path):
            error_msg = f"Maaf, file fisik '{filename}' tidak ditemukan di server."
            yield format_sse(error_msg, "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            return

        # 3. Read PDF (Using PyMuPDF)
        yield format_sse(status=f"📂 Membaca dokumen {filename}...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        try:
            import fitz
            doc = fitz.open(file_path)
            total_pages = len(doc)
        except Exception as e:
            logger.error(f"[MODE_FOCUS] Error opening PDF: {e}")
            yield format_sse("Maaf, file PDF tidak dapat dibaca atau rusak.", "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            return

        # 4. Deteksi Tipe PDF (Text vs Scan) & Set Chunk Size
        sample_text = ""
        for i in range(min(3, total_pages)):
            sample_text += doc.load_page(i).get_text("text").strip()
            
        is_document_scanned = len(sample_text.strip()) < 50
        
        # Jika text PDF, LLM bisa menampung banyak halaman sekaligus (128k context)
        # Jika scanned (gambar), kita harus melimit batch agar tidak OOM
        chunk_size = 15 if is_document_scanned else 200

        start_page = 0
        answer_found = False

        # Persiapkan Chat History context
        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        
        while start_page < total_pages and not answer_found:
            end_page = min(start_page + chunk_size, total_pages)
            yield format_sse(status=f"🔍 Menganalisis halaman {start_page + 1} - {end_page}...", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)

            extracted_text = ""
            base64_images = []
            
            # Coba ekstrak teks dulu
            for page_num in range(start_page, end_page):
                page = doc.load_page(page_num)
                text = page.get_text("text").strip()
                if text:
                    extracted_text += f"\n--- HALAMAN {page_num + 1} ---\n{text}\n"

            is_scanned = len(extracted_text.strip()) < 50 or is_document_scanned
            
            if is_scanned:
                # Dokumen Scan -> Convert ke Image
                yield format_sse(status=f"👁️ Membaca visual (scan) halaman {start_page + 1} - {end_page}...", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)
                for page_num in range(start_page, end_page):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("png")
                    encoded = base64.b64encode(img_data).decode("utf-8")
                    base64_images.append(encoded)

            precheck = detect_precheck(user_message, "compliance", False)
            # Siapkan system prompt
            system_prompt = build_response_prompt_compliance(
                employee_name=employee_name,
                precheck=precheck,
                is_thinking=is_thinking,
                start_page=start_page,
                end_page=end_page,
                filename=filename,
                extracted_text=extracted_text,
                is_scanned=is_scanned,
                user_scenario=user_message
            )

            # Buat message payload
            user_payload = {"role": "user", "content": user_message}
            if base64_images:
                user_payload["images"] = base64_images
                
            current_messages = [{"role": "system", "content": system_prompt}] + messages_dict + [user_payload]

            is_empty_flag = False
            buffer = ""
            started_streaming = False
            
            # Hitung estimasi token (1 token ~ 4 karakter)
            sys_tokens = len(system_prompt) // 4
            hist_tokens = sum(len(m.get("content", "")) for m in messages_dict) // 4
            rag_tokens = 0 # Focus mode uses web/search context inside system prompt mostly, so we can treat it as sys_tokens
            total_used = sys_tokens + hist_tokens + rag_tokens
            num_ctx = 256000

            session_uuid_to_use = session_uuid or (routing_data.get("_session_uuid") if routing_data else None)
            if session_uuid_to_use:
                from backend.app.services.chat.chat_history_service import chat_history_service
                obs_dict = {
                    "msg": "Generating deep focus response",
                    "memory": {
                        "system_tokens": sys_tokens,
                        "history_tokens": hist_tokens,
                        "rag_tokens": rag_tokens,
                        "total_used": total_used,
                        "max_ctx": num_ctx
                    }
                }
                await chat_history_service.save_agent_step(
                    session_id=session_uuid_to_use,
                    step_number=3,
                    tool_called="CALL_2_COMPLIANCE",
                    tool_input=f"Prompt chars: {len(system_prompt)}",
                    observation=json.dumps(obs_dict)
                )

            async for chunk_line in stream_ollama_chat(
                messages=current_messages,
                model_name=settings.MODEL_PERSONA, # TETAP PAKAI TEXT LLM
                is_thinking=is_thinking,
                temperature=0.1,
                num_ctx=256000,
                num_predict=8192,
                request=request
            ):

                try:
                    chunk = json.loads(chunk_line.strip())
                except json.JSONDecodeError:
                    continue

                event_type = chunk.get("event_type", "chunk")
                is_done = chunk.get("done", False)
                
                if event_type == "chunk":
                    char = chunk.get("chunk", "")
                    thought = chunk.get("thinking", "")
                    
                    if not started_streaming:
                        if thought:
                            yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
                            
                        if char:
                            buffer += char
                        
                        # Buffer hingga 30 karakter untuk mendeteksi kata KOSONG dengan aman
                        if len(buffer) >= 30 or is_done:
                            if "KOSONG" in buffer.upper():
                                is_empty_flag = True
                                break # Stop LLM stream, langsung lanjut iterasi berikutnya
                            elif buffer.strip():
                                started_streaming = True
                                yield format_sse(status="✨ Menemukan jawaban!", event_type=SSEEventType.STATUS)
                                yield format_sse(chunk=buffer, event_type=SSEEventType.CHUNK)
                    else:
                        if thought:
                            yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
                        if char:
                            yield format_sse(chunk=char, event_type=SSEEventType.CHUNK)

            if not is_empty_flag and started_streaming:
                answer_found = True
                yield format_sse("", "", True, event_type=SSEEventType.DONE)
                return
            elif not started_streaming and "KOSONG" not in buffer.upper():
                # Kasus jika jawaban LLM sangat pendek (di bawah 30 karakter) tapi bukan KOSONG
                answer_found = True
                yield format_sse(status="✨ Menemukan jawaban!", event_type=SSEEventType.STATUS)
                yield format_sse(buffer, "", False, event_type=SSEEventType.CHUNK)
                yield format_sse("", "", True, event_type=SSEEventType.DONE)
                return

            # Jika KOSONG, lanjut iterasi
            logger.info(f"[MODE_FOCUS] Jawaban tidak ditemukan di hal {start_page + 1}-{end_page}")
            start_page += chunk_size
            if start_page < total_pages:
                yield format_sse(status=f"⏳ Menelusuri halaman {start_page + 1} - {min(start_page + chunk_size, total_pages)}...", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)

        if not answer_found:
            yield format_sse("Maaf, informasi yang Anda cari tidak ditemukan di seluruh isi dokumen ini.", "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
