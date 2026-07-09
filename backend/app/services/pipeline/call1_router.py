"""
Call 1 Router — Intent Classifier & Query Generator
====================================================

Deterministic JSON routing dengan 12 parameter kontrol.
Karakteristik: temp=0.0, num_predict=200, num_ctx=4096, is_thinking=False

Model: gemma4:12B
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response

logger = logging.getLogger("CAKRA_ROUTER")


# ═══════════════════════════════════════════════════════════════════════════════
# SMART SIGNAL STRIPPING
# ═══════════════════════════════════════════════════════════════════════════════


def extract_routing_signals_for_call1(user_content: str) -> str:
    """
    Memotong lemak token (kodingan/log panjang) dari teks user untuk
    menjaga context window Call 1, tanpa menghilangkan instruksi manusia.
    """
    lines = user_content.split("\n")
    filtered_lines = []

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        # 1. Pertahankan baris pendek (< 120 char)
        if len(cleaned_line) < 120:
            filtered_lines.append(line)
            continue

        # 2. Periksa densitas simbol pemrograman / log error
        symbol_density = len(re.findall(r"[{};\[\]()=\-><+$_&|]", cleaned_line))
        space_count = cleaned_line.count(" ")

        if symbol_density > 5 or space_count < 3:
            if len(cleaned_line) > 200:
                filtered_lines.append(
                    f"{cleaned_line[:80]} ... [snippet terpotong] ... {cleaned_line[-40:]}"
                )
            else:
                filtered_lines.append(line)
        else:
            filtered_lines.append(line)

    final_text = "\n".join(filtered_lines)

    # Batas ceiling absolut 3000 char
    if len(final_text) > 3000:
        return (
            f"{final_text[:1500]}\n\n... [ringkasan tengah] ...\n\n{final_text[-1500:]}"
        )

    return final_text


# ═══════════════════════════════════════════════════════════════════════════════
# CALL 1 EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════


async def execute_call1_routing(
    request: Request,
    user_message: str,
    context_history_str: str,
    precheck: Dict[str, Any],
    ocr_text: Optional[str] = None,
    is_guest: bool = False,
    is_first_chat: bool = False,
) -> Dict[str, Any]:
    """
    Execute Call 1: Intent Classification & Routing.

    Returns:
      Dict dengan 12 parameter routing.
    """
    from backend.app.services.pipeline.system_prompts import build_call1_routing_prompt

    # Smart Signal Stripping
    stripped_message = extract_routing_signals_for_call1(user_message)

    # Build prompt
    system_prompt = build_call1_routing_prompt(
        user_message=stripped_message,
        context_history_str=context_history_str,
        precheck=precheck,
        ocr_text=ocr_text,
        is_guest=is_guest,
        is_first_chat=is_first_chat,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": stripped_message},
    ]

    logger.info(
        f"[CALL1] Executing routing | user_msg_len={len(user_message)} | stripped_len={len(stripped_message)}"
    )

    try:
        routing_json = await generate_json_response(
            model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
            messages=messages,
            request=request,
            temperature=0.0,
            num_ctx=16384,
            num_predict=1024,
            timeout=30.0,
        )

        routing = _validate_and_normalize_routing(routing_json, precheck)

        logger.info(
            f"[CALL1] Routing complete | need_rag={routing['need_rag']} | "
            f"queries={routing['queries']} | is_coding={routing['is_coding']}"
        )

        return routing

    except Exception as e:
        logger.error(f"[CALL1] Error: {e} → fallback to rule-based routing")
        return _build_fallback_routing(precheck)


def _validate_and_normalize_routing(
    routing_json: Dict[str, Any],
    precheck: Dict[str, Any],
) -> Dict[str, Any]:
    """Validasi dan normalize routing JSON dari Call 1."""
    default_routing = {
        "need_rag": False,
        "queries": [],
        "query_judul": [],
        "search_tags": [],
        "context_snippets": [],
        "is_coding": False,
        "is_generate_file": False,  # MODE GENERATE FILE: True jika user meminta dibuatkan file
        "is_generate_email": False, # MODE EMAIL: True jika user meminta dibuatkan email
        "need_analytic": False,
        "is_self_correction": False,
        "is_ambiguous": False,
        "is_multi_document": False,
        "is_multi_turn_task": False,
        "task_list": [],
        "pronoun": "unknown",
        "tone_hint": "casual",
        "detected_language": "id",
        "requires_visual": False,
        "session_title": None,
    }

    routing = {**default_routing, **routing_json}

    routing["need_rag"] = bool(routing_json.get("need_rag", False))

    queries = routing_json.get("queries", [])
    if isinstance(queries, list):
        routing["queries"] = [
            str(q).strip() for q in queries if isinstance(q, str) and q.strip()
        ][:5]
    else:
        routing["queries"] = []

    query_judul = routing_json.get("query_judul", [])
    if isinstance(query_judul, list):
        routing["query_judul"] = [str(q).strip() for q in query_judul if isinstance(q, str) and q.strip()]
    else:
        routing["query_judul"] = [str(query_judul)] if query_judul else []

    search_tags = routing_json.get("search_tags", [])
    if isinstance(search_tags, list):
        routing["search_tags"] = [str(t).strip() for t in search_tags if isinstance(t, str) and t.strip()]
    else:
        routing["search_tags"] = []

    context_snippets = routing_json.get("context_snippets", [])
    if isinstance(context_snippets, list):
        routing["context_snippets"] = [str(c).strip() for c in context_snippets if isinstance(c, str) and c.strip()]
    else:
        routing["context_snippets"] = []

    routing["is_coding"] = bool(routing_json.get("is_coding", False))
    routing["is_generate_file"] = bool(routing_json.get("is_generate_file", False))
    routing["is_generate_email"] = bool(routing_json.get("is_generate_email", False))
    routing["needs_code_analysis"] = bool(routing_json.get("needs_code_analysis", False))
    routing["need_analytic"] = bool(routing_json.get("need_analytic", False))
    routing["is_self_correction"] = bool(routing_json.get("is_self_correction", False))
    routing["is_ambiguous"] = bool(routing_json.get("is_ambiguous", False))
    routing["is_multi_document"] = bool(routing_json.get("is_multi_document", False))
    routing["is_multi_turn_task"] = bool(routing_json.get("is_multi_turn_task", False))

    task_list = routing_json.get("task_list", [])
    if isinstance(task_list, list):
        routing["task_list"] = [
            str(t).strip() for t in task_list if isinstance(t, str) and t.strip()
        ]
    else:
        routing["task_list"] = []

    valid_pronouns = [
        "informal_gue_lo",
        "formal_saya_anda",
        "familiar_aku_kamu",
        "unknown",
    ]
    pronoun = routing_json.get("pronoun", "unknown")
    routing["pronoun"] = pronoun if pronoun in valid_pronouns else "unknown"

    valid_tones = ["casual", "formal", "empathetic"]
    tone = routing_json.get("tone_hint", "formal")
    routing["tone_hint"] = tone if tone in valid_tones else "formal"

    valid_langs = ["id", "en", "mixed"]
    lang = routing_json.get("detected_language", "id")
    routing["detected_language"] = lang if lang in valid_langs else "id"

    # Override dengan precheck jika ada hint yang kuat
    if precheck.get("need_rag_hint") is True and not routing["need_rag"]:
        logger.warning("[CALL1] Precheck override: need_rag forced to True")
        routing["need_rag"] = True

    if precheck.get("is_coding") and not routing["is_coding"]:
        logger.warning("[CALL1] Precheck override: is_coding forced to True")
        routing["is_coding"] = True
        
    if precheck.get("is_generate_email") and not routing["is_generate_email"]:
        logger.warning("[CALL1] Precheck override: is_generate_email forced to True")
        routing["is_generate_email"] = True

    if routing["need_rag"]:
        from backend.app.services.pipeline.modes.mode_utils import build_rule_based_queries

        user_message = precheck.get("_user_message", "")
        rule_based_queries = build_rule_based_queries(user_message)
        
        # Ambil pure keyword asli dari rule_based_queries index 0
        pure_keyword = rule_based_queries[0] if rule_based_queries else user_message

        if not routing["queries"]:
            routing["queries"] = rule_based_queries
            logger.info(f"[CALL1] Rule-based queries generated: {routing['queries']}")
        else:
            # Amankan query dari gemma, tapi paksa query 1 jadi pure keyword user
            gemma_queries = [q for q in routing["queries"] if q.lower() != pure_keyword.lower()]
            routing["queries"] = [pure_keyword] + gemma_queries[:2]
            logger.info(f"[CALL1] Queries modified. Query 1 forced to user keyword: {routing['queries']}")

    return routing


def _build_fallback_routing(precheck: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback routing berdasarkan rule-based precheck."""
    from backend.app.services.pipeline.modes.mode_utils import build_rule_based_queries

    need_rag_hint = precheck.get("need_rag_hint")
    user_message = precheck.get("_user_message", "")

    if need_rag_hint is True:
        queries = build_rule_based_queries(user_message)
        return {
            "need_rag": True,
            "queries": queries,
            "query_judul": [user_message],
            "search_tags": [],
            "context_snippets": [],
            "is_coding": False,
            "is_generate_file": False,
            "is_generate_email": False,
            "needs_code_analysis": False,
            "need_analytic": False,
            "is_self_correction": False,
            "is_ambiguous": False,
            "is_multi_document": False,
            "is_multi_turn_task": False,
            "task_list": [],
            "pronoun": precheck.get("pronoun", "unknown"),
            "tone_hint": "formal",
            "detected_language": "id",
        }
    else:
        return {
            "need_rag": False,
            "queries": [],
            "query_judul": [],
            "search_tags": [],
            "context_snippets": [],
            "is_coding": precheck.get("is_coding", False),
            "is_generate_file": False,
            "is_generate_email": False,
            "needs_code_analysis": False,
            "need_analytic": False,
            "is_self_correction": False,
            "is_ambiguous": False,
            "is_multi_document": False,
            "is_multi_turn_task": False,
            "task_list": [],
            "pronoun": precheck.get("pronoun", "unknown"),
            "tone_hint": "formal",
            "detected_language": "id",
        }
