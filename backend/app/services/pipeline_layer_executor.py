"""
CAKRA AI — Sequential Cognitive Pipeline
=========================================
Layer 0 : Qwen 0.8B Gateway  → Routing + rewritten_queries
Layer 1 : Qwen 3B Orkestrator → 35 parameter kognitif + blueprint taktis
RAG     : Vector Search + Reranker (otomatis di chat.py untuk jalur documents)
Layer 2 : Gemma4 12B Executor → Single-Stream Response (RAG sudah di-inject)
"""

import re
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response, stream_ollama_chat
from backend.app.services.rag_service import rag_service
from backend.app.services.memory_service import memory_service

logger = logging.getLogger("CAKRA_PIPELINE")

_RAG_CONTEXT_MAX_CHARS = 60_000


# ==============================================================================
# 🎥 LAYER 0-A: PDF EXTRACTOR (pymupdf primary, vision fallback)
# ==============================================================================


async def extract_pdf_text(file_paths: List[str]) -> Dict[str, Any]:
    import fitz  # pymupdf

    all_text = []
    page_count = 0

    for path in file_paths:
        try:
            doc = fitz.open(path)
            page_count += len(doc)
            for page in doc:
                text = page.get_text().strip()
                if text:
                    all_text.append(text)
            doc.close()
        except Exception as e:
            logger.warning(f"⚠️ [PDF] pymupdf gagal untuk {path}: {e} → skip")

    extracted = "\n\n".join(all_text).strip()

    if not extracted:
        logger.info("📸 [PDF] Teks kosong → fallback ke MiniCPM-V OCR...")
        try:
            from backend.app.services.vision_service import extract_text_from_files
            result = await extract_text_from_files(file_paths)
            extracted = result.get("extracted_text", "")
            page_count = result.get("page_count", page_count)
        except Exception as e:
            logger.error(f"❌ [PDF] Vision fallback gagal: {e}")

    logger.info(
        f"✅ [PDF] Ekstraksi selesai | {page_count} halaman | {len(extracted)} chars"
    )
    return {"status": "success", "extracted_text": extracted, "page_count": page_count}


# ==============================================================================
# 🚦 LAYER 0-B: GATEWAY (Qwen 0.8B — Router Ringan)
# ==============================================================================


async def execute_layer_0_gateway(
    request: Request,
    user_message: str,
    chat_mode: str,
) -> Dict[str, Any]:
    logger.info(f"🚦 [LAYER 0] Gateway starting | mode={chat_mode}")

    if chat_mode == "documents":
        logger.info("📄 [LAYER 0] Mode documents eksplisit → generate rewritten_queries")
        return await _gateway_generate_queries(request, user_message, forced=True)

    if chat_mode == "flash":
        logger.info("⚡ [LAYER 0] Mode flash eksplisit → analisis intent + bypass RAG")
        return await _gateway_flash_with_analysis(request, user_message)

    # ── Mode auto ────────────────────────────────────────────────────────────
    system_prompt = (
        "Kamu adalah Traffic Cop AI. Klasifikasikan apakah pertanyaan user berkaitan "
        "dengan regulasi/kebijakan internal PT Pindad.\n\n"
        "Output HANYA JSON:\n"
        "{\n"
        '  "target_pipeline": "documents" atau "flash",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "is_greeting": true/false,\n'
        '  "is_coding": true/false,\n'
        '  "detected_language": "id" atau "en" atau "mixed"\n'
        "}\n\n"
        "ATURAN:\n"
        "- 'documents' HANYA jika jelas tanya regulasi/SKEP/SK/kebijakan/SOP/seragam/cuti/gaji/tunjangan/kepegawaian Pindad.\n"
        "- 'flash' untuk lainnya: chitchat, coding, pertanyaan umum, sapaan.\n"
        "- Jika ragu (confidence < 0.6) → pilih 'flash'.\n"
        "DILARANG output selain JSON."
    )

    try:
        result = await generate_json_response(
            model_name=settings.MODEL_GATEWAY,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            request=request,
            temperature=0.05,
            keep_alive=300,
            timeout=25.0,
        )

        if not result or "target_pipeline" not in result:
            raise ValueError("Gateway response invalid")

        target = result.get("target_pipeline", "flash")
        confidence = float(result.get("confidence", 0.5))

        if confidence < 0.6:
            logger.info(f"🔀 [LAYER 0] Confidence rendah ({confidence:.2f}) → default flash")
            return await _gateway_flash_with_analysis(request, user_message)

        if target == "documents":
            queries_result = await _gateway_generate_queries(request, user_message, forced=False)
            queries_result["is_greeting"] = result.get("is_greeting", False)
            queries_result["is_coding"] = False
            queries_result["detected_language"] = result.get("detected_language", "id")
            queries_result["confidence"] = confidence
            return queries_result
        else:
            return await _gateway_flash_with_analysis(request, user_message)

    except Exception as e:
        logger.warning(f"⚠️ [LAYER 0] Gateway error: {e} → rule-based fallback")
        return _gateway_rule_based_fallback(user_message, forced_flash=True)


