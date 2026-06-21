"""
Gemma4 Agentic Engine — Single-Model Pipeline
==============================================

Menggantikan Layer 0 (qwen3 gateway) + Layer 2 (gemma executor) dalam satu engine.

Alur:
  1. Pre-check rule-based (instant, tanpa LLM) → deteksi chitchat/coding/attachment
  2. [chitchat] → Phase 2 langsung (jawab cepat, no thinking)
  3. [normal/rag] → Phase 1: Gemma4 stream thinking → parse routing decision
  4. [if need_rag] → run_rag_pipeline → inject context
  5. Phase 2: Gemma4 stream jawaban final

SSE output ke FE tetap sama: THINKING → SOURCES → CHUNK → DONE
"""

import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Dict, Any, List, Optional

from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.pipeline.sse_validation import (
    SSEEventType,
    format_sse,
)
from backend.app.services.pipeline.system_prompts import (
    build_intent_analysis_prompt,
    build_response_prompt,
)

logger = logging.getLogger("CAKRA_AGENTIC")

# ─── Rule-based pre-check constants ──────────────────────────────────────────
_CODING_KEYWORDS = [
    "import ", "export ", "const ", "async ", "await ", "function",
    "def ", "return ", "class ", "select ", "docker", "sql ", "query",
    "react", "python", "javascript", "coding", "usecontext", "usememo",
    "typescript", "golang", "kotlin", "flutter", "dart",
]
_GREETING_KEYWORDS = [
    "hai", "halo", "hello", "hi ", "apa kabar", "selamat pagi",
    "selamat siang", "selamat sore", "selamat malam", "assalamualaikum",
    "pagi", "siang", "malam",
]
_DOC_KEYWORDS = [
    "ketentuan", "peraturan", "skep", "sk direksi", "surat edaran",
    "regulasi", "kebijakan", "prosedur", "sop", "seragam", "cuti", "gaji",
    "tunjangan", "rekrutmen", "rekrut", "pegawai", "pindad", "aturan",
    "pasal", "syarat", "lembur", "pensiun", "promosi", "jabatan",
    "seleksi", "penerimaan",
]

# JSON marker yang Gemma tulis di dalam <think>
_ROUTING_JSON_PATTERN = re.compile(
    r'\{[^{}]*"need_rag"\s*:\s*(true|false)[^{}]*\}',
    re.DOTALL | re.IGNORECASE,
)


# ─── Rule-based pre-detection ──────────────────────────────────────────────────

def _detect_precheck(
    user_message: str,
    chat_mode: str,
    has_attachment: bool,
) -> Dict[str, Any]:
    """
    Instant rule-based detection sebelum Gemma dipanggil.
    Hasilnya menjadi hint untuk Phase 1 prompt dan bisa short-circuit ke Phase 2.
    """
    msg_lower = user_message.lower()

    is_coding = any(kw in msg_lower for kw in _CODING_KEYWORDS)
    is_greeting = any(kw in msg_lower for kw in _GREETING_KEYWORDS)
    is_doc_query = any(kw in msg_lower for kw in _DOC_KEYWORDS)

    # Pronoun detection
    if any(w in msg_lower for w in ["gue", "lo", "gw"]):
        pronoun, mirroring = "informal_gue_lo", "mirror_casual"
    elif any(w in msg_lower for w in ["saya", "anda", "bapak", "ibu"]):
        pronoun, mirroring = "formal_saya_anda", "stay_formal_safe"
    elif any(w in msg_lower for w in ["aku", "kamu"]):
        pronoun, mirroring = "familiar_aku_kamu", "mirror_casual"
    else:
        pronoun, mirroring = "unknown", "stay_formal_safe"

    slang = [s for s in ["bolo", "cuy", "bro", "gan", "sis"] if s in msg_lower]
    profanity = (
        "low_misuh"
        if any(w in msg_lower for w in ["asu", "jancuk", "anjir", "bangsat"])
        else "none"
    )

    word_count = len(user_message.split())
    is_chitchat = (
        is_greeting
        or (word_count <= 5 and not is_coding and not is_doc_query and not has_attachment)
    )

    # Force RAG paths
    if chat_mode == "documents" or has_attachment:
        need_rag_hint = True
        is_chitchat = False
    elif is_coding or is_chitchat:
        need_rag_hint = False
    elif is_doc_query:
        need_rag_hint = True
    else:
        need_rag_hint = None  # biarkan Gemma putuskan

    return {
        "is_chitchat": is_chitchat,
        "is_coding": is_coding,
        "is_greeting": is_greeting,
        "is_doc_query": is_doc_query,
        "need_rag_hint": need_rag_hint,
        "pronoun": pronoun,
        "mirroring": mirroring,
        "slang": slang,
        "profanity": profanity,
        "word_count": word_count,
    }


