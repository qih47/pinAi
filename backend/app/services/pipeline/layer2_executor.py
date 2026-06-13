import re
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.pipeline.system_prompts import (
    _build_gemma_system_prompt,
    _build_gemma_context_prompt,
)

logger = logging.getLogger("CAKRA_PIPELINE")

async def execute_layer_2_gemma_agentic(
    request: Request,
    messages: List[Dict[str, str]],
    cognitive_params: Dict[str, Any],
    preloaded_rag_context: Optional[str] = None,
    preloaded_rag_sources: Optional[List[Dict]] = None,
) -> AsyncGenerator[str, None]:
    """
    Layer 2: Gemma4 Single-Stream Executor
    
    🔥 REFACTOR:
    - Tidak ada [PANGGIL_RAG:] trigger (RAG sudah di-handle di chat.py)
    - <think> TIDAK dikirim ke FE, hanya log terminal
    - SSE status lebih granular untuk UX yang lebih hidup
    """
    logger.info("[LAYER_2_EXECUTOR] Gemma single-stream executor starting...")

    gateway_info = cognitive_params.get("_gateway", {})
    target_pipeline = gateway_info.get("target_pipeline", "flash")
    is_greeting = gateway_info.get("is_greeting", False)
    intent_type = gateway_info.get("intent_type", "chitchat")
    need_rag = cognitive_params.get("need_rag", False)
    is_coding = cognitive_params.get("is_coding", False)
    emotion = cognitive_params.get("emotion", "neutral")
    tone = cognitive_params.get("tone", "profesional")
    employee_name = cognitive_params.get("employee_name", "Pegawai")

    # 🔥 FIX: Ambil 5 turn terakhir untuk context
    if len(messages) > 5:
        messages = messages[-5:]
        logger.info(f"[LAYER_2_EXECUTOR] Context trimmed to last {len(messages)} turns")

    # ── Kirim sources ke FE jika ada (dari RAG paralel) ─────────────────────
    if preloaded_rag_sources:
        logger.info(f"[LAYER_2_EXECUTOR] Forwarding {len(preloaded_rag_sources)} RAG sources to frontend")
        yield _format_sse("", "", False, sources=preloaded_rag_sources)

    # ── Status update ke FE — GRANULAR & INFORMATIF ──────────────────────────
    if target_pipeline == "flash":
        if is_greeting:
            yield _format_sse("", "💬 Menyapa dengan hangat...", False)
        elif is_coding:
            yield _format_sse("", "💻 Menganalisis kode dan logika...", False)
        else:
            yield _format_sse("", "💭 Merumuskan jawaban...", False)
    elif preloaded_rag_context:
        yield _format_sse("", "📖 Menganalisis dokumen regulasi...", False)
        await asyncio.sleep(0)
        yield _format_sse("", f"🎯 Menyesuaikan gaya untuk {employee_name}...", False)
    else:
        yield _format_sse("", "💭 CAKRA sedang berpikir...", False)
    
    await asyncio.sleep(0)

    # ── Build system prompt dengan konteks lengkap ───────────────────────────
    base_system_prompt = _build_gemma_system_prompt(cognitive_params)
    final_system_prompt = _build_gemma_context_prompt(
        system_prompt=base_system_prompt,
        cognitive_params=cognitive_params,
        rag_context=preloaded_rag_context,
        rag_sources=preloaded_rag_sources,
    )

    stream_messages = [{"role": "system", "content": final_system_prompt}, *messages]

    # ── Dynamic num_ctx & temperature berdasarkan konteks ────────────────────
    has_rag = bool(preloaded_rag_context)
    detected_intent = cognitive_params.get("detected_intent", "NORMAL")
    if is_coding:
        # Coding pipeline: expanded context window for long code snippets and error logs
        num_ctx = 16384
        logger.info("[LAYER_2_EXECUTOR] Coding mode detected → num_ctx expanded to 16K")
        
    elif detected_intent == "chitchat":
        # Casual conversation and greetings: minimal context for faster response
        num_ctx = 2048
        
    else:
        # Document RAG pipeline: large context for regulatory documents
        num_ctx = 32768 if has_rag else 8192
        
    
    # Temperature adaptif berdasarkan intent
    if is_greeting or detected_intent == "chitchat":
        temperature = 0.75  # Lebih kreatif untuk sapaan
    elif is_coding:
        temperature = 0.3   # Lebih deterministik untuk kode
    elif has_rag:
        temperature = 0.4   # Balanced untuk RAG
    else:
        temperature = 0.55  # Default

    logger.info(
        f"[LAYER_2_EXECUTOR] Stream config | pipeline={target_pipeline} | "
        f"num_ctx={num_ctx} | temp={temperature} | has_rag={has_rag} | "
        f"intent={intent_type} | emotion={emotion}"
    )

    yield _format_sse("", "✍️ Menyusun respons final...", False)
    await asyncio.sleep(0)

    # ── Single Stream: parse <think> untuk log terminal SAJA ─────────────────
    # 🔥 FIX: <think> TIDAK dikirim ke FE, hanya log terminal
    in_think_tag = False
    think_buffer = ""
    think_logged = False

    try:
        async for chunk_line in stream_ollama_chat(
            model_name=settings.MODEL_PERSONA,
            messages=stream_messages,
            request=request,
            temperature=temperature,
            keep_alive=-1,
            num_ctx=num_ctx,
        ):
            try:
                chunk_data = json.loads(chunk_line.strip())
                chunk_text = chunk_data.get("chunk", "")
                native_thought = chunk_data.get("thought", "")
            except (json.JSONDecodeError, AttributeError):
                chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                native_thought = ""

            # Handle native thought (jika model support) — LOG SAJA
            if native_thought:
                think_buffer += native_thought
                continue

            if not chunk_text:
                continue

            # ── Parse <think> tag — LOG KE TERMINAL, JANGAN KE FE ────────────
            if "<think>" in chunk_text:
                in_think_tag = True
                # Kirim teks sebelum <think> sebagai chunk (jika ada)
                before_think = chunk_text.split("<think>")[0]
                if before_think.strip():
                    yield _format_sse(before_think, "", False)
                chunk_text = chunk_text.split("<think>", 1)[1] if "<think>" in chunk_text else ""

            if in_think_tag and "</think>" in chunk_text:
                # End of think block
                think_content, after_think = chunk_text.split("</think>", 1)
                think_buffer += think_content
                
                if think_buffer.strip():
                    logger.info(
                        f"[LAYER_2_THINK] Extracted {len(think_buffer)} chars from <think> block:\n"
                        f"{'─' * 60}\n{think_buffer.strip()}\n{'─' * 60}"
                    )
                    think_logged = True
                
                in_think_tag = False
                chunk_text = after_think

            if in_think_tag:
                # Accumulate thinking content — JANGAN YIELD KE FE
                think_buffer += chunk_text
                continue

            # ── Regular chunk (response) — KIRIM KE FE ───────────────────────
            if chunk_text:
                # Filter leak pattern (defense in depth)
                leak_patterns = ["[PANGGIL_RAG:", "[PANGGAL_RAG:", "[PANGGILAN_RAG:"]
                if any(p in chunk_text for p in leak_patterns):
                    logger.warning(f"[LAYER_2_EXECUTOR] RAG trigger leak detected and filtered: {chunk_text[:80]}")
                    clean = chunk_text
                    for p in leak_patterns:
                        clean = clean.replace(p, "")
                    clean = re.sub(r'\[PANGG[A-Z]*_RAG:[^\]]*\]', '', clean)
                    if clean.strip():
                        yield _format_sse(clean, "", False)
                else:
                    yield _format_sse(chunk_text, "", False)

    except Exception as e:
        logger.error(f"[LAYER2_STREAM_ERROR] Stream error: {e}")
        yield _format_sse("Maaf, terjadi kendala teknis. Silakan coba lagi.", "", False)

    # ── Final log jika thinking tidak pernah di-log (edge case) ──────────────
    if think_buffer.strip() and not think_logged:
        logger.info(
            f"[LAYER_2_THINK] Deferred think block — {len(think_buffer)} chars:\n"
            f"{'─' * 60}\n{think_buffer.strip()}\n{'─' * 60}"
        )

    yield _format_sse("", "", True)


def _format_sse(
    chunk: str, thinking: str = "", done: bool = False, sources: list = None
) -> str:
    """
    Format SSE response.
    
    🔥 NOTE: Field 'thinking' sekarang TIDAK digunakan untuk kirim ke FE.
    Hanya 'chunk', 'done', dan 'sources' yang aktif.
    Field 'thinking' dipertahankan untuk backward compatibility.
    """
    payload = {"chunk": chunk, "thinking": thinking, "done": done}
    if sources is not None:
        payload["sources"] = sources
    return json.dumps(payload, ensure_ascii=False) + "\n"
