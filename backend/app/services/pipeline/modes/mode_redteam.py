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
            
        yield format_sse(status="🕵️ Membedah dokumen sasaran", status_key="OPENING_REDTEAM_DOC", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.05)

        # 1. Resolusi Identitas Dokumen Terpadu (PG dokumen & MySQL berita & Smart Fallback)
        from backend.app.services.tools.document_resolver import find_valid_pdf_file, resolve_isolated_document
        
        ctx_nomor = context_isolation.get("nomor", "") if (context_isolation and isinstance(context_isolation, dict)) else ""
        ctx_filename = context_isolation.get("filename", "") if (context_isolation and isinstance(context_isolation, dict)) else ""
        
        resolved = await resolve_isolated_document(
            isolated_doc_id=isolated_doc_id,
            doc_title=doc_title,
            doc_nomor=ctx_nomor,
            doc_filename=ctx_filename
        )
        pg_doc_id = resolved.get("pg_doc_id")
        filename = resolved.get("filename")
        file_path = resolved.get("file_path")
        doc_title = resolved.get("title") or doc_title
        doc_nomor = resolved.get("nomor") or ctx_nomor
        doc_tanggal = resolved.get("tanggal") or (context_isolation.get("tanggal", "") if isinstance(context_isolation, dict) else "")
        doc_jenis = resolved.get("jenis") or (context_isolation.get("category", "Regulasi") if isinstance(context_isolation, dict) else "Regulasi")

        logger.info(f"[MODE_REDTEAM] Unified resolved: id={resolved.get('doc_id')}, title='{doc_title}', nomor='{doc_nomor}', file_path={file_path}")

        async def fallback_to_rag(reason: str):
            logger.warning(f"[MODE_REDTEAM] Fallback to RAG triggered: {reason}")
            yield format_sse(status="🔄 Mencari secara global", status_key="SEARCHING_GLOBAL", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)
            from backend.app.services.pipeline.modes.mode_documents import ModeDocuments
            fallback_handler = ModeDocuments()
            
            target_ctx = dict(context_isolation) if isinstance(context_isolation, dict) else {}
            target_ctx.update({
                "isolated_doc_id": resolved.get("doc_id") or isolated_doc_id,
                "id_dokumen": resolved.get("doc_id") or isolated_doc_id,
                "title": doc_title,
                "nomor": doc_nomor,
                "filename": filename
            })
            fb_routing = dict(routing_data) if isinstance(routing_data, dict) else {}
            if doc_title or doc_nomor:
                existing_q = fb_routing.get("queries") or [user_message]
                target_q = f"{doc_title} {doc_nomor}".strip()
                if target_q and target_q not in existing_q:
                    fb_routing["queries"] = [target_q, *existing_q]
                fb_routing["search_tags"] = [doc_title, doc_nomor, *(fb_routing.get("search_tags") or [])]

            async for chunk in fallback_handler.execute(
                user_message=user_message,
                chat_history=chat_history,
                is_thinking=is_thinking,
                attachments=attachments,
                context_isolation=target_ctx,
                routing_data=fb_routing,
                request=request,
                employee_name=employee_name,
                current_user_npp=current_user_npp,
                session_uuid=session_uuid
            ):
                yield chunk

        # Jika file fisik tidak ada, tetapi ada chunks di dokumen_chunk
        text_map = None
        all_base64_images = []
        total_pages = 1
        if (not file_path or not os.path.exists(file_path)) and resolved.get("has_chunks") and pg_doc_id:
            try:
                from backend.app.core.database import get_db
                async with get_db() as pg_conn:
                    c_rows = await pg_conn.fetch(
                        "SELECT chunk_id, content, COALESCE(NULLIF(NULLIF(page_number, '0'), ''), '1') as page_number FROM dokumen_chunk WHERE dokumen_id = $1 ORDER BY chunk_id ASC LIMIT 50",
                        pg_doc_id
                    )
                    if c_rows:
                        text_map = []
                        for idx, r in enumerate(c_rows):
                            try:
                                p_val = int(r["page_number"])
                                p_0 = max(0, p_val - 1) if p_val > 1 else idx
                                text_map.append({"page_num": p_0, "text": r["content"]})
                            except Exception:
                                text_map.append({"page_num": idx, "text": r["content"]})
                        total_pages = len(text_map)
                        logger.info(f"[MODE_REDTEAM] Loaded {len(text_map)} chunks directly from dokumen_chunk for pg_id={pg_doc_id}")
            except Exception as chunk_err:
                logger.warning(f"[MODE_REDTEAM] Error fetching chunks from PG: {chunk_err}")

        if not file_path and not text_map:
            async for chunk in fallback_to_rag("File not found in DB or missing isolated_doc_id"):
                yield chunk
            return

        logger.info(f"[MODE_REDTEAM] Target file or text ready: file_path={file_path}, text_map_len={len(text_map) if text_map else 0}")

        # 3. Brain-First Check / Fast Parallel OCR & Rendering via Document Intelligence
        doc_id_key = str(os.path.basename(file_path)) if file_path else str(pg_doc_id or resolved.get('doc_id') or 'redteam_doc')
        brain = None

        if session_uuid and current_user_npp:
            from backend.app.services.session.session_brain_service import SessionBrainService
            brain = SessionBrainService(current_user_npp, session_uuid)
            cached_brain = brain.get_document(doc_id_key)
            if cached_brain and "text_map" in cached_brain:
                yield format_sse(status="🧠 Dari memori sesi", status_key="BRAIN_HIT", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)
                text_map = cached_brain["text_map"]
                all_base64_images = cached_brain.get("images", [])
                total_pages = cached_brain.get("total_pages", len(text_map))

        if text_map is None and file_path and os.path.exists(file_path):
            yield format_sse(status="📄 Memuat dokumen", status_key="DOC_LOADING", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)
            cache_key = session_uuid or file_path
            text_map, all_base64_images, total_pages = await extract_and_ocr_document_async(file_path, cache_key=cache_key, render_images=True)

            if brain:
                await brain.save_document(doc_id_key, {
                    "title": doc_title or os.path.basename(file_path),
                    "text_map": text_map,
                    "images": all_base64_images,
                    "total_pages": total_pages,
                })
                yield format_sse(status="💾 Menyimpan ke memori", status_key="BRAIN_SAVE", event_type=SSEEventType.STATUS)
                await asyncio.sleep(0.01)

        # 4. Two-Stage Context-Aware Reranking & Structural Continuity Engine
        yield format_sse(status=f"🔍 Menganalisis seluruh {total_pages} halaman dokumen", status_key="ANALYZING_REDTEAM_PAGES", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.05)


        explicit_pages = extract_explicit_pages_from_query(user_message, total_pages)
        selected_pages, final_base64_images, final_extracted_text = await two_stage_rerank_cluster_async(
            user_message=user_message,
            text_map=text_map,
            all_base64_images=all_base64_images,
            total_pages=total_pages,
            explicit_pages=explicit_pages,
            top_k_seeds=4,
            file_path=file_path
        )

        # 5. Sampaikan SSE Bertahap ke frontend:
        halaman_str = ", ".join([str(p+1) for p in selected_pages])
        yield format_sse(status=f"📌 Ditemukan Klausul Sasaran pada Halaman {halaman_str}!", status_key="FOUND_TARGET_CLAUSE_PAGE", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.2)
        
        yield format_sse(status=f"⚔️ Membedah celah hukum dari 2 sudut pandang ekstrem", status_key="DISSECTING_LEGAL_LOOPHOLES", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.1)

        # 6. Persiapkan Chat History & Prompt (Maks 5 putaran dialog / 10 pesan)
        messages_dict = [{"role": m.role, "content": m.content} for m in chat_history if getattr(m, "role", None) != "system"]
        if messages_dict and messages_dict[-1].get("role") == "user" and messages_dict[-1].get("content") == user_message:
            messages_dict = messages_dict[:-1]
        trimmed_messages = messages_dict[-10:] if len(messages_dict) > 10 else messages_dict
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

        # Buat message payload: Kirim GAMBAR ASLI seluruh halaman terpilih ke Gemma Vision (hingga 12 halaman)
        user_payload = {"role": "user", "content": user_message}
        if final_base64_images:
            valid_images = [img for img in final_base64_images if img and len(img) > 100]
            if valid_images:
                user_payload["images"] = valid_images[:12]
                logger.info(f"[MODE_REDTEAM] 🖼️ Injected {len(user_payload['images'])} page images into Call 2 (Gemma Vision)")
            
        current_messages = [{"role": "system", "content": system_prompt}] + trimmed_messages + [user_payload]

        buffer = ""
        started_streaming = False
        
        # Hitung estimasi token
        sys_tokens = len(system_prompt) // 4
        hist_tokens = sum(len(m.get("content", "")) for m in trimmed_messages) // 4
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
