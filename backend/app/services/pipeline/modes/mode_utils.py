import logging
from typing import List, Dict, Any, Optional

_CODING_KEYWORDS = ["import ", "export ", "const ", "async ", "await ", "function", "def ", "return ", "class ", "select ", "docker", "sql ", "query", "react", "python", "javascript", "coding", "usecontext", "usememo", "typescript", "golang", "kotlin", "flutter", "dart"]
_GREETING_KEYWORDS = ["hai", "halo", "hello", "hi ", "apa kabar", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "assalamualaikum", "pagi", "siang", "malam"]
_DOC_KEYWORDS = ["ketentuan", "peraturan", "skep", "sk direksi", "surat edaran", "regulasi", "kebijakan", "prosedur", "sop", "seragam", "cuti", "gaji", "tunjangan", "rekrutmen", "rekrut", "pegawai", "pindad", "aturan", "pasal", "syarat", "lembur", "pensiun", "promosi", "jabatan", "seleksi", "penerimaan"]

def detect_precheck(user_message: str, chat_mode: str, has_attachment: bool) -> Dict[str, Any]:
    msg_lower = user_message.lower()

    is_coding = any(kw in msg_lower for kw in _CODING_KEYWORDS)
    is_greeting = any(kw in msg_lower for kw in _GREETING_KEYWORDS)
    is_doc_query = any(kw in msg_lower for kw in _DOC_KEYWORDS)

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
    is_chitchat = is_greeting or (word_count <= 5 and not is_coding and not is_doc_query and not has_attachment)

    if chat_mode == "documents" or has_attachment:
        need_rag_hint = True
        is_chitchat = False
    elif is_coding or is_chitchat:
        need_rag_hint = False
    elif is_doc_query:
        need_rag_hint = True
    else:
        need_rag_hint = None

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

    trash_words = [
        "apakah", "ada", "yang", "lebih", "detail", "lagi", "seperti", 
        "kalau", "gimana", "bagaimana", "sih", "cuy", "thanks", "ya", 
        "mohon", "info", "tentang", "atau", "dan", "di", "ke", "dari", "untuk",
        "buat", "dong", "sih?", "dong?", "ya?", "ketentuan", "ketentuannya", "ketentuannya?",
        "aturan", "aturannya", "aturannya?", "regulasi", "regulasinya", "regulasinya?",
        "kebijakan", "kebijakannya", "kebijakannya?", "apa", "aja", "saja",
        "jelaskan", "tolong", "kasih", "tau", "beritahu", "beri", "tahu", "jelasin",
        "bisa", "gak", "nggak", "engga", "ngga", "tidak", "dong,"
    ]
    words = [w for w in msg_lower.split() if w not in trash_words and len(w) > 2]
    if words:
        core = " ".join(words[:3])
        return [core, f"ketentuan {core}", f"regulasi {core}"]

    short = " ".join(msg.split()[:3])
    return [short, f"ketentuan {short}", f"regulasi {short}"]

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
    if module_name == "chitchat":
        return build_response_prompt_chitchat(employee_name, precheck, is_thinking)
    elif module_name == "coding":
        return build_response_prompt_coding(employee_name, precheck, is_thinking)
    elif module_name == "rag":
        return build_response_prompt_rag(employee_name, precheck, is_thinking, rag_context, rag_sources)
    elif module_name == "multi_document":
        return build_response_prompt_multi_document(employee_name, precheck, is_thinking, rag_context, rag_sources)
    elif module_name == "analytic":
        return build_response_prompt_analytic(employee_name, precheck, is_thinking)
    elif module_name == "self_correction":
        return build_response_prompt_self_correction(employee_name, precheck, is_thinking)
    elif module_name == "ambiguous":
        return build_response_prompt_ambiguous(employee_name, precheck, is_thinking)
    elif module_name == "general_expert":
        return build_response_prompt_general_expert(employee_name, precheck, is_thinking)
    else:
        return build_response_prompt_chitchat(employee_name, precheck, is_thinking)

def get_module_config(module_name: str) -> Dict[str, Any]:
    configs = {
        "chitchat": {"num_ctx": 8192, "temperature": 0.75}, # Naik dari 2048
        "coding": {"num_ctx": 8192, "temperature": 0.3},
        "rag": {"num_ctx": 16384, "temperature": 0.4},
        "multi_document": {"num_ctx": 16384, "temperature": 0.35},
        "analytic": {"num_ctx": 8192, "temperature": 0.3},
        "self_correction": {"num_ctx": 8192, "temperature": 0.5}, # Naik dari 4096
        "ambiguous": {"num_ctx": 4096, "temperature": 0.6}, # Naik dari 2048
        "general_expert": {"num_ctx": 8192, "temperature": 0.6}, # Naik dari 4096
    }
    return configs.get(module_name, configs["chitchat"])
