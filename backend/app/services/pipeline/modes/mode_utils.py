import logging
from typing import List, Dict, Any, Optional

_CODING_KEYWORDS = ["import ", "export ", "const ", "async ", "await ", "function", "def ", "return ", "class ", "select ", "docker", "sql ", "query", "react", "python", "javascript", "coding", "koding", "usecontext", "usememo", "typescript", "golang", "kotlin", "flutter", "dart", "frontend", "backend", "jsx", "html", "css", "tailwind"]
_GREETING_KEYWORDS = ["hai", "halo", "hello", "hi ", "apa kabar", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "assalamualaikum", "pagi", "siang", "malam", "thanks", "thank you", "terima kasih", "makasih", "ok", "oke", "siap", "tq", "nuhun", "suwun", "mantap", "sip"]
_DOC_KEYWORDS = ["ketentuan", "peraturan", "skep", "sk direksi", "surat edaran", "regulasi", "kebijakan", "prosedur", "sop", "seragam", "cuti", "gaji", "tunjangan", "rekrutmen", "rekrut", "pegawai", "pindad", "aturan", "pasal", "syarat", "lembur", "pensiun", "promosi", "jabatan", "seleksi", "penerimaan"]

def detect_precheck(user_message: str, chat_mode: str, has_attachment: bool) -> Dict[str, Any]:
    msg_lower = user_message.lower()

    is_coding = any(kw in msg_lower for kw in _CODING_KEYWORDS)
    is_greeting = any(kw in msg_lower for kw in _GREETING_KEYWORDS)
    is_doc_query = any(kw in msg_lower for kw in _DOC_KEYWORDS)
    
    _EMAIL_KEYWORDS = ["kirim email", "buat email", "draft email", "balas email", "email ke", "draf email"]
    is_generate_email = any(kw in msg_lower for kw in _EMAIL_KEYWORDS)
    
    _VISUAL_KEYWORDS = ["visual", "diagram", "alur", "flowchart", "grafik", "bagan"]
    requires_visual = any(kw in msg_lower for kw in _VISUAL_KEYWORDS)

    if any(w in msg_lower for w in ["gue", "lo", "gw"]):
        pronoun, mirroring = "informal_gue_lo", "mirror_casual"
    elif any(w in msg_lower for w in ["saya", "anda", "bapak", "ibu"]):
        pronoun, mirroring = "formal_saya_anda", "stay_formal_safe"
    elif any(w in msg_lower for w in ["aku", "kamu"]):
        pronoun, mirroring = "familiar_aku_kamu", "mirror_casual"
    else:
        pronoun, mirroring = "unknown", "stay_formal_safe"

    slang = [s for s in ["bolo", "cuy", "bro", "gan", "sis"] if s in msg_lower]
    profanity = "low_misuh" if any(w in msg_lower for w in ["asu", "jancuk", "anjir", "bangsat"]) else "none"

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
        is_chitchat = is_greeting or (word_count <= 4 and not is_coding and not is_doc_query and not has_attachment)

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
        "mirroring": mirroring,
        "slang": slang,
        "profanity": profanity,
        "word_count": word_count,
        "requires_visual": requires_visual,
        "is_generate_email": is_generate_email,
        "_user_message": user_message
    }

