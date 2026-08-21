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
from backend.app.services.pipeline.modes.mode_utils import detect_precheck
from backend.app.services.pipeline.prompts.rag_prompts import build_response_prompt_focus
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.paths import get_abs_path, BASE_DIR
from backend.app.core.database import get_peraturan_db
from backend.app.core.config import settings

logger = logging.getLogger("MODE_FOCUS")

class ModeFocus:
    """
    Mode Focus: Context Isolation.
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
        
        logger.info("[MODE_FOCUS] Starting Focus Mode Execution")
        isolated_doc_id = context_isolation.get("isolated_doc_id") if context_isolation else None
        
        yield format_sse(status="🎯 Menginisialisasi Mode Fokus...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.1)

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
                
        async def fallback_to_rag(reason: str):
            logger.warning(f"[MODE_FOCUS] Fallback to RAG triggered: {reason}")
            yield format_sse(status="🔄 File target tidak tersedia, beralih ke pencarian global...", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)
            from backend.app.services.pipeline.modes.mode_documents import ModeDocuments
            fallback_handler = ModeDocuments()
            async for chunk in fallback_handler.execute(
                user_message=user_message,
                chat_history=chat_history,
                is_thinking=is_thinking,
                attachments=attachments,
                context_isolation=None,
                routing_data=routing_data,
                request=request,
                employee_name=employee_name,
                current_user_npp=current_user_npp,
                session_uuid=session_uuid
            ):
                yield chunk

        if not filename:
            async for chunk in fallback_to_rag("File not found in DB or missing isolated_doc_id"):
                yield chunk
            return

        # 2. Resolve File Path (pinAi/file_peraturan)
        file_path = os.path.join(str(BASE_DIR), "file_peraturan", filename)
        logger.info(f"[MODE_FOCUS] Target file: {file_path}")

        if not os.path.exists(file_path):
            async for chunk in fallback_to_rag(f"Physical file '{filename}' not found"):
                yield chunk
            return

        # 3. Read PDF (Using PyMuPDF)
        yield format_sse(status=f"📂 Membaca dokumen {filename}...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.1)

        try:
            import fitz
            doc = fitz.open(file_path)
            total_pages = len(doc)
        except Exception as e:
            logger.error(f"[MODE_FOCUS] Error opening PDF: {e}")
            async for chunk in fallback_to_rag(f"Failed to open PDF: {e}"):
                yield chunk
            return

        session_uuid_to_use = session_uuid or (routing_data.get("_session_uuid") if routing_data else None)
        
        from backend.app.utils.focus_cache import get_focus_cache, set_focus_cache
        from backend.app.services.rag.reranker_service import reranker_service
        
        cached_data = get_focus_cache(session_uuid_to_use)
        
        if cached_data:
            logger.info(f"[MODE_FOCUS] 🚀 Memakai data cache (Bypass rendering & ekstraksi)")
            yield format_sse(status="🚀 Membaca data dokumen dari cache...", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.1)
            text_map = cached_data["text_map"]
            all_base64_images = cached_data["images"]
        else:
            yield format_sse(status=f"⚙️ Memproses & Mengekstrak teks dari {total_pages} halaman...", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.1)
            
            logger.info(f"[MODE_FOCUS] 👁️ Mengekstrak teks & merender PDF ke gambar untuk {total_pages} halaman...")
            
            def extract_and_render():
                t_map = []
                imgs = []
                for page_num in range(total_pages):
                    page = doc.load_page(page_num)
                    
                    # 1. Extract Text
                    text = page.get_text("text").strip()
                    t_map.append({
                        "page_num": page_num,
                        "text": text
                    })
                    
                    # 2. Render Image
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("png")
                    encoded = base64.b64encode(img_data).decode("utf-8")
                    imgs.append(encoded)
                return t_map, imgs
            
            render_start = datetime.datetime.now()
            text_map, all_base64_images = await asyncio.to_thread(extract_and_render)
            render_duration = (datetime.datetime.now() - render_start).total_seconds()
            logger.info(f"[MODE_FOCUS] ✅ Selesai proses {total_pages} halaman dalam {render_duration:.2f} detik.")
            
            set_focus_cache(session_uuid_to_use, text_map, all_base64_images)

        # 4. Filter & Rerank
        yield format_sse(status="🔍 Mencari halaman yang paling relevan (Reranker)...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.1)
        
        corpus_texts = [item["text"] if item["text"] else "[FULL IMAGE SCAN]" for item in text_map]
        
        # BGE Reranker
        scores = await reranker_service.compute_scores(user_message, corpus_texts)
        
        page_scores = []
        for idx, score in enumerate(scores):
            page_scores.append({
                "page_num": text_map[idx]["page_num"],
                "text": text_map[idx]["text"],
                "score": score
            })
            
        # Urutkan berdasarkan skor tertinggi
        page_scores.sort(key=lambda x: x["score"], reverse=True)
        
        # Ambil Top 5 halaman yang ada teksnya
        top_text_pages = [p["page_num"] for p in page_scores if len(p["text"]) >= 50][:5]
        
        # Halaman Full Scan (tanpa teks) akan dimasukkan semua ke Gemma 
        # sesuai instruksi user (karena Pindad kebanyakan teks native).
        full_scan_pages = [p["page_num"] for p in page_scores if len(p["text"]) < 50]
        
        # Gabungkan dan urutkan
        selected_pages = list(set(top_text_pages + full_scan_pages))
        selected_pages.sort()
        
        # Jika tidak ada yang terpilih (aneh), fallback ambil 5 halaman pertama
        if not selected_pages:
            selected_pages = list(range(min(5, total_pages)))
            
        logger.info(f"[MODE_FOCUS] Halaman terpilih (Top K + Scans): {selected_pages}")
        
        # Ambil base64 images HANYA untuk halaman terpilih
        final_base64_images = [all_base64_images[p] for p in selected_pages]
        
        # Sampaikan status ke frontend
        halaman_str = ", ".join([str(p+1) for p in selected_pages])
        if len(halaman_str) > 50:
             halaman_str = halaman_str[:50] + "..."
             
        yield format_sse(status=f"🎯 Membaca halaman {halaman_str}", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.1)

        # Persiapkan Chat History context
        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]

        precheck = detect_precheck(user_message, "focus", False)
        extracted_texts_list = []
        for p in selected_pages:
            t = text_map[p]["text"]
            if t.strip():
                extracted_texts_list.append(f"--- TEKS HALAMAN {p+1} ---\n{t}\n")
        
        final_extracted_text = "\n".join(extracted_texts_list)
        is_scanned_flag = len(final_extracted_text.strip()) < 50

        # Siapkan system prompt
        system_prompt = build_response_prompt_focus(
            employee_name=employee_name,
            precheck=precheck,
            is_thinking=is_thinking,
            selected_pages=selected_pages,
            filename=filename,
            extracted_text=final_extracted_text, 
            is_scanned=is_scanned_flag
        )
        
        if precheck and precheck.get("requires_visual"):
            from backend.app.services.pipeline.prompts.visual_prompts import VISUAL_SYSTEM_PROMPT
            system_prompt += "\n\n" + VISUAL_SYSTEM_PROMPT + "\n\n"

        # Buat message payload
        user_payload = {"role": "user", "content": user_message}
        if final_base64_images:
            user_payload["images"] = final_base64_images
            
        current_messages = [{"role": "system", "content": system_prompt}] + messages_dict + [user_payload]

        buffer = ""
        started_streaming = False
        
        # Hitung estimasi token (1 token ~ 4 karakter)
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in messages_dict) // 4
        rag_tokens = 0 
        total_used = sys_tokens + hist_tokens + rag_tokens
        num_ctx = 16384

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
                tool_called="CALL_2_FOCUS",
                tool_input=f"Prompt chars: {len(system_prompt)}",
                observation=json.dumps(obs_dict)
            )

        async for chunk_line in stream_ollama_chat(
            messages=current_messages,
            model_name=settings.MODEL_PERSONA,
            is_thinking=is_thinking,
            temperature=0.1,
            num_ctx=16384,
            num_predict=-1,
            request=request
        ):
            try:
                chunk = json.loads(chunk_line.strip())
            except json.JSONDecodeError:
                continue

            event_type = chunk.get("event_type", "chunk")
            
            if event_type == "chunk":
                char = chunk.get("chunk", "")
                thought = chunk.get("thinking", "")
                
                if not started_streaming:
                    if thought:
                        yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
                        
                    if char:
                        buffer += char
                    
                    if len(buffer) >= 5:
                        started_streaming = True
                        yield format_sse(status="✨ Menemukan jawaban!", event_type=SSEEventType.STATUS)
                        yield format_sse(chunk=buffer, event_type=SSEEventType.CHUNK)
                else:
                    if thought:
                        yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
                    if char:
                        yield format_sse(chunk=char, event_type=SSEEventType.CHUNK)

        if started_streaming:
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
        else:
            # Jika LLM sama sekali tidak menjawab karakter apa pun
            if buffer:
                yield format_sse(buffer, "", False, event_type=SSEEventType.CHUNK)
            else:
                yield format_sse("Maaf, informasi yang Anda cari tidak ditemukan atau gagal diproses.", "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
