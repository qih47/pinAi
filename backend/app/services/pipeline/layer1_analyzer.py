import logging
from typing import Dict, Any, List, Optional
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response
from backend.app.services.memory_service import memory_service
from backend.app.utils.retry_handler import (
    retry_with_backoff,
    layer1_circuit_breaker,
)

logger = logging.getLogger("CAKRA_PIPELINE")

async def execute_layer_1_analyzer(
    request: Request,
    messages: List[Dict[str, str]],
    gateway_result: Dict[str, Any],
    employee_npp: Optional[str],
    ocr_text: Optional[str] = None,
    rag_metadata: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info("[LAYER_1_ANALYZER] Cognitive Analyzer starting (Qwen 3B)...")

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

        # Layer 1 Cognitive Analyzer with retry (30s timeout — increased for Qwen 3B)
        async def layer1_analyzer_call():
            return await generate_json_response(
                model_name=settings.MODEL_ROUTER,
                messages=analyze_messages,
                request=request,
                temperature=0.1,
                keep_alive=300,
                timeout=30.0,
            )

        qwen_result = await retry_with_backoff(
            coro_func=layer1_analyzer_call,
            max_retries=2,
            initial_delay=0.5,
            max_delay=5.0,
            timeout=30.0,
            operation_name="Layer 1 Cognitive Analyzer",
            circuit_breaker=layer1_circuit_breaker,
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
                f"[LAYER_1_ANALYZER] Result OK | intent={qwen_result.get('detected_intent')} | "
                f"need_rag={qwen_result.get('need_rag')} | is_coding={qwen_result.get('is_coding')}"
            )
            return qwen_result

        raise ValueError("Qwen 3B returned empty or invalid JSON")

    except Exception as e:
        logger.warning(f"[LAYER_1_ANALYZER] Error: {e} → rule-based fallback")
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
        logger.info("[LAYER_1_FALLBACK] Flash mode → need_rag=False (unconditional)")
    elif target_pipeline == "documents":
        need_rag = False
        logger.info("[LAYER_1_FALLBACK] Documents mode → need_rag=False (parallel RAG already executed)")
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
