"""
Call 1 Router — Intent Classifier & Query Generator
====================================================

Deterministic JSON routing dengan 12 parameter kontrol.
Karakteristik: temp=0.0, num_predict=200/150, num_ctx=4096, is_thinking=False

Model: gemma4:31b (Single Model Architecture)
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response

logger = logging.getLogger("CAKRA_ROUTER")

# 🛡️ Negasi Coding / File: jika user menyatakan "bukan coding", "bukan kode", dll.
CODING_NEGATIONS = [
    "bukan coding", "bukan koding", "bukan kode", "bukan urusan coding",
    "bukan masalah coding", "bukan ngoding", "gausah coding", "ga usah coding",
    "tidak coding", "jangan coding", "jangan ngoding", "non coding", "non-coding",
    "masalah teknis bukan coding", "isu teknis bukan coding"
]


# ═══════════════════════════════════════════════════════════════════════════════
# SMART SIGNAL STRIPPING
# ═══════════════════════════════════════════════════════════════════════════════


def extract_routing_signals_for_dispatcher(user_content: str) -> str:
    """
    Memotong lemak token (kodingan/log panjang) dari teks user untuk
    menjaga context window Dispatcher, tanpa menghilangkan instruksi manusia.
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

def _sanitize_web_query(query: str, user_message: str = "") -> str:
    """
    Pembersihan teknis murni untuk web search query hasil penalaran LLM Router:
    Menghapus tanda kutip pembungkus string, karakter baris baru/tab, dan spasi berlebih
    tanpa memotong kata kunci semantik esensial (seperti 'berita', 'terbaru', 'informasi', 'kabar').
    Sekaligus menyelaraskan jangkar tahun aktual secara dinamis (universal).
    """
    if not query:
        return ""
    cleaned = query.strip()
    cleaned = re.sub(r'^["\']+|["\']+$', '', cleaned).strip()
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    try:
        from backend.app.services.web_tools.web_search import normalize_temporal_web_query
        cleaned = normalize_temporal_web_query(cleaned, user_message=user_message)
    except Exception as e:
        logger.debug(f"[Router Query] Temporal normalize skipped: {e}")
        
    return cleaned or query.strip()


_RAG_TITLE_STOPWORDS = {
    "informasi", "berdasarkan", "terkait", "tentang", "mengenai", "aturan", "ketentuan",
    "panduan", "prosedur", "pedoman", "soal", "kebijakan", "dokumen", "peraturan", "dan",
    "yang", "di", "ke", "dari", "untuk", "pada", "dalam", "dengan", "adalah", "ini", "itu",
    "pt", "persero", "pindad", "apakah", "bagaimana", "seperti", "atas", "oleh", "secara",
    "sebagaimana", "dimaksud", "tersebut", "setiap", "semua", "bila", "jika", "maupun", "atau"
}

def _sanitize_rag_title_and_tags(
    query_judul_raw: Any,
    search_tags_raw: Any,
    user_message: str = "",
    key_subject: str = "",
    active_topic: str = "",
    need_rag: bool = False,
) -> Tuple[List[str], List[str]]:
    """
    Sanitasi cerdas untuk query_judul dan search_tags:
    1. Memecah kalimat naratif deskriptif menjadi array token judul target (misal: "Informasi Cuti dalam Dokumen PKB"
       -> ["PKB", "Perjanjian Kerja Bersama", "Cuti"]).
    2. Menjamin search_tags selalu terisi jika need_rag=True dengan mengekstrak tag kategori dari entitas dokumen & konteks.
    """
    if not need_rag:
        return [], []

    clean_titles: List[str] = []
    
    # 1. Normalisasi list raw titles
    raw_list: List[str] = []
    if isinstance(query_judul_raw, list):
        for q in query_judul_raw:
            if isinstance(q, str) and q.strip():
                raw_list.append(q.strip())
    elif isinstance(query_judul_raw, str) and query_judul_raw.strip():
        raw_list.append(query_judul_raw.strip())
        
    for text in raw_list:
        # Deteksi akronim dalam kurung (misal "(PKB)", "(SOP)")
        parenthesized = re.findall(r'\(([A-Za-z0-9/_-]+)\)', text)
        for p in parenthesized:
            p_upper = p.upper()
            if p_upper not in clean_titles:
                clean_titles.append(p_upper)
            if p_upper == "PKB" and "Perjanjian Kerja Bersama" not in clean_titles:
                clean_titles.append("Perjanjian Kerja Bersama")

        # Cek apakah text berupa kalimat deskriptif panjang (> 3 kata)
        words = text.split()
        if len(words) > 3:
            # Ambil akronim berhuruf kapital mandiri
            acronyms = re.findall(r'\b[A-Z0-9]{2,}\b', text)
            for acr in acronyms:
                if acr not in clean_titles:
                    clean_titles.append(acr)
                if acr == "PKB" and "Perjanjian Kerja Bersama" not in clean_titles:
                    clean_titles.append("Perjanjian Kerja Bersama")
            
            # Ambil kata-kata substantif (bukan stopwords)
            content_words = [
                w.strip("(),.-;:") for w in words 
                if len(w.strip("(),.-;:")) >= 3 and w.strip("(),.-;:").lower() not in _RAG_TITLE_STOPWORDS
            ]
            for cw in content_words:
                cw_title = cw.title()
                if cw_title not in clean_titles and cw.upper() not in clean_titles:
                    clean_titles.append(cw_title)
        else:
            # Frasa ringkas <= 3 kata, masukkan langsung
            clean_phrase = text.strip("(),.-;:")
            if clean_phrase and clean_phrase not in clean_titles:
                clean_titles.append(clean_phrase)

    # 1B. Jika user_message menyebutkan dokumen regulasi utama tapi model lupa memasukkan ke query_judul
    user_msg_lower = (user_message or "").lower()
    if "pkb" in user_msg_lower or "perjanjian kerja bersama" in user_msg_lower:
        if "PKB" not in clean_titles:
            clean_titles.insert(0, "PKB")
        if "Perjanjian Kerja Bersama" not in clean_titles:
            clean_titles.append("Perjanjian Kerja Bersama")
    if "sop" in user_msg_lower and "SOP" not in clean_titles:
        clean_titles.insert(0, "SOP")
    if "skep" in user_msg_lower and "SKEP" not in clean_titles:
        clean_titles.insert(0, "SKEP")
                
    # 2. Sanitasi & auto-derivation search_tags
    clean_tags: List[str] = []
    if isinstance(search_tags_raw, list):
        for t in search_tags_raw:
            if isinstance(t, str) and t.strip():
                tag_norm = t.strip().lower()
                if tag_norm not in clean_tags and tag_norm not in _RAG_TITLE_STOPWORDS:
                    clean_tags.append(tag_norm)
    elif isinstance(search_tags_raw, str) and search_tags_raw.strip():
        for t in search_tags_raw.split(","):
            tag_norm = t.strip().lower()
            if tag_norm and tag_norm not in clean_tags and tag_norm not in _RAG_TITLE_STOPWORDS:
                clean_tags.append(tag_norm)

    # Jika need_rag=True tapi search_tags kosong/sedikit, derive dari query_judul & konteks
    if need_rag and len(clean_tags) < 2:
        for title in clean_titles:
            # Pecah setiap kata dari title untuk dijadikan tag mandiri (misal: "Perjanjian Kerja Bersama" -> "pkb")
            for word in title.split():
                w_low = word.strip("(),.-;:").lower()
                if len(w_low) >= 3 and w_low not in _RAG_TITLE_STOPWORDS:
                    if w_low not in clean_tags:
                        clean_tags.append(w_low)
            t_low = title.lower()
            if len(t_low) >= 3 and t_low not in _RAG_TITLE_STOPWORDS:
                if t_low not in clean_tags:
                    clean_tags.append(t_low)
                    
        combined_ctx = f"{user_message} {key_subject} {active_topic}".lower()
        common_corporate_tags = [
            "pkb", "sop", "skep", "cuti", "lembur", "gaji", "tunjangan", "pensiun",
            "mutasi", "promosi", "rekrutmen", "seragam", "k3", "disiplin", "sanksi",
            "kontrak", "kepegawaian", "sdm", "peraturan", "fasilitas", "kesehatan"
        ]
        for ct in common_corporate_tags:
            if ct in combined_ctx and ct not in clean_tags:
                clean_tags.append(ct)

    return clean_titles, clean_tags


# ═══════════════════════════════════════════════════════════════════════════════
# DISPATCHER ROUTING EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════


