import json
import asyncio
import logging
import time
from typing import AsyncGenerator

from backend.app.services.pipeline.sse_validation import (
    SSEEventType,
    format_sse
)
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.peraturan_service import search_and_ocr_by_judul
from backend.app.services.chat_history_service import chat_history_service
from backend.app.services.pipeline.prompts.redteam_prompts import build_redteam_system_prompt

import logging
logger = logging.getLogger("CAKRA_MODE_REDTEAM")

class ModeRedTeam:
    """
    Mode eksekusi untuk Red-Team Clause Analysis.
    Sistem akan fokus pada HANYA SATU dokumen (isolated_doc_id).
    Lalu membedah celah hukum dari 2 sudut pandang ekstrem.
    """
    async def execute(
        self,
        user_message: str,
        chat_history: list,
        is_thinking: bool,
        attachments: list = None,
        context_isolation: dict = None,
        routing_data: dict = None,
        request = None,
        employee_name: str = "Pegawai",
        current_user_npp: str = None
    ) -> AsyncGenerator[str, None]:
        logger.info(f"[MODE_REDTEAM] Executing Red-Team Mode. Precheck data: {routing_data}")
        start_time = time.time()
        
        yield format_sse(status="🕵️ Mengisolasi dokumen target...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        isolated_doc_id = routing_data.get("isolated_doc_id")
        judul_context = ""
        judul_sources = []
        
        if isolated_doc_id:
            yield format_sse(status="🔍 Membedah lapisan dokumen secara mendalam...", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)
            
            # Ekstrak data dokumen dengan mencari judul
            # TODO: Ideally we fetch by ID, tapi fallback ke judul karena DB structure
            doc_title = routing_data.get("isolated_doc_title", "")
            if doc_title:
                judul_context, _, judul_sources = await search_and_ocr_by_judul(doc_title)
                
        # Fallback to search if no isolated_doc_id was found or failed to fetch
        if not judul_context:
            judul_context, _, judul_sources = await search_and_ocr_by_judul(user_message)
            
        yield format_sse(status="⚖️ Mengaktifkan Persona Ganda (Manajemen vs Pegawai)...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)
        
        if judul_sources:
            # Tampilkan dokumen yang diisolasi ke UI
            rag_sources = judul_sources[:1]
            yield format_sse("", "", False, sources=rag_sources, event_type=SSEEventType.SOURCES)
            await asyncio.sleep(0.01)
            
        system_prompt = build_redteam_system_prompt(
            employee_name=employee_name,
            precheck=routing_data,
            is_thinking=is_thinking,
            rag_context=judul_context
        )
        
        # ── Step 2: Inject Chat History (Long-Term Memory) ──
        session_chunks = routing_data.get("_session_chunks_text", "")
        if session_chunks:
            system_prompt += f"\n\n[RIWAYAT PERCAKAPAN SEBELUMNYA DALAM SESI INI]:\n{session_chunks}"

        # Convert chat history to dict list
        current_messages = [{"role": m.role, "content": m.content} for m in chat_history]
        # Insert system prompt at the beginning
        current_messages.insert(0, {"role": "system", "content": system_prompt})
        
        response_stream = stream_ollama_chat(
            messages=current_messages,
            model_name=settings.MODEL_PERSONA,
            is_thinking=is_thinking,
            temperature=0.7, # Sedikit lebih kreatif untuk mencari celah
            request=request
        )
        
        yield format_sse(status="⚔️ Menulis hasil debat argumen...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        final_thinking = ""
        final_answer = ""
        
        async for chunk_line in response_stream:
            try:
                chunk = json.loads(chunk_line.strip())
            except json.JSONDecodeError:
                continue

            event_type = chunk.get("event_type", "chunk")
            
            if event_type == "chunk":
                char = chunk.get("chunk", "")
                thought = chunk.get("thinking", "")
                
                if thought:
                    final_thinking += thought
                    yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
                
                if char:
                    final_answer += char
                    yield format_sse(chunk=char, event_type=SSEEventType.CHUNK)
            elif event_type == "error":
                err_msg = chunk.get("error", "Unknown Error")
                logger.error(f"[MODE_REDTEAM] LLM Stream Error: {err_msg}")
                yield format_sse(chunk=f"\n\n[SYSTEM ERROR]: {err_msg}", event_type=SSEEventType.ERROR)
                
        logger.info(f"[MODE_REDTEAM] Completed in {time.time() - start_time:.2f}s")
