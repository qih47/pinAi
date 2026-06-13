import logging
from typing import Dict, Any
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response
from backend.app.utils.retry_handler import (
    retry_with_backoff,
    layer0_circuit_breaker,
)

logger = logging.getLogger("CAKRA_PIPELINE")

async def execute_layer_0_gateway(
    request: Request,
    user_message: str,
    chat_mode: str,
) -> Dict[str, Any]:
    logger.info(f"[LAYER_0_GATEWAY] Gateway starting | mode={chat_mode}")

    if chat_mode == "documents":
        logger.info("[LAYER_0_GATEWAY] Explicit 'documents' mode → generating rewritten queries")
        return await _gateway_generate_queries(request, user_message, forced=True)

    if chat_mode == "flash":
        logger.info("[LAYER_0_GATEWAY] Explicit 'flash' mode → intent analysis, bypass RAG")
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
        # Layer 0 with retry + circuit breaker (25s timeout)
        async def layer0_call():
            return await generate_json_response(
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

        result = await retry_with_backoff(
            coro_func=layer0_call,
            max_retries=2,
            initial_delay=0.5,
            max_delay=5.0,
            timeout=25.0,
            operation_name="Layer 0 Gateway",
            circuit_breaker=layer0_circuit_breaker,
        )

        if not result or "target_pipeline" not in result:
            raise ValueError("Gateway response invalid")

        target = result.get("target_pipeline", "flash")
        confidence = float(result.get("confidence", 0.5))

        if confidence < 0.6:
            logger.info(f"[LAYER_0_GATEWAY] Low confidence ({confidence:.2f}) → defaulting to flash")
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
        logger.warning(f"[LAYER_0_GATEWAY] Gateway error: {e} → rule-based fallback")
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
                f"[LAYER_0_FLASH] Intent: {result.get('intent_type')} | "
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
        logger.warning(f"[LAYER_0_FLASH] Analysis error: {e} → fallback")

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
        # Layer 0 rewriter with retry (15s timeout)
        async def layer0_rewriter_call():
            return await generate_json_response(
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

        result = await retry_with_backoff(
            coro_func=layer0_rewriter_call,
            max_retries=2,
            initial_delay=0.5,
            max_delay=3.0,
            timeout=15.0,
            operation_name="Layer 0 Query Rewriter",
            circuit_breaker=layer0_circuit_breaker,
        )

        if result and "rewritten_queries" in result:
            queries = result["rewritten_queries"]
            if isinstance(queries, list) and len(queries) > 0:
                logger.info(f"[LAYER_0_REWRITER] Generated {len(queries)} rewritten queries")
                return {
                    "target_pipeline": "documents",
                    "rewritten_queries": queries[:3],
                    "confidence": float(result.get("confidence", 0.9)),
                    "is_greeting": False,
                    "is_coding": False,
                    "detected_language": "id",
                }
    except Exception as e:
        logger.warning(f"[LAYER_0_REWRITER] Query rewrite error: {e} → fallback")

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
        logger.info(f"[LAYER_0_FALLBACK] Rule-based forced flash | greeting={is_greeting} | coding={is_coding}")
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


def _gateway_flash_result() -> Dict[str, Any]:
    return {
        "target_pipeline": "flash",
        "rewritten_queries": [],
        "confidence": 0.5,
        "is_greeting": False,
        "is_coding": False,
        "detected_language": "id",
        "intent_type": "chitchat",
    }
