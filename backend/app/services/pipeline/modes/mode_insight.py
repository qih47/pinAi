import logging
import os
import asyncio
import base64
import json
import re
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request

from backend.app.api.schemas.chat_schemas import ChatMessageSchema
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.prompts.rag_prompts import build_response_prompt_insight
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.paths import BASE_DIR
from backend.app.core.database import get_peraturan_db
from backend.app.core.config import settings
import aiomysql

logger = logging.getLogger("MODE_INSIGHT")

class ModeInsight:
    """
    Mode Insight: Generates an AI summary for a specific document.
    Extracts text/images from PDF and calls the LLM.
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
        
        logger.info("[MODE_INSIGHT] Starting Insight Mode Execution")
        document_id = context_isolation.get("isolated_doc_id")
        
        if not document_id:
            yield format_sse("Maaf, ID dokumen tidak ditemukan.", "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            return

        judul = ""
        isi_berita = ""
        filename = ""
        
        try:
            async with get_peraturan_db() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        "SELECT judul, isi_berita, COALESCE(NULLIF(gambar, ''), NULLIF(gambar2, ''), NULLIF(gambar3, '')) AS filename FROM berita WHERE id_berita = %s",
                        (document_id,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        judul = row["judul"]
                        isi_berita = row["isi_berita"] or ""
                        filename = row["filename"]
        except Exception as e:
            logger.error(f"[MODE_INSIGHT] DB Error: {e}")
            yield format_sse("Gagal mengambil data dokumen dari database.", "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            return
            
        if not row:
            yield format_sse("Maaf, dokumen tidak ditemukan.", "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            return

        # Bersihkan HTML dan ambil maksimal 8000 karakter pertama
        clean_text = re.sub('<[^<]+>', ' ', isi_berita)
        clean_text = ' '.join(clean_text.split())[:8000]
        
        base64_images = []
        if len(clean_text) < 50 and filename:
            try:
                import fitz
                file_path = os.path.join(BASE_DIR, "file_peraturan", filename)
                if os.path.exists(file_path):
                    doc = fitz.open(file_path)
                    extracted_texts = []
                    # Ambil maksimal 5 halaman pertama saja agar cepat
                    for i in range(min(5, len(doc))):
                        page = doc.load_page(i)
                        extracted_texts.append(page.get_text().strip())
                        # Convert to image for Gemma vision fallback
                        pix = page.get_pixmap(dpi=150)
                        img_data = pix.tobytes("png")
                        encoded = base64.b64encode(img_data).decode("utf-8")
                        base64_images.append(encoded)
                    doc.close()
                    pdf_text = " ".join(extracted_texts)
                    pdf_text = ' '.join(pdf_text.split())[:8000]
                    if len(pdf_text) > 50:
                        clean_text = pdf_text
            except Exception as e:
                logger.warning(f"⚠️ [MODE_INSIGHT] Gagal ekstrak teks PDF: {e}")

        if len(clean_text) < 50 and not base64_images:
            yield format_sse("Maaf, dokumen ini tidak memiliki teks yang cukup untuk dirangkum (kemungkinan dokumen hasil scan tanpa teks yang bisa dibaca mesin).", "", False, event_type=SSEEventType.CHUNK)
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            return
            
        system_prompt = build_response_prompt_insight(judul, clean_text)
        
        user_msg = {"role": "user", "content": system_prompt}
        if base64_images:
            user_msg["images"] = base64_images
            
        messages = [user_msg]
        
        model_name = getattr(settings, "MODEL_PERSONA", "gemma4:12b")
        
        async for chunk_str in stream_ollama_chat(
            model_name=model_name,
            messages=messages,
            request=request,
            temperature=0.3,
            num_predict=-1
        ):
            try:
                data = json.loads(chunk_str)
                if "chunk" in data:
                    yield format_sse(data["chunk"], "", False, event_type=SSEEventType.CHUNK)
                if data.get("done"):
                    yield format_sse("", "", True, event_type=SSEEventType.DONE)
            except:
                pass