def _build_rule_based_queries(user_message: str) -> List[str]:
    """Fallback rule-based query builder jika parsing intent Gemma gagal."""
    msg = user_message.strip()
    msg_lower = msg.lower()

    prefix_map = [
        (["cuti", "izin", "libur"],
         ["ketentuan cuti pegawai", "hak cuti karyawan", "SKEP cuti"]),
        (["gaji", "upah", "penghasilan"],
         ["ketentuan gaji pegawai", "struktur penghasilan", "SK gaji tunjangan"]),
        (["seragam", "pakaian", "baju", "dinas"],
         ["ketentuan seragam dinas", "aturan pakaian kerja", "SKEP seragam"]),
        (["rekrut", "recruitment", "lamaran", "seleksi", "proses", "ipk"],
         ["proses rekrutmen pindad", "seleksi penerimaan pegawai", "ketentuan rekrutmen"]),
        (["tunjangan", "fasilitas", "benefit"],
         ["ketentuan tunjangan pegawai", "fasilitas karyawan", "SK tunjangan"]),
        (["lembur", "overtime"],
         ["ketentuan lembur pegawai", "aturan kerja lembur", "SKEP lembur"]),
        (["promosi", "kenaikan", "jabatan"],
         ["prosedur kenaikan jabatan", "ketentuan promosi pegawai", "SK kenaikan pangkat"]),
        (["pensiun", "masa kerja"],
         ["ketentuan pensiun pegawai", "aturan masa kerja", "SK pensiun"]),
        (["sop", "prosedur", "standar"],
         ["SOP prosedur operasional", "standar prosedur kerja", "instruksi kerja"]),
    ]

    for keywords, prefixes in prefix_map:
        if any(kw in msg_lower for kw in keywords):
            return prefixes[:3]

    trash_words = [
        "apakah", "ada", "yang", "lebih", "detail", "lagi", "seperti", "kalau",
        "gimana", "bagaimana", "sih", "cuy", "thanks", "ya", "mohon", "info",
        "tentang", "atau", "dan", "di", "ke", "dari", "untuk",
    ]
    words = [w for w in msg_lower.split() if w not in trash_words and len(w) > 2]
    if words:
        core = " ".join(words[:3])
        return [core, f"ketentuan {core}", f"regulasi {core}"]

    short = " ".join(msg.split()[:3])
    return [short, f"ketentuan {short}", f"regulasi {short}"]