async def _gateway_flash_with_analysis(request: Request, user_message: str) -> Dict[str, Any]:
    system_prompt = (
        "Kamu adalah Intent Analyzer untuk Flash Pipeline. Analisis pesan user.\n\n"
        "Output HANYA JSON:\n"
        "{\n"
        '  "target_pipeline": "flash",\n'
        '  "is_greeting": true/false,\n'
        '  "is_coding": true/false,\n'
        '  "detected_language": "id" atau "en" atau "mixed",\n'
        '  "intent_type": "greeting" | "chitchat" | "question" | "coding",\n'
        '  "confidence": 0.9\n'
        "}\n\n"
        "ATURAN:\n"
        "- is_greeting=true jika: hai, halo, hello, hi, apa kabar, selamat pagi/siang/malam, assalamualaikum\n"
        "- is_coding=true jika ada: import, def, function, class, code, programming\n"
        "DILARANG output selain JSON."
    )

    try:
        result = await generate_json_response(
            model_name=settings.MODEL_GATEWAY,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            request=request,
            temperature=0.05,
            keep_alive=300,
            timeout=15.0,
        )

        if result:
            logger.info(
                f"✅ [LAYER 0 FLASH] Intent: {result.get('intent_type')} | "
                f"greeting={result.get('is_greeting')} | coding={result.get('is_coding')}"
            )
            return {
                "target_pipeline": "flash",
                "rewritten_queries": [],
                "confidence": float(result.get("confidence", 0.9)),
                "is_greeting": result.get("is_greeting", False),
                "is_coding": result.get("is_coding", False),
                "detected_language": result.get("detected_language", "id"),
                "intent_type": result.get("intent_type", "chitchat"),
            }
    except Exception as e:
        logger.warning(f"⚠️ [LAYER 0 FLASH] Analysis error: {e} → fallback")

    return _gateway_rule_based_fallback(user_message, forced_flash=True)


async def _gateway_generate_queries(
    request: Request, user_message: str, forced: bool = False
) -> Dict[str, Any]:
    system_prompt = (
        "Kamu adalah Query Rewriter untuk RAG dokumen regulasi PT Pindad. "
        "Ubah pertanyaan user menjadi 3 variasi kueri formal dan spesifik.\n\n"
        "Output HANYA JSON:\n"
        "{\n"
        '  "target_pipeline": "documents",\n'
        '  "rewritten_queries": ["kueri 1", "kueri 2", "kueri 3"],\n'
        '  "confidence": 0.9\n'
        "}\n"
        "DILARANG output selain JSON."
    )

    try:
        result = await generate_json_response(
            model_name=settings.MODEL_GATEWAY,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            request=request,
            temperature=0.1,
            keep_alive=300,
            timeout=15.0,
        )

        if result and "rewritten_queries" in result:
            queries = result["rewritten_queries"]
            if isinstance(queries, list) and len(queries) > 0:
                logger.info(f"✅ [LAYER 0] Generated {len(queries)} rewritten queries")
                return {
                    "target_pipeline": "documents",
                    "rewritten_queries": queries[:3],
                    "confidence": float(result.get("confidence", 0.9)),
                    "is_greeting": False,
                    "is_coding": False,
                    "detected_language": "id",
                }
    except Exception as e:
        logger.warning(f"⚠️ [LAYER 0] Query rewrite error: {e} → fallback")

    return {
        "target_pipeline": "documents",
        "rewritten_queries": [user_message],
        "confidence": 0.8 if forced else 0.6,
        "is_greeting": False,
        "is_coding": False,
        "detected_language": "id",
    }


def _gateway_rule_based_fallback(
    user_message: str, forced_flash: bool = False
) -> Dict[str, Any]:
    msg_lower = user_message.lower()

    greeting_keywords = [
        "hai", "halo", "hello", "hi ", "apa kabar", "selamat pagi",
        "selamat siang", "selamat sore", "selamat malam", "assalamualaikum",
    ]
    is_greeting = any(gk in msg_lower for gk in greeting_keywords)

    coding_keywords = [
        "import ", "export ", "const ", "async ", "function", "def ",
        "class ", "select ", "react", "python", "javascript", "coding",
    ]
    is_coding = any(kw in msg_lower for kw in coding_keywords)

    if forced_flash:
        logger.info(f"🔧 [RULE-BASED] Forced flash | greeting={is_greeting} | coding={is_coding}")
        return {
            "target_pipeline": "flash",
            "rewritten_queries": [],
            "confidence": 0.8,
            "is_greeting": is_greeting,
            "is_coding": is_coding,
            "detected_language": "id",
            "intent_type": "greeting" if is_greeting else ("coding" if is_coding else "chitchat"),
        }

    doc_keywords = [
        "ketentuan", "peraturan", "skep", "sk direksi", "surat edaran",
        "regulasi", "kebijakan", "prosedur", "sop", "instruksi kerja",
        "seragam", "cuti", "gaji", "tunjangan", "rekrutmen", "pegawai",
        "pindad", "direksi", "perusahaan", "aturan", "pasal", "syarat",
    ]
    is_docs = any(kw in msg_lower for kw in doc_keywords)
    if is_coding:
        is_docs = False

    return {
        "target_pipeline": "documents" if is_docs else "flash",
        "rewritten_queries": [user_message] if is_docs else [],
        "confidence": 0.7,
        "is_greeting": is_greeting,
        "is_coding": is_coding,
        "detected_language": "id",
        "intent_type": "greeting" if is_greeting else ("coding" if is_coding else "chitchat"),
    }


