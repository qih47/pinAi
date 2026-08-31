import logging
from typing import List, Dict, Any, Optional

_CODING_KEYWORDS = ["import ", "export ", "const ", "async ", "await ", "function", "def ", "return ", "class ", "select ", "docker", "sql ", "query", "react", "python", "javascript", "coding", "koding", "usecontext", "usememo", "typescript", "golang", "kotlin", "flutter", "dart", "frontend", "backend", "jsx", "html", "css", "tailwind"]
_GREETING_KEYWORDS = ["hai", "halo", "hello", "hi ", "apa kabar", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "assalamualaikum", "pagi", "siang", "malam", "thanks", "thank you", "terima kasih", "makasih", "ok", "oke", "siap", "tq", "nuhun", "suwun", "mantap", "sip"]
_DOC_KEYWORDS = ["ketentuan", "peraturan", "skep", "sk direksi", "surat edaran", "regulasi", "kebijakan", "prosedur", "sop", "seragam", "cuti", "gaji", "tunjangan", "rekrutmen", "rekrut", "pegawai", "pindad", "aturan", "pasal", "syarat", "lembur", "pensiun", "promosi", "jabatan", "seleksi", "penerimaan"]

def detect_precheck(user_message: str, chat_mode: str, has_attachment: bool, user_default_pronoun: Optional[str] = None) -> Dict[str, Any]:
    msg_lower = user_message.lower()

    is_coding = any(kw in msg_lower for kw in _CODING_KEYWORDS)
    is_greeting = any(kw in msg_lower for kw in _GREETING_KEYWORDS)
    is_doc_query = any(kw in msg_lower for kw in _DOC_KEYWORDS)
    
    _EMAIL_KEYWORDS = ["kirim email", "buat email", "draft email", "balas email", "email ke", "draf email"]
    is_generate_email = any(kw in msg_lower for kw in _EMAIL_KEYWORDS)
    
    _VISUAL_KEYWORDS = ["visual", "diagram", "alur", "flowchart", "grafik", "bagan"]
    requires_visual = any(kw in msg_lower for kw in _VISUAL_KEYWORDS)

    import re

    # Strict word-boundary regex untuk deteksi kata ganti eksplisit
    has_explicit_gue_lo = bool(re.search(r'\b(gue|gw|gua|lo|lu|elu)\b', msg_lower))
    has_formal_pronoun = bool(re.search(r'\b(saya|anda|bapak|ibu|beliau)\b', msg_lower))
    has_aku_kamu = bool(re.search(r'\b(aku|kamu|kita|kami)\b', msg_lower))

    slang = [s for s in ["bolo", "cuy", "bro", "gan", "sis", "boss", "bos", "bang", "aa", "teteh", "mas", "mba"] if re.search(r'\b' + re.escape(s) + r'\b', msg_lower)]
    profanity = "low_misuh" if any(w in msg_lower for w in ["asu", "jancuk", "anjir", "bangsat"]) else "none"

    if user_default_pronoun in ["informal_gue_lo", "formal_saya_anda", "familiar_aku_kamu"]:
        # 1. Prioritas absolut preferensi eksplisit user dari settings / onboarding
        pronoun = user_default_pronoun
        mirroring = "mirror_casual" if user_default_pronoun == "informal_gue_lo" else "stay_formal_safe"
    elif has_explicit_gue_lo:
        # 2. Mode Adaptif / Mirroring: user pakai gue/lo -> balas santai
        pronoun, mirroring = "informal_gue_lo", "mirror_casual"
    elif has_formal_pronoun:
        # 2. Mode Adaptif / Mirroring: user pakai saya/anda -> balas formal
        pronoun, mirroring = "formal_saya_anda", "stay_formal_safe"
    elif has_aku_kamu:
        # 2. Mode Adaptif / Mirroring: user pakai aku/kamu -> balas hangat
        pronoun, mirroring = "familiar_aku_kamu", "mirror_casual"
    elif slang:
        # 2. Mode Adaptif / Mirroring: user pakai slang (cuy, bro, bos) -> balas santai
        pronoun, mirroring = "informal_gue_lo", "mirror_casual"
    else:
        # 3. Default aman korporat Pindad jika belum ada input kata ganti eksplisit
        pronoun, mirroring = "formal_saya_anda", "stay_formal_safe"

    # Deteksi Nuansa Emosi & Mood User
    if any(w in msg_lower for w in ["makasih", "terima kasih", "keren", "mantap", "top", "gokil", "thanks", "thank you"]):
        tone_hint = "celebratory"
    elif any(w in msg_lower for w in ["pusing", "bingung", "error mulu", "kesel", "susah", "gagal terus", "capek", "frustasi"]):
        tone_hint = "empathetic_supportive"
    elif any(w in msg_lower for w in ["cepet", "singkat", "to the point", "buruan", "sekarang", "langsung aja"]):
        tone_hint = "direct_concise"
    elif has_formal_pronoun or not has_explicit_gue_lo:
        tone_hint = "formal"
    else:
        tone_hint = "casual"

    word_count = len(user_message.split())
    # Jangan anggap is_greeting jika pesannya terlalu panjang (kemungkinan ada instruksi setelah sapaan)
    if word_count > 8:
        is_greeting = False
        
    _INSTRUCTION_VERBS = [
        "buat", "buatkan", "buatin", "bikin", "bikinin", "analisa", "analisis", 
        "jelaskan", "jelasin", "tabel", "timeline", "jadwal", "lanjut", "lanjutkan", 
        "coba", "gas", "tolong", "perbaiki", "fix", "ubah", "ganti", "edit", 
        "tampilkan", "ringkas", "rangkum", "terapkan"
    ]
    has_instruction = any(iv in msg_lower for iv in _INSTRUCTION_VERBS)

    if has_instruction:
        is_greeting = False
        is_chitchat = False
    else:
        is_chitchat = is_greeting

    # SPRINT 5: Proteksi sapaan & ucapan terima kasih/apresiasi di mode apapun!
    # Jangan paksakan need_rag_hint=True jika user sekadar sapaan ringan / makasih di mode "documents"
    if is_chitchat and not is_doc_query and not has_instruction:
        need_rag_hint = False
    elif chat_mode == "documents" or has_attachment or is_doc_query:
        need_rag_hint = True
        is_chitchat = False
    elif is_coding:
        need_rag_hint = False
    else:
        need_rag_hint = None
        
    if is_generate_email:
        is_chitchat = False
        need_rag_hint = False

    return {
        "is_chitchat": is_chitchat,
        "is_coding": is_coding,
        "is_greeting": is_greeting,
        "is_doc_query": is_doc_query,
        "need_rag_hint": need_rag_hint,
        "pronoun": pronoun,
        "tone_hint": tone_hint,
        "mirroring": mirroring,
        "slang": slang,
        "profanity": profanity,
        "word_count": word_count,
        "requires_visual": requires_visual,
        "is_generate_email": is_generate_email,
        "_user_message": user_message
    }