def _parse_routing_from_thinking(accumulated_thinking: str, precheck: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse keputusan routing dari accumulated <think> content Gemma.

    Gemma diinstruksikan untuk menulis JSON routing di dalam think-nya:
      {"need_rag": true, "queries": ["q1", "q2", "q3"]}

    Jika parsing gagal → fallback ke precheck hints + rule-based queries.
    """
    if not accumulated_thinking:
        return _build_fallback_routing(precheck)

    # Cari JSON routing marker di dalam thinking
    matches = _ROUTING_JSON_PATTERN.findall(accumulated_thinking)

    # Cari JSON object lengkap yang mengandung need_rag
    json_pattern = re.compile(
        r'\{[^{}]*"need_rag"[^{}]*\}',
        re.DOTALL | re.IGNORECASE,
    )
    json_matches = json_pattern.findall(accumulated_thinking)

    for raw_json in reversed(json_matches):  # ambil yang terakhir muncul
        try:
            data = json.loads(raw_json)
            need_rag = bool(data.get("need_rag", False))
            queries = data.get("queries", [])

            if not isinstance(queries, list):
                queries = []

            # Validasi queries
            queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]

            # Jika need_rag tapi tidak ada queries → buat rule-based
            if need_rag and not queries:
                queries = _build_rule_based_queries(
                    precheck.get("_user_message", "")
                )

            logger.info(
                f"[AGENTIC] Routing parsed from think | need_rag={need_rag} | "
                f"queries={queries}"
            )
            return {"need_rag": need_rag, "queries": queries[:3]}

        except (json.JSONDecodeError, AttributeError):
            continue

    # Fallback jika tidak ada JSON yang valid
    logger.warning("[AGENTIC] No routing JSON found in thinking → using precheck fallback")
    return _build_fallback_routing(precheck)


def _build_fallback_routing(precheck: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback routing berdasarkan rule-based precheck."""
    need_rag_hint = precheck.get("need_rag_hint")
    user_message = precheck.get("_user_message", "")

    if need_rag_hint is True:
        queries = _build_rule_based_queries(user_message)
        return {"need_rag": True, "queries": queries}
    else:
        return {"need_rag": False, "queries": []}


# ─── Main Agentic Engine ────────────────────────────────────────────────────────

async def execute_gemma_agentic(
    request: Request,
    messages: List[Dict[str, str]],
    chat_mode: str = "auto",
    has_attachment: bool = False,
    ocr_text: Optional[str] = None,
    employee_name: str = "Pegawai",
) -> AsyncGenerator[str, None]:
    """
    Single-model Gemma4 Agentic Engine.

    Menggantikan execute_layer_0_gateway + execute_layer_2_gemma_agentic.
    SSE output format ke FE identik: THINKING → [SOURCES] → CHUNK → DONE.

    Args:
        request: FastAPI Request (untuk GPU semaphore)
        messages: List chat messages [{role, content}]
        chat_mode: "auto" | "documents" | "flash"
        has_attachment: True jika ada file attachment (PDF/image dari FE)
        ocr_text: Hasil OCR dari vision pipeline (jika ada PDF)
        employee_name: Nama pegawai yang sedang chat
    """
    user_message = messages[-1]["content"] if messages else ""
    logger.info(f"[AGENTIC] Starting | mode={chat_mode} | attachment={has_attachment} | user={employee_name}")

    # Context history (5 turns terakhir, exclude message saat ini)
    context_history_str = ""
    if len(messages) > 1:
        context_history_str = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in messages[-5:-1]]
        )

    # ── Step 1: Pre-check rule-based ──────────────────────────────────────────
    precheck = _detect_precheck(user_message, chat_mode, has_attachment)
    precheck["_user_message"] = user_message  # simpan untuk fallback

    is_chitchat = precheck["is_chitchat"]
    is_coding = precheck["is_coding"]
    need_rag_hint = precheck["need_rag_hint"]

    logger.info(
        f"[AGENTIC] Precheck | chitchat={is_chitchat} | coding={is_coding} | "
        f"need_rag_hint={need_rag_hint}"
    )

    # ── Step 2: Chitchat fast-path (skip thinking, langsung jawab) ────────────
    if is_chitchat and not has_attachment and chat_mode not in ("documents",):
        logger.info("[AGENTIC] Chitchat fast-path → Phase 2 direct (no think)")
        yield format_sse("", "💬 Menyiapkan balasan hangat", False, event_type=SSEEventType.THINKING)
        await asyncio.sleep(0.01)

        async for sse in _phase2_response_stream(
            request=request,
            messages=messages,
            precheck=precheck,
            employee_name=employee_name,
            rag_context=None,
            rag_sources=None,
            ocr_text=ocr_text,
            is_chitchat=True,
        ):
            yield sse
        return

    # ── Step 3: Phase 1 — Intent Analysis Stream ──────────────────────────────
    # Gemma stream thinking, kita kumpulkan untuk di-parse routing decision-nya
    if is_coding:
        yield format_sse("", "💻 Menganalisis struktur kode", False, event_type=SSEEventType.THINKING)
    elif need_rag_hint is True:
        yield format_sse("", "🔍 Memeriksa relevansi dokumen", False, event_type=SSEEventType.THINKING)
    else:
        yield format_sse("", "🧠 Memahami konteks pesan", False, event_type=SSEEventType.THINKING)
    await asyncio.sleep(0.01)

    # Jika precheck sudah pasti (forced path), skip Phase 1 LLM call
    if need_rag_hint is not None:
        logger.info(f"[AGENTIC] Routing forced by precheck | need_rag={need_rag_hint}")
        routing = _build_fallback_routing(precheck)
    else:
        # Phase 1: Gemma analyze intent dan putuskan routing
        routing, phase1_thinking_events = await _phase1_intent_analysis(
            request=request,
            user_message=user_message,
            context_history_str=context_history_str,
            precheck=precheck,
            ocr_text=ocr_text,
        )
        # Stream thinking events dari Phase 1 ke FE
        for event in phase1_thinking_events:
            yield event
            await asyncio.sleep(0.005)

    need_rag = routing["need_rag"]
    rag_queries = routing["queries"]

    # ── Step 4: RAG Pipeline (jika diperlukan) ────────────────────────────────
    rag_context = None
    rag_sources = None

    if need_rag and rag_queries:
        logger.info(f"[AGENTIC] RAG triggered | queries={rag_queries}")

        from backend.app.services.rag.rag_pipeline import run_rag_pipeline
        from backend.app.services.pipeline.sse_validation import SSEEventType as _SSE

        async for sse in run_rag_pipeline(
            rewritten_queries=rag_queries,
            limit_per_query=3,
        ):
            raw = sse.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
                event_type = data.get("event_type")

                if event_type == _SSE.PIPELINE_DATA:
                    rag_context = data["payload"].get("context")
                    rag_sources = data["payload"].get("sources")
                    logger.info(
                        f"[AGENTIC] RAG done | {len(rag_context or '')} chars | "
                        f"{len(rag_sources or [])} sources"
                    )
                
                # 🔥 FIX UTAMA 1: Pastikan event SOURCES dan THINKING dari run_rag_pipeline 
                # tetap di-yield ke luar agar bisa ditangkap oleh router API dan diteruskan ke FE
                if event_type in (_SSE.SOURCES, _SSE.THINKING):
                    yield sse
                    await asyncio.sleep(0.005)

            except (json.JSONDecodeError, AttributeError):
                yield sse
                await asyncio.sleep(0.01)
                
    elif need_rag and not rag_queries:
        logger.warning("[AGENTIC] need_rag=True tapi queries kosong → skip RAG")

    # ── Step 5: Phase 2 — Response Stream ────────────────────────────────────
    logger.info("[AGENTIC] Phase 2: Response stream starting")
    
    # 🔥 FIX UTAMA 2: Jika RAG berhasil membawa dokumen, pancarkan ulang event SOURCES 
    # tepat sebelum menyusun jawaban agar FE siap merender metadata rujukan
    if rag_sources:
        yield format_sse("", "", False, sources=rag_sources, event_type=SSEEventType.SOURCES)
        await asyncio.sleep(0.01)

    yield format_sse("", "✍️ Menyusun jawaban", False, event_type=SSEEventType.THINKING)
    await asyncio.sleep(0.01)

    async for sse in _phase2_response_stream(
        request=request,
        messages=messages,
        precheck=precheck,
        employee_name=employee_name,
        rag_context=rag_context,
        rag_sources=rag_sources,
        ocr_text=ocr_text,
        is_chitchat=False,
    ):
        yield sse