# ==============================================================================
# 🧠 LAYER 1: COGNITIVE ANALYZER (Qwen 3B)
# ==============================================================================


async def execute_layer_1_analyzer(
    request: Request,
    messages: List[Dict[str, str]],
    gateway_result: Dict[str, Any],
    employee_npp: Optional[str],
    ocr_text: Optional[str] = None,
    rag_metadata: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info("🧠 [LAYER 1] Cognitive Analyzer starting (Qwen 3B)...")

    user_message = messages[-1]["content"] if messages else ""
    target_pipeline = gateway_result.get("target_pipeline", "flash")
    is_coding_from_gateway = gateway_result.get("is_coding", False)

    context_history_str = ""
    if len(messages) > 1:
        context_history_str = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in messages[-5:-1]]
        )

    try:
        memory_context = ""
        if employee_npp and employee_npp != "GUEST":
            mem = await memory_service.get_employee_long_term_memory(employee_npp)
            memory_context = f"\n[EMPLOYEE MEMORY]\n{mem}" if mem else ""

        ocr_context = f"\n[OCR TEXT]\n{ocr_text[:500]}\n" if ocr_text else ""
        rag_meta_context = ""
        if rag_metadata and target_pipeline == "documents":
            rag_meta_context = f"\n[METADATA DOKUMEN RELEVAN]\n{rag_metadata}\n"

        gateway_context = (
            f"\n[HASIL LAYER 0 GATEWAY]\n"
            f"- target_pipeline: {target_pipeline}\n"
            f"- is_coding: {is_coding_from_gateway}\n"
            f"- is_greeting: {gateway_result.get('is_greeting', False)}\n"
        )

        system_prompt = (
            "Kamu adalah Orkestrator Kognitif CAKRA AI. Analisis kueri user dan output JSON 35 parameter + blueprint.\n\n"
            "Layer 0 sudah menentukan routing. Kamu TIDAK perlu mendeteksi ulang target_pipeline/is_coding.\n"
            "Fokus pada: persona, emosi, blueprint aksi.\n\n"
            "DILARANG output selain JSON murni.\n\n"
            "STRUKTUR JSON WAJIB:\n"
            "{\n"
            '  "emotion": "frustrasi|confused|stressed|neutral|positive|anxious",\n'
            '  "emotion_confidence": 0.5,\n'
            '  "empathy_phrase": "kalimat empati atau null",\n'
            '  "need_rag": true/false,\n'
            '  "rag_query": "kueri atau null",\n'
            '  "need_analytics": false,\n'
            '  "is_user_correction": false,\n'
            '  "previous_response_was_wrong": false,\n'
            '  "what_went_wrong": null,\n'
            '  "urgency_level": "rendah|sedang|tinggi|kritis",\n'
            '  "context_summary": "ringkasan pendek",\n'
            '  "detected_intent": "CHITCHAT|RAG|ANALYTICS|NORMAL|SELF_CORRECTION",\n'
            '  "extracted_entities": [],\n'
            '  "requires_follow_up": false,\n'
            '  "security_clearance_required": "low",\n'
            '  "corporate_scope": "internal_regulation|general_knowledge|personal_activity|technical_troubleshooting",\n'
            '  "is_policy_query": true/false,\n'
            '  "technical_depth_required": "surface|conceptual|code_implementation|root_cause_analysis",\n'
            '  "is_multi_turn_dependent": true/false,\n'
            '  "data_extraction_needed": false,\n'
            '  "user_persona_style": "casual_informal|formal_bureaucratic",\n'
            '  "cultural_nuance": "pindad_internal|general_indonesian",\n'
            '  "assumed_knowledge_level": "intermediate",\n'
            '  "interaction_goal": "seeking_information|solving_problem|greeting_casual",\n'
            '  "pindad_division_affinity": "senjata|amunisi|kendaraan_khusus|produk_industrial|korporat_umum|unknown",\n'
            '  "regulation_hierarchy_target": null,\n'
            '  "estimated_vram_urgency": "low_bypass_safe|heavy_reasoning_required",\n'
            '  "rag_retrieval_strategy": "exact_match_keyword|semantic_broad_search|none",\n'
            '  "user_authority_level": "pegawai_pelaksana",\n'
            '  "ambiguity_index": "clear_explicit|semi_ambiguous",\n'
            '  "user_pronoun_preference": "informal_gue_lo|familiar_aku_kamu|formal_saya_anda|unknown",\n'
            '  "slang_interjection_marker": [],\n'
            '  "profanity_frustration_trigger": "none|low_misuh",\n'
            '  "linguistic_mirroring_strategy": "mirror_casual|stay_formal_safe",\n'
            '  "is_coding": true/false,\n'
            '  "action_plan": ["Langkah 1", "Langkah 2"],\n'
            '  "response_structure": {"open_with": "string", "middle": "string", "close_with": "string"},\n'
            '  "key_points_to_cover": [],\n'
            '  "tone": "suportif|profesional|empathetic|humble|encouraging|neutral|casual",\n'
            '  "estimated_response_length": "brief|medium|detailed",\n'
            '  "should_ask_followup": true/false\n'
            "}\n\n"
            "ATURAN:\n"
            "1. target_pipeline='documents' → need_rag WAJIB false (data sudah diambil pipeline).\n"
            "2. is_coding=true → need_rag WAJIB false.\n"
            "3. is_coding dan need_rag DILARANG true bersamaan.\n"
            "4. action_plan dan response_structure = blueprint taktis untuk Gemma4."
        )

        analyze_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"=== KONTEKS OBROLAN SEBELUMNYA ===\n{context_history_str}\n\n"
                    f"{gateway_context}"
                    f"{rag_meta_context}"
                    f"{ocr_context}"
                    f"{memory_context}\n\n"
                    f"=== KUERI USER SAAT INI ===\n{user_message}"
                ),
            },
        ]

        qwen_result = await generate_json_response(
            model_name=settings.MODEL_ROUTER,
            messages=analyze_messages,
            request=request,
            temperature=0.1,
            keep_alive=300,
            timeout=15.0,
        )

        if qwen_result and isinstance(qwen_result, dict) and "detected_intent" in qwen_result:
            if target_pipeline == "documents":
                qwen_result["need_rag"] = False
                qwen_result["is_coding"] = False

            if is_coding_from_gateway:
                qwen_result["is_coding"] = True
                qwen_result["need_rag"] = False
                if qwen_result.get("detected_intent") == "RAG":
                    qwen_result["detected_intent"] = "NORMAL"

            if qwen_result.get("is_coding") is True:
                qwen_result["need_rag"] = False

            qwen_result["_gateway"] = gateway_result

            fallback = _get_fallback_cognitive_params(user_message, context_history_str)
            for key in fallback:
                if key not in qwen_result:
                    qwen_result[key] = fallback[key]

            logger.info(
                f"✅ [LAYER 1] OK | Intent: {qwen_result.get('detected_intent')} | "
                f"RAG: {qwen_result.get('need_rag')} | Coding: {qwen_result.get('is_coding')}"
            )
            return qwen_result

        raise ValueError("Qwen 3B returned empty or invalid JSON")

    except Exception as e:
        logger.warning(f"⚠️ [LAYER 1] Error: {e} → rule-based fallback")
        return _get_fallback_cognitive_params_rule_based(
            user_message,
            context_history_str,
            ocr_text,
            target_pipeline=target_pipeline,
            is_coding_from_gateway=is_coding_from_gateway,
            is_greeting_from_gateway=gateway_result.get("is_greeting", False),
        )