def build_rule_based_queries(user_message: str, context_subject: str = "", context_topic: str = "") -> List[str]:
    """
    Ekstrak kata kunci pencarian yang presisi dari pesan user dan entitas multi-turn.
    - Max 2 queries (untuk efisiensi vector search)
    - Dedup kata sebelum digabung (fix "PKB PKB")
    - Strip kata instruksi visual/format ("diagram", "flowchart", "grafik", dst.)
    """
    import re
    raw_msg = (user_message or "").strip()
    # Bersihkan tanda baca
    clean_msg = re.sub(r"[?!.,;:\'\"()\[\]{}]", " ", raw_msg)
    clean_msg = re.sub(r"\s{2,}", " ", clean_msg).strip()
    msg_lower = clean_msg.lower()

    # Kata pengisi / pertanyaan / konjungsi
    stop_words = {
        "apakah", "ada", "yang", "lebih", "detail", "lagi", "seperti", "kalau", "kalo",
        "gimana", "bagaimana", "sih", "cuy", "thanks", "ya", "mohon", "info", "tentang",
        "atau", "dan", "di", "ke", "dari", "untuk", "buat", "dong", "apa", "aja", "saja",
        "jelaskan", "tolong", "kasih", "tau", "beritahu", "beri", "tahu", "jelasin",
        "bisa", "gak", "nggak", "engga", "ngga", "tidak", "dalam", "membahas", "bahas",
        "coba", "mengenai", "terkait", "soal", "itu", "ini", "pada", "oleh", "dengan",
        "kepada", "adalah", "merupakan", "yaitu", "perbedaan", "bandingkan", "dibanding",
        "menurut", "sesuai", "ga", "kah", "dong?", "ya?"
    }

    # ✂️ Kata instruksi visual/format yang harus dibuang dari query dokumen
    visual_instruction_words = {
        "sekalian", "bikinin", "buatkan", "buat", "bikin", "gambarkan", "tampilkan",
        "diagram", "flowchart", "alir", "grafik", "chart", "tabel", "visualisasi",
        "ilustrasi", "gambar", "infografis", "infographic", "mermaid", "plot",
        "timeline", "skema", "schema", "draw", "render", "generate",
    }

    words = [
        w for w in msg_lower.split()
        if w not in stop_words
        and w not in visual_instruction_words
        and len(w) >= 2
    ]

    subject = (context_subject or "").strip()
    clean_subject = re.sub(r"[?!.,;:\'\"()\[\]{}]", " ", subject).strip()
    if clean_subject.lower() in ["obrolan umum", "obrolan cakra ai", "general", "none", "null"]:
        clean_subject = ""

    def dedup_words(text: str) -> str:
        """Hapus kata duplikat yang muncul berurutan atau ganda dalam string."""
        tokens = text.split()
        seen_t = set()
        result = []
        for t in tokens:
            t_lower = t.lower()
            if t_lower not in seen_t:
                seen_t.add(t_lower)
                result.append(t)
        return " ".join(result)

    queries = []

    # 1. Multi-Turn Anaphora Context Fusion
    if clean_subject:
        subject_words = set(clean_subject.lower().split())
        user_specific_words = [w for w in words if w not in subject_words]
        user_specific = " ".join(user_specific_words)

        if user_specific:
            # Gabung subject + user-specific, dedup kata yang sama
            q1 = dedup_words(f"{clean_subject} {user_specific}")
            queries.append(q1)
        else:
            queries.append(clean_subject)

    # 2. Ekstraksi langsung dari kata spesifik di user_message (tanpa subject prefix)
    if words:
        full_core = dedup_words(" ".join(words[:5]))  # Max 5 kata, deduped
        if full_core not in queries:
            queries.append(full_core)

    # 3. Fallback
    if not queries:
        if clean_subject:
            queries.append(clean_subject)
        elif words:
            queries.append(dedup_words(" ".join(words[:4])))

    # Bersihkan: hapus generik kosong, whitespace, duplikat query
    seen = set()
    cleaned_result = []
    for q in queries:
        q_str = dedup_words(q.strip())
        if q_str and q_str.lower() not in seen and q_str.lower() not in {"ketentuan", "regulasi", "aturan", "sop"}:
            seen.add(q_str.lower())
            cleaned_result.append(q_str)

    # ✅ Max 2 queries — efisiensi vector search
    return cleaned_result[:2]