async def dispatch_intent_route(
    request: Request,
    user_message: str,
    context_history_str: str,
    precheck: Dict[str, Any],
    ocr_text: Optional[str] = None,
    is_guest: bool = False,
    is_first_chat: bool = False,
    previous_topic: Optional[str] = None,
    previous_subject: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute Dispatcher Routing: Intent Classification & Routing.

    Returns:
      Dict dengan 12 parameter routing.
    """
    from backend.app.services.pipeline.system_prompts import build_dispatcher_prompt

    # Quick bypass HANYA untuk sapaan murni 1-2 kata (misal: "halo", "pagi", "hai")
    is_complex = precheck.get("is_coding", False) or precheck.get("is_doc_query", False) or precheck.get("is_generate_email", False)
    is_pure_greeting = (precheck.get("is_greeting", False) or precheck.get("is_chitchat", False)) and len(user_message.split()) <= 2 and not is_complex
    if is_pure_greeting and not is_first_chat:
        logger.info("[DISPATCHER_ROUTER] ⚡ Pure greeting detected -> Quick routing bypass")
        return _build_fallback_routing(precheck)

    # ⚡ FAST PATH: Kelanjutan langsung (lanjut, gas, terapkan) jika riwayat sebelumnya adalah koding/file
    continuation_keywords = {"lanjut", "gas", "terapkan", "next", "lanjutkan", "gas koding", "oke gas", "oke lanjut", "terapkan ini", "gas lanjut"}
    clean_msg = user_message.strip().lower()
    has_prior_coding = "<create_file" in context_history_str or "is_generate_file" in context_history_str or "GENERATE_FILE" in context_history_str
    if clean_msg in continuation_keywords and has_prior_coding and not is_first_chat:
        logger.info(f"[DISPATCHER_ROUTER] ⚡ Direct continuation '{clean_msg}' detected -> 0ms Fast-Path to GENERATE_FILE")
        fast_routing = _build_fallback_routing(precheck)
        fast_routing["is_generate_file"] = True
        fast_routing["is_coding"] = True
        fast_routing["is_ambiguous"] = False
        fast_routing["need_rag"] = False
        fast_routing["active_topic"] = previous_topic or "Frontend / Coding Project"
        fast_routing["key_subject"] = previous_subject or "Kode & Implementasi File"
        fast_routing["pronoun"] = precheck.get("pronoun", "informal_gue_lo")
        return fast_routing

    if previous_topic and not precheck.get("previous_topic"):
        precheck["previous_topic"] = previous_topic
    if previous_subject and not precheck.get("previous_subject"):
        precheck["previous_subject"] = previous_subject

    # Smart Signal Stripping
    stripped_message = extract_routing_signals_for_dispatcher(user_message)

    # Build prompt
    system_prompt = build_dispatcher_prompt(
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

    # Alokasi num_predict dinamis hemat token untuk kecepatan respons maksimal (~0.8s - 1.2s)
    # Dioptimalkan ke 200/150 karena Call 1 kini lean tanpa beban query generation
    dynamic_predict = 200 if is_first_chat else 150

    # Tentukan model yang digunakan
    effective_model = model_name or getattr(settings, "MODEL_ROUTER", "/home/qisthi/models/gemma-4-31B-it-AWQ")

    # Kunci num_ctx adaptif: Gemma (vocab 256k -> ~3.1k tokens) cukup 4096. Model lain (Granite/Llama/MiniCPM vocab 128k -> ~5.1k tokens) butuh 8192.
    if any(k in effective_model.lower() for k in ["granite", "llama", "mistral", "qwen", "minicpm"]):
        router_ctx = 8192
    else:
        router_ctx = getattr(settings, "NUM_CTX_ROUTER", 4096)

    logger.info(
        f"[DISPATCHER_ROUTER] Executing routing | model={effective_model} | user_msg_len={len(user_message)} | stripped_len={len(stripped_message)} | "
        f"dynamic_num_predict={dynamic_predict} | prompt_chars={len(system_prompt) + len(stripped_message)} | ctx={router_ctx}"
    )

    try:
        from datetime import datetime
        t0_dispatcher = datetime.now()
        routing_json = await generate_json_response(
            model_name=effective_model,
            messages=messages,
            request=request,
            temperature=0.0,
            top_p=0.1,
            top_k=1,
            keep_alive=-1,
            num_ctx=router_ctx,
            num_predict=dynamic_predict,
            timeout=120.0,
        )
        duration_dispatcher_ms = (datetime.now() - t0_dispatcher).total_seconds() * 1000

        # Bersihkan setiap field bernilai False, None, atau empty array agar benar-benar sparse
        clean_sparse_json = {
            k: v for k, v in routing_json.items() 
            if v is not False and v is not None and v != [] and v != ""
        }

        routing = _validate_and_normalize_routing(
            clean_sparse_json, 
            precheck,
            is_first_chat=is_first_chat,
            user_message=user_message,
            is_guest=is_guest,
            context_history_str=context_history_str,
        )

        routing["_router_prompt_tokens"] = routing_json.get("_prompt_tokens", 0) if isinstance(routing_json, dict) else 0
        routing["_router_completion_tokens"] = routing_json.get("_completion_tokens", 0) if isinstance(routing_json, dict) else 0

        # ── KOTAK 1: [CALL 1 ROUTING & DECISION DASHBOARD] ────────────────────
        active_mode = "GENERAL / CHITCHAT"
        if precheck.get("_detected_urls"):
            active_mode = f"URL READER ({', '.join(precheck.get('_detected_urls', []))})"
        elif routing.get("is_chitchat") or routing.get("is_greeting"):
            active_mode = "CHITCHAT / OBROLAN SANTAI"
        elif routing.get("need_rag"):
            active_mode = "RAG REGULASI INTERNAL"
        elif routing.get("is_web_search"):
            active_mode = "WEB SEARCH EKSTERNAL"
        elif routing.get("is_coding"):
            active_mode = "CODING & SCRIPTING"
        elif routing.get("is_docwriter"):
            active_mode = "DOKUMEN WRITER BUMN"
        elif routing.get("is_generate_file"):
            active_mode = "FILE GENERATION (<create_file>)"
        elif routing.get("is_generate_email"):
            active_mode = "SMART EMAIL DINAS"
        elif routing.get("need_analytic"):
            active_mode = "ANALITIK & MATEMATIS"
        elif routing.get("is_ambiguous"):
            active_mode = "AMBIGU / DECISION WIZARD"

        need_rag_str = "✅ True (Ambil regulasi internal)" if routing.get("need_rag") else "❌ False"
        web_search_str = "✅ True (Cari di internet)" if routing.get("is_web_search") else "❌ False"
        target_q = routing.get("queries", [])
        target_q_str = str(target_q[:2]) if target_q else "[]"
        if len(target_q) > 2:
            target_q_str += f" (+{len(target_q)-2} lainnya)"

        vt = routing.get("visual_types", [])
        visual_str = f"✅ {', '.join(vt)}" if (routing.get("requires_visual") and vt) else "❌ None"

        active_features = []
        if routing.get("is_url_read"):
            active_features.append("URL Reader")
        if routing.get("is_ambiguous"):
            active_features.append("Decision Wizard")
        if routing.get("is_troubleshooting"):
            active_features.append("Troubleshooting")
        if routing.get("is_comparative"):
            active_features.append("Comparative Matrix")
        if routing.get("has_actionable_workflow"):
            active_features.append("Actionable Workflow")
        if routing.get("is_deep_research"):
            active_features.append("Deep Research")
        if routing.get("is_security_critical"):
            active_features.append("Security Critical")
        if routing.get("is_generate_file"):
            active_features.append("File Generator")
        if routing.get("is_docwriter"):
            active_features.append("DocWriter")
        if routing.get("is_generate_email"):
            active_features.append("Smart Email")
        if routing.get("is_coding"):
            active_features.append("Coding Sandbox")
        if routing.get("is_map_query"):
            active_features.append("Peta Pindad")

        features_str = ", ".join(active_features) if active_features else "Standar (Tanpa Modul Berat)"

        clean_user_msg = user_message.replace("\n", " ").strip()
        topic_str = f"{routing.get('active_topic', '-')} / {routing.get('key_subject', '-')}".strip(" /")

        INNER_W = 98
        BORDER_W = INNER_W + 2

        def _make_rows(text: str, inner_width: int = INNER_W, indent_spaces: int = 4) -> list:
            import wcwidth
            w_text = wcwidth.wcswidth(text)
            if w_text <= inner_width:
                pad = inner_width - w_text
                return [f"║ {text}{' ' * max(0, pad)} ║"]
            
            # Deteksi indentasi awal asli dari teks
            leading_spaces = len(text) - len(text.lstrip(" "))
            prefix_indent = " " * leading_spaces
            clean_text = text.lstrip(" ")
            
            words = clean_text.split(" ")
            lines = []
            curr = prefix_indent
            for w in words:
                if not w:
                    continue
                cand = (curr + " " + w) if curr.strip() else (prefix_indent + w)
                if wcwidth.wcswidth(cand) <= inner_width:
                    curr = cand
                else:
                    if curr.strip():
                        lines.append(curr)
                        curr = (" " * indent_spaces) + w
                    else:
                        lines.append(w)
                        curr = ""
            if curr.strip():
                lines.append(curr)

            res = []
            for line in lines:
                w_line = wcwidth.wcswidth(line)
                if w_line > inner_width:
                    cur_ch = ""
                    for ch in line:
                        if wcwidth.wcswidth(cur_ch + ch) > inner_width:
                            break
                        cur_ch += ch
                    line = cur_ch
                    w_line = wcwidth.wcswidth(line)
                pad = inner_width - w_line
                res.append(f"║ {line}{' ' * max(0, pad)} ║")
            return res

        top_border = "╔" + ("═" * BORDER_W) + "╗"
        mid_border = "╠" + ("═" * BORDER_W) + "╣"
        bot_border = "╚" + ("═" * BORDER_W) + "╝"

        detected_urls_list = precheck.get("_detected_urls", [])
        detected_urls_str = f"✅ {detected_urls_list}" if detected_urls_list else "❌ None"

        raw_qj = routing.get("query_judul", [])
        qj_str = f"✅ {raw_qj}" if raw_qj else "❌ None (Semua Dokumen)"

        raw_st = routing.get("search_tags", [])
        st_str = f"✅ {raw_st}" if raw_st else "❌ None"

        lang_tone_str = f"Lang: {routing.get('detected_language', 'id')} | Pronoun: {routing.get('pronoun', 'unknown')} | Tone: {routing.get('tone_hint', 'formal')}"

        query_rows = []
        if not target_q:
            query_rows = [*_make_rows("   • Search Queries : ❌ [] (Nihil / Percakapan Langsung)", indent_spaces=22)]
        else:
            query_rows = [*_make_rows(f"   • Search Queries : ({len(target_q)} query aktif)", indent_spaces=22)]
            for idx, q_item in enumerate(target_q, start=1):
                query_rows.extend(_make_rows(f"     [{idx}] \"{q_item}\"", indent_spaces=11))

        rag_specific_rows = []
        if routing.get("need_rag"):
            rag_specific_rows = [
                *_make_rows(f"   • Query Judul    : {qj_str}", indent_spaces=22),
                *_make_rows(f"   • Search Tags    : {st_str}", indent_spaces=22),
            ]

        ambiguity_rows = []
        if routing.get("is_ambiguous") and routing.get("ambiguity_reason"):
            ambiguity_rows = [
                *_make_rows(f"   • Alasan Ambigu  : \"{routing.get('ambiguity_reason')}\"", indent_spaces=22)
            ]

        history_str = "✅ True (Konteks Multi-turn Aktif)" if routing.get("needs_history") else "⚡ False (Bypass Riwayat / Single-turn Cepat)"

        c1_lines = [
            top_border,
            *_make_rows(f"📌 [DISPATCHER ROUTING & DECISION DASHBOARD] (model: {effective_model}, {duration_dispatcher_ms:.0f}ms)"),
            mid_border,
            *_make_rows(f"👤 PESAN : \"{clean_user_msg}\""),
            mid_border,
            *_make_rows("🔎 KEPUTUSAN KANAL DATA (SUMBER TUNGGAL)"),
            *_make_rows(f"   • Need RAG       : {need_rag_str}"),
            *rag_specific_rows,
            *_make_rows(f"   • Web Search     : {web_search_str}"),
            *_make_rows(f"   • URL Reader     : {detected_urls_str}", indent_spaces=22),
            *query_rows,
            mid_border,
            *_make_rows("🧩 KEPUTUSAN KANAL FORMAT CALL 2 (KOMPONEN AKTIF)"),
            *_make_rows(f"   • Mode Terpilih  : {active_mode}"),
            *_make_rows(f"   • Visual Output  : {visual_str}"),
            *_make_rows(f"   • Fitur Khusus   : {features_str}", indent_spaces=22),
            *_make_rows(f"   • Topik / Subjek : {topic_str}"),
            *_make_rows(f"   • Gaya & Persona : {lang_tone_str}", indent_spaces=22),
            *ambiguity_rows,
            bot_border
        ]

        logger.info("\n" + "\n".join(c1_lines))

        return routing

    except Exception as e:
        logger.error(f"[DISPATCHER_ROUTER] Error: {e} → fallback to rule-based routing")
        return _build_fallback_routing(precheck)


def _validate_and_normalize_routing(
    routing_json: Dict[str, Any],
    precheck: Dict[str, Any],
    is_first_chat: bool = False,
    user_message: str = "",
    is_guest: bool = False,
    context_history_str: str = "",
) -> Dict[str, Any]:
    """Validasi dan normalize routing JSON dari Call 1."""
    is_guest = is_guest or precheck.get("is_guest", False)
    default_routing = {
        "active_topic": str(routing_json.get("active_topic") or precheck.get("previous_topic") or "Obrolan Umum"),
        "key_subject": str(routing_json.get("key_subject") or precheck.get("previous_subject") or "").strip(),
        "need_rag": False,
        "queries": [],
        "query_judul": [],
        "search_tags": [],
        "context_snippets": [],
        "is_coding": False,
        "is_troubleshooting": False,
        "is_comparative": False,
        "has_actionable_workflow": False,
        "is_deep_research": False,
        "is_security_critical": False,
        "is_generate_file": False,  # MODE GENERATE FILE: True jika user meminta dibuatkan file
        "is_generate_email": False, # MODE EMAIL: True jika user meminta dibuatkan email
        "is_docwriter": False,      # MODE DOC WRITER: True jika user meminta draf naskah dinas atau buka editor
        "is_url_read": False,       # MODE URL READER: True jika user melampirkan URL spesifik untuk dibaca/dirangkum/dibandingkan
        "need_analytic": False,
        "is_self_correction": False,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "is_multi_document": False,
        "is_multi_turn_task": False,
        "task_list": [],
        "pronoun": "unknown",
        "tone_hint": "casual",
        "detected_language": "id",
        "requires_visual": False,
        "visual_types": [],
        "session_title": None,
        "is_chitchat": False,
        "is_map_query": False,
        "fetch_urls": [],
        "session_chunk_ids": [],
        "target_brain_assets": [],
        "needs_live_refetch": False,
        "wizard": None,
        "needs_history": False,
    }

    routing = {**default_routing, **routing_json}
    routing["_user_message"] = user_message
    routing["active_topic"] = str(routing_json.get("active_topic") or precheck.get("previous_topic") or "Obrolan Umum").strip()
    routing["key_subject"] = str(routing_json.get("key_subject") or precheck.get("previous_subject") or "").strip()
    routing["is_ambiguous"] = bool(routing_json.get("is_ambiguous", False))
    routing["ambiguity_reason"] = str(routing_json.get("ambiguity_reason") or "").strip()
    routing["is_generate_file"] = bool(routing_json.get("is_generate_file", False))
    routing["is_generate_email"] = bool(routing_json.get("is_generate_email", False))
    routing["is_docwriter"] = bool(routing_json.get("is_docwriter", False)) or bool(precheck.get("is_docwriter", False))
    routing["is_url_read"] = bool(routing_json.get("is_url_read", False))
    if precheck.get("_detected_urls") and not routing_json.get("need_rag") and not routing_json.get("is_web_search"):
        routing["is_url_read"] = True
    routing["is_coding"] = bool(routing_json.get("is_coding", False))
    if any(neg in user_msg_lower for neg in CODING_NEGATIONS):
        routing["is_coding"] = False
        routing["is_generate_file"] = False
    routing["is_troubleshooting"] = bool(routing_json.get("is_troubleshooting", False))
    routing["is_comparative"] = bool(routing_json.get("is_comparative", False))
    user_msg_lower = (user_message or "").lower()
    if any(k in user_msg_lower for k in ["bandingkan", "cocokkan", "sinkronkan", "crosscheck", "cross check", "cek silang", "apa bedanya", "perbedaan"]):
        routing["is_comparative"] = True
        routing["needs_history"] = True

    routing["has_actionable_workflow"] = bool(routing_json.get("has_actionable_workflow", False))
    routing["is_deep_research"] = bool(routing_json.get("is_deep_research", False))
    routing["is_security_critical"] = bool(routing_json.get("is_security_critical", False))
    routing["is_chitchat"] = bool(routing_json.get("is_chitchat", False))
    target_assets = routing_json.get("target_brain_assets") or routing_json.get("session_chunk_ids") or []
    if isinstance(target_assets, list):
        parsed_ids = [int(a) for a in target_assets if str(a).isdigit()]
        routing["target_brain_assets"] = parsed_ids
        routing["session_chunk_ids"] = parsed_ids
    else:
        routing["target_brain_assets"] = []
        routing["session_chunk_ids"] = []
    routing["needs_live_refetch"] = bool(routing_json.get("needs_live_refetch", False))

    routing["needs_history"] = bool(routing_json.get("needs_history") is True) or routing["is_comparative"]
    if routing["target_brain_assets"]:
        routing["needs_history"] = True
    has_prior_context = bool(precheck.get("has_prior_context")) or bool(precheck.get("has_prior_chitchat")) or bool(precheck.get("has_prior_coding")) or bool(precheck.get("has_prior_rag")) or bool(precheck.get("has_prior_visual"))
    if is_first_chat and not has_prior_context:
        routing["needs_history"] = False
    elif (
        routing.get("is_self_correction")
        or precheck.get("is_replying_to_wizard")
        or precheck.get("is_replying_to_assistant_question")
    ):
        routing["needs_history"] = True
    topic_sub_text = f"{routing['active_topic']} {routing['key_subject']}".lower()
    user_msg_lower = (user_message or "").lower()

    # 🛡️ GREETING & CHITCHAT GATEKEEPER:
    # Sapaan murni ("pagi brother", "halo cuy", "assalamualaikum", dll) BUKAN permintaan dokumen regulasi!
    is_simple_greeting = (
        bool(precheck.get("is_greeting"))
        or bool(precheck.get("is_chitchat"))
        or (any(kw in user_msg_lower for kw in ["halo", "hai", "pagi", "siang", "sore", "malam", "assalamualaikum", "sampurasun", "apa kabar"]) and len(user_message.split()) <= 4)
    ) and not any(kw in user_msg_lower for kw in ["dokumen", "regulasi", "peraturan", "pkb", "sop", "skep", "pasal", "kebijakan", "surat", "cuti", "gaji", "tunjangan", "dinas", "kpi", "audit"])

    # Deteksi cerdas: jika active_topic / key_subject menunjukkan sapaan/salam/cuaca/waktu, tandai is_chitchat = True
    if is_simple_greeting:
        routing["is_chitchat"] = True
        routing["is_web_search"] = False
        routing["need_rag"] = False
        routing["queries"] = []
        routing["query_judul"] = []
        routing["search_tags"] = []
        logger.info("[DISPATCHER_ROUTER] 💬 Simple greeting detected -> forcing need_rag=False, is_web_search=False, is_chitchat=True, clearing query_judul & search_tags")
    elif not routing.get("need_rag") and not routing["is_coding"] and not routing["is_generate_file"]:
        if any(kw in topic_sub_text for kw in ["sapaan", "salam", "chitchat", "greeting", "kabar", "energi positif", "semangat pagi", "cuaca", "suhu", "waktu", "jam berapa", "tanggal berapa"]) or precheck.get("is_greeting") or precheck.get("is_chitchat"):
            routing["is_chitchat"] = True

    # Deteksi cerdas: jika user bertanya cuaca hari ini / cuaca lokal saat ini (BUKAN prakiraan masa depan / 7 hari ke depan):
    is_future_forecast = any(kw in user_msg_lower for kw in ["7 hari", "minggu depan", "besok", "lusa", "forecast", "prakiraan", "seminggu", "prediksi", "chart", "grafik"])
    is_current_weather = ("cuaca" in topic_sub_text or "cuaca" in user_msg_lower or "suhu" in user_msg_lower) and not any(city in user_msg_lower for city in ["tokyo", "london", "new york", "paris", "singapore", "amerika", "eropa"]) and not is_future_forecast

    if not is_simple_greeting:
        routing["need_rag"] = bool(routing_json.get("need_rag", False))
    else:
        routing["need_rag"] = False
    routing["need_analytic"] = bool(routing_json.get("need_analytic", False))
    routing["is_self_correction"] = bool(routing_json.get("is_self_correction", False))
    routing["is_multi_document"] = bool(routing_json.get("is_multi_document", False))
    routing["is_multi_turn_task"] = bool(routing_json.get("is_multi_turn_task", False))
    routing["requires_visual"] = bool(routing_json.get("requires_visual", False)) or bool(precheck.get("requires_visual", False))
    
    # Normalisasi visual_types (bisa string tunggal atau array)
    raw_visual_types = routing_json.get("visual_types") or routing_json.get("visual_type") or precheck.get("visual_types") or precheck.get("visual_type") or []
    if isinstance(raw_visual_types, str):
        routing["visual_types"] = [raw_visual_types.strip().lower()]
    elif isinstance(raw_visual_types, list):
        routing["visual_types"] = [str(v).strip().lower() for v in raw_visual_types if v]
    else:
        routing["visual_types"] = []
        
    if routing["visual_types"]:
        routing["requires_visual"] = True
        
    # Auto-detect visual_types jika requires_visual tapi visual_types belum terisi
    if routing["requires_visual"] and not routing["visual_types"]:
        user_lower = (user_message or "").lower()
        # 1. Grafik Data Numerik & Statistik (Standard s/d Advance: bar, line, pie, radar, scatter, area, donut, histogram, heatmap, dll)
        if any(w in user_lower for w in [
            "grafik", "chart", "bar", "pie", "line", "garis", "kurva", "area", 
            "donut", "donat", "radar", "scatter", "histogram", "heatmap", "funnel", 
            "gauge", "tren", "trend", "distribusi", "fluktuasi", "statistik", "metrik"
        ]):
            routing["visual_types"].append("chart")
            
        # 2. Diagram Alur, Proses, Relasi & Arsitektur
        if any(w in user_lower for w in [
            "diagram", "alur", "flowchart", "arsitektur", "bagan", "sequence", 
            "erd", "mindmap", "peta konsep", "hierarki", "hirarki", "skema"
        ]):
            routing["visual_types"].append("mermaid")
            
        # 3. Jadwal Waktu & Milestone
        if any(w in user_lower for w in [
            "jadwal", "timeline", "gantt", "roadmap", "milestone", "sprint", "tenggat", "jadwal proyek"
        ]):
            routing["visual_types"].append("gantt")
            
        # 4. Tabel Interaktif & Rekapitulasi Data
        if any(w in user_lower for w in [
            "tabel", "grid", "datagrid", "spreadsheet", "rekap data", "kolom"
        ]):
            routing["visual_types"].append("datagrid")
            
        # 5. Peta & Geografis
        if any(w in user_lower for w in [
            "peta", "map", "lokasi", "koordinat", "geografis", "denah", "posisi"
        ]):
            routing["visual_types"].append("map")
            
        # 6. Infografis & Ringkasan Visual
        if any(w in user_lower for w in [
            "infografis", "infographic", "dashboard", "ringkasan visual", "kpi"
        ]):
            routing["visual_types"].append("infographic")

        # 7. Slides & Presentasi
        if any(w in user_lower for w in [
            "slide", "slides", "presentasi", "presentation", "powerpoint", "ppt", "dek presentasi"
        ]):
            routing["visual_types"].append("slides")

        if not routing["visual_types"]:
            routing["visual_types"] = ["mermaid"]
            
    routing["is_map_query"] = bool(routing_json.get("is_map_query", False)) or bool(precheck.get("is_map_query", False))
    if routing["is_map_query"]:
        routing["need_rag"] = False
        routing["query_judul"] = []
        logger.info("[DISPATCHER_ROUTER] 🌍 is_map_query detected -> overriding need_rag=False")
    
    raw_chunk_ids = routing_json.get("target_brain_assets") or routing_json.get("session_chunk_ids") or routing.get("target_brain_assets") or []
    if isinstance(raw_chunk_ids, list):
        parsed = [int(x) for x in raw_chunk_ids if str(x).isdigit()]
        routing["session_chunk_ids"] = parsed
        routing["target_brain_assets"] = parsed
    elif isinstance(raw_chunk_ids, (int, str)) and str(raw_chunk_ids).isdigit():
        routing["session_chunk_ids"] = [int(raw_chunk_ids)]
        routing["target_brain_assets"] = [int(raw_chunk_ids)]
    else:
        routing["session_chunk_ids"] = []
        routing["target_brain_assets"] = []
    
    from backend.app.services.pipeline.intent_dictionary import (
        is_explicit_web_search_required,
        is_pure_opinion_or_chitchat
    )

    # Deteksi cerdas opini/afirmasi/curhat/keluh kesah: jika user memberi tanggapan opini tanpa meminta cari di web
    is_opinion = is_pure_opinion_or_chitchat(user_message)
    is_explicit_web = is_explicit_web_search_required(user_message)

    # Otomatis aktifkan is_web_search jika ada queries dan bukan dokumen internal / bukan koding / bukan cuaca saat ini
    if is_current_weather:
        logger.info("[DISPATCHER_ROUTER] ⛅ Cuaca lokal saat ini terdeteksi. Mematikan is_web_search agar dijawab instan via Ambient Context Persona.")
        routing["is_web_search"] = False
        routing["queries"] = []
        routing["is_chitchat"] = True
    elif is_opinion and not is_explicit_web:
        logger.info("[DISPATCHER_ROUTER] 💬 Pesan opini/afirmasi/chitchat terdeteksi. Mematikan is_web_search agar dijawab empatik & reflektif via Persona Core.")
        routing["is_web_search"] = False
        routing["queries"] = []
        routing["is_chitchat"] = True
    # 🌐 Penyelarasan Yurisdiksi: Jika model memilih Data Luar (Web Search) bersamaan dengan Dokumen Internal
    forced_mode_clean = str(precheck.get("forced_mode") or "").lower().strip()
    is_forced_doc_mode = forced_mode_clean in ["documents", "document", "rag", "focus", "compliance", "redteam", "audit"]
    has_doc_signal = any(kw in user_msg_lower for kw in [
        "dokumen", "pkb", "sop", "peraturan", "skep", "surat keputusan", "surat edaran",
        "naskah dinas", "cuti", "pasal", "tunjangan", "dinas", "kpi", "audit", "auditor", "sanksi",
        "indisipliner", "kompensasi", "anggaran dasar", "akta", "disiplin", "pelanggaran",
        "karyawan", "pegawai", "celah", "hukum", "direksi", "komisaris", "belanja modal", "kewenangan"
    ])

    if routing_json.get("queries") and not routing["need_rag"] and not routing["is_coding"] and not routing["is_generate_file"]:
        # Hanya aktifkan web search jika memang diminta di JSON atau terdeteksi di spektrum web search / public web
        if routing_json.get("is_web_search", False) or is_explicit_web or precheck.get("is_public_web"):
            routing["is_web_search"] = True
        elif is_forced_doc_mode or has_doc_signal or precheck.get("need_rag_hint") or precheck.get("is_doc_query"):
            routing["need_rag"] = True
            routing["is_web_search"] = False
            routing["is_chitchat"] = False
            logger.info("[DISPATCHER_ROUTER] 📚 Document signal or forced doc mode detected with queries -> setting need_rag=True")
        else:
            routing["is_web_search"] = False
            routing["queries"] = []
            routing["is_chitchat"] = True
    else:
        # Jika LLM Call 1 sudah menentukan need_rag=True, prioritaskan keputusan model dan jangan biarkan regex luar menimpa
        if routing.get("need_rag"):
            routing["is_web_search"] = False
        else:
            routing["is_web_search"] = bool(routing_json.get("is_web_search", False)) or is_explicit_web or bool(precheck.get("is_public_web"))

    if routing.get("is_web_search") and (is_forced_doc_mode or has_doc_signal):
        routing["need_rag"] = True
        routing["is_web_search"] = False
        if not routing.get("queries"):
            routing["queries"] = [user_message]
        logger.info("[DISPATCHER_ROUTER] 📚 Resolving document/web intent: internal document intent takes priority (need_rag=True, is_web_search=False)")
    elif routing.get("is_web_search") and routing.get("need_rag"):
        routing["need_rag"] = False
        routing["query_judul"] = []
        logger.info("[DISPATCHER_ROUTER] 🌐 Resolving dual-intent conflict: is_web_search takes priority over need_rag for external data")

    # 🌐 Penyelarasan URL Reader vs Web Search:
    # Jika is_url_read aktif dan pengguna TIDAK meminta pencarian web luar secara eksplisit, matikan is_web_search
    if routing.get("is_url_read") and not routing_json.get("is_web_search") and not is_explicit_web:
        routing["is_web_search"] = False
        routing["queries"] = []
        logger.info("[DISPATCHER_ROUTER] 🔗 is_url_read active without explicit web search request -> setting is_web_search=False, queries=[]")

    # 🎯 SELF-CORRECTION DYNAMIC CONTEXT RESOLUTION
    # Sanggahan/koreksi user harus adaptif terhadap domain yang sedang dibahas:
    if routing.get("is_self_correction"):
        last_action = str(precheck.get("last_responder_action") or "").upper()
        active_topic_lower = str(routing.get("active_topic") or precheck.get("active_topic") or "").lower()
        key_sub_lower = str(routing.get("key_subject") or precheck.get("key_subject") or "").lower()

        has_explicit_web_req = is_explicit_web or any(w in user_msg_lower for w in ["cari di web", "googling", "search di google", "riset online", "berita luar"])
        has_doc_audit_context = (
            "AUDIT" in last_action or "ATTACHMENT" in last_action or "REGULASI" in last_action 
            or "DOKUMEN" in last_action or any(w in active_topic_lower for w in ["dokumen", "audit", "regulasi", "koreksi", "typo", "halaman"])
            or any(w in key_sub_lower for w in ["dokumen", "audit", "regulasi", "koreksi", "typo", "halaman"])
            or any(w in user_msg_lower for w in ["typo", "tulis tangan", "tulisan tangan", "halaman", "angka", "huruf", "dokumen", "lembar", "bukan typo"])
        )

        if not has_explicit_web_req:
            if has_doc_audit_context:
                logger.info("[DISPATCHER_ROUTER] 🛡️ Dynamic Self-Correction: Local document/audit feedback detected -> disabling is_web_search, routing to document clarification context.")
                routing["is_web_search"] = False
                routing["queries"] = []
                routing["is_chitchat"] = True
            elif "CODING" in last_action or routing.get("is_coding"):
                logger.info("[DISPATCHER_ROUTER] 🛡️ Dynamic Self-Correction: Coding context detected -> maintaining is_coding.")
                routing["is_web_search"] = False
                routing["is_coding"] = True
            elif routing.get("need_rag") or "REGULASI" in last_action:
                logger.info("[DISPATCHER_ROUTER] 🛡️ Dynamic Self-Correction: Regulation context detected -> maintaining need_rag.")
                routing["is_web_search"] = False
                routing["need_rag"] = True

    # ── 🔄 UNIVERSAL BIDIRECTIONAL CONTEXT SYNCHRONIZATION (RESPONDER ➔ DISPATCHER) ──
    # Mengetahui profil tindakan Responder pada turn sebelumnya (wizard, visual, coding, chitchat, RAG)
    is_replying_to_wizard = bool(
        precheck.get("is_replying_to_wizard") 
        or precheck.get("is_wizard_confirmation") 
        or (context_history_str and "[RESPONDER_ACTION: WIZARD_DITANYAKAN]" in context_history_str)
    )
    has_prior_visual = bool(
        precheck.get("has_prior_visual") 
        or (context_history_str and "[RESPONDER_ACTION: VISUAL_DIBUAT]" in context_history_str)
    )
    has_prior_coding = bool(
        precheck.get("has_prior_coding") 
        or (context_history_str and "[RESPONDER_ACTION: KODE_FILE_DIBUAT]" in context_history_str)
    )
    has_prior_chitchat = bool(
        precheck.get("has_prior_chitchat") 
        or (context_history_str and "[RESPONDER_ACTION: CHITCHAT_DIJAWAB]" in context_history_str)
    )

    # 1. 🧙 Penanganan Konfirmasi Wizard:
    if is_replying_to_wizard:
        # 🛡️ ANTI-LOOP: User sedang menjawab pertanyaan wizard Responder, TIDAK BOLEH ambigu lagi!
        routing["is_ambiguous"] = False
        logger.info("[DISPATCHER_ROUTER] 🎯 Resolving Wizard Answer from Responder -> Overriding is_ambiguous=False")
        
        # Resolusi Domain Berdasarkan Jawaban User / Opsi Wizard:
        # A. Visual / Grafik / Diagram (misal: "bikin chart pie", "bar chart", "flowchart")
        if any(w in user_msg_lower for w in ["chart", "grafik", "pie", "bar", "line", "diagram", "mermaid", "datagrid", "tabel"]):
            routing["requires_visual"] = True
            if any(w in user_msg_lower for w in ["chart", "grafik", "pie", "bar", "line", "radar", "donut"]):
                routing["visual_types"] = ["chart"]
            elif any(w in user_msg_lower for w in ["diagram", "alur", "mermaid"]):
                routing["visual_types"] = ["mermaid"]
            routing["need_rag"] = False
            routing["is_chitchat"] = False

        # B. Regulasi / Dokumen Internal (misal: "cuti tahunan", "PKB 2024", "SOP")
        elif any(w in user_msg_lower for w in ["cuti", "pkb", "sop", "sk", "peraturan", "tunjangan", "dinas", "pindad", "pegawai"]) or (precheck.get("last_wizard", {}).get("title", "").lower().find("cuti") != -1 or precheck.get("last_wizard", {}).get("title", "").lower().find("regulasi") != -1):
            if not is_guest:
                routing["need_rag"] = True
                routing["is_chitchat"] = False
                routing["is_web_search"] = False
                if not routing.get("queries") or len(routing["queries"][0].split()) <= 2:
                    wiz_title = precheck.get("last_wizard", {}).get("title", "")
                    routing["queries"] = [f"{wiz_title} {user_message}".strip()]
                if not routing.get("query_judul"):
                    if "pkb" in user_msg_lower or "cuti" in user_msg_lower:
                        routing["query_judul"] = ["PKB", "Cuti"]
                    elif "sop" in user_msg_lower:
                        routing["query_judul"] = ["SOP"]

        # C. Koding / Tech Stack (misal: "react", "fastapi", "python")
        elif any(w in user_msg_lower for w in ["react", "vue", "python", "fastapi", "sql", "koding", "script", "node", "nextjs"]):
            routing["is_coding"] = True
            routing["need_rag"] = False
            routing["is_chitchat"] = False

    # 2. 📊 Penanganan Kelanjutan Visual (Call 2 baru saja membuat visual):
    if has_prior_visual and not routing["need_rag"]:
        visual_mod_kw = ["warna", "ganti", "ubah", "potongan", "pie", "bar", "line", "tambah", "label", "tampilan", "judul", "chart", "grafik", "diagram"]
        if any(w in user_msg_lower for w in visual_mod_kw) and len(user_message.split()) <= 15:
            routing["requires_visual"] = True
            routing["is_chitchat"] = False
            if not routing["visual_types"]:
                last_vt = precheck.get("last_visual_type") or "chart"
                routing["visual_types"] = [last_vt]
            logger.info(f"[DISPATCHER_ROUTER] 📊 Continuous Visual Refinement detected -> requires_visual=True, visual_types={routing['visual_types']}")

    # 3. 💻 Penanganan Kelanjutan Koding (Call 2 baru saja membuat kode/file):
    if has_prior_coding and not routing["need_rag"]:
        coding_cont_kw = ["tambah", "fitur", "fungsi", "error", "bug", "perbaiki", "lanjut", "jalankan", "file", "kode", "skrip", "refactor", "ubah fungsi"]
        if any(w in user_msg_lower for w in coding_cont_kw) and len(user_message.split()) <= 15:
            routing["is_coding"] = True
            routing["is_chitchat"] = False
            logger.info("[DISPATCHER_ROUTER] 💻 Continuous Coding Refinement detected -> is_coding=True")

    # 4. 💬 Penanganan Kelanjutan Basa-basi (Call 2 baru saja menjawab chitchat):
    if has_prior_chitchat and not routing["need_rag"] and not routing["is_coding"] and not routing["requires_visual"]:
        casual_ack_kw = {"mantap", "siap", "oke", "ok", "haha", "wkwk", "makasih", "terima kasih", "thanks", "tq", "sip", "semangat", "keren", "bener", "betul", "iya", "nice", "good"}
        user_words = set(re.findall(r'\b[a-zA-Z0-9_]+\b', user_msg_lower))
        has_doc_terms = any(kw in user_msg_lower for kw in ["dokumen", "pkb", "sop", "peraturan", "skep", "surat", "cuti", "pasal", "gaji", "tunjangan", "kpi", "audit"])
        if not has_doc_terms and (user_words & casual_ack_kw) and len(user_message.split()) <= 6:
            routing["is_chitchat"] = True
            routing["is_web_search"] = False
            routing["is_ambiguous"] = False
            logger.info("[DISPATCHER_ROUTER] 💬 Continuous Casual / Chitchat flow detected -> is_chitchat=True")

    # 5. 📚 Penanganan Kelanjutan Dokumen / Regulasi Multi-turn:
    # Jika percakapan sebelumnya membahas dokumen/PKB/regulasi dan pesan lanjutan menanyakan rincian
    has_prior_doc_context = bool(context_history_str and any(kw in context_history_str.lower() for kw in ["pkb", "pasal", "peraturan", "sop", "skep", "surat keputusan", "ketentuan", "kebijakan"]))
    if has_prior_doc_context and not routing["need_rag"] and not routing.get("is_coding") and not is_simple_greeting:
        follow_up_doc_kw = ["bagaimana dengan", "bagaimana kalau", "lalu", "kalau", "kompensasi", "lembur", "lapangan", "sanksi", "syarat", "ketentuan", "aturan", "berapa", "karyawan", "pegawai", "hak"]
        if any(w in user_msg_lower for w in follow_up_doc_kw):
            routing["need_rag"] = True
            routing["is_chitchat"] = False
            routing["is_web_search"] = False
            if not routing.get("queries"):
                routing["queries"] = [user_message]
            logger.info(f"[DISPATCHER_ROUTER] 📚 Continuous Document Context detected from history -> need_rag=True, queries={routing['queries']}")

    # ── ATURAN STRICT MODE DOKUMEN (USER EXPLICIT INTENT OVERRIDE) ───────────
    # Jika user secara manual mengunci Mode Dokumen (forced_mode), pastikan need_rag aktif HANYA jika bukan web search atau koding
    is_explicit_doc_mode = (
        is_forced_doc_mode
        and not routing.get("is_web_search")
        and not routing.get("is_coding")
        and not is_simple_greeting
    )
    if is_explicit_doc_mode:
        routing["need_rag"] = True
        routing["is_web_search"] = False
        routing["is_chitchat"] = False
        routing["is_ambiguous"] = False
        if not routing.get("queries"):
            routing["queries"] = [user_message]
        logger.info(f"[DISPATCHER_ROUTER] 📚 Explicit Document Mode enforced: need_rag=True, queries={routing['queries']}")

    # ── ATURAN DOKUMEN WRITER & DRAF NASKAH DINAS (OVERRIDE AMBIGUOUS) ─────────
    # Jika pengguna meminta membuka editor atau membuat draf naskah dinas resmi (SE, SKEP, Memo),
    # pastikan BUKAN ambigu dan jangan pernah di-gate oleh wizard! Khusus Pegawai (Bukan Tamu/Guest).
    is_docwriter_intent = bool(
        not is_guest and (
            routing.get("is_docwriter")
            or precheck.get("is_docwriter")
            or re.search(r'\b(buka|open|tampil(kan)?|muncul(kan)?|akses)\b.{0,25}\b(editor|writer|studio)\b', user_msg_lower)
            or (any(kw in user_msg_lower for kw in ["surat edaran", "skep", "nota dinas", "surat keputusan", "naskah dinas"]) and any(v in user_msg_lower for v in ["draft", "draf", "siapkan", "buatkan", "susun", "bikin", "buka", "buat", "tulis"]))
            or bool(re.search(r'\b(draft|draf|buatkan|siapkan|bikin|susun)\b.{0,20}\b(se|skep|surat)\b', user_msg_lower))
            or bool(re.search(r'\b(edit|ubah|ganti|tambah|tambahkan|revisi|perbarui|update|hapus)\b.{0,30}\b(poin|point|dasar|bagian|huruf|ketentuan|tentang|judul|draf|dokumen)\b', user_msg_lower))
            or bool(re.search(r'\b(edit|ubah|ganti|tambah|tambahkan)\s+(di\s+|bagian\s+|poin\s+|point\s+)?[a-z]\b', user_msg_lower))
            or any(kw in user_msg_lower for kw in [
                "buka editor", "buka dokumen editor", "buka editornya", "buka dokumen writer",
                "dokumen writer", "dokumen editor", "draft surat", "draf surat", "draft skep", "draf skep",
                "draft se", "draf se", "draft memo", "draf memo", "draft nota dinas", "draf nota dinas",
                "draft surat edaran", "draf surat edaran", "siapkan draft", "siapkan draf",
                "buatkan draft", "buatkan draf", "susun draft", "susun draf"
            ])
        )
    )
    if is_docwriter_intent:
        routing["is_docwriter"] = True
        routing["is_ambiguous"] = False
        routing["is_chitchat"] = False
        routing["is_greeting"] = False
        logger.info("[DISPATCHER_ROUTER] 📄 Document Writer intent enforced -> is_docwriter=True & is_ambiguous=False")

    # ── ATURAN STRICT AMBIGUOUS GATE ──────────────────────────────────────────
    # Jika is_ambiguous True, paksa need_rag = False dan kosongkan search queries/web search
    # agar sistem tidak buang latency RAG & langsung menanyakan klarifikasi/wizard ke user.
    if routing["is_ambiguous"]:
        routing["need_rag"] = False
        routing["queries"] = []
        routing["query_judul"] = []
        routing["search_tags"] = []
        routing["is_web_search"] = False
        logger.info(f"[DISPATCHER_ROUTER] ❓ Ambiguity Gate activated -> reason: '{routing.get('ambiguity_reason')}'")

    # ── ATURAN STRICT MUTUAL EXCLUSION: need_rag VS is_web_search & is_coding ─────────────
    # need_rag (dokumen internal Pindad) dan is_web_search/is_coding DILARANG KERAS sama-sama aktif!
    if routing.get("is_web_search") and not is_explicit_doc_mode:
        # Jika web search aktif (misal DPR RI, berita, internet), matikan need_rag
        if routing.get("need_rag"):
            logger.info("[DISPATCHER_ROUTER] 🌐 Web search is active. Setting need_rag=False.")
            routing["need_rag"] = False
    elif routing.get("need_rag"):
        routing["is_web_search"] = False
        if routing.get("is_coding"):
            logger.warning("[DISPATCHER_ROUTER] 🛡️ Strict Mutual Exclusion: need_rag=True, forcing is_coding=False!")
            routing["is_coding"] = False
        if routing.get("is_generate_file"):
            logger.warning("[DISPATCHER_ROUTER] 🛡️ Strict Mutual Exclusion: need_rag=True, forcing is_generate_file=False!")
            routing["is_generate_file"] = False

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

    # fetch_urls tidak lagi dihasilkan oleh Call 1 — URL fetching ditangani secara
    # deterministik oleh mode_hub berdasarkan regex detection (precheck["_detected_urls"])
    routing["fetch_urls"] = []

    queries = routing.get("queries") or routing_json.get("queries", [])
    is_web_search = bool(routing.get("is_web_search", False))
    if isinstance(queries, list) and (routing.get("is_web_search") or routing.get("need_rag") or routing.get("is_self_correction")):
        cleaned_queries = [
            str(q).strip() for q in queries if isinstance(q, str) and q.strip()
        ][:5]
        # Sanitize filler kata di web search queries dan disambiguasi overexpansion
        if is_web_search:
            cleaned_queries = [_sanitize_web_query(q, user_message) for q in cleaned_queries]
        routing["queries"] = cleaned_queries

    else:
        routing["queries"] = []

    raw_query_judul = routing.get("query_judul") or routing_json.get("query_judul", [])
    raw_search_tags = routing.get("search_tags") or routing_json.get("search_tags", [])

    clean_qj, clean_st = _sanitize_rag_title_and_tags(
        query_judul_raw=raw_query_judul,
        search_tags_raw=raw_search_tags,
        user_message=user_message,
        key_subject=routing.get("key_subject", ""),
        active_topic=routing.get("active_topic", ""),
        need_rag=bool(routing.get("need_rag", False)),
    )
    routing["query_judul"] = clean_qj
    routing["search_tags"] = clean_st
    logger.info(f"[DISPATCHER_ROUTER] Sanitized query_judul: {routing['query_judul']} | search_tags: {routing['search_tags']}")

    context_snippets = routing_json.get("context_snippets", [])
    if isinstance(context_snippets, list):
        routing["context_snippets"] = [str(c).strip() for c in context_snippets if isinstance(c, str) and c.strip()]
    else:
        routing["context_snippets"] = []

    routing["is_coding"] = bool(routing.get("is_coding", False))
    routing["is_generate_file"] = bool(routing.get("is_generate_file", False))
    routing["is_generate_email"] = bool(routing.get("is_generate_email", False))
    routing["needs_code_analysis"] = bool(routing.get("needs_code_analysis") or routing_json.get("needs_code_analysis", False))
    routing["need_analytic"] = bool(routing.get("need_analytic", False))
    routing["is_self_correction"] = bool(routing.get("is_self_correction", False))
    routing["is_ambiguous"] = bool(routing.get("is_ambiguous", False))
    routing["is_multi_document"] = bool(routing.get("is_multi_document", False))
    routing["is_multi_turn_task"] = bool(routing.get("is_multi_turn_task", False))
    routing["is_map_query"] = bool(routing.get("is_map_query", False)) or bool(routing_json.get("is_map_query", False)) or bool(precheck.get("is_map_query", False))
    if routing["is_map_query"]:
        routing["need_rag"] = False
        routing["query_judul"] = []

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

    # Ekstraksi dynamic response format dari Call 1 Router LLM
    valid_formats = ["yes_no", "concise", "detailed", "standard"]
    raw_resp_format = routing_json.get("response_format")
    if raw_resp_format in valid_formats:
        routing["response_format"] = raw_resp_format
    elif precheck.get("response_format") in valid_formats:
        routing["response_format"] = precheck["response_format"]
    else:
        routing["response_format"] = "standard"

    raw_format_constraint = routing_json.get("format_constraint")
    if isinstance(raw_format_constraint, str) and raw_format_constraint.strip():
        routing["format_constraint"] = raw_format_constraint.strip()
    elif precheck.get("format_constraint"):
        routing["format_constraint"] = str(precheck["format_constraint"]).strip()
    else:
        routing["format_constraint"] = None

    # Ekstrak judul obrolan untuk sidebar kiri (Gemma 4 Call 1 LLM)
    from backend.app.services.pipeline.modes.mode_utils import format_session_title, GENERIC_SESSION_TITLES
    session_title = routing_json.get("session_title")
    if isinstance(session_title, str) and session_title.strip() and session_title.strip().lower() not in GENERIC_SESSION_TITLES:
        routing["session_title"] = format_session_title(session_title, user_message=user_message)
    elif is_first_chat:
        # Fallback bertingkat:
        # 1. Gunakan key_subject atau active_topic jika informatif
        subj = routing_json.get("key_subject") or routing_json.get("active_topic")
        if subj and subj.strip().lower() not in GENERIC_SESSION_TITLES:
            routing["session_title"] = format_session_title(subj, user_message=user_message)
        else:
            # 2. Format dari pesan pengguna agar judul langsung luwes di sidebar
            formatted_user = format_session_title(user_message, user_message=user_message)
            if formatted_user and formatted_user.strip().lower() not in GENERIC_SESSION_TITLES:
                routing["session_title"] = formatted_user
            else:
                routing["session_title"] = "Sapaan & Obrolan Santai"
    else:
        routing["session_title"] = None

    # Override dengan precheck jika ada hint yang kuat (HANYA jika bukan public web search, bukan URL reader, dan BUKAN chitchat/greeting/closing)
    if precheck.get("need_rag_hint") is True and not routing["need_rag"] and not routing.get("is_web_search") and not precheck.get("has_url_context") and not precheck.get("is_public_web") and not routing.get("is_chitchat") and not routing.get("is_greeting"):
        logger.warning("[DISPATCHER_ROUTER] Precheck override: need_rag forced to True")
        routing["need_rag"] = True

    if precheck.get("is_coding") and not routing["is_coding"]:
        logger.warning("[DISPATCHER_ROUTER] Precheck override: is_coding forced to True")
        routing["is_coding"] = True
        

    if precheck.get("is_generate_email") and not routing["is_generate_email"]:
        logger.warning("[DISPATCHER_ROUTER] Precheck override: is_generate_email forced to True")
        routing["is_generate_email"] = True

    # Sanity check: Jika user meminta diagram, flowchart, grafik, arsitektur, atau data dummy TANPA instruksi cari di web
    if (routing.get("requires_visual") or precheck.get("requires_visual")) and routing.get("is_web_search"):
        user_msg_lower = precheck.get("_user_message", "").lower()
        is_visual_creation = any(w in user_msg_lower for w in [
            "diagram", "flowchart", "alur", "bagan", "skema", "arsitektur", 
            "grafik", "chart", "visualisasi", "dummy", "data tiruan", "simulasi"
        ])
        has_explicit_web_kw = any(sw in user_msg_lower for sw in [
            "cari di web", "google", "berita", "terbaru", "terkini", "internet", "cuaca", "saham", "inflasi"
        ])
        if is_visual_creation and not has_explicit_web_kw:
            logger.warning("[DISPATCHER_ROUTER] Sanitizing false positive is_web_search on visual diagram/chart task")
            routing["is_web_search"] = False
            routing["queries"] = []

    # Sanity check: Jika user hanya meminta data dummy / perbandingan data di chat TANPA instruksi buat/ekspor file fisik atau coding
    if (routing.get("is_generate_file") or routing.get("is_coding")) and not precheck.get("is_coding"):
        user_msg_lower = precheck.get("_user_message", "").lower()
        file_export_keywords = ["file", "ekspor", "export", "unduh", "download", "excel", "xlsx", "csv", "docx", "word", "pdf", ".md", ".py", ".js", "script", "koding", "coding", "aplikasi", "komponen", "proyek", "project", "repo", "source code", "bikin file", "buat file"]
        has_file_intent = any(k in user_msg_lower for k in file_export_keywords)
        is_plain_data_query = any(k in user_msg_lower for k in ["data dummy", "data dumy", "data simulasi", "perbandingan penjualan", "contoh data", "tabel perbandingan", "tabel dummy", "angka dummy"])
        if is_plain_data_query and not has_file_intent:
            logger.warning("[DISPATCHER_ROUTER] Sanitizing false positive is_generate_file/is_coding on plain chat data simulation request")
            routing["is_generate_file"] = False
            routing["is_coding"] = False
            routing["requires_visual"] = True

    if routing["need_rag"]:
        # 🚫 Internal Document RAG dilarang keras mengaktifkan is_web_search
        routing["is_web_search"] = False
        from backend.app.services.pipeline.modes.mode_utils import build_rule_based_queries

        user_msg = (user_message or precheck.get("_user_message", "")).strip()
        ctx_sub = (routing.get("key_subject") or precheck.get("previous_subject", "")).strip()
        ctx_top = (routing.get("active_topic") or precheck.get("previous_topic", "")).strip()
        rule_based_queries = [q.strip() for q in build_rule_based_queries(user_msg, ctx_sub, ctx_top) if q and q.strip()]
        
        # Ambil pure keyword asli dari rule_based_queries index 0
        pure_keyword = rule_based_queries[0] if rule_based_queries else user_msg

        if not routing.get("queries"):
            routing["queries"] = rule_based_queries if rule_based_queries else ([user_msg] if user_msg else [])
            logger.info(f"[DISPATCHER_ROUTER] Rule-based queries fallback generated: {routing['queries']}")
        else:
            # 🎯 Percayai query cerdas dari Call 1 (Gemma) secara langsung tanpa pemotongan/penimpaan paksa
            gemma_queries = [q.strip() for q in routing["queries"] if q and q.strip()]
            routing["queries"] = gemma_queries[:3]
            logger.info(f"[DISPATCHER_ROUTER] Using intelligent queries from Gemma Router: {routing['queries']}")

    # Final cleanup: buang string kosong / spasi dari queries
    if isinstance(routing.get("queries"), list):
        routing["queries"] = [q.strip() for q in routing["queries"] if isinstance(q, str) and q.strip()]

    # Pastikan is_web_search selalu memiliki minimal 1 query pencarian
    if routing.get("is_web_search") and not routing.get("queries"):
        routing["queries"] = [routing.get("key_subject") or user_message]

    # Auto-tag is_generate_file jika user secara eksplisit meminta script/file yang dibuat/disimpan
    file_intent_keywords = [
        "buatkan file", "bikin file", "buat file", "simpan ke excel", "simpan ke file",
        "simpan ke csv", "buatkan script", "bikin script", "ekspor ke", "export ke", "generate file"
    ]
    if any(k in user_msg_lower for k in file_intent_keywords) and routing.get("is_coding"):
        routing["is_generate_file"] = True

    # ── DETERMINISTIC MINIMAL 1-PARAMETER GUARD ───────────────────────────────
    # Memastikan tidak ada JSON hasil routing yang 'kosong' tanpa satupun parameter kapabilitas aktif
    capability_flags = [
        routing.get("need_rag"),
        routing.get("is_web_search"),
        bool(precheck.get("_detected_urls")),
        routing.get("is_coding"),
        routing.get("is_generate_file"),
        routing.get("is_generate_email"),
        routing.get("is_ambiguous"),
        routing.get("is_map_query"),
        routing.get("is_chitchat"),
        routing.get("requires_visual"),
    ]
    
    if not any(capability_flags):
        user_text = f"{user_message} {routing.get('active_topic', '')} {routing.get('key_subject', '')}".lower()
        
        # 1. Cek indikasi Dokumen / Regulasi Internal Pindad
        rag_keywords = [
            "skep", "sk", "sop", "pkb", "peraturan", "keputusan", "surat edaran", "direksi", 
            "pindad", "organisasi", "tata kerja", "otk", "cuti", "mutasi", "gaji", "tunjangan",
            "alutsista", "senjata", "munisi", "kendaraan khusus", "anoa", "komodo", "ss2", "harimau"
        ]
        visual_keywords = ["grafik", "chart", "diagram", "flowchart", "bagan alir", "visualisasi", "kurva", "plot", "gantt", "infografis", "jadikan grafik", "buat grafik"]
        coding_keywords = ["koding", "coding", "code", "fungsi", "function", "script", "sql", "query", "endpoint", "api", "bug", "error", "trace", "python", "javascript", "react", "html", "css", "database"]
        file_keywords = ["buatkan file", "bikin file", "export", "ekspor", "unduh excel", "unduh word", "generate file", ".xlsx", ".docx", ".pdf", ".py"]
        email_keywords = ["buatkan email", "draf email", "kirim email", "tulis email"]
        web_keywords = ["berita", "kabar terbaru", "kabar terkini", "kabar pasar", "kabar bumn", "kabar dunia", "terkini", "hari ini", "terbaru", "cuaca besok", "cuaca 7 hari", "saham", "kurs", "presiden", "juara", "pilkada", "gempa"]
        map_keywords = ["lokasi", "alamat", "dimana", "peta", "gedung", "divisi", "turen", "bandung"]
        
        # 0. Prioritaskan Map / Location query
        if any(k in user_text for k in ["lokasi", "alamat", "dimana", "di mana", "koordinat", "peta", "letak pabrik"]) or precheck.get("is_map_query"):
            routing["is_map_query"] = True
            routing["need_rag"] = False
            routing["query_judul"] = []
            logger.info("[DISPATCHER_ROUTER] 🛡️ Guard: Auto-activated is_map_query (location intent takes precedence)")
        elif any(k in user_text for k in visual_keywords) or precheck.get("requires_visual"):
            routing["requires_visual"] = True
            logger.info("[DISPATCHER_ROUTER] 🛡️ Guard: Auto-activated requires_visual (visual/chart intent detected)")
        elif any(k in user_text for k in file_keywords) and not any(neg in user_msg_lower for neg in CODING_NEGATIONS):
            routing["is_generate_file"] = True
            logger.info("[DISPATCHER_ROUTER] 🛡️ Guard: Auto-activated is_generate_file (file intent detected)")
        elif any(k in user_text for k in email_keywords):
            routing["is_generate_email"] = True
            logger.info("[DISPATCHER_ROUTER] 🛡️ Guard: Auto-activated is_generate_email (email intent detected)")
        elif (any(k in user_text for k in coding_keywords) or precheck.get("is_coding")) and not any(neg in user_msg_lower for neg in CODING_NEGATIONS):
            routing["is_coding"] = True
            logger.info("[DISPATCHER_ROUTER] 🛡️ Guard: Auto-activated is_coding (coding intent detected)")
        elif any(k in user_text for k in rag_keywords) or precheck.get("is_doc_query") or precheck.get("need_rag_hint"):
            routing["need_rag"] = True
            if not routing.get("query_judul"):
                from backend.app.services.pipeline.modes.mode_utils import build_rule_based_queries
                routing["query_judul"] = [routing.get("key_subject") or user_message]
                routing["queries"] = build_rule_based_queries(user_message, routing.get("key_subject"), routing.get("active_topic"))
            logger.info(f"[DISPATCHER_ROUTER] 🛡️ Guard: Auto-activated need_rag | query_judul={routing['query_judul']}")
        elif any(k in user_text for k in web_keywords) and not is_simple_greeting:
            routing["is_web_search"] = True
            if not routing.get("queries"):
                routing["queries"] = [routing.get("key_subject") or user_message]
            logger.info(f"[DISPATCHER_ROUTER] 🛡️ Guard: Auto-activated is_web_search | queries={routing['queries']}")

    # 🛡️ Hard-enforce Negasi Coding / File: pastikan tidak ada kebocoran flag coding/file jika user menyangkal
    if any(neg in user_msg_lower for neg in CODING_NEGATIONS):
        routing["is_coding"] = False
        routing["is_generate_file"] = False

    # 🔒 GUEST HARD-WALL SECURITY GUARD:
    # Tamu DILARANG KERAS mengakses dokumen/arsip internal PT Pindad dan Document Studio dalam kondisi apapun!
    # TAPI tamu TETAP BISA melakukan web search publik!
    if is_guest:
        routing["is_docwriter"] = False
        if routing.get("need_rag"):
            logger.info("[DISPATCHER_ROUTER] 🛡️ Guest Mode: Forcing need_rag=False (RAG hard-block for Guest)")
            routing["need_rag"] = False
            routing["query_judul"] = []
            # Jika tidak ada kapabilitas lain yang aktif, cek apakah web search bisa diaktifkan
            if not any([
                routing.get("is_coding"),
                routing.get("is_generate_file"),
                routing.get("is_web_search"),
                routing.get("requires_visual"),
                routing.get("need_analytic"),
                routing.get("is_ambiguous")
            ]):
                # Cek apakah precheck mengisyaratkan web publik → aktifkan web search, bukan chitchat
                _is_pub = precheck.get("is_public_web", False) if isinstance(precheck, dict) else False
                if _is_pub:
                    routing["is_web_search"] = True
                    if not routing.get("queries"):
                        routing["queries"] = [routing.get("key_subject") or user_message]
                    logger.info("[DISPATCHER_ROUTER] 🌐 Guest Mode: RAG blocked but is_public_web → activating web search")
                else:
                    routing["is_chitchat"] = True
        routing["is_multi_document"] = False

    return routing



def _build_fallback_routing(precheck: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback routing komprehensif (Safety Net) berbasis rule-based & sinyal precheck.
    Mengawal seluruh 15 fitur CAKRA AI agar tetap berfungsi optimal jika LLM Call 1
    mengalami timeout, beban antrean GPU, atau format parsing error.
    """
    from backend.app.services.pipeline.modes.mode_utils import build_rule_based_queries
    from backend.app.services.web_tools.url_reader import is_incidental_url

    user_message = (precheck.get("_user_message") or "").strip()
    user_lower = user_message.lower()
    is_guest = bool(precheck.get("is_guest", False))

    # 1. Bersihkan detected URLs dari URL insidental / error log
    raw_detected = precheck.get("_detected_urls", [])
    valid_detected_urls = [u for u in raw_detected if not is_incidental_url(u, user_message)]

    # 2. Inisialisasi skema lengkap 15 kapabilitas
    fallback = {
        "active_topic": str(precheck.get("previous_topic") or "Obrolan Cakra AI").strip(),
        "key_subject": str(precheck.get("previous_subject") or user_message[:50]).strip(),
        "need_rag": False,
        "queries": [],
        "query_judul": [],
        "search_tags": [],
        "context_snippets": [],
        "fetch_urls": [],  # Tidak lagi diisi oleh fallback — ditangani deterministik oleh mode_hub
        "is_url_read": bool(valid_detected_urls),
        "is_web_search": False,
        "is_coding": bool(precheck.get("is_coding", False)),
        "is_docwriter": bool(precheck.get("is_docwriter", False)) and not is_guest,
        "is_generate_file": bool(precheck.get("is_generate_file", False)),
        "is_generate_email": bool(precheck.get("is_generate_email", False)),
        "needs_code_analysis": False,
        "need_analytic": bool(precheck.get("need_analytic", False)),
        "is_self_correction": False,
        "is_ambiguous": bool(precheck.get("is_ambiguous", False)),
        "is_troubleshooting": bool(precheck.get("is_troubleshooting", False)),
        "is_comparative": bool(precheck.get("is_comparative", False)),
        "has_actionable_workflow": bool(precheck.get("has_actionable_workflow", False)),
        "is_deep_research": bool(precheck.get("is_deep_research", False)),
        "is_security_critical": bool(precheck.get("is_security_critical", False)),
        "requires_visual": bool(precheck.get("requires_visual", False)),
        "is_map_query": bool(precheck.get("is_map_query", False)),
        "is_chitchat": bool(precheck.get("is_chitchat", False) or precheck.get("is_greeting", False)),
        "is_multi_document": False,
        "is_multi_turn_task": False,
        "task_list": [],
        "pronoun": precheck.get("pronoun", "unknown"),
        "tone_hint": precheck.get("tone_hint", "formal"),
        "detected_language": "id",
        "session_title": None,
    }

    # 3. Sinyal Keyword Safety Net untuk 15 Fitur:
    # A. Visualisasi & Bagan Alir
    visual_kws = ["diagram", "flowchart", "grafik", "chart", "bagan alir", "visualisasi", "gantt", "kurva", "plot"]
    if any(k in user_lower for k in visual_kws):
        fallback["requires_visual"] = True

    # B. Pembuatan File Fisik
    file_kws = ["buatkan file", "bikin file", "ekspor", "export", "unduh excel", "unduh word", ".xlsx", ".docx", ".pdf"]
    if any(k in user_lower for k in file_kws):
        fallback["is_generate_file"] = True

    # C. Persuratan Dinas & Email
    email_kws = ["buatkan email", "draf email", "nota dinas", "surat dinas", "surat tugas", "memo dinas"]
    if any(k in user_lower for k in email_kws):
        fallback["is_generate_email"] = True

    # D. Troubleshooting & Error
    trouble_kws = ["error", "bug", "gagal", "crash", "traceback", "kenapa tidak bisa", "tidak connect", "timeout", "econnrefused"]
    if any(k in user_lower for k in trouble_kws):
        fallback["is_troubleshooting"] = True

    # E. Komparasi / Perbandingan
    comp_kws = ["bandingkan", "perbedaan", "vs", "komparasi", "kelebihan dan kekurangan", "pilih mana", "lebih bagus mana"]
    if any(k in user_lower for k in comp_kws):
        fallback["is_comparative"] = True

    # F. Workflow & SOP Actionable
    sop_kws = ["sop", "prosedur", "tahapan", "alur pengajuan", "syarat izin", "langkah-langkah", "tata cara"]
    if any(k in user_lower for k in sop_kws):
        fallback["has_actionable_workflow"] = True

    # G. Deep Research / Enterprise Architecture
    research_kws = ["analisis mendalam", "kajian", "studi kelayakan", "arsitektur sistem", "evaluasi komprehensif"]
    if any(k in user_lower for k in research_kws):
        fallback["is_deep_research"] = True

    # H. Security Critical
    sec_kws = ["keamanan", "enkripsi", "jwt", "otentikasi", "vulnerability", "hardening", "owasp", "bcrypt", "password hash"]
    if any(k in user_lower for k in sec_kws):
        fallback["is_security_critical"] = True

    # I. Map / Lokasi
    map_kws = ["lokasi", "alamat", "dimana gedung", "peta", "turen", "bandung", "fasilitas pindad"]
    if any(k in user_lower for k in map_kws):
        fallback["is_map_query"] = True

    # J. Deteksi Ambiguitas (Pesan umum ringkas tanpa detail)
    ambiguous_prompts = [
        "aturan cuti", "soal cuti", "prosedur mutasi", "buatkan surat dinas", "bikin nota dinas",
        "diagram alur", "bikin aplikasi", "buatkan web", "aplikasi error", "sistem down"
    ]
    if any(p in user_lower for p in ambiguous_prompts) and len(user_message.split()) <= 4:
        fallback["is_ambiguous"] = True

    # K. Dokumen & Regulasi Internal (RAG)
    rag_kws = [
        "skep", "sk", "sop", "pkb", "peraturan", "keputusan", "surat edaran", "direksi",
        "pindad", "organisasi", "tata kerja", "otk", "cuti", "mutasi", "gaji", "tunjangan",
        "alutsista", "senjata", "munisi", "kendaraan khusus", "anoa", "komodo", "ss2", "harimau"
    ]
    is_doc_intent = any(k in user_lower for k in rag_kws) or precheck.get("need_rag_hint") or precheck.get("is_doc_query")
    if is_doc_intent and not is_guest and not fallback["is_ambiguous"]:
        fallback["need_rag"] = True
        fallback["query_judul"] = [user_message]
        fallback["queries"] = build_rule_based_queries(user_message, fallback["key_subject"], fallback["active_topic"])
        fallback["is_web_search"] = False

    # L. Web Search & Web Reader
    web_kws = ["berita", "kabar terbaru", "kabar terkini", "kabar pasar", "kabar bumn", "kabar dunia", "terkini", "hari ini", "terbaru", "cuaca besok", "cuaca 7 hari", "saham", "kurs"]
    is_greeting_kws = ["hai", "halo", "apa kabar", "gimana kabar", "kabarnya", "selamat pagi", "selamat siang", "terima kasih", "makasih", "semangat"]
    is_greeting_msg = any(kw in user_lower for kw in is_greeting_kws)
    if any(k in user_lower for k in web_kws) and not fallback["need_rag"] and not is_greeting_msg:
        fallback["is_web_search"] = True
        fallback["queries"] = [user_message]

    # URL Reader kini ditangani deterministik oleh mode_hub (bukan di fallback routing)
    # Tidak perlu lagi mematikan is_web_search berdasarkan fetch_urls di sini

    # N. Chitchat & Sapaan
    if is_greeting_msg:
        if not fallback["need_rag"] and not fallback["is_coding"] and not fallback["is_generate_file"]:
            fallback["is_chitchat"] = True
            fallback["is_web_search"] = False
            fallback["queries"] = []

    fallback["response_format"] = precheck.get("response_format", "standard")
    fallback["format_constraint"] = precheck.get("format_constraint")

    # 4. Strict Guest Isolation Guard
    if is_guest:
        fallback["need_rag"] = False
        fallback["is_docwriter"] = False
        fallback["query_judul"] = []
        # Jangan hapus queries/is_web_search jika memang ini adalah web search publik!
        if not fallback.get("is_web_search"):
            fallback["queries"] = []

    logger.info(f"[DISPATCHER_ROUTER] Fallback routing constructed successfully | need_rag={fallback['need_rag']} | is_coding={fallback['is_coding']} | is_ambiguous={fallback['is_ambiguous']} | requires_visual={fallback['requires_visual']}")
    return fallback

async def dispatch_preset_route(
    user_message: str,
    forced_mode: str = "auto",
    is_first_chat: bool = False,
    context_history_str: str = "",
    previous_topic: Optional[str] = None,
    previous_subject: Optional[str] = None,
    precheck: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    """
    Mini routing analyzer untuk jalur preset/bypass dengan multi-turn reasoning.
    Menganalisis pesan user dan mengembalikan dict routing:
      - session_title  : str | None  — hanya jika is_first_chat=True
      - is_ambiguous   : bool        — True jika pesan terlalu umum/ambigu
      - requires_visual: bool        — True jika perlu output diagram/grafik
      - need_analytic  : bool        — True jika perlu analisis data/statistik
      - queries        : List[str]   — Query pencarian mandiri hasil penggabungan konteks multi-turn
      - query_judul    : List[str]   — Target judul/regulasi jika terdeteksi
      - key_subject    : str         — Subjek spesifik yang sedang dibahas
      - active_topic   : str         — Topik umum
    """
    if not user_message or not user_message.strip():
        return {}

    precheck = precheck or {}

    from datetime import datetime
    from backend.app.services.pipeline.prompts.core_prompts import build_preset_dispatcher_prompt
    from backend.app.services.pipeline.modes.mode_utils import format_session_title, GENERIC_SESSION_TITLES

    prompt = build_preset_dispatcher_prompt(
        user_message=user_message.strip(),
        forced_mode=forced_mode,
        is_first_chat=is_first_chat,
        context_history_str=context_history_str,
        previous_topic=previous_topic,
        previous_subject=previous_subject,
    )
    model = getattr(settings, "MODEL_ROUTER", "/home/qisthi/models/gemma-4-31B-it-AWQ")
    router_ctx = getattr(settings, "NUM_CTX_ROUTER", 4096)

    try:
        t0 = datetime.now()
        res_json = await generate_json_response(
            model_name=model,
            messages=[{"role": "user", "content": prompt}],
            request=request,
            temperature=0.1,
            top_p=0.2,
            keep_alive=-1,
            num_ctx=router_ctx,
            num_predict=150,
            timeout=8.0,
        )
        duration_ms = (datetime.now() - t0).total_seconds() * 1000

        if not isinstance(res_json, dict):
            return {}

        result: Dict[str, Any] = {}

        # Multi-turn queries
        if res_json.get("queries") and isinstance(res_json["queries"], list):
            valid_q = [str(q).strip() for q in res_json["queries"] if str(q).strip()]
            if valid_q:
                result["queries"] = valid_q

        # Query judul & search tags
        raw_preset_qj = res_json.get("query_judul")
        raw_preset_st = res_json.get("search_tags")
        clean_qj, clean_st = _sanitize_rag_title_and_tags(
            query_judul_raw=raw_preset_qj,
            search_tags_raw=raw_preset_st,
            user_message=user_message,
            key_subject=res_json.get("key_subject", ""),
            active_topic=res_json.get("active_topic", ""),
            need_rag=forced_mode in ["documents", "document", "rag", "focus", "audit", "compliance", "redteam"],
        )
        if clean_qj:
            result["query_judul"] = clean_qj
        if clean_st:
            result["search_tags"] = clean_st
        logger.info(f"[PRESET_DISPATCHER] Sanitized query_judul: {result.get('query_judul', [])} | search_tags: {result.get('search_tags', [])}")

        # Proteksi sapaan di preset:
        user_msg_p_lower = user_message.lower()
        is_preset_greeting = (
            bool(precheck.get("is_greeting"))
            or bool(precheck.get("is_chitchat"))
            or (any(kw in user_msg_p_lower for kw in ["halo", "hai", "pagi", "siang", "sore", "malam", "assalamualaikum", "sampurasun", "apa kabar"]) and len(user_message.split()) <= 4)
        ) and not any(kw in user_msg_p_lower for kw in ["dokumen", "regulasi", "peraturan", "pkb", "sop", "skep", "pasal", "kebijakan", "surat", "cuti", "gaji", "tunjangan", "dinas", "kpi", "audit"])
        if is_preset_greeting:
            result["is_chitchat"] = True
            result["need_rag"] = False
            result["queries"] = []
            result["query_judul"] = []
            result["search_tags"] = []
            logger.info("[PRESET_DISPATCHER] 💬 Greeting detected in preset mode -> forcing need_rag=False, is_chitchat=True")

        # Entity tracking
        if res_json.get("key_subject") and isinstance(res_json["key_subject"], str):
            result["key_subject"] = res_json["key_subject"].strip()
        if res_json.get("active_topic") and isinstance(res_json["active_topic"], str):
            result["active_topic"] = res_json["active_topic"].strip()

        # Target brain assets & live refetch
        if res_json.get("target_brain_assets"):
            tb = res_json["target_brain_assets"]
            if isinstance(tb, list):
                result["target_brain_assets"] = [int(x) for x in tb if str(x).isdigit()]
                result["session_chunk_ids"] = result["target_brain_assets"]
        if res_json.get("needs_live_refetch") is True:
            result["needs_live_refetch"] = True

        # Multi-turn history requirement
        if res_json.get("needs_history") is True or result.get("target_brain_assets"):
            result["needs_history"] = True
        elif is_first_chat:
            result["needs_history"] = False
        elif (
            (precheck and precheck.get("is_replying_to_wizard"))
            or (precheck and precheck.get("is_replying_to_assistant_question"))
        ):
            result["needs_history"] = True

        # Ambiguity flag & Universal Responder Synchronization:
        precheck = precheck or {}
        is_replying_to_wizard = (
            precheck.get("is_replying_to_wizard") 
            or precheck.get("is_wizard_confirmation") 
            or ("[RESPONDER_ACTION: WIZARD_DITANYAKAN]" in context_history_str)
        )
        has_prior_visual = (
            precheck.get("has_prior_visual") 
            or ("[RESPONDER_ACTION: VISUAL_DIBUAT]" in context_history_str)
        )
        has_prior_coding = (
            precheck.get("has_prior_coding") 
            or ("[RESPONDER_ACTION: KODE_FILE_DIBUAT]" in context_history_str)
        )
        has_prior_chitchat = (
            precheck.get("has_prior_chitchat") 
            or ("[RESPONDER_ACTION: CHITCHAT_DIJAWAB]" in context_history_str)
        )
        has_prior_context = bool(context_history_str and context_history_str.strip())
        is_detailed_confirmation = any(user_message.strip().lower().startswith(kw) for kw in ["gunakan ", "pilih ", "fokus pada ", "rujuk ", "opsi ", "chart ", "buatkan ", "bikin "]) or len(user_message.strip()) > 40

        # Jika user merespon/mengonfirmasi pilihan wizard dari Responder:
        if is_replying_to_wizard:
            # 🛡️ ANTI-LOOP: Jangan pernah tandai ambigu lagi saat user menjawab wizard!
            result["is_ambiguous"] = False
            logger.info("[PRESET_DISPATCHER] 🎯 Resolving Wizard Answer from Responder -> Enforcing is_ambiguous=False")
            
            # Jika user menjawab chart/pie/bar di jalur preset:
            user_lower_p = user_message.lower()
            if any(w in user_lower_p for w in ["pie", "bar", "line", "chart", "grafik", "diagram"]):
                result["requires_visual"] = True
                if any(w in user_lower_p for w in ["pie", "bar", "line", "chart", "grafik"]):
                    result["visual_types"] = ["chart"]
                elif any(w in user_lower_p for w in ["diagram", "alur"]):
                    result["visual_types"] = ["mermaid"]
                    
            # Rewriting query mandiri jika perlu
            if precheck.get("last_wizard") and (not result.get("queries") or len(result["queries"][0].split()) <= 2):
                wiz_title = precheck["last_wizard"].get("title", "")
                result["queries"] = [f"{wiz_title} {user_message}".strip()]
        elif res_json.get("is_ambiguous") is True and not is_detailed_confirmation and not has_prior_context:
            result["is_ambiguous"] = True
            result["ambiguity_reason"] = str(res_json.get("ambiguity_reason") or "").strip()
            logger.info(f"[PRESET_DISPATCHER] ❓ Ambiguity detected -> reason: '{result['ambiguity_reason']}'")
        is_guest_user = bool(precheck.get("is_guest", False))
        if not is_guest_user and (
            precheck.get("is_docwriter")
            or res_json.get("is_docwriter") is True
            or re.search(r'\b(buka|open|tampil(kan)?|muncul(kan)?|akses)\b.{0,25}\b(editor|writer|studio)\b', user_message.lower())
            or any(kw in user_message.lower() for kw in ["buka editor", "dokumen writer", "dokumen editor", "draft surat", "draf surat", "draft skep", "draf skep", "draft se", "draf se", "draft memo", "draf memo", "draft nota dinas", "draf nota dinas", "siapkan draft", "siapkan draf", "buatkan draft", "buatkan draf"])
        ):
            result["is_docwriter"] = True
            result["is_ambiguous"] = False

        # Kelanjutan visual refinement jika Call 2 sebelumnya telah membuat visual
        user_lower_check = user_message.lower()
        if has_prior_visual and any(w in user_lower_check for w in ["warna", "ganti", "ubah", "potongan", "pie", "bar", "chart", "grafik", "diagram"]):
            result["requires_visual"] = True
            if not result.get("visual_types"):
                result["visual_types"] = [precheck.get("last_visual_type") or "chart"]

        # Visual flag & sub-types
        raw_vt = res_json.get("visual_types") or res_json.get("visual_type") or []
        if res_json.get("requires_visual") is True or raw_vt:
            result["requires_visual"] = True
            if isinstance(raw_vt, str):
                result["visual_types"] = [raw_vt.strip().lower()]
            elif isinstance(raw_vt, list):
                result["visual_types"] = [str(v).strip().lower() for v in raw_vt if v]
            else:
                result["visual_types"] = []
                
            # Auto-detect visual_types jika kosong
            if not result["visual_types"]:
                user_lower = user_message.lower()
                if any(w in user_lower for w in [
                    "grafik", "chart", "bar", "pie", "line", "garis", "kurva", "area", 
                    "donut", "donat", "radar", "scatter", "histogram", "heatmap", "funnel", 
                    "gauge", "tren", "trend", "distribusi", "fluktuasi", "statistik", "metrik"
                ]):
                    result["visual_types"].append("chart")
                if any(w in user_lower for w in [
                    "diagram", "alur", "flowchart", "arsitektur", "bagan", "sequence", 
                    "erd", "mindmap", "peta konsep", "hierarki", "hirarki", "skema"
                ]):
                    result["visual_types"].append("mermaid")
                if any(w in user_lower for w in [
                    "jadwal", "timeline", "gantt", "roadmap", "milestone", "sprint", "tenggat", "jadwal proyek"
                ]):
                    result["visual_types"].append("gantt")
                if any(w in user_lower for w in [
                    "tabel", "grid", "datagrid", "spreadsheet", "rekap data", "kolom"
                ]):
                    result["visual_types"].append("datagrid")
                if any(w in user_lower for w in [
                    "peta", "map", "lokasi", "koordinat", "geografis", "denah", "posisi"
                ]):
                    result["visual_types"].append("map")
                if any(w in user_lower for w in [
                    "infografis", "infographic", "dashboard", "ringkasan visual", "kpi"
                ]):
                    result["visual_types"].append("infographic")
                if any(w in user_lower for w in [
                    "slide", "slides", "presentasi", "presentation", "powerpoint", "ppt", "dek presentasi"
                ]):
                    result["visual_types"].append("slides")
                if not result["visual_types"]:
                    result["visual_types"] = ["mermaid"]

        # Modular capability flags (Garansi 18 Kapabilitas Lengkap & Utuh)
        for flag in [
            "need_analytic", "is_troubleshooting", "is_comparative", 
            "has_actionable_workflow", "is_deep_research", "is_security_critical", 
            "is_generate_file", "is_docwriter", "is_generate_email", 
            "is_coding", "is_url_read", "is_web_search", "is_map_query"
        ]:
            if res_json.get(flag) is True:
                result[flag] = True

        # Session title — hanya jika first_chat
        if is_first_chat:
            raw_title = res_json.get("session_title")
            if isinstance(raw_title, str) and raw_title.strip() and raw_title.strip().lower() not in GENERIC_SESSION_TITLES:
                result["session_title"] = format_session_title(raw_title)

        # Kembalikan strict sparse dictionary (hanya nilai bernilai True/non-empty)
        clean_result = {
            k: v for k, v in result.items()
            if v is not False and v is not None and v != [] and v != ""
        }
        logger.info(f"⚡ [PRESET_DISPATCHER] Result in {duration_ms:.1f}ms: {clean_result} (mode={forced_mode}, first_chat={is_first_chat})")
        return clean_result

    except Exception as e:
        logger.warning(f"[PRESET_DISPATCHER] Gagal via LLM: {e}")


    # Fallback: jika first_chat, coba generate title dari teks user saja
    if is_first_chat:
        from backend.app.services.pipeline.modes.mode_utils import format_session_title, GENERIC_SESSION_TITLES
        formatted = format_session_title(user_message)
        if formatted and formatted.strip().lower() not in GENERIC_SESSION_TITLES:
            return {"session_title": formatted}

    return {}


async def generate_preset_dispatcher_title(user_message: str, request: Optional[Request] = None) -> Optional[str]:
    """
    Menghasilkan judul sesi jalur preset.
    """
    result = await dispatch_preset_route(
        user_message=user_message,
        forced_mode="auto",
        is_first_chat=True,
        request=request,
    )
    return result.get("session_title")



async def generate_dispatcher_web_queries(user_message: str, request: Optional[Request] = None) -> List[str]:
    """
    Menghasilkan 1-2 kata kunci pencarian web cerdas via Gemma 4 e4b
    dari pesan user yang santai/penuh keluhan (< 300 ms).
    """
    if not user_message or not user_message.strip():
        return []

    from datetime import datetime
    from backend.app.services.web_tools.web_search import sanitize_web_query

    clean_fallback = sanitize_web_query(user_message.strip())
    model = getattr(settings, "MODEL_ROUTER", "/home/qisthi/models/gemma-4-31B-it-AWQ")
    router_ctx = getattr(settings, "NUM_CTX_ROUTER", 4096)

    now = datetime.now()
    prompt = (
        "Kamu adalah Cakra Search Query Optimizer.\n"
        f"JANGKAR TEMPORAL: Tahun berjalan saat ini adalah {now.year} (Hari ini: {now.strftime('%d-%m-%Y')}).\n"
        "Tugas: Ubah pesan pengguna yang santai, penuh keluhan, emosional, atau bahasa gaul menjadi 1-2 kata kunci pencarian web/Google yang bersih, objektif, dan efektif mencari berita/fakta terpercaya.\n"
        f"ATURAN TAHUN: Jika pesan menanyakan hal terkini/terbaru/viral, gunakan tahun {now.year} (atau rentang {now.year-1}-{now.year}) atau kata kunci bersih tanpa tahun. DILARANG KERAS menyematkan tahun lampau ({now.year-2} ke bawah) ke dalam query kecuali diminta eksplisit oleh user.\n"
        f'Pesan user: "{user_message.strip()}"\n'
        "Format output WAJIB JSON murni tanpa markdown:\n"
        '{"queries": ["kata kunci 1", "kata kunci 2"]}'
    )

    try:
        t0 = datetime.now()
        res_json = await generate_json_response(
            model_name=model,
            messages=[{"role": "user", "content": prompt}],
            request=request,
            temperature=0.1,
            top_p=0.3,
            keep_alive=-1,
            num_ctx=router_ctx,
            num_predict=50,
            timeout=8.0,
        )
        duration_ms = (datetime.now() - t0).total_seconds() * 1000
        queries = res_json.get("queries") if isinstance(res_json, dict) else None
        if isinstance(queries, list) and queries:
            clean_queries = [sanitize_web_query(str(q), user_message=user_message) for q in queries if str(q).strip()]
            clean_queries = [q for q in clean_queries if q]
            if clean_queries:
                logger.info(f"⚡ [DISPATCHER_WEB_QUERIES] Generated {clean_queries} in {duration_ms:.1f}ms (from: '{user_message}')")
                return clean_queries
    except Exception as e:
        logger.warning(f"[DISPATCHER_WEB_QUERIES] Gagal generate query via LLM: {e}")

    return [clean_fallback] if clean_fallback else [user_message.strip()]