def build_rule_based_queries(user_message: str) -> List[str]:
    msg = user_message.strip()
    msg_lower = msg.lower()

    prefix_map = [
        (["cuti", "izin", "libur"], ["ketentuan cuti pegawai", "hak cuti karyawan", "SKEP cuti"]),
        (["gaji", "upah", "penghasilan"], ["ketentuan gaji pegawai", "struktur penghasilan", "SK gaji tunjangan"]),
        (["seragam", "pakaian", "baju", "dinas"], ["ketentuan seragam dinas", "aturan pakaian kerja", "SKEP seragam"]),
        (["rekrut", "recruitment", "lamaran", "seleksi", "proses", "ipk"], ["proses rekrutmen pindad", "seleksi penerimaan pegawai", "ketentuan rekrutmen"]),
        (["tunjangan", "fasilitas", "benefit"], ["ketentuan tunjangan pegawai", "fasilitas karyawan", "SK tunjangan"]),
        (["lembur", "overtime"], ["ketentuan lembur pegawai", "aturan kerja lembur", "SKEP lembur"]),
        (["promosi", "kenaikan", "jabatan"], ["prosedur kenaikan jabatan", "ketentuan promosi pegawai", "SK kenaikan pangkat"]),
        (["pensiun", "masa kerja"], ["ketentuan pensiun pegawai", "aturan masa kerja", "SK pensiun"]),
        (["sop", "prosedur", "standar"], ["SOP prosedur operasional", "standar prosedur kerja", "instruksi kerja"]),
        (["rab", "pengadaan", "tender", "lelang"], ["ketentuan RAB", "regulasi pengadaan", "prosedur tender"]),
    ]

    for keywords, prefixes in prefix_map:
        if any(kw in msg_lower for kw in keywords):
            return prefixes[:3]

    trash_words = {
        "apakah", "ada", "yang", "lebih", "detail", "lagi", "seperti", "kalau", "kalo",
        "gimana", "bagaimana", "sih", "cuy", "thanks", "ya", "mohon", "info", "tentang",
        "atau", "dan", "di", "ke", "dari", "untuk", "buat", "dong", "apa", "aja", "saja",
        "jelaskan", "tolong", "kasih", "tau", "beritahu", "beri", "tahu", "jelasin",
        "bisa", "gak", "nggak", "engga", "ngga", "tidak", "dalam", "membahas", "bahas",
        "coba", "mengenai", "terkait", "soal", "itu", "ini", "pada", "oleh", "dengan",
        "kepada", "adalah", "merupakan", "yaitu", "dong", "sih?", "dong?", "ya?",
        "ketentuan", "ketentuannya", "aturan", "aturannya", "regulasi", "regulasinya",
        "kebijakan", "kebijakannya", "prosedur", "pasal", "ayat", "bab", "coba", "hal"
    }
    words = [w for w in msg_lower.split() if w.strip("?,.!") not in trash_words and len(w) > 2]
    if words:
        full_core = " ".join(words)
        queries = [full_core]
        if len(words) >= 2:
            # Subjek tanpa kata pertama (jika kata pertama adalah nama dokumen seperti pud, skep, pkb)
            subjek_only = " ".join(words[1:]) if len(words) > 1 else full_core
            queries.append(subjek_only)
            # Kombinasi dokumen dan kata akhir
            if len(words) >= 3:
                queries.append(f"{words[0]} {words[-1]}")
            queries.append(f"ketentuan {full_core}")
        else:
            queries.extend([f"ketentuan {full_core}", f"regulasi {full_core}"])
        # Hapus duplikat sambil menjaga urutan
        seen = set()
        return [q for q in queries if not (q in seen or seen.add(q))][:4]

    short = " ".join(msg.split()[:3])
    return [short, f"ketentuan {short}", f"regulasi {short}"]

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

    if precheck and precheck.get("requires_visual") is True:
        prompt += "\n\n" + VISUAL_SYSTEM_PROMPT + "\n\n"

    if is_thinking:
        prompt = "<|think|>\n" + prompt
        
    return prompt

def get_module_config(module_name: str) -> Dict[str, Any]:
    configs = {
        "chitchat": {"num_ctx": 16384, "temperature": 1.0},
        "coding": {"num_ctx": 16384, "temperature": 1.0},
        "rag": {"num_ctx": 16384, "temperature": 1.0},
        "multi_document": {"num_ctx": 16384, "temperature": 1.0},
        "analytic": {"num_ctx": 16384, "temperature": 1.0},
        "self_correction": {"num_ctx": 16384, "temperature": 1.0},
        "ambiguous": {"num_ctx": 16384, "temperature": 1.0},
        "general_expert": {"num_ctx": 32768, "temperature": 1.0},
    }
    return configs.get(module_name, {"num_ctx": 16384, "temperature": 1.0})