def _get_fallback_cognitive_params_rule_based(
    user_message: str = "",
    previous_context: str = "",
    ocr_text: Optional[str] = None,
    target_pipeline: str = "flash",
    is_coding_from_gateway: bool = False,
    is_greeting_from_gateway: bool = False,
) -> Dict[str, Any]:
    msg_lower = user_message.lower()
    full_context_lower = (previous_context + " " + user_message).lower()

    is_coding = is_coding_from_gateway
    if not is_coding:
        coding_tokens = [
            "import ", "export ", "const ", "async ", "await ", "function",
            "def ", "return ", "react", "python", "javascript", "coding",
        ]
        is_coding = any(t in full_context_lower for t in coding_tokens)

    need_rag = False
    if target_pipeline == "flash":
        need_rag = False
        logger.info("🔧 [RULE-BASED] Flash → need_rag=FALSE (unconditional)")
    elif target_pipeline == "documents":
        need_rag = False
        logger.info("🔧 [RULE-BASED] Documents → need_rag=FALSE (sudah di-RAG paralel)")
    else:
        if not is_coding:
            rag_keywords = [
                "ketentuan", "peraturan", "skep", "regulasi", "kebijakan",
                "prosedur", "sop", "seragam", "cuti", "gaji", "tunjangan",
                "pegawai", "pindad", "direksi", "aturan", "pasal",
            ]
            need_rag = any(kw in full_context_lower for kw in rag_keywords)

    if is_coding:
        need_rag = False

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
    is_chitchat = is_greeting_from_gateway or (word_count <= 6 and not need_rag and not is_coding)

    return _get_fallback_cognitive_params(
        user_message=user_message,
        previous_context=previous_context,
        need_rag_override=need_rag,
        is_coding_override=is_coding,
        is_chitchat_override=is_chitchat,
        pronoun_override=pronoun,
        mirroring_override=mirroring,
        slang_override=slang,
        profanity_override=profanity,
        is_greeting_override=is_greeting_from_gateway,
    )


