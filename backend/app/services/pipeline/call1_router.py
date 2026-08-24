"""
Call 1 Router — Intent Classifier & Query Generator
====================================================

Deterministic JSON routing dengan 12 parameter kontrol.
Karakteristik: temp=0.0, num_predict=200, num_ctx=4096, is_thinking=False

Model: gemma4:31b (Single Model Architecture)
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
    # Hapus ISI FILE secara total dari pertimbangan routing
    user_content = re.sub(r'--- ISI FILE:.*?-------------------', '', user_content, flags=re.DOTALL)
    
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
# WEB QUERY SANITIZER
# ═══════════════════════════════════════════════════════════════════════════════

_WEB_QUERY_FILLER_PREFIXES = re.compile(
    r"^(mencari(\s+referensi)?(\s+terkait)?|carikan(\s+(saya|aku|gue|gw))?(\s+informasi)?|"
    r"cari(\s+(informasi|info|data|tahu|tahu))?|tolong(\s+carikan)?|informasi(\s+tentang|\s+lain)?|"
    r"info(\s+tentang|\s+lain)?|data(\s+tentang|\s+lain)?|terkait|mengenai|tentang|referensi(\s+terkait)?|"
    r"analisa(\s+tentang)?|jelaskan(\s+tentang)?|lainnya|lain)\s+",
    re.IGNORECASE
)

def _sanitize_web_query(query: str) -> str:
    """
    Bersihkan prefix filler kata bahasa Indonesia dari web search query.
    Contoh: "data lain qwen3.8" → "qwen3.8"
    """
    cleaned = query.strip()
    # Ulangi hingga semua prefix filler terkikis (bisa berlapis)
    for _ in range(5):
        new_cleaned = _WEB_QUERY_FILLER_PREFIXES.sub("", cleaned).strip()
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned
    return cleaned or query.strip()


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
    previous_topic: Optional[str] = None,
    previous_subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute Call 1: Intent Classification & Routing.

    Returns:
      Dict dengan 12 parameter routing.
    """
    from backend.app.services.pipeline.system_prompts import build_call1_routing_prompt

    # Quick bypass HANYA untuk sapaan murni 1-2 kata (misal: "halo", "pagi", "hai")
    is_complex = precheck.get("is_coding", False) or precheck.get("is_doc_query", False) or precheck.get("is_generate_email", False)
    is_pure_greeting = (precheck.get("is_greeting", False) or precheck.get("is_chitchat", False)) and len(user_message.split()) <= 2 and not is_complex
    if is_pure_greeting and not is_first_chat:
        logger.info("[CALL1] ⚡ Pure greeting detected -> Quick routing bypass")
        return _build_fallback_routing(precheck)

    # ⚡ FAST PATH: Kelanjutan langsung (lanjut, gas, terapkan) jika riwayat sebelumnya adalah koding/file
    continuation_keywords = {"lanjut", "gas", "terapkan", "next", "lanjutkan", "gas koding", "oke gas", "oke lanjut", "terapkan ini", "gas lanjut"}
    clean_msg = user_message.strip().lower()
    has_prior_coding = "<create_file" in context_history_str or "is_generate_file" in context_history_str or "GENERATE_FILE" in context_history_str
    if clean_msg in continuation_keywords and has_prior_coding and not is_first_chat:
        logger.info(f"[CALL1] ⚡ Direct continuation '{clean_msg}' detected -> 0ms Fast-Path to GENERATE_FILE")
        fast_routing = _build_fallback_routing(precheck)
        fast_routing["is_generate_file"] = True
        fast_routing["is_coding"] = True
        fast_routing["is_ambiguous"] = False
        fast_routing["need_rag"] = False
        fast_routing["active_topic"] = previous_topic or "Frontend / Coding Project"
        fast_routing["key_subject"] = previous_subject or "Kode & Implementasi File"
        fast_routing["pronoun"] = precheck.get("pronoun", "informal_gue_lo")
        return fast_routing

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
        previous_topic=previous_topic,
        previous_subject=previous_subject,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": stripped_message},
    ]

    # Alokasi num_predict dinamis (Sparse JSON murni, super hemat token & sub-detik)
    dynamic_predict = 250 if is_first_chat else 160

    # Kunci num_ctx konstan di 4096 agar sama persis dengan warmup (tidak memicu re-alokasi KV context di Ollama)
    router_ctx = 4096

    logger.info(
        f"[CALL1] Executing routing | user_msg_len={len(user_message)} | stripped_len={len(stripped_message)} | "
        f"dynamic_num_predict={dynamic_predict} | prompt_chars={len(system_prompt) + len(stripped_message)} | ctx={router_ctx}"
    )

    try:
        routing_json = await generate_json_response(
            model_name=getattr(settings, "MODEL_ROUTER", "gemma4:e4b"),
            messages=messages,
            request=request,
            temperature=0.0,
            keep_alive=-1,
            num_ctx=router_ctx,
            num_predict=dynamic_predict,
            timeout=120.0,
        )


        import json
        logger.info(f"[CALL1] 📦 Raw JSON Payload dari LLM:\n{json.dumps(routing_json, indent=2)}")

        routing = _validate_and_normalize_routing(
            routing_json, 
            precheck,
            is_first_chat=is_first_chat,
            user_message=user_message
        )

        logger.info(
            f"[CALL1] Routing complete | need_rag={routing['need_rag']} | "
            f"queries={routing['queries']} | is_coding={routing['is_coding']} | is_ambiguous={routing['is_ambiguous']}"
        )

        return routing

    except Exception as e:
        logger.error(f"[CALL1] Error: {e} → fallback to rule-based routing")
        return _build_fallback_routing(precheck)