# ─── Phase 1: Intent Analysis ──────────────────────────────────────────────────

async def _phase1_intent_analysis(
    request: Request,
    user_message: str,
    context_history_str: str,
    precheck: Dict[str, Any],
    ocr_text: Optional[str],
) -> tuple[Dict[str, Any], List[str]]:
    """
    Phase 1: Gemma streaming untuk analisis intent.

    Mengembalikan:
      - routing dict: {"need_rag": bool, "queries": [...]}
      - list SSE string (thinking events) untuk di-yield ke FE
    """
    system_prompt = build_intent_analysis_prompt(
        user_message=user_message,
        context_history_str=context_history_str,
        precheck=precheck,
        ocr_text=ocr_text,
    )

    # Gunakan hanya 2 messages: system + user terakhir untuk Phase 1
    phase1_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    accumulated_thinking = ""
    thinking_events: List[str] = []

    try:
        async for chunk_line in stream_ollama_chat(
            model_name=settings.MODEL_PERSONA,
            messages=phase1_messages,
            request=request,
            temperature=0.1,   # rendah — kita butuh keputusan deterministik
            keep_alive=-1,
            num_ctx=2048,
            num_predict=512,   # cukup untuk routing decision
        ):
            try:
                chunk_data = json.loads(chunk_line.strip())
                thought = chunk_data.get("thought", "")
                chunk_text = chunk_data.get("chunk", "")
            except (json.JSONDecodeError, AttributeError):
                thought = ""
                chunk_text = ""

            if thought:
                accumulated_thinking += thought
                # Stream thinking ke FE
                from backend.app.services.pipeline.sse_validation import format_sse as _fmt
                evt = _fmt("", thought, False, event_type=SSEEventType.THINKING)
                if evt:
                    thinking_events.append(evt)

            # Phase 1 tidak stream chunk ke FE — kita hanya butuh thinking
            # (chunk dari Phase 1 diabaikan, Phase 2 yang akan jawab)

    except Exception as e:
        logger.error(f"[AGENTIC_PHASE1] Error: {e} → fallback routing")

    routing = _parse_routing_from_thinking(accumulated_thinking, precheck)
    return routing, thinking_events