def build_clean_web_search_query(user_message: str) -> str:
    """
    Membersihkan pesan user dari kata-kata instruksi/basa-basi sebelum dikirim ke mesin pencarian.
    Contoh: "coba carikan di pindad.com susunan direksinya yang terbaru"
            → "pindad.com susunan direksi terbaru"
    """
    import re

    msg = user_message.strip()

    # Hapus frasa instruksi di awal kalimat (greedy dari kiri)
    instruction_prefixes = [
        r"^coba\s+carikan\s+",
        r"^carikan\s+",
        r"^tolong\s+cari(kan)?\s+",
        r"^coba\s+cari(kan)?\s+",
        r"^cari(kan)?\s+",
        r"^coba\s+lihat\s+",
        r"^coba\s+cek\s+",
        r"^cek\s+",
        r"^lihat(in)?\s+",
        r"^tampil(kan)?\s+",
        r"^tunjukkan\s+",
        r"^beri\s+tahu\s+(aku|gue|saya)?\s*",
        r"^beritahu\s+(aku|gue|saya)?\s*",
        r"^kasih\s+tau\s+(aku|gue|saya)?\s*",
    ]
    for pattern in instruction_prefixes:
        msg = re.sub(pattern, "", msg, flags=re.IGNORECASE).strip()

    # Hapus frasa preposisi yang tidak bermakna di awal ("di", "dari", "ke", "di dalam", "di situs")
    preposition_prefixes = [
        r"^di\s+dalam\s+",
        r"^di\s+situs\s+",
        r"^di\s+website\s+",
        r"^di\s+laman\s+",
        r"^di\s+web\s+",
        r"^di\s+halaman\s+",
        r"^di\s+(?=\S)",   # "di pindad.com" → hapus "di "
    ]
    for pattern in preposition_prefixes:
        msg = re.sub(pattern, "", msg, flags=re.IGNORECASE).strip()

    # Hapus kata instruksi/basa-basi umum yang biasa muncul di tengah/akhir
    filler_words = [
        r"\btolong\b", r"\bmohon\b", r"\bya\b", r"\bdong\b", r"\bsih\b",
        r"\bcuy\b", r"\bbro\b", r"\bgan\b", r"\bmin\b", r"\bboss\b",
        r"\bboleh\s+tahu\b", r"\bboleh\b", r"\bsekarang\b",
        r"\bmengenai\b", r"\bterkait\b", r"\btentang\b", r"\bsoal\b",
        r"\byang\s+ada\s+di\b", r"\bada\s+di\b",
        r"\binfomasi\b", r"\binformasi\b",
    ]
    for pattern in filler_words:
        msg = re.sub(pattern, "", msg, flags=re.IGNORECASE).strip()

    # Hapus spasi ganda yang tersisa
    msg = re.sub(r"\s{2,}", " ", msg).strip()

    # Jika setelah dibersihkan hasilnya kosong, kembalikan pesan asli
    if not msg:
        return user_message.strip()

    return msg


