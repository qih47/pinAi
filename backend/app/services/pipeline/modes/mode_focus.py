import logging
import json
import re
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
from backend.app.core.paths import get_abs_path, BASE_DIR, FILE_PERATURAN_DIR, UPLOAD_DIR, DOCUMENTS_DIR
from backend.app.core.database import get_peraturan_db, get_db
from backend.app.core.config import settings
from backend.app.services.pipeline.document_intelligence import (
    extract_and_ocr_document_async,
    two_stage_rerank_cluster_async,
    extract_explicit_pages_from_query
)

logger = logging.getLogger("MODE_FOCUS")

class ModeFocus:
    """
    Mode Focus: Context Isolation.
    Membaca dokumen spesifik (PDF/dokumen regulasi/PKB/berita) secara eksklusif (tanpa tercampur dokumen lain).
    Mendukung resolusi dari PostgreSQL dokumen, MySQL berita, dan dokumen_chunk.
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
        
        isolated_doc_id = None
        doc_title = None
        if context_isolation and isinstance(context_isolation, dict):
            isolated_doc_id = context_isolation.get("isolated_doc_id") or context_isolation.get("id_dokumen") or context_isolation.get("doc_id")
            doc_title = context_isolation.get("title") or context_isolation.get("doc_title")
        if not isolated_doc_id and request and getattr(request, "isolated_doc_id", None):
            isolated_doc_id = request.isolated_doc_id
            
        yield format_sse(status="🎯 Membuka dokumen fokus rujukan", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.05)

        # 1. Resolusi Identitas Dokumen dari PostgreSQL (dokumen) & MySQL (berita)
        filename = None
        pg_doc_id = None
        db_file_path = None

        if isinstance(isolated_doc_id, str) and isolated_doc_id.lower().endswith(".pdf"):
            filename = isolated_doc_id
            
        # 1.1 Coba Query PostgreSQL dokumen
        if not filename and isolated_doc_id:
            try:
                async with get_db() as pg_conn:
                    doc_row = None
                    if str(isolated_doc_id).isdigit():
                        doc_row = await pg_conn.fetchrow(
                            "SELECT id, judul, filename FROM dokumen WHERE id = $1", 
                            int(isolated_doc_id)
                        )
                    if not doc_row and isinstance(isolated_doc_id, str):
                        doc_row = await pg_conn.fetchrow(
                            "SELECT id, judul, filename FROM dokumen WHERE filename = $1 OR judul ILIKE $1 LIMIT 1",
                            isolated_doc_id
                        )
                    if doc_row:
                        pg_doc_id = doc_row["id"]
                        filename = doc_row["filename"]
                        doc_title = doc_title or doc_row["judul"] or filename
                        logger.info(f"[MODE_FOCUS] Resolved from PG dokumen: id={pg_doc_id}, filename={filename}")
            except Exception as e:
                logger.warning(f"[MODE_FOCUS] PG query error: {e}")

        # 1.2 Coba Query MySQL berita jika belum ditemukan di PG
        if not filename and isolated_doc_id:
            try:
                async with get_peraturan_db() as conn:
                    async with conn.cursor() as cur:
                        query = """
                            SELECT judul, COALESCE(NULLIF(gambar, ''), NULLIF(gambar2, ''), NULLIF(gambar3, '')) AS filename 
                            FROM berita 
                            WHERE id_berita = %s
                        """
                        await cur.execute(query, (isolated_doc_id,))
                        row = await cur.fetchone()
                        if row and row[1]:
                            doc_title = doc_title or row[0]
                            filename = row[1]
                            logger.info(f"[MODE_FOCUS] Resolved from MySQL berita: filename={filename}")
            except Exception as e:
                logger.error(f"[MODE_FOCUS] MySQL Error: {e}")

        # 2. Cari Lokasi Fisik File di Disk
        file_path = None
        candidate_paths = []
        if db_file_path:
            candidate_paths.append(db_file_path)
            candidate_paths.append(os.path.join(BASE_DIR, db_file_path.lstrip("/")))
        if filename:
            candidate_paths.extend([
                os.path.join(FILE_PERATURAN_DIR, filename),
                os.path.join(DOCUMENTS_DIR, filename),
                os.path.join(UPLOAD_DIR, filename),
                os.path.join(BASE_DIR, "file_peraturan", filename),
                os.path.join(BASE_DIR, filename),
            ])

        for path in candidate_paths:
            if path and os.path.exists(path):
                file_path = path
                break

        # 3. Ekstrak Teks Dokumen
        selected_pages = [0]
        final_base64_images = []
        final_extracted_text = ""

        # Skenario A: File fisik ditemukan di disk -> Jalankan Document Intelligence & OCR
        if file_path and os.path.exists(file_path):
            logger.info(f"[MODE_FOCUS] Processing physical file: {file_path}")
            cache_key = session_uuid or file_path
            yield format_sse(status=f"⚙️ Memindai isi {doc_title or filename or 'dokumen'}", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.05)

            text_map, all_base64_images, total_pages = await extract_and_ocr_document_async(file_path, cache_key=cache_key)

            yield format_sse(status=f"🔍 Menganalisis {total_pages} halaman dokumen rujukan", event_type=SSEEventType.STATUS)
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

        # Skenario B: File fisik tidak di disk, tapi chunk teks sudah ada di PostgreSQL dokumen_chunk
        elif pg_doc_id or isolated_doc_id:
            logger.info(f"[MODE_FOCUS] File physical not found, fetching direct chunks from dokumen_chunk for doc_id={pg_doc_id or isolated_doc_id}")
            yield format_sse(status="📂 Mengambil teks utuh dari arsip dokumen", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.05)

            try:
                async with get_db() as pg_conn:
                    target_id = pg_doc_id if pg_doc_id else (int(isolated_doc_id) if str(isolated_doc_id).isdigit() else None)
                    if target_id:
                        c_rows = await pg_conn.fetch(
                            "SELECT chunk_id, content, COALESCE(NULLIF(NULLIF(page_number, '0'), ''), '1') as page_number FROM dokumen_chunk WHERE dokumen_id = $1 ORDER BY chunk_id ASC LIMIT 30",
                            target_id
                        )
                        if c_rows:
                            final_extracted_text = "\n\n---\n\n".join(r["content"] for r in c_rows)
                            parsed_pages = []
                            for r in c_rows:
                                try:
                                    p_val = int(r["page_number"])
                                    p_0 = max(0, p_val - 1)
                                    if p_0 not in parsed_pages:
                                        parsed_pages.append(p_0)
                                except (ValueError, TypeError):
                                    pass
                            selected_pages = parsed_pages[:5] if parsed_pages else [0]
            except Exception as e:
                logger.error(f"[MODE_FOCUS] Error fetching PG chunks: {e}")

        # Skenario C: Dokumen benar-benar tidak ditemukan -> Fallback ke RAG global
        if not final_extracted_text and not file_path:
            logger.warning(f"[MODE_FOCUS] Fallback to RAG triggered: File not found in DB or missing isolated_doc_id ({isolated_doc_id})")
            yield format_sse(status="🔄 Mencari secara global di arsip", event_type=SSEEventType.STATUS)
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
            return

        # 4. Sampaikan SSE Status Halaman Dokumen Terfokus
        halaman_str = ", ".join([str(p+1 if isinstance(p, int) else p) for p in selected_pages])
        yield format_sse(status=f"📌 Konteks Terfokus: {doc_title or filename or 'Dokumen Rujukan'} (Hal. {halaman_str})", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.1)

        # 5. Persiapkan Chat History & Prompt Focus Eksklusif
        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        precheck = detect_precheck(user_message, "focus", False)

        system_prompt = build_response_prompt_focus(
            employee_name=employee_name,
            precheck=precheck,
            is_thinking=is_thinking,
            selected_pages=selected_pages,
            filename=doc_title or filename or "Dokumen Rujukan",
            extracted_text=final_extracted_text, 
            is_scanned=False
        )
        
        if precheck and precheck.get("requires_visual"):
            from backend.app.services.pipeline.prompts.visual_prompts import VISUAL_SYSTEM_PROMPT
            system_prompt += "\n\n" + VISUAL_SYSTEM_PROMPT + "\n\n"

        # Buat message payload: Kirim GAMBAR ASLI halaman terpilih ke Gemma Vision jika ada
        user_payload = {"role": "user", "content": user_message}
        if final_base64_images:
            user_payload["images"] = final_base64_images[:4]
            
        current_messages = [{"role": "system", "content": system_prompt}] + messages_dict + [user_payload]

        buffer = ""
        started_streaming = False
        num_ctx = 16384

        session_uuid_to_use = session_uuid or (routing_data.get("session_uuid") if routing_data else None)
        if session_uuid_to_use:
            from backend.app.services.chat.chat_history_service import chat_history_service
            sys_tokens = len(system_prompt) // 4
            hist_tokens = sum(len(m.get("content", "")) for m in messages_dict) // 4
            total_used = sys_tokens + hist_tokens
            obs_dict = {
                "rag_mode": "FOCUS",
                "used_tokens": total_used,
                "max_tokens": num_ctx,
                "context_usage_percent": round((total_used / num_ctx) * 100, 1),
                "is_thinking": is_thinking,
                "timestamp": datetime.datetime.now().isoformat(),
                "pages_selected": selected_pages,
                "doc_title": doc_title or filename
            }
            try:
                await chat_history_service.save_active_tokens_observation(
                    session_uuid=session_uuid_to_use,
                    tokens_observation=obs_dict
                )
            except Exception as e:
                logger.warning(f"[MODE_FOCUS] Failed saving token obs: {e}")

        # 6. Stream Respons Ollama (Call 2 Focus)
        async for chunk in stream_ollama_chat(
            model_name=getattr(settings, "MODEL_PERSONA", "gemma4:31b"),
            messages=current_messages,
            request=request,
            temperature=0.1,
            num_ctx=num_ctx,
            num_predict=8192,
            is_thinking=is_thinking,
            stream_speed=0.01,
            employee_name=employee_name
        ):
            if not started_streaming:
                started_streaming = True
                yield format_sse(status="", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)

            buffer += chunk
            yield chunk

        # Format sources json eksklusif
        sources_list = [{
            "id": isolated_doc_id or pg_doc_id,
            "title": doc_title or filename or "Dokumen Rujukan",
            "filename": filename or doc_title,
            "halaman": selected_pages
        }]
        sources_tag = f"\n\n<sources_json>{json.dumps(sources_list)}</sources_json>"
        yield sources_tag