def _validate_and_normalize_routing(
    routing_json: Dict[str, Any],
    precheck: Dict[str, Any],
    is_first_chat: bool = False,
    user_message: str = "",
) -> Dict[str, Any]:
    """Validasi dan normalize routing JSON dari Call 1."""
    default_routing = {
        "active_topic": str(routing_json.get("active_topic") or precheck.get("previous_topic") or "Obrolan Umum"),
        "key_subject": str(routing_json.get("key_subject") or precheck.get("previous_subject") or "").strip(),
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
        "is_chitchat": False,
        "is_map_query": False,
        "fetch_urls": [],
        "wizard": None,
    }

    routing = {**default_routing, **routing_json}
    routing["active_topic"] = str(routing_json.get("active_topic") or precheck.get("previous_topic") or "Obrolan Umum").strip()
    routing["key_subject"] = str(routing_json.get("key_subject") or precheck.get("previous_subject") or "").strip()
    routing["is_ambiguous"] = bool(routing_json.get("is_ambiguous", False))
    routing["is_generate_file"] = bool(routing_json.get("is_generate_file", False))
    routing["is_generate_email"] = bool(routing_json.get("is_generate_email", False))
    routing["is_coding"] = bool(routing_json.get("is_coding", False))
    routing["is_chitchat"] = bool(routing_json.get("is_chitchat", False))
    routing["need_rag"] = bool(routing_json.get("need_rag", False))
    routing["need_analytic"] = bool(routing_json.get("need_analytic", False))
    routing["is_self_correction"] = bool(routing_json.get("is_self_correction", False))
    routing["is_multi_document"] = bool(routing_json.get("is_multi_document", False))
    routing["is_multi_turn_task"] = bool(routing_json.get("is_multi_turn_task", False))
    routing["requires_visual"] = bool(routing_json.get("requires_visual", False))
    routing["is_map_query"] = bool(routing_json.get("is_map_query", False))
    routing["is_web_search"] = bool(routing_json.get("is_web_search", False))

    # ── ATURAN STRICT AMBIGUOUS GATE ──────────────────────────────────────────
    # Jika is_ambiguous True, paksa need_rag = False dan kosongkan search queries/web search
    # agar sistem tidak buang latency RAG & langsung menanyakan klarifikasi/wizard ke user.
    if routing["is_ambiguous"]:
        routing["need_rag"] = False
        routing["queries"] = []
        routing["query_judul"] = []
        routing["search_tags"] = []
        routing["is_web_search"] = False

    # Tangkap jika model mengembalikan pronoun sebagai boolean flag atau inheritance dari precheck
    if routing.get("pronoun") not in ["informal_gue_lo", "formal_saya_anda", "familiar_aku_kamu"]:
        if routing_json.get("informal_gue_lo") in [True, "true", "True", "cuy", "boss", "bro"]:
            routing["pronoun"] = "informal_gue_lo"
        elif routing_json.get("formal_saya_anda") in [True, "true", "True"]:
            routing["pronoun"] = "formal_saya_anda"
        elif routing_json.get("familiar_aku_kamu") in [True, "true", "True"]:
            routing["pronoun"] = "familiar_aku_kamu"
        elif precheck.get("pronoun") in ["informal_gue_lo", "formal_saya_anda", "familiar_aku_kamu"]:
            routing["pronoun"] = precheck.get("pronoun")
        else:
            routing["pronoun"] = "unknown"

    # Tone Hint Normalization & Inheritance
    valid_tones = ["casual", "formal", "empathetic", "empathetic_supportive", "celebratory", "direct_concise"]
    current_tone = routing_json.get("tone_hint")
    if current_tone in valid_tones:
        routing["tone_hint"] = current_tone
    elif precheck.get("tone_hint") in valid_tones:
        routing["tone_hint"] = precheck.get("tone_hint")
    else:
        routing["tone_hint"] = "casual"

    fetch_urls = routing_json.get("fetch_urls", [])
    if isinstance(fetch_urls, list):
        routing["fetch_urls"] = [
            str(u).strip() for u in fetch_urls 
            if isinstance(u, str) and (u.strip().startswith("http://") or u.strip().startswith("https://"))
        ]
    elif isinstance(fetch_urls, str) and (fetch_urls.strip().startswith("http://") or fetch_urls.strip().startswith("https://")):
        routing["fetch_urls"] = [fetch_urls.strip()]
    else:
        routing["fetch_urls"] = []

    # Fallback jika model lupa menyertakan fetch_urls tapi ada URL/domain di pesan user
    if not routing["fetch_urls"] and precheck.get("_detected_urls"):
        routing["fetch_urls"] = precheck.get("_detected_urls")
        logger.info(f"[CALL1] Auto-populated fetch_urls from precheck detected URLs: {routing['fetch_urls']}")

    queries = routing_json.get("queries", [])
    is_web_search = bool(routing_json.get("is_web_search", False))
    if isinstance(queries, list):
        cleaned_queries = [
            str(q).strip() for q in queries if isinstance(q, str) and q.strip()
        ][:5]
        # Sanitize filler kata di web search queries
        if is_web_search:
            cleaned_queries = [_sanitize_web_query(q) for q in cleaned_queries]
        routing["queries"] = cleaned_queries
    else:
        routing["queries"] = []

    query_judul = routing_json.get("query_judul", [])
    if isinstance(query_judul, list):
        routing["query_judul"] = [str(q).strip() for q in query_judul if isinstance(q, str) and q.strip()]
    else:
        routing["query_judul"] = [str(query_judul)] if query_judul else []
        
    logger.info(f"[CALL1] Extracted query_judul: {routing['query_judul']}")

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
    routing["is_ambiguous"] = bool(routing.get("is_ambiguous") or routing_json.get("is_ambiguous", False))
    routing["is_multi_document"] = bool(routing_json.get("is_multi_document", False))
    routing["is_multi_turn_task"] = bool(routing_json.get("is_multi_turn_task", False))
    routing["is_map_query"] = bool(routing_json.get("is_map_query", False))

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

    # Ekstrak atau buat fallback judul obrolan untuk sidebar kiri (SPRINT 5 OPTIMIZED)
    session_title = routing_json.get("session_title")
    if isinstance(session_title, str) and session_title.strip() and session_title.strip().lower() not in ["null", "none", "obrolan baru", ""]:
        routing["session_title"] = session_title.strip()
    elif is_first_chat:
        words = [w for w in user_message.split() if len(w) >= 3 and w.lower() not in ["jadi", "gimana", "nih", "coba", "jelasin", "tolong", "buatkan", "dong"]]
        auto_title = " ".join(words[:4]).title() if words else "Obrolan Cakra AI"
        routing["session_title"] = auto_title
        logger.info(f"[CALL1] Auto-fallback session_title generated: '{auto_title}'")
    else:
        routing["session_title"] = None

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

    # Sanity check: Jika user meminta grafik dummy / visualisasi internal, jangan biarkan web search terpancing
    if (routing.get("requires_visual") or precheck.get("requires_visual")) and routing.get("is_web_search"):
        user_msg_lower = precheck.get("_user_message", "").lower()
        if any(w in user_msg_lower for w in ["dummy", "grafik", "garfik", "chart", "diagram", "flowchart", "perbandingan 2 data", "visualisasi"]):
            if not any(sw in user_msg_lower for sw in ["cari di web", "google", "berita", "terbaru", "terkini", "internet"]):
                logger.warning("[CALL1] Sanitizing false positive is_web_search on visual dummy/chart task")
                routing["is_web_search"] = False
                routing["queries"] = []

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

    routing["is_chitchat"] = bool(routing_json.get("is_chitchat", False))

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
            "is_chitchat": False,
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
            "is_chitchat": precheck.get("is_chitchat", False),
        }
