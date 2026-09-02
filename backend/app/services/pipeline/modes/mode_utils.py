import logging
from typing import List, Dict, Any, Optional

_CODING_KEYWORDS = ["import ", "export ", "const ", "async ", "await ", "function", "def ", "return ", "class ", "select ", "docker", "sql ", "query", "react", "python", "javascript", "coding", "koding", "usecontext", "usememo", "typescript", "golang", "kotlin", "flutter", "dart", "frontend", "backend", "jsx", "html", "css", "tailwind"]
_GREETING_KEYWORDS = ["hai", "halo", "hello", "hi ", "apa kabar", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "assalamualaikum", "pagi", "siang", "malam", "thanks", "thank you", "terima kasih", "makasih", "ok", "oke", "siap", "tq", "nuhun", "suwun", "mantap", "sip"]
_DOC_KEYWORDS = ["ketentuan", "peraturan", "skep", "surat keputusan", "surat edaran", "regulasi", "kebijakan", "prosedur", "sop", "seragam", "cuti", "gaji", "tunjangan", "rekrutmen", "rekrut", "pegawai", "pindad", "aturan", "pasal", "syarat", "lembur", "pensiun", "promosi", "jabatan", "seleksi", "penerimaan", "ik "]
_PUBLIC_WEB_KEYWORDS = [
    "cari di web", "carikan di web", "cari web", "search web", "browsing", "di internet", 
    "web publik", "sumber publik", "di google", "berita online", "berita terkini", 
    "dpr", "dpr ri", "dpr-ri", "presiden ri", "kementerian", "menteri", "mahkamah konstitusi", 
    "pilkada", "pemilu", "bmkg", "prakiraan cuaca", "kurs rupiah", "ihsg", "inflasi nasional"
]