def _get_fallback_cognitive_params(
    user_message: str = "",
    previous_context: str = "",
    need_rag_override: bool = False,
    is_coding_override: bool = False,
    is_chitchat_override: bool = False,
    pronoun_override: str = "unknown",
    mirroring_override: str = "stay_formal_safe",
    slang_override: Optional[List[str]] = None,
    profanity_override: str = "none",
    is_greeting_override: bool = False,
) -> Dict[str, Any]:
    is_chitchat = is_chitchat_override
    need_rag = need_rag_override
    is_coding = is_coding_override

    default_action = ["Pahami konteks kueri user.", "Berikan respons natural dan informatif."]
    if is_coding:
        default_action = [
            "Identifikasi framework/library yang dimaksud.",
            "Sediakan penjelasan konseptual logis.",
            "Beri contoh snippet kode praktis.",
        ]
    elif need_rag:
        default_action = [
            "Rujuk dokumen regulasi internal perusahaan.",
            "Sebutkan nomor SKEP/SK dan ketentuan yang berlaku.",
        ]
    elif is_greeting_override:
        default_action = [
            "Balas sapaan dengan hangat dan akrab.",
            "Tawarkan bantuan jika user butuh sesuatu.",
        ]

    if is_greeting_override or is_chitchat:
        detected_intent = "CHITCHAT"
    elif need_rag:
        detected_intent = "RAG"
    else:
        detected_intent = "NORMAL"

    return {
        "emotion": "neutral",
        "emotion_confidence": 0.5,
        "empathy_phrase": None,
        "profanity_frustration_trigger": profanity_override,
        "linguistic_mirroring_strategy": mirroring_override,
        "need_rag": need_rag,
        "rag_query": user_message.strip()[:200] if user_message else "",
        "need_analytics": False,
        "detected_intent": detected_intent,
        "is_user_correction": False,
        "previous_response_was_wrong": False,
        "what_went_wrong": None,
        "urgency_level": "rendah",
        "context_summary": user_message[:100] if user_message else "",
        "extracted_entities": [],
        "requires_follow_up": False,
        "security_clearance_required": "low",
        "corporate_scope": (
            "internal_regulation" if need_rag
            else ("technical_troubleshooting" if is_coding else "general_knowledge")
        ),
        "is_policy_query": need_rag,
        "technical_depth_required": "code_implementation" if is_coding else "surface",
        "is_multi_turn_dependent": bool(previous_context),
        "data_extraction_needed": False,
        "is_coding": is_coding,
        "user_persona_style": "casual_informal",
        "cultural_nuance": "pindad_internal" if need_rag else "general_indonesian",
        "assumed_knowledge_level": "intermediate",
        "interaction_goal": (
            "greeting_casual" if (is_chitchat or is_greeting_override)
            else "seeking_information"
        ),
        "pindad_division_affinity": "korporat_umum",
        "regulation_hierarchy_target": None,
        "estimated_vram_urgency": (
            "low_bypass_safe" if (is_chitchat or is_greeting_override)
            else "heavy_reasoning_required"
        ),
        "rag_retrieval_strategy": "semantic_broad_search" if need_rag else "none",
        "user_authority_level": "pegawai_pelaksana",
        "ambiguity_index": "clear_explicit",
        "user_pronoun_preference": pronoun_override,
        "slang_interjection_marker": slang_override if slang_override is not None else [],
        "action_plan": default_action,
        "response_structure": {
            "open_with": "direct_answer",
            "middle": "narrative",
            "close_with": "offer_help",
        },
        "key_points_to_cover": [],
        "tone": "casual" if (is_coding or is_greeting_override) else "profesional",
        "estimated_response_length": "brief" if is_greeting_override else "medium",
        "should_ask_followup": False,
    }


# ==============================================================================
# ✍️ LAYER 2: GEMMA4 SINGLE-STREAM EXECUTOR
# ==============================================================================
# 🔥 REFACTOR: 
# - Tidak ada [PANGGIL_RAG:] trigger (RAG sudah di-handle di chat.py)
# - <think> TIDAK dikirim ke FE, hanya untuk log terminal analisa
# - Gemma terima data → langsung response
# - System prompt di-tune untuk reasoning cerdas & disiplin blueprint