def sanitize_history_for_rag(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Membersihkan riwayat pesan dari blok kode besar, script, dan data web search
    agar tidak mengontaminasi penalaran RAG / regulasi internal.
    """
    import re
    sanitized = []
    for msg in messages:
        content = msg.get("content", "")
        if not content:
            continue
        # Hapus blok kode program ```...```
        cleaned = re.sub(r'```(?:python|javascript|js|ts|html|css|bash|sh|json|sql|c\+\+|cpp|java|go|rust|xml|yaml|yml)?[\s\S]*?```', '[Kode/Script program pada percakapan sebelumnya ditiadakan agar tidak mengontaminasi rujukan regulasi]', content)
        # Hapus blok artefak web search jika ada
        cleaned = re.sub(r'\[WEB_SEARCH_RESULT[\s\S]*?\]', '', cleaned)
        cleaned = re.sub(r'\[TOOL:\s*WEB_SEARCH[\s\S]*?\]', '', cleaned)
        sanitized.append({**msg, "content": cleaned})
    return sanitized


def select_call2_module(routing: Dict[str, Any], has_rag_context: bool) -> str:
    if has_rag_context:
        if routing.get("is_multi_document"):
            return "multi_document"   # dari "rag_multi_document"
        return "rag"                  # dari "rag_standard"
    if routing.get("is_coding"):
        return "coding"               # dari "coding_expert"
    if routing.get("need_analytic"):
        return "analytic"             # dari "analytic_expert"
    if routing.get("is_self_correction"):
        return "self_correction"      # sudah benar
    if routing.get("is_ambiguous"):
        return "ambiguous"            # dari "ambiguous_handler"
    if routing.get("is_chitchat") or routing.get("is_greeting"):
        return "chitchat"             # sudah benar
    topic_sub = f"{routing.get('active_topic', '')} {routing.get('key_subject', '')}".lower()
    if any(kw in topic_sub for kw in ["sapaan", "salam", "chitchat", "greeting", "kabar", "semangat pagi"]):
        return "chitchat"
    return "general_expert"           # sudah benar

def build_call2_system_prompt(
    module_name: str,
    employee_name: str,
    precheck: Dict[str, Any],
    is_thinking: bool = True,
    rag_context: Optional[str] = None,
    rag_sources: Optional[List[Dict]] = None,
    ocr_text: Optional[str] = None,
) -> str:
    from backend.app.services.pipeline.system_prompts import (
        build_response_prompt_chitchat,
        build_response_prompt_coding,
        build_response_prompt_rag,
        build_response_prompt_multi_document,
        build_response_prompt_analytic,
        build_response_prompt_self_correction,
        build_response_prompt_ambiguous,
        build_response_prompt_general_expert,
    )
    from backend.app.services.pipeline.prompts.visual_prompts import VISUAL_SYSTEM_PROMPT

    if module_name == "chitchat":
        prompt = build_response_prompt_chitchat(employee_name, precheck, is_thinking)
    elif module_name == "coding":
        prompt = build_response_prompt_coding(employee_name, precheck, is_thinking)
    elif module_name == "rag":
        prompt = build_response_prompt_rag(employee_name, precheck, is_thinking, rag_context, rag_sources)
    elif module_name == "multi_document":
        prompt = build_response_prompt_multi_document(employee_name, precheck, is_thinking, rag_context, rag_sources)
    elif module_name == "analytic":
        prompt = build_response_prompt_analytic(employee_name, precheck, is_thinking)
    elif module_name == "self_correction":
        prompt = build_response_prompt_self_correction(employee_name, precheck, is_thinking)
    elif module_name == "ambiguous":
        prompt = build_response_prompt_ambiguous(employee_name, precheck, is_thinking)
    elif module_name == "general_expert":
        prompt = build_response_prompt_general_expert(employee_name, precheck, is_thinking)
    else:
        prompt = build_response_prompt_chitchat(employee_name, precheck, is_thinking)

    if precheck:
        from backend.app.services.pipeline.prompts.core_prompts import (
            VISUAL_CAPABILITIES_GUIDANCE,
            INTERACTIVE_WIZARD_GUIDANCE,
            TROUBLESHOOTING_GUIDANCE,
            COMPARATIVE_MATRIX_GUIDANCE,
            ACTIONABLE_WORKFLOW_GUIDANCE,
            DEEP_RESEARCH_GUIDANCE,
            SECURITY_CRITICAL_GUIDANCE,
        )

        # 🛡️ STRICT ISOLATION GUARD: Jika need_rag=True, DILARANG KERAS mengutip koding atau web search masa lalu
        if precheck.get("need_rag") or module_name in ["rag", "multi_document"]:
            prompt += (
                "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🚨 ATURAN MUTLAK ISOLASI REGULASI & DOKUMEN (ANTI-KONTAMINASI CODING & WEB SEARCH)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "1. Sesi ini adalah verifikasi dokumen, regulasi, SOP, atau kebijakan resmi internal PT Pindad.\n"
                "2. DILARANG KERAS memunculkan, mengutip, atau meneruskan potongan kode program/koding/script dari percakapan sebelumnya.\n"
                "3. DILARANG KERAS menggunakan atau mencampur data hasil pencarian web luar (web search).\n"
                "4. Jawaban WAJIB 100% berfokus pada pasal, regulasi, SOP, dan rujukan dokumen internal yang tersedia.\n"
            )

        # Injeksi Wizard jika ambigu atau troubleshooting pada modul selain ambiguous
        if (precheck.get("is_ambiguous") or precheck.get("is_troubleshooting")) and module_name != "ambiguous":
            if "INTERACTIVE DECISION WIZARD" not in prompt:
                prompt += "\n\n" + INTERACTIVE_WIZARD_GUIDANCE

        # Injeksi Troubleshooting
        if precheck.get("is_troubleshooting"):
            prompt += "\n\n" + TROUBLESHOOTING_GUIDANCE

        # Injeksi Comparative Matrix
        if precheck.get("is_comparative"):
            prompt += "\n\n" + COMPARATIVE_MATRIX_GUIDANCE

        # Injeksi Actionable Workflow & SOP
        if precheck.get("has_actionable_workflow"):
            prompt += "\n\n" + ACTIONABLE_WORKFLOW_GUIDANCE

        # Injeksi Deep Research
        if precheck.get("is_deep_research"):
            prompt += "\n\n" + DEEP_RESEARCH_GUIDANCE

        # Injeksi Security Critical
        if precheck.get("is_security_critical"):
            prompt += "\n\n" + SECURITY_CRITICAL_GUIDANCE

        # Injeksi Visual Capabilities
        if precheck.get("requires_visual") is True and module_name != "chitchat":
            prompt += "\n\n" + VISUAL_CAPABILITIES_GUIDANCE + "\n\n" + VISUAL_SYSTEM_PROMPT + "\n\n"

    return prompt

def get_module_config(module_name: str, precheck: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    configs = {
        "chitchat": {
            "num_ctx": 16384,
            "temperature": 0.8,
            "top_p": 0.95,
            "top_k": 64,
            "num_predict": 512,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 512,
        },
        "coding": {
            "num_ctx": 16384,
            "temperature": 0.2,
            "top_p": 0.85,
            "top_k": 40,
            "num_predict": 8192,
            "repeat_penalty": 1.05,
            "repeat_last_n": 128,
            "num_batch": 512,
        },
        "rag": {
            "num_ctx": 16384,
            "temperature": 0.1,
            "top_p": 0.85,
            "top_k": 40,
            "num_predict": 8192,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 1024,
        },
        "multi_document": {
            "num_ctx": 16384,
            "temperature": 0.1,
            "top_p": 0.85,
            "top_k": 40,
            "num_predict": 8192,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 1024,
        },
        "analytic": {
            "num_ctx": 16384,
            "temperature": 0.2,
            "top_p": 0.85,
            "top_k": 40,
            "num_predict": 8192,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 512,
        },
        "self_correction": {
            "num_ctx": 16384,
            "temperature": 0.2,
            "top_p": 0.85,
            "top_k": 40,
            "num_predict": 4096,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 512,
        },
        "ambiguous": {
            "num_ctx": 16384,
            "temperature": 0.1,
            "top_p": 0.85,
            "top_k": 40,
            "num_predict": 1536,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 512,
        },
        "general_expert": {
            "num_ctx": 16384,
            "temperature": 0.6,
            "top_p": 0.90,
            "top_k": 50,
            "num_predict": 4096,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 512,
        },
    }
    cfg = dict(
        configs.get(
            module_name,
            {
                "num_ctx": 16384,
                "temperature": 0.7,
                "top_p": 0.90,
                "top_k": 50,
                "num_predict": 8192,
                "repeat_penalty": 1.1,
                "repeat_last_n": 128,
                "num_batch": 512,
            }
        )
    )

    if precheck:
        if precheck.get("is_deep_research"):
            cfg["num_predict"] = 8192
            cfg["temperature"] = 0.2
        elif precheck.get("is_ambiguous") and module_name == "coding":
            cfg["num_predict"] = 4096

    return cfg
