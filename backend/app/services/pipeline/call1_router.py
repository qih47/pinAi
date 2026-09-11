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
from typing import Dict, Any, List, Optional, Tuple
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

def _sanitize_web_query(query: str, user_message: str = "") -> str:
    """
    Bersihkan prefix filler kata bahasa Indonesia dari web search query
    dan tangani over-expansion / disambiguasi semantik (seperti 'demo' unjuk rasa vs 'demo produk').
    Contoh: "data lain qwen3.8" → "qwen3.8"
    """
    cleaned = query.strip()
    # Ulangi hingga semua prefix filler terkikis (bisa berlapis)
    for _ in range(5):
        new_cleaned = _WEB_QUERY_FILLER_PREFIXES.sub("", cleaned).strip()
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned

    # 🚨 Disambiguasi Semantik: "demo" (unjuk rasa massa) vs "demo produk"
    lower_q = cleaned.lower()
    if "demo produk" in lower_q or "pameran teknologi" in lower_q or "jadwal pameran" in lower_q:
        user_msg_lower = (user_message or "").lower()
        civic_hints = ["jakarta", "dpr", "monas", "patung kuda", "istana", "bandung", "surabaya", "malang", "hari ini", "terkini", "masih ada", "jalan", "polisi", "buruh", "mahasiswa"]
        product_hints = ["produk", "software", "aplikasi", "alat", "senjata", "fitur", "gadget", "hp", "mobil", "motor"]
        
        # Jika konteks user adalah situasi kota/wilayah dan TIDAK meminta produk secara eksplisit
        if any(h in user_msg_lower for h in civic_hints) and not any(p in user_msg_lower for p in product_hints):
            cleaned = re.sub(r'demo\s+produk\s*', 'demonstrasi unjuk rasa ', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'(&\s*)?(jadwal\s+)?pameran(\s+teknologi)?\s*', '', cleaned, flags=re.IGNORECASE).strip()
            if "unjuk rasa" not in cleaned.lower() and "demonstrasi" not in cleaned.lower():
                cleaned = f"demonstrasi unjuk rasa {cleaned}"

    return cleaned.strip() or query.strip()


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
    model_name: Optional[str] = None,
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

    if previous_topic and not precheck.get("previous_topic"):
        precheck["previous_topic"] = previous_topic
    if previous_subject and not precheck.get("previous_subject"):
        precheck["previous_subject"] = previous_subject

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

    # Alokasi num_predict dinamis hemat token untuk kecepatan respons maksimal (~1.2s - 1.5s)
    dynamic_predict = 350 if is_first_chat else 250

    # Tentukan model yang digunakan
    effective_model = model_name or getattr(settings, "MODEL_ROUTER", "gemma4:e4b")

    # Kunci num_ctx adaptif: Gemma (vocab 256k -> ~3.1k tokens) cukup 4096. Model lain (Granite/Llama vocab 128k -> ~5.1k tokens) butuh 8192.
    if any(k in effective_model.lower() for k in ["granite", "llama", "mistral", "qwen"]):
        router_ctx = 8192
    else:
        router_ctx = getattr(settings, "NUM_CTX_ROUTER", 4096)

    logger.info(
        f"[CALL1] Executing routing | model={effective_model} | user_msg_len={len(user_message)} | stripped_len={len(stripped_message)} | "
        f"dynamic_num_predict={dynamic_predict} | prompt_chars={len(system_prompt) + len(stripped_message)} | ctx={router_ctx}"
    )

    try:
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


        # Bersihkan setiap field bernilai False, None, atau empty array agar benar-benar sparse
        clean_sparse_json = {
            k: v for k, v in routing_json.items() 
            if v is not False and v is not None and v != [] and v != ""
        }
        import json
        logger.info(f"[CALL1] 📦 Raw JSON Payload dari LLM:\n{json.dumps(clean_sparse_json, indent=2)}")

        routing = _validate_and_normalize_routing(
            clean_sparse_json, 
            precheck,
            is_first_chat=is_first_chat,
            user_message=user_message,
            is_guest=is_guest,
            context_history_str=context_history_str,
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
        "wizard": None,
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
    routing["is_coding"] = bool(routing_json.get("is_coding", False))
    routing["is_troubleshooting"] = bool(routing_json.get("is_troubleshooting", False))
    routing["is_comparative"] = bool(routing_json.get("is_comparative", False))
    routing["has_actionable_workflow"] = bool(routing_json.get("has_actionable_workflow", False))
    routing["is_deep_research"] = bool(routing_json.get("is_deep_research", False))
    routing["is_security_critical"] = bool(routing_json.get("is_security_critical", False))
    routing["is_chitchat"] = bool(routing_json.get("is_chitchat", False))
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
        routing["need_rag"] = False
        routing["queries"] = []
        routing["query_judul"] = []
        routing["search_tags"] = []
        logger.info("[CALL1] 💬 Simple greeting detected -> forcing need_rag=False, is_chitchat=True, clearing query_judul & search_tags")
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

        if not routing["visual_types"]:
            routing["visual_types"] = ["mermaid"]
            
    routing["is_map_query"] = bool(routing_json.get("is_map_query", False)) or bool(precheck.get("is_map_query", False))
    if routing["is_map_query"]:
        routing["need_rag"] = False
        routing["query_judul"] = []
        logger.info("[CALL1] 🌍 is_map_query detected -> overriding need_rag=False")
    
    raw_chunk_ids = routing_json.get("session_chunk_ids", [])
    if isinstance(raw_chunk_ids, list):
        routing["session_chunk_ids"] = [int(x) for x in raw_chunk_ids if str(x).isdigit()]
    elif isinstance(raw_chunk_ids, (int, str)) and str(raw_chunk_ids).isdigit():
        routing["session_chunk_ids"] = [int(raw_chunk_ids)]
    else:
        routing["session_chunk_ids"] = []
    
    from backend.app.services.pipeline.intent_dictionary import (
        is_explicit_web_search_required,
        is_pure_opinion_or_chitchat
    )

    # Deteksi cerdas opini/afirmasi/curhat/keluh kesah: jika user memberi tanggapan opini tanpa meminta cari di web
    is_opinion = is_pure_opinion_or_chitchat(user_message)
    is_explicit_web = is_explicit_web_search_required(user_message)

    # Otomatis aktifkan is_web_search jika ada queries dan bukan dokumen internal / bukan koding / bukan cuaca saat ini
    if is_current_weather:
        logger.info("[CALL1] ⛅ Cuaca lokal saat ini terdeteksi. Mematikan is_web_search agar dijawab instan via Ambient Context Persona.")
        routing["is_web_search"] = False
        routing["queries"] = []
        routing["is_chitchat"] = True
    elif is_opinion and not is_explicit_web:
        logger.info("[CALL1] 💬 Pesan opini/afirmasi/chitchat terdeteksi. Mematikan is_web_search agar dijawab empatik & reflektif via Persona Core.")
        routing["is_web_search"] = False
        routing["queries"] = []
        routing["is_chitchat"] = True
    elif routing_json.get("queries") and not routing["need_rag"] and not routing["is_coding"] and not routing["is_generate_file"]:
        # Hanya aktifkan web search jika memang diminta di JSON atau terdeteksi di spektrum web search
        if routing_json.get("is_web_search", False) or is_explicit_web:
            routing["is_web_search"] = True
        else:
            routing["is_web_search"] = False
            routing["queries"] = []
            routing["is_chitchat"] = True
    else:
        routing["is_web_search"] = bool(routing_json.get("is_web_search", False))

    # 🌐 Penyelarasan Yurisdiksi: Jika model memilih Data Luar (Web Search) tanpa mode dokumen internal eksplisit, prioritaskan Web Search
    forced_mode_clean = str(precheck.get("forced_mode") or "").lower().strip()
    is_forced_doc_mode = forced_mode_clean in ["documents", "document", "rag"]
    if routing["is_web_search"] and routing["need_rag"] and not is_forced_doc_mode:
        routing["need_rag"] = False
        routing["query_judul"] = []
        logger.info("[CALL1] 🌐 Resolving dual-intent conflict: is_web_search takes priority over need_rag for external data")

    # ── 🔄 UNIVERSAL BIDIRECTIONAL CONTEXT SYNCHRONIZATION (CALL 2 ➔ CALL 1) ──
    # Mengetahui profil tindakan Call 2 pada turn sebelumnya (wizard, visual, coding, chitchat, RAG)
    is_replying_to_wizard = bool(
        precheck.get("is_replying_to_wizard") 
        or precheck.get("is_wizard_confirmation") 
        or (context_history_str and "[CALL2_ACTION: WIZARD_DITANYAKAN]" in context_history_str)
    )
    has_prior_visual = bool(
        precheck.get("has_prior_visual") 
        or (context_history_str and "[CALL2_ACTION: VISUAL_DIBUAT]" in context_history_str)
    )
    has_prior_coding = bool(
        precheck.get("has_prior_coding") 
        or (context_history_str and "[CALL2_ACTION: KODE_FILE_DIBUAT]" in context_history_str)
    )
    has_prior_chitchat = bool(
        precheck.get("has_prior_chitchat") 
        or (context_history_str and "[CALL2_ACTION: CHITCHAT_DIJAWAB]" in context_history_str)
    )

    # 1. 🧙 Penanganan Konfirmasi Wizard:
    if is_replying_to_wizard:
        # 🛡️ ANTI-LOOP: User sedang menjawab pertanyaan wizard Call 2, TIDAK BOLEH ambigu lagi!
        routing["is_ambiguous"] = False
        logger.info("[CALL1] 🎯 Resolving Wizard Answer from Call 2 -> Overriding is_ambiguous=False")
        
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
            logger.info(f"[CALL1] 📊 Continuous Visual Refinement detected -> requires_visual=True, visual_types={routing['visual_types']}")

    # 3. 💻 Penanganan Kelanjutan Koding (Call 2 baru saja membuat kode/file):
    if has_prior_coding and not routing["need_rag"]:
        coding_cont_kw = ["tambah", "fitur", "fungsi", "error", "bug", "perbaiki", "lanjut", "jalankan", "file", "kode", "skrip", "refactor", "ubah fungsi"]
        if any(w in user_msg_lower for w in coding_cont_kw) and len(user_message.split()) <= 15:
            routing["is_coding"] = True
            routing["is_chitchat"] = False
            logger.info("[CALL1] 💻 Continuous Coding Refinement detected -> is_coding=True")

    # 4. 💬 Penanganan Kelanjutan Basa-basi (Call 2 baru saja menjawab chitchat):
    if has_prior_chitchat and not routing["need_rag"] and not routing["is_coding"] and not routing["requires_visual"]:
        casual_ack_kw = ["mantap", "siap", "oke", "ok", "haha", "wkwk", "makasih", "terima kasih", "thanks", "tq", "sip", "semangat", "keren", "bener", "betul", "iya", "nice", "good"]
        if any(w in user_msg_lower for w in casual_ack_kw) and len(user_message.split()) <= 10:
            routing["is_chitchat"] = True
            routing["is_web_search"] = False
            routing["is_ambiguous"] = False
            logger.info("[CALL1] 💬 Continuous Casual / Chitchat flow detected -> is_chitchat=True")

    # ── ATURAN STRICT MODE DOKUMEN (USER EXPLICIT INTENT OVERRIDE) ───────────
    # Jika user secara manual mengunci Mode Dokumen (forced_mode), pastikan need_rag aktif HANYA jika bukan web search, koding, atau chitchat
    is_explicit_doc_mode = (
        is_forced_doc_mode
        and not routing.get("is_web_search")
        and not routing.get("is_chitchat")
        and not routing.get("is_coding")
        and not is_simple_greeting
    )
    if is_explicit_doc_mode and not routing["is_ambiguous"]:
        routing["need_rag"] = True
        routing["is_web_search"] = False
        routing["is_chitchat"] = False
        if not routing.get("queries"):
            routing["queries"] = [user_message]
        logger.info(f"[CALL1] 📚 Explicit Document Mode enforced: need_rag=True, queries={routing['queries']}")

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
        logger.info("[CALL1] 📄 Document Writer intent enforced -> is_docwriter=True & is_ambiguous=False")

    # ── ATURAN STRICT AMBIGUOUS GATE ──────────────────────────────────────────
    # Jika is_ambiguous True, paksa need_rag = False dan kosongkan search queries/web search
    # agar sistem tidak buang latency RAG & langsung menanyakan klarifikasi/wizard ke user.
    if routing["is_ambiguous"]:
        routing["need_rag"] = False
        routing["queries"] = []
        routing["query_judul"] = []
        routing["search_tags"] = []
        routing["is_web_search"] = False
        logger.info(f"[CALL1] ❓ Ambiguity Gate activated -> reason: '{routing.get('ambiguity_reason')}'")

    # ── ATURAN STRICT MUTUAL EXCLUSION: need_rag VS is_web_search & is_coding ─────────────
    # need_rag (dokumen internal Pindad) dan is_web_search/is_coding DILARANG KERAS sama-sama aktif!
    if routing.get("is_web_search") and not is_explicit_doc_mode:
        # Jika web search aktif (misal DPR RI, berita, internet), matikan need_rag
        if routing.get("need_rag"):
            logger.info("[CALL1] 🌐 Web search is active. Setting need_rag=False.")
            routing["need_rag"] = False
    elif routing.get("need_rag"):
        routing["is_web_search"] = False
        if routing.get("is_coding"):
            logger.warning("[CALL1] 🛡️ Strict Mutual Exclusion: need_rag=True, forcing is_coding=False!")
            routing["is_coding"] = False
        if routing.get("is_generate_file"):
            logger.warning("[CALL1] 🛡️ Strict Mutual Exclusion: need_rag=True, forcing is_generate_file=False!")
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

    from backend.app.services.web_tools.url_reader import is_incidental_url

    fetch_urls = routing_json.get("fetch_urls", [])
    if isinstance(fetch_urls, list):
        routing["fetch_urls"] = [
            str(u).strip() for u in fetch_urls 
            if isinstance(u, str) and (u.strip().startswith("http://") or u.strip().startswith("https://"))
            and not is_incidental_url(str(u).strip(), user_message)
        ]
    elif isinstance(fetch_urls, str) and (fetch_urls.strip().startswith("http://") or fetch_urls.strip().startswith("https://")):
        clean_u = fetch_urls.strip()
        routing["fetch_urls"] = [clean_u] if not is_incidental_url(clean_u, user_message) else []
    else:
        routing["fetch_urls"] = []

    # Fallback jika model lupa menyertakan fetch_urls tapi ada URL/domain valid di pesan user
    if not routing["fetch_urls"] and precheck.get("_detected_urls"):
        valid_detected = [u for u in precheck.get("_detected_urls") if not is_incidental_url(u, user_message)]
        if valid_detected:
            routing["fetch_urls"] = valid_detected
            logger.info(f"[CALL1] Auto-populated fetch_urls from precheck detected URLs: {routing['fetch_urls']}")

    # Jika user memberikan URL untuk dibaca langsung, prioritaskan URL Reader daripada DuckDuckGo Web Search
    if routing["fetch_urls"]:
        routing["is_web_search"] = False

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
    logger.info(f"[CALL1] Sanitized query_judul: {routing['query_judul']} | search_tags: {routing['search_tags']}")

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

    # Override dengan precheck jika ada hint yang kuat (HANYA jika bukan public web search dan BUKAN chitchat/greeting/closing)
    if precheck.get("need_rag_hint") is True and not routing["need_rag"] and not routing.get("is_web_search") and not precheck.get("is_public_web") and not routing.get("is_chitchat") and not routing.get("is_greeting"):
        logger.warning("[CALL1] Precheck override: need_rag forced to True")
        routing["need_rag"] = True

    if precheck.get("is_coding") and not routing["is_coding"]:
        logger.warning("[CALL1] Precheck override: is_coding forced to True")
        routing["is_coding"] = True
        

    if precheck.get("is_generate_email") and not routing["is_generate_email"]:
        logger.warning("[CALL1] Precheck override: is_generate_email forced to True")
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
            logger.warning("[CALL1] Sanitizing false positive is_web_search on visual diagram/chart task")
            routing["is_web_search"] = False
            routing["queries"] = []

    # Sanity check: Jika user hanya meminta data dummy / perbandingan data di chat TANPA instruksi buat/ekspor file fisik atau coding
    if (routing.get("is_generate_file") or routing.get("is_coding")) and not precheck.get("is_coding"):
        user_msg_lower = precheck.get("_user_message", "").lower()
        file_export_keywords = ["file", "ekspor", "export", "unduh", "download", "excel", "xlsx", "csv", "docx", "word", "pdf", ".md", ".py", ".js", "script", "koding", "coding", "aplikasi", "komponen", "proyek", "project", "repo", "source code", "bikin file", "buat file"]
        has_file_intent = any(k in user_msg_lower for k in file_export_keywords)
        is_plain_data_query = any(k in user_msg_lower for k in ["data dummy", "data dumy", "data simulasi", "perbandingan penjualan", "contoh data", "tabel perbandingan", "tabel dummy", "angka dummy"])
        if is_plain_data_query and not has_file_intent:
            logger.warning("[CALL1] Sanitizing false positive is_generate_file/is_coding on plain chat data simulation request")
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

        if not routing["queries"]:
            routing["queries"] = rule_based_queries
            logger.info(f"[CALL1] Rule-based queries generated from subject/context: {routing['queries']}")
        else:
            # Amankan query dari gemma, tapi paksa query 1 jadi pure keyword user jika spesifik
            gemma_queries = [q.strip() for q in routing["queries"] if q and q.strip() and q.lower() != pure_keyword.lower()]
            if pure_keyword and pure_keyword.lower() not in ["ketentuan", "regulasi", "aturan"]:
                routing["queries"] = [pure_keyword] + gemma_queries[:2]
            else:
                routing["queries"] = gemma_queries[:3] if gemma_queries else rule_based_queries
            logger.info(f"[CALL1] Queries finalized: {routing['queries']}")

    # Final cleanup: buang string kosong / spasi dari queries
    if isinstance(routing.get("queries"), list):
        routing["queries"] = [q.strip() for q in routing["queries"] if isinstance(q, str) and q.strip()]

    # ── DETERMINISTIC MINIMAL 1-PARAMETER GUARD ───────────────────────────────
    # Memastikan tidak ada JSON hasil routing yang 'kosong' tanpa satupun parameter kapabilitas aktif
    capability_flags = [
        routing.get("need_rag"),
        routing.get("is_web_search"),
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
        web_keywords = ["berita", "kabar", "terkini", "hari ini", "terbaru", "cuaca besok", "cuaca 7 hari", "saham", "kurs", "presiden", "juara", "pilkada", "gempa"]
        map_keywords = ["lokasi", "alamat", "dimana", "peta", "gedung", "divisi", "turen", "bandung"]
        
        # 0. Prioritaskan Map / Location query
        if any(k in user_text for k in ["lokasi", "alamat", "dimana", "di mana", "koordinat", "peta", "letak pabrik"]) or precheck.get("is_map_query"):
            routing["is_map_query"] = True
            routing["need_rag"] = False
            routing["query_judul"] = []
            logger.info("[CALL1] 🛡️ Guard: Auto-activated is_map_query (location intent takes precedence)")
        elif any(k in user_text for k in visual_keywords) or precheck.get("requires_visual"):
            routing["requires_visual"] = True
            logger.info("[CALL1] 🛡️ Guard: Auto-activated requires_visual (visual/chart intent detected)")
        elif any(k in user_text for k in file_keywords):
            routing["is_generate_file"] = True
            logger.info("[CALL1] 🛡️ Guard: Auto-activated is_generate_file (file intent detected)")
        elif any(k in user_text for k in email_keywords):
            routing["is_generate_email"] = True
            logger.info("[CALL1] 🛡️ Guard: Auto-activated is_generate_email (email intent detected)")
        elif any(k in user_text for k in coding_keywords) or precheck.get("is_coding"):
            routing["is_coding"] = True
            logger.info("[CALL1] 🛡️ Guard: Auto-activated is_coding (coding intent detected)")
        elif any(k in user_text for k in rag_keywords) or precheck.get("is_doc_query") or precheck.get("need_rag_hint"):
            routing["need_rag"] = True
            if not routing.get("query_judul"):
                from backend.app.services.pipeline.modes.mode_utils import build_rule_based_queries
                routing["query_judul"] = [routing.get("key_subject") or user_message]
                routing["queries"] = build_rule_based_queries(user_message, routing.get("key_subject"), routing.get("active_topic"))
            logger.info(f"[CALL1] 🛡️ Guard: Auto-activated need_rag | query_judul={routing['query_judul']}")
        elif any(k in user_text for k in web_keywords):
            routing["is_web_search"] = True
            if not routing.get("queries"):
                routing["queries"] = [routing.get("key_subject") or user_message]
            logger.info(f"[CALL1] 🛡️ Guard: Auto-activated is_web_search | queries={routing['queries']}")
    # 🔒 GUEST HARD-WALL SECURITY GUARD:
    # Tamu DILARANG KERAS mengakses dokumen/arsip internal PT Pindad dan Document Studio dalam kondisi apapun!
    # TAPI tamu TETAP BISA melakukan web search publik!
    if is_guest:
        routing["is_docwriter"] = False
        if routing.get("need_rag"):
            logger.info("[CALL1] 🛡️ Guest Mode: Forcing need_rag=False (RAG hard-block for Guest)")
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
                    logger.info("[CALL1] 🌐 Guest Mode: RAG blocked but is_public_web → activating web search")
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
        "fetch_urls": valid_detected_urls,
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
    web_kws = ["berita", "kabar", "terkini", "hari ini", "terbaru", "cuaca besok", "cuaca 7 hari", "saham", "kurs"]
    if any(k in user_lower for k in web_kws) and not fallback["need_rag"]:
        fallback["is_web_search"] = True
        fallback["queries"] = [user_message]

    # M. Prioritas URL Reader atas Web Search
    if fallback["fetch_urls"]:
        fallback["is_web_search"] = False

    # N. Chitchat & Sapaan
    if any(kw in user_lower for kw in ["hai", "halo", "selamat pagi", "selamat siang", "terima kasih", "makasih", "semangat"]):
        if not fallback["need_rag"] and not fallback["is_coding"] and not fallback["is_generate_file"]:
            fallback["is_chitchat"] = True

    # 4. Strict Guest Isolation Guard
    if is_guest:
        fallback["need_rag"] = False
        fallback["is_docwriter"] = False
        fallback["query_judul"] = []
        # Jangan hapus queries/is_web_search jika memang ini adalah web search publik!
        if not fallback.get("is_web_search"):
            fallback["queries"] = []

    logger.info(f"[CALL1] Fallback routing constructed successfully | need_rag={fallback['need_rag']} | is_coding={fallback['is_coding']} | is_ambiguous={fallback['is_ambiguous']} | requires_visual={fallback['requires_visual']}")
    return fallback

async def generate_call1_preset_routing(
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

    from datetime import datetime
    from backend.app.services.pipeline.prompts.core_prompts import build_call1_preset_prompt
    from backend.app.services.pipeline.modes.mode_utils import format_session_title, GENERIC_SESSION_TITLES

    prompt = build_call1_preset_prompt(
        user_message=user_message.strip(),
        forced_mode=forced_mode,
        is_first_chat=is_first_chat,
        context_history_str=context_history_str,
        previous_topic=previous_topic,
        previous_subject=previous_subject,
    )
    model = getattr(settings, "MODEL_ROUTER", "gemma4:e4b")
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
            need_rag=forced_mode in ["documents", "document", "rag", "focus", "audit", "compliance"],
        )
        if clean_qj:
            result["query_judul"] = clean_qj
        if clean_st:
            result["search_tags"] = clean_st
        logger.info(f"[CALL1_PRESET_ROUTING] Sanitized query_judul: {result.get('query_judul', [])} | search_tags: {result.get('search_tags', [])}")

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
            logger.info("[CALL1_PRESET_ROUTING] 💬 Greeting detected in preset mode -> forcing need_rag=False, is_chitchat=True")

        # Entity tracking
        if res_json.get("key_subject") and isinstance(res_json["key_subject"], str):
            result["key_subject"] = res_json["key_subject"].strip()
        if res_json.get("active_topic") and isinstance(res_json["active_topic"], str):
            result["active_topic"] = res_json["active_topic"].strip()

        # Ambiguity flag & Universal Call 2 Synchronization:
        precheck = precheck or {}
        is_replying_to_wizard = precheck.get("is_replying_to_wizard") or precheck.get("is_wizard_confirmation") or ("[CALL2_ACTION: WIZARD_DITANYAKAN]" in context_history_str)
        has_prior_visual = precheck.get("has_prior_visual") or ("[CALL2_ACTION: VISUAL_DIBUAT]" in context_history_str)
        has_prior_coding = precheck.get("has_prior_coding") or ("[CALL2_ACTION: KODE_FILE_DIBUAT]" in context_history_str)
        has_prior_chitchat = precheck.get("has_prior_chitchat") or ("[CALL2_ACTION: CHITCHAT_DIJAWAB]" in context_history_str)
        has_prior_context = bool(context_history_str and context_history_str.strip())
        is_detailed_confirmation = any(user_message.strip().lower().startswith(kw) for kw in ["gunakan ", "pilih ", "fokus pada ", "rujuk ", "opsi ", "chart ", "buatkan ", "bikin "]) or len(user_message.strip()) > 40

        # Jika user merespon/mengonfirmasi pilihan wizard dari Call 2:
        if is_replying_to_wizard:
            # 🛡️ ANTI-LOOP: Jangan pernah tandai ambigu lagi saat user menjawab wizard!
            result["is_ambiguous"] = False
            logger.info("[CALL1_PRESET_ROUTING] 🎯 Resolving Wizard Answer from Call 2 -> Enforcing is_ambiguous=False")
            
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
            logger.info(f"[CALL1_PRESET_ROUTING] ❓ Ambiguity detected -> reason: '{result['ambiguity_reason']}'")
        is_guest_user = bool(precheck.get("is_guest", False))
        if not is_guest_user and (
            precheck.get("is_docwriter")
            or re.search(r'\b(buka|open|tampil(kan)?|muncul(kan)?|akses)\b.{0,25}\b(editor|writer|studio)\b', user_message.lower())
            or any(kw in user_message.lower() for kw in ["buka editor", "dokumen writer", "dokumen editor", "draft surat", "draf surat", "draft skep", "draf skep", "draft se", "draf se", "draft memo", "draf memo", "draft nota dinas", "draf nota dinas", "siapkan draft", "siapkan draf", "buatkan draft", "buatkan draf"])
        ):
            result["is_docwriter"] = True
            result["is_ambiguous"] = False
        else:
            result["is_docwriter"] = False

        # Kelanjutan visual refinement jika Call 2 sebelumnya telah membuat visual
        user_lower_check = user_message.lower()
        if has_prior_visual and any(w in user_lower_check for w in ["warna", "ganti", "ubah", "potongan", "pie", "bar", "chart", "grafik", "diagram"]):
            result["requires_visual"] = True
            if not result.get("visual_types"):
                result["visual_types"] = [precheck.get("last_visual_type") or "chart"]

        # Visual flag & sub-types
        if res_json.get("requires_visual") is True:
            result["requires_visual"] = True
            raw_vt = res_json.get("visual_types") or res_json.get("visual_type") or []
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
                if not result["visual_types"]:
                    result["visual_types"] = ["mermaid"]

        # Modular capability flags
        for flag in [
            "need_analytic", "is_troubleshooting", "is_comparative", 
            "has_actionable_workflow", "is_security_critical", 
            "is_generate_file", "is_map_query"
        ]:
            if res_json.get(flag) is True:
                result[flag] = True

        # Session title — hanya jika first_chat
        if is_first_chat:
            raw_title = res_json.get("session_title")
            if isinstance(raw_title, str) and raw_title.strip() and raw_title.strip().lower() not in GENERIC_SESSION_TITLES:
                result["session_title"] = format_session_title(raw_title)

        logger.info(f"⚡ [CALL1_PRESET_ROUTING] Result in {duration_ms:.1f}ms: {result} (mode={forced_mode}, first_chat={is_first_chat})")
        return result

    except Exception as e:
        logger.warning(f"[CALL1_PRESET_ROUTING] Gagal via LLM: {e}")


    # Fallback: jika first_chat, coba generate title dari teks user saja
    if is_first_chat:
        from backend.app.services.pipeline.modes.mode_utils import format_session_title, GENERIC_SESSION_TITLES
        formatted = format_session_title(user_message)
        if formatted and formatted.strip().lower() not in GENERIC_SESSION_TITLES:
            return {"session_title": formatted}

    return {}


async def generate_call1_preset_title(user_message: str, request: Optional[Request] = None) -> Optional[str]:
    """
    Deprecated: dipertahankan sebagai backward-compat alias.
    Gunakan generate_call1_preset_routing() untuk jalur preset.
    """
    result = await generate_call1_preset_routing(
        user_message=user_message,
        forced_mode="auto",
        is_first_chat=True,
        request=request,
    )
    return result.get("session_title")



async def generate_call1_web_queries(user_message: str, request: Optional[Request] = None) -> List[str]:
    """
    Menghasilkan 1-2 kata kunci pencarian web cerdas via Gemma 4 e4b
    dari pesan user yang santai/penuh keluhan (< 300 ms).
    """
    if not user_message or not user_message.strip():
        return []

    from datetime import datetime
    from backend.app.services.web_tools.web_search import sanitize_web_query

    clean_fallback = sanitize_web_query(user_message.strip())
    model = getattr(settings, "MODEL_ROUTER", "gemma4:e4b")
    router_ctx = getattr(settings, "NUM_CTX_ROUTER", 4096)

    prompt = (
        "Kamu adalah Cakra Search Query Optimizer.\n"
        "Tugas: Ubah pesan pengguna yang santai, penuh keluhan, emosional, atau bahasa gaul menjadi 1-2 kata kunci pencarian web/Google yang bersih, objektif, dan efektif mencari berita/fakta terpercaya.\n"
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
            clean_queries = [sanitize_web_query(str(q)) for q in queries if str(q).strip()]
            clean_queries = [q for q in clean_queries if q]
            if clean_queries:
                logger.info(f"⚡ [CALL1_WEB_QUERIES] Generated {clean_queries} in {duration_ms:.1f}ms (from: '{user_message}')")
                return clean_queries
    except Exception as e:
        logger.warning(f"[CALL1_WEB_QUERIES] Gagal generate query via LLM: {e}")

    return [clean_fallback] if clean_fallback else [user_message.strip()]