# ─── Phase 2: Response Stream ──────────────────────────────────────────────────

async def _phase2_response_stream(
    request: Request,
    messages: List[Dict[str, str]],
    precheck: Dict[str, Any],
    employee_name: str,
    rag_context: Optional[str],
    rag_sources: Optional[List[Dict]],
    ocr_text: Optional[str],
    is_chitchat: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Phase 2: Gemma streaming untuk jawaban final.
    Ini yang menghasilkan CHUNK SSE ke FE.
    """
    has_rag = bool(rag_context)

    system_prompt = build_response_prompt(
        employee_name=employee_name,
        precheck=precheck,
        rag_context=rag_context,
        rag_sources=rag_sources,
        ocr_text=ocr_text,
        is_chitchat=is_chitchat,
    )

    # Trim messages untuk efisiensi
    trimmed_messages = messages[-3:] if len(messages) > 3 else messages

    stream_messages = [
        {"role": "system", "content": system_prompt},
        *trimmed_messages,
    ]

    # Context window berdasarkan mode
    if is_chitchat:
        num_ctx = 2048
        temperature = 0.75
    elif precheck.get("is_coding"):
        num_ctx = 8192
        temperature = 0.3
    elif has_rag:
        num_ctx = 16384
        temperature = 0.4
    else:
        num_ctx = 4096
        temperature = 0.55

    logger.info(
        f"[AGENTIC_PHASE2] Stream | chitchat={is_chitchat} | has_rag={has_rag} | "
        f"num_ctx={num_ctx} | temp={temperature}"
    )

    try:
        async for chunk_line in stream_ollama_chat(
            model_name=settings.MODEL_PERSONA,
            messages=stream_messages,
            request=request,
            temperature=temperature,
            keep_alive=-1,
            num_ctx=num_ctx,
            num_predict=8192,
        ):
            try:
                chunk_data = json.loads(chunk_line.strip())
                chunk_text = chunk_data.get("chunk", "")
                native_thought = chunk_data.get("thought", "")
            except (json.JSONDecodeError, AttributeError):
                chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                native_thought = ""

            if native_thought:
                yield format_sse("", native_thought, False, event_type=SSEEventType.THINKING)
            elif chunk_text:
                yield format_sse(chunk_text, "", False, event_type=SSEEventType.CHUNK)

    except Exception as e:
        logger.error(f"[AGENTIC_PHASE2] Stream error: {e}")
        yield format_sse(
            "Maaf, terjadi kendala teknis. Silakan coba lagi.",
            "", False,
            event_type=SSEEventType.CHUNK,
        )

    yield format_sse("", "", True, event_type=SSEEventType.DONE)