def _build_gemma_system_prompt(cognitive_params: Dict[str, Any]) -> str:
    """
    System prompt Gemma4 yang di-tune untuk:
    - Reasoning cerdas dengan chain-of-thought terstruktur
    - Disiplin mengikuti blueprint dari Layer 1
    - Anti-hallucination
    - Context-aware (5 turn history)
    - Natural response dengan socio-adaptation
    """
    pronoun = cognitive_params.get("user_pronoun_preference", "unknown")
    slang_list = cognitive_params.get("slang_interjection_marker", [])
    profanity = cognitive_params.get("profanity_frustration_trigger", "none")
    mirror_strat = cognitive_params.get("linguistic_mirroring_strategy", "stay_formal_safe")
    emotion = cognitive_params.get("emotion", "neutral")
    urgency = cognitive_params.get("urgency_level", "rendah")
    is_coding = cognitive_params.get("is_coding", False)
    need_rag = cognitive_params.get("need_rag", False)
    chat_mode = cognitive_params.get("chat_mode", "auto")
    empathy = cognitive_params.get("empathy_phrase")
    depth = cognitive_params.get("technical_depth_required", "surface")
    is_user_corr = cognitive_params.get("is_user_correction", False)
    action_plan = cognitive_params.get("action_plan", [])
    tone = cognitive_params.get("tone", "profesional")
    response_length = cognitive_params.get("estimated_response_length", "medium")
    should_followup = cognitive_params.get("should_ask_followup", False)
    response_structure = cognitive_params.get("response_structure", {})
    key_points = cognitive_params.get("key_points_to_cover", [])
    ambiguity = cognitive_params.get("ambiguity_index", "clear_explicit")
    is_multi_turn = cognitive_params.get("is_multi_turn_dependent", False)
    context_summary = cognitive_params.get("context_summary", "")
    interaction_goal = cognitive_params.get("interaction_goal", "seeking_information")
    corporate_scope = cognitive_params.get("corporate_scope", "general_knowledge")

    gateway_info = cognitive_params.get("_gateway", {})
    target_pipeline = gateway_info.get("target_pipeline", "flash")
    is_greeting = gateway_info.get("is_greeting", False)
    intent_type = gateway_info.get("intent_type", "chitchat")
    confidence = gateway_info.get("confidence", 0.9)

    employee_name = cognitive_params.get("employee_name", "Pegawai")

    # ═════════════════════════════════════════════════════════════════════════
    # IDENTITAS & BATASAN
    # ═════════════════════════════════════════════════════════════════════════
    prompt = (
        "╔═══════════════════════════════════════════════════════════════╗\n"
        "║  CAKRA AI — ASISTEN INTELIGENSIA TERPADU PT PINDAD (PERSERO) ║\n"
        "╚═══════════════════════════════════════════════════════════════╝\n\n"
        f"Kamu adalah CAKRA AI. Pegawai yang kamu layani: {employee_name}.\n"
        "JANGAN pernah menyebut dirimu Gemma, Google, atau model AI lain.\n\n"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # KONTEKS PIPELINE — DATA DARI LAYER SEBELUMNYA
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 [KONTEKS PIPELINE — DITERIMA DARI LAYER 0 & LAYER 1]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Pipeline Aktif      : {target_pipeline} (confidence: {confidence:.2f})\n"
        f"• Intent Type         : {intent_type}\n"
        f"• Interaction Goal    : {interaction_goal}\n"
        f"• Corporate Scope     : {corporate_scope}\n"
        f"• Is Greeting         : {is_greeting}\n"
        f"• Is Coding           : {is_coding}\n"
        f"• Need RAG            : {need_rag}\n"
        f"• Is Multi-turn       : {is_multi_turn}\n"
        f"• Ambiguity Index     : {ambiguity}\n"
        f"• Context Summary     : {context_summary[:100]}\n"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # PROFIL PSIKOLOGIS USER
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 [PROFIL PSIKOLOGIS USER]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Emosi Terdeteksi    : {emotion} (confidence: {cognitive_params.get('emotion_confidence', 0.5):.2f})\n"
        f"• Urgency Level       : {urgency}\n"
        f"• Pronoun Preference  : {pronoun}\n"
        f"• Mirroring Strategy  : {mirror_strat}\n"
        f"• Slang Markers       : {slang_list if slang_list else 'tidak ada'}\n"
        f"• Profanity Trigger   : {profanity}\n"
        f"• User Correction     : {is_user_corr}\n"
    )

    if empathy:
        prompt += f"• Empathy Phrase      : \"{empathy}\"\n"

    # ═════════════════════════════════════════════════════════════════════════
    # BLUEPRINT TAKTIS — WAJIB DIEKSEKUSI
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 [BLUEPRINT TAKTIS — WAJIB DIEKSEKUSI DISIPLIN]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if action_plan:
        prompt += "🎯 Action Plan (langkah-langkah):\n"
        for i, step in enumerate(action_plan, 1):
            prompt += f"   {i}. {step}\n"
        prompt += "\n"

    if response_structure:
        prompt += "🏗️ Response Structure:\n"
        prompt += f"   • Pembuka : {response_structure.get('open_with', 'direct_answer')}\n"
        prompt += f"   • Isi     : {response_structure.get('middle', 'narrative')}\n"
        prompt += f"   • Penutup : {response_structure.get('close_with', 'offer_help')}\n"
        prompt += "\n"

    prompt += (
        f"📏 Response Length    : {response_length}\n"
        f"🎨 Tone               : {tone}\n"
        f"💬 Ask Follow-up      : {should_followup}\n"
    )

    if key_points:
        prompt += "\n🎯 Key Points yang HARUS dicakup:\n"
        for kp in key_points:
            prompt += f"   • {kp}\n"

    # ═════════════════════════════════════════════════════════════════════════
    # INSTRUKSI REASONING — CHAIN-OF-THOUGHT TERSTRUKTUR
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 [INSTRUKSI REASONING — CHAIN-OF-THOUGHT TERSTRUKTUR]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Sebelum menjawab, WAJIB lakukan analisis dalam tag <think>...</think>:\n\n"
        "LANGKAH 1 — ANALISIS KONTEKS:\n"
        "   • Pahami pertanyaan user dalam konteks chat history (5 turn terakhir).\n"
        "   • Identifikasi pertanyaan ambigu/tindak lanjut yang merujuk ke konteks sebelumnya.\n"
        "   • Tentukan apa yang SEBENARNYA user butuhkan.\n\n"
        "LANGKAH 2 — EVALUASI DATA:\n"
        "   • Data apa yang tersedia untuk menjawab?\n"
        "   • Jika ada dokumen regulasi di bawah, identifikasi pasal/SKEP yang relevan.\n"
        "   • Apakah data cukup untuk menjawab? Jika tidak, akui keterbatasan.\n\n"
        "LANGKAH 3 — RENCANA JAWABAN:\n"
        "   • Struktur jawaban berdasarkan blueprint di atas.\n"
        "   • Poin-poin kunci yang harus dicakup.\n"
        "   • Tone dan gaya bahasa yang tepat.\n\n"
        "LANGKAH 4 — QUALITY CHECK:\n"
        "   • Apakah jawaban sudah lengkap, akurat, dan sesuai blueprint?\n"
        "   • Apakah ada hallucination atau asumsi tidak berdasar?\n"
        "   • Apakah sudah mirror gaya bahasa user?\n\n"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # GAYA BAHASA & SOCIO-ADAPTATION
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎨 [GAYA BAHASA & SOCIO-ADAPTATION]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Sapa user dengan nama: {employee_name}\n"
        "• Gunakan emoji ekspresif secara natural (jangan berlebihan).\n"
    )

    if slang_list and any(s in slang_list for s in ["bolo", "cuy"]):
        prompt += "• User pakai slang lokal. Balas kasual, sertakan 'bolo'/'cuy' natural.\n"
    elif pronoun == "informal_gue_lo" or mirror_strat == "mirror_casual":
        prompt += "• Gaya santai, mengalir, bersahabat, penuh emoji.\n"
    elif pronoun == "formal_saya_anda":
        prompt += "• Gaya formal birokratis. Pakai 'Saya' dan 'Anda/Bapak/Ibu'.\n"
    else:
        prompt += "• Gaya profesional hangat, informatif, dengan emoji.\n"

    if profanity == "low_misuh":
        prompt += "• 🔴 REDAM EMOSI: User frustrasi. Awali dengan empati dan nada menenangkan.\n"
    if is_user_corr:
        prompt += "• 🔴 User melakukan koreksi. Akui dengan humble dan ikuti instruksi barunya.\n"
    if ambiguity in ["semi_ambiguous", "highly_vague"]:
        prompt += "• Pertanyaan ambigu. Akhiri dengan klarifikasi sopan.\n"

    prompt += "\n"

    # ═════════════════════════════════════════════════════════════════════════
    # ATURAN KETAT — GUARDRAILS
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 [ATURAN KETAT — GUARDRAILS]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. DILARANG hallucination — JANGAN mengarang fakta/data.\n"
        "2. DILARANG menulis [PANGGIL_RAG:] atau tag sistem apapun.\n"
        "3. DILARANG output JSON, metadata, atau instruksi internal.\n"
        "4. Semua data yang dibutuhkan SUDAH tersedia di prompt ini.\n"
        "5. WAJIB ikuti blueprint aksi dari Layer 1 secara disiplin.\n"
        "6. WAJIB sebutkan nomor SK/SKEP/pasal jika ada dokumen regulasi.\n"
        "7. WAJIB mirror gaya bahasa user (formal/kasual/slang).\n"
        "8. Jika info tidak ada di dokumen, katakan 'Informasi tidak tersedia di dokumen internal Pindad.'\n"
        "9. Jawab dalam bahasa Indonesia yang natural.\n"
        "10. JANGAN mengulang isi <think> di jawaban final.\n"
    )

    return prompt