def detect_precheck(user_message: str, chat_mode: str, has_attachment: bool, user_default_pronoun: Optional[str] = None) -> Dict[str, Any]:
    msg_lower = user_message.lower()

    is_coding = any(kw in msg_lower for kw in _CODING_KEYWORDS)
    is_greeting = any(kw in msg_lower for kw in _GREETING_KEYWORDS)
    is_public_web = any(kw in msg_lower for kw in _PUBLIC_WEB_KEYWORDS)
    is_doc_query = any(kw in msg_lower for kw in _DOC_KEYWORDS) and not is_public_web
    
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
        
    farewell_phrases = ["balik dulu", "pamit", "pulang dulu", "besok lanjut", "nanti lanjut", "dadah", "bye", "good night", "selamat malam", "selamat istirahat", "mau balik", "offline dulu"]
    is_farewell = any(fp in msg_lower for fp in farewell_phrases)

    _INSTRUCTION_VERBS = [
        "buat", "buatkan", "buatin", "bikin", "bikinin", "analisa", "analisis", 
        "jelaskan", "jelasin", "tabel", "timeline", "jadwal", 
        "coba", "gas", "tolong", "perbaiki", "fix", "ubah", "ganti", "edit", 
        "tampilkan", "ringkas", "rangkum", "terapkan"
    ]
    if not is_farewell and any(w in msg_lower for w in ["lanjut", "lanjutkan"]):
        has_instruction = True
    else:
        has_instruction = any(iv in msg_lower for iv in _INSTRUCTION_VERBS)

    if is_farewell:
        is_greeting = True
        is_chitchat = True
        has_instruction = False
    elif has_instruction:
        is_greeting = False
        is_chitchat = False
    else:
        is_chitchat = is_greeting

    # SPRINT 5: Proteksi sapaan & ucapan terima kasih/apresiasi/pamitan di mode apapun!
    # Prioritaskan chat_mode eksplisit jika user memilih mode dokumen
    is_explicit_doc_mode = str(chat_mode).lower().strip() in ["documents", "document", "global_chat"]

    if (is_chitchat or is_farewell) and not is_doc_query and not has_instruction and not is_explicit_doc_mode:
        need_rag_hint = False
    elif is_explicit_doc_mode:
        need_rag_hint = True
        is_public_web = False
        is_chitchat = False
    elif is_public_web:
        need_rag_hint = False
        is_chitchat = False
    elif has_attachment or is_doc_query:
        need_rag_hint = True
        is_chitchat = False
    elif is_coding:
        need_rag_hint = False
    else:
        need_rag_hint = None
        
    from backend.app.services.pipeline.intent_dictionary import extract_slang_mirror
    slang_mirror = extract_slang_mirror(user_message, user_pronoun=pronoun)

    return {
        "chat_mode": chat_mode,
        "is_chitchat": is_chitchat,
        "is_coding": is_coding,
        "is_greeting": is_greeting,
        "is_doc_query": is_doc_query,
        "is_public_web": is_public_web,
        "need_rag_hint": need_rag_hint,
        "pronoun": pronoun,
        "tone_hint": tone_hint,
        "mirroring": mirroring,
        "slang": slang,
        "slang_mirror": slang_mirror,
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


def select_call2_module(routing: Dict[str, Any], has_rag_context: bool = False) -> str:
    # 🚨 Prioritas 1: Jika request bersifat ambigu / bercabang, selalu prioritaskan ambiguous handler
    # agar menyajikan kartu wizard / opsi klarifikasi interaktif alih-alih mengeksekusi langsung
    if routing.get("is_ambiguous"):
        return "ambiguous"
    if has_rag_context:
        if routing.get("is_multi_document"):
            return "multi_document"   # dari "rag_multi_document"
        return "rag"                  # dari "rag_standard"
    if routing.get("is_coding"):
        return "coding"               # dari "coding_expert"
    if routing.get("need_analytic") or routing.get("requires_visual"):
        return "analytic"             # visual / analytic expert
    if routing.get("is_self_correction"):
        return "self_correction"      # sudah benar
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

        # Injeksi Visual Capabilities (Chart, Mermaid, Gantt, Infografis)
        if precheck.get("requires_visual") is True:
            prompt += "\n\n" + VISUAL_CAPABILITIES_GUIDANCE + "\n\n" + VISUAL_SYSTEM_PROMPT + "\n\n"

    return prompt

def get_module_config(module_name: str, precheck: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    configs = {
        "chitchat": {
            "num_ctx": 16384,
            "temperature": 0.8,
            "top_p": 0.95,
            "top_k": 64,
            "num_predict": 4096,
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
            "num_batch": 512,
        },
        "multi_document": {
            "num_ctx": 16384,
            "temperature": 0.1,
            "top_p": 0.85,
            "top_k": 40,
            "num_predict": 8192,
            "repeat_penalty": 1.1,
            "repeat_last_n": 128,
            "num_batch": 512,
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


_ACRONYMS = {
    "php": "PHP",
    "css": "CSS",
    "js": "JS",
    "jsx": "JSX",
    "ts": "TS",
    "tsx": "TSX",
    "html": "HTML",
    "sql": "SQL",
    "api": "API",
    "rest": "REST",
    "ui": "UI",
    "ux": "UX",
    "pdf": "PDF",
    "csv": "CSV",
    "xlsx": "XLSX",
    "docx": "DOCX",
    "sop": "SOP",
    "pkb": "PKB",
    "skep": "SKEP",
    "sdm": "SDM",
    "k3": "K3",
    "it": "IT",
    "ai": "AI",
    "llm": "LLM",
    "rag": "RAG",
    "sse": "SSE",
    "db": "DB",
    "url": "URL",
    "jwt": "JWT",
    "auth": "Auth",
    "nextcloud": "Nextcloud",
    "pindad": "Pindad",
    "cakra": "CAKRA",
    "react": "React",
    "vue": "Vue",
    "node": "Node",
    "python": "Python",
    "fastapi": "FastAPI",
    "vite": "Vite",
    "tailwind": "Tailwind",
}

_CONVERSATIONAL_FILLERS = {
    "sekarang", "coba", "pake", "pakai", "tolong", "bikin", "buatkan", "buat", "bikinin",
    "gimana", "dong", "cuy", "nih", "ya", "bro", "gan", "bang", "mas", "mba", "bos", "aja",
    "saja", "kan", "deh", "yuk", "lah", "plis", "please", "can", "you", "help", "me", "kali",
    "halo", "hai", "assalamualaikum", "pagi", "siang", "malam", "tes", "test"
}

GENERIC_SESSION_TITLES = {
    "salam", "sapaan", "sapaan pembuka", "halo", "hai", "tes", "test",
    "obrolan baru", "percakapan baru", "salam & sapaan", "salam dan sapaan",
    "greeting", "greetings", "general greeting", "n/a", "na", "none", "null",
    "undefined", "tanya", "pertanyaan", "bantuan", "help", "chitchat",
    "obrolan", "percakapan", "obrolan santai", "salam pembuka", "new chat", "untitled"
}

def format_session_title(title_input: str, max_words: int = 5, max_chars: int = 40) -> str:
    """
    Cleans and formats session titles naturally, preserving technical acronyms
    and stripping conversational slang/fillers.
    """
    if not title_input or not isinstance(title_input, str):
        return "Obrolan Cakra AI"

    cleaned = title_input.strip().strip('"').strip("'").strip(".").strip("`")
    
    # 🚫 Jika judul hanya berisi satu kata sapaan generik atau N/A, fallback ke judul ramah
    if cleaned.lower() in GENERIC_SESSION_TITLES:
        return "Obrolan Cakra AI"
    
    # Strip common leading command phrases
    for prefix in [
        "Buatkan format ", "Buatkan draft ", "Buatkan ", "Bikinin ", "Buat ", "Gambarkan ",
        "Visualisasikan ", "Generate ", "Susun ", "Cari di web: ", "Cari di web ",
        "Cari di arsip dokumen: ", "Cari kode: ", "Cari: ", "Jelaskan tentang ", "Tolong jelaskan ",
        "Tolong buatkan ", "Tolong buat ", "Tolong carikan ", "Tolong bantu "
    ]:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
            break

    words = cleaned.split()
    if not words:
        return "Obrolan Cakra AI"

    # Filter leading and trailing filler words
    start_idx = 0
    while start_idx < len(words) and words[start_idx].lower().strip(".,!?:;\"'") in _CONVERSATIONAL_FILLERS:
        start_idx += 1

    end_idx = len(words)
    while end_idx > start_idx and words[end_idx - 1].lower().strip(".,!?:;\"'") in _CONVERSATIONAL_FILLERS:
        end_idx -= 1

    trimmed_words = words[start_idx:end_idx] if start_idx < end_idx else words
    target_words = trimmed_words[:max_words]

    # Format each word with smart casing
    formatted_words = []
    for w in target_words:
        clean_w = w.strip(".,!?:;\"'")
        punct_end = w[len(clean_w):] if len(clean_w) < len(w) else ""
        lower_w = clean_w.lower()
        if lower_w in _ACRONYMS:
            formatted_words.append(_ACRONYMS[lower_w] + punct_end)
        elif len(clean_w) > 1 and clean_w.isupper():
            formatted_words.append(clean_w + punct_end)
        elif lower_w in ["dan", "di", "ke", "dari", "pada", "untuk", "dengan", "atau", "vs", "&"] and formatted_words:
            formatted_words.append(lower_w + punct_end)
        else:
            formatted_words.append(clean_w.capitalize() + punct_end)

    result = " ".join(formatted_words).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(" ", 1)[0]
    return result if result and result.lower() not in GENERIC_SESSION_TITLES else "Obrolan Cakra AI"

