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
from backend.app.services.pipeline.prompts.redteam_prompts import build_redteam_system_prompt
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.paths import get_abs_path, BASE_DIR
from backend.app.core.database import get_peraturan_db
from backend.app.core.config import settings
from backend.app.services.pipeline.document_intelligence import (
    extract_and_ocr_document_async,
    two_stage_rerank_cluster_async,
    extract_explicit_pages_from_query
)

logger = logging.getLogger("MODE_REDTEAM")

class ModeRedTeam:
    """
    Mode Red-Team: Bedah Celah Hukum & Analisis Risiko Regulasi.
    Membedah klausul dokumen secara utuh dari dua sudut pandang ekstrem (Manajemen vs Pegawai/Auditor)
    menggunakan Two-Stage Context-Aware Reranking & Structural Continuity Engine.
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
        
        logger.info("[MODE_REDTEAM] Starting Red-Team Mode Execution")
        isolated_doc_id = None
        doc_title = None
        doc_nomor = ""
        doc_tanggal = ""
        doc_jenis = "Regulasi"
        if context_isolation and isinstance(context_isolation, dict):
            isolated_doc_id = context_isolation.get("isolated_doc_id") or context_isolation.get("id_dokumen") or context_isolation.get("doc_id")
            doc_title = context_isolation.get("title") or context_isolation.get("doc_title")
            doc_nomor = context_isolation.get("nomor", "")
            doc_tanggal = context_isolation.get("tanggal", "")
            doc_jenis = context_isolation.get("jenis") or context_isolation.get("category", "Regulasi")
        if not isolated_doc_id and routing_data and isinstance(routing_data, dict):
            isolated_doc_id = routing_data.get("isolated_doc_id") or routing_data.get("id_dokumen") or routing_data.get("doc_id")
            doc_title = doc_title or routing_data.get("title") or routing_data.get("doc_title")
            doc_nomor = doc_nomor or routing_data.get("nomor", "")
            doc_tanggal = doc_tanggal or routing_data.get("tanggal", "")
            doc_jenis = doc_jenis if doc_jenis and doc_jenis != "Regulasi" else routing_data.get("jenis", doc_jenis)
        if not isolated_doc_id and request and getattr(request, "isolated_doc_id", None):
            isolated_doc_id = request.isolated_doc_id
            
        yield format_sse(status="🕵️ Membedah dokumen sasaran", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.05)

        # 1. Fetch Filename and Metadata from Database or Direct Filename
        filename = None
        if isinstance(isolated_doc_id, str) and isolated_doc_id.lower().endswith(".pdf"):
            filename = isolated_doc_id
        if isolated_doc_id:
            try:
                async with get_peraturan_db() as conn:
                    async with conn.cursor() as cur:
                        query = """
                            SELECT b.judul,
                                   COALESCE(NULLIF(b.gambar, ''), NULLIF(b.gambar2, ''), NULLIF(b.gambar3, ''), NULLIF(b.linkper, '')) AS filename,
                                   COALESCE(b.noper, '') as nomor,
                                   COALESCE(b.tanggal, '') as tanggal,
                                   COALESCE(k.nama_kategori, 'Regulasi') as jenis
                            FROM berita b
                            LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                            WHERE b.id_berita = %s
                        """
                        await cur.execute(query, (isolated_doc_id,))
                        row = await cur.fetchone()
                        if row:
                            doc_title = doc_title or row[0]
                            filename = filename or row[1]
                            doc_nomor = doc_nomor or row[2]
                            doc_tanggal = doc_tanggal or (str(row[3]) if row[3] else "")
                            doc_jenis = doc_jenis if doc_jenis and doc_jenis != "Regulasi" else (row[4] or doc_jenis)
                            logger.info(f"[MODE_REDTEAM] Resolved from MySQL: id={isolated_doc_id}, title='{doc_title}', nomor='{doc_nomor}'")
            except Exception as e:
                logger.error(f"[MODE_REDTEAM] DB Error: {e}")
                
        async def fallback_to_rag(reason: str):
            logger.warning(f"[MODE_REDTEAM] Fallback to RAG triggered: {reason}")
            yield format_sse(status="🔄 Mencari secara global", event_type=SSEEventType.STATUS)
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
        file_path = os.path.join(BASE_DIR, "file_peraturan", filename)
        if not os.path.exists(file_path):
            file_path = os.path.join(BASE_DIR, filename)
            
        if not os.path.exists(file_path):
            async for chunk in fallback_to_rag(f"File physical path not found: {file_path}"):
                yield chunk
            return

        logger.info(f"[MODE_REDTEAM] Target file: {file_path}")

        # 3. Brain-First Check / Fast Parallel OCR & Rendering via Document Intelligence
        doc_id_key = str(os.path.basename(file_path))
        text_map = None
        all_base64_images = None
        total_pages = None
        brain = None

        if session_uuid and current_user_npp:
            from backend.app.services.session.session_brain_service import SessionBrainService
            brain = SessionBrainService(current_user_npp, session_uuid)
            cached_brain = brain.get_document(doc_id_key)
            if cached_brain and "text_map" in cached_brain:
                yield format_sse(status="🧠 Dari memori sesi", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)
                text_map = cached_brain["text_map"]
                all_base64_images = cached_brain.get("images", [])
                total_pages = cached_brain.get("total_pages", len(text_map))

        if text_map is None:
            yield format_sse(status="📄 Memuat dokumen", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)
            cache_key = session_uuid or file_path
            text_map, all_base64_images, total_pages = await extract_and_ocr_document_async(file_path, cache_key=cache_key)

            if brain:
                await brain.save_document(doc_id_key, {
                    "title": os.path.basename(file_path),
                    "text_map": text_map,
                    "images": all_base64_images,
                    "total_pages": total_pages,
                })
                yield format_sse(status="💾 Menyimpan ke memori", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)

        # 4. Two-Stage Context-Aware Reranking & Structural Continuity Engine
        yield format_sse(status=f"🔍 Menganalisis seluruh {total_pages} halaman dokumen", event_type=SSEEventType.STATUS)
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

        # 5. Sampaikan SSE Bertahap ke frontend:
        halaman_str = ", ".join([str(p+1) for p in selected_pages])
        yield format_sse(status=f"📌 Ditemukan Klausul Sasaran pada Halaman {halaman_str}!", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.2)
        
        yield format_sse(status=f"⚔️ Membedah celah hukum dari 2 sudut pandang ekstrem", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.1)

        # 6. Persiapkan Chat History & Prompt
        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history]
        precheck = detect_precheck(user_message, "redteam", False)

        system_prompt = build_redteam_system_prompt(
            employee_name=employee_name,
            precheck=precheck,
            is_thinking=is_thinking,
            filename=doc_title or filename,
            extracted_text=final_extracted_text,
            user_topic=user_message,
            selected_pages=selected_pages,
            doc_nomor=doc_nomor,
            doc_jenis=doc_jenis,
            doc_tanggal=doc_tanggal
        )

        # Buat message payload: Kirim GAMBAR ASLI halaman terpilih ke Gemma Vision
        user_payload = {"role": "user", "content": user_message}
        if final_base64_images:
            user_payload["images"] = final_base64_images[:4]
            
        current_messages = [{"role": "system", "content": system_prompt}] + messages_dict + [user_payload]

        buffer = ""
        started_streaming = False
        
        # Hitung estimasi token
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in messages_dict) // 4
        total_used = sys_tokens + hist_tokens
        num_ctx = 16384

        session_uuid_to_use = session_uuid or (routing_data.get("session_uuid") if routing_data else None)
        if session_uuid_to_use:
            from backend.app.services.chat.chat_history_service import chat_history_service
            obs_dict = {
                "rag_mode": "REDTEAM",
                "used_tokens": total_used,
                "max_tokens": num_ctx,
                "context_usage_percent": round((total_used / num_ctx) * 100, 1),
                "is_thinking": is_thinking,
                "timestamp": datetime.datetime.now().isoformat(),
                "pages_selected": [p + 1 for p in selected_pages]
            }
            try:
                await chat_history_service.save_active_tokens_observation(
                    session_uuid=session_uuid_to_use,
                    tokens_observation=obs_dict
                )
            except Exception as e:
                logger.warning(f"[MODE_REDTEAM] Failed saving token obs: {e}")

        async for chunk in stream_ollama_chat(
            model_name=getattr(settings, "MODEL_PERSONA", "gemma4:31b"),
            messages=current_messages,
            request=request,
            temperature=0.4, # Sedikit lebih analitis untuk red-team reasoning
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

        # Format sources json
        sources_list = [{
            "id": isolated_doc_id,
            "title": doc_title or filename,
            "filename": filename,
            "nomor": doc_nomor,
            "tanggal": doc_tanggal,
            "jenis": doc_jenis,
            "halaman": [p + 1 for p in selected_pages]
        }]
        yield format_sse("", "", False, sources=sources_list, event_type=SSEEventType.SOURCES)