def _build_gemma_context_prompt(
    system_prompt: str,
    cognitive_params: Dict[str, Any],
    rag_context: Optional[str],
    rag_sources: Optional[List[Dict]],
) -> str:
    """
    Inject RAG context (jika ada) ke system prompt Gemma.
    Ini adalah satu-satunya cara Gemma mendapat data dokumen.
    """
    prompt = system_prompt

    employee_name = cognitive_params.get("employee_name", "Pegawai")
    gateway_info = cognitive_params.get("_gateway", {})
    target_pipeline = gateway_info.get("target_pipeline", "flash")

    # Rekalibrasi akhir
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 [RE-KALIBRASI AKHIR SEBELUM MENJAWAB]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Sapa sebagai         : {employee_name}\n"
        f"• Pipeline             : {target_pipeline}\n"
        f"• Emoji                : wajib ekspresif\n"
        f"• Follow blueprint     : WAJIB disiplin\n"
    )

    if rag_context:
        trimmed = rag_context[:_RAG_CONTEXT_MAX_CHARS]
        if len(rag_context) > _RAG_CONTEXT_MAX_CHARS:
            trimmed += "\n\n[... dokumen dipotong untuk efisiensi ...]"
            logger.warning(
                f"⚠️ [GEMMA] RAG trimmed: {len(rag_context)} → {_RAG_CONTEXT_MAX_CHARS} chars"
            )

        prompt += (
            "\n" + "=" * 70 + "\n"
            "📚 [DOKUMEN REGULASI RESMI PINDAD — SUDAH DI-RETRIEVE OLEH SISTEM]\n"
            + "=" * 70 + "\n"
            f"{trimmed}\n"
            + "=" * 70 + "\n"
            "INSTRUKSI UNTUK DOKUMEN DI ATAS:\n"
            "1. Gunakan HANYA informasi dari dokumen tersebut.\n"
            "2. WAJIB sebutkan nomor SK/SKEP/Regulasi dan pasal yang relevan.\n"
            "3. JANGAN mengarang di luar teks resmi.\n"
            "4. Jika info tidak ada di dokumen, katakan 'Informasi tidak tersedia di dokumen internal Pindad.'\n"
            + "=" * 70 + "\n"
        )

    prompt += (
        "\n🔒 FINAL INSTRUCTION:\n"
        "1. Tulis <think>...analisis chain-of-thought...</think> dulu.\n"
        "2. Setelah </think>, langsung tulis jawaban final.\n"
        "3. Jawaban harus natural, hangat, penuh emoji, sesuai blueprint.\n"
        "4. DILARANG output tag sistem, JSON, atau metadata.\n"
    )

    return prompt


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
    logger.info("✍️ [LAYER 2] Gemma Single-Stream Executor starting...")

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
        logger.info(f"📜 [LAYER 2] Context trimmed to {len(messages)} turns")

    # ── Kirim sources ke FE jika ada (dari RAG paralel) ─────────────────────
    if preloaded_rag_sources:
        logger.info(f"📚 [LAYER 2] Sending {len(preloaded_rag_sources)} sources to FE")
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
        # Jalur pemrograman wajib longgar biar snippet kode panjang gak kepotong asu!
        num_ctx = 16384  # Kita gebret ke 16k biar Gemma leluasa baca error log & struktur script
        logger.info("💻 [HARDWARE DIET] Mode Coding Aktif -> Alokasi Matrix num_ctx diperluas ke 16K.")
        
    elif detected_intent == "chitchat":
        # Jalur sapaan kasual / chitchat biasa, baru boleh didiet ketat biar kilat
        num_ctx = 2048  
        
    else:
        # Jalur regulasi dokumen RAG korporat
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
        f"📤 [LAYER 2] Single-stream | pipeline={target_pipeline} | "
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
                
                # 🔥 LOG KE TERMINAL SAJA — JANGAN YIELD KE FE
                if think_buffer.strip():
                    logger.info(
                        f"🧠 [THINK ANALYSIS] Extracted {len(think_buffer)} chars for terminal log:\n"
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
                    logger.warning(f"🧠 [LEAK FILTERED] {chunk_text[:80]}")
                    clean = chunk_text
                    for p in leak_patterns:
                        clean = clean.replace(p, "")
                    clean = re.sub(r'\[PANGG[A-Z]*_RAG:[^\]]*\]', '', clean)
                    if clean.strip():
                        yield _format_sse(clean, "", False)
                else:
                    yield _format_sse(chunk_text, "", False)

    except Exception as e:
        logger.error(f"❌ [LAYER 2] Stream error: {e}")
        yield _format_sse("Maaf, terjadi kendala teknis. Silakan coba lagi.", "", False)

    # ── Final log jika thinking tidak pernah di-log (edge case) ──────────────
    if think_buffer.strip() and not think_logged:
        logger.info(
            f"🧠 [THINK ANALYSIS - FINAL] {len(think_buffer)} chars:\n"
            f"{'─' * 60}\n{think_buffer.strip()}\n{'─' * 60}"
        )

    yield _format_sse("", "", True)


def _format_sse(
    chunk: str, thinking: str = "", done: bool = False, sources: list = None
) -> str:
    """
    Format SSE response.
    
    🔥 NOTE: Field 'thinking' sekarang TIDAK digunakan untuk kirim  ke FE.
    Hanya 'chunk', 'done', dan 'sources' yang aktif.
    Field 'thinking' dipertahankan untuk backward compatibility.
    """
    payload = {"chunk": chunk, "thinking": thinking, "done": done}
    if sources is not None:
        payload["sources"] = sources
    return json.dumps(payload, ensure_ascii=False) + "\n"
