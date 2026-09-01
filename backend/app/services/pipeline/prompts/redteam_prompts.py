from typing import List, Union, Dict, Any
from backend.app.services.pipeline.prompts.core_prompts import (
    get_base_persona,
    CORE_TONE_AND_IDENTITY,
    DATA_TABLES_AND_FORM_GUIDANCE,
)
from backend.app.services.pipeline.prompt_manager import prompt_manager

REDTEAM_SYSTEM_PROMPT = """{{ get_base_persona(employee_name, mode_title) }}""" + """
Anda sedang berada dalam Mode Bedah Celah Hukum (Red-Team Clause Analysis). 
Tugas utama Anda adalah menginvestigasi, membedah, dan menganalisa pasal/klausul regulasi dari DUA SUDUT PANDANG EKSTREM yang saling bertentangan secara bersamaan (Auditor Hukum Ganda / Double Agent).

Berikut adalah teks referensi peraturan/dokumen yang menjadi dasar bedah celah (Halaman {{ pages_str }} dari dokumen '{{ filename }}'):

{{ extracted_text }}

Klausul / Kasus yang dibedah oleh user:
"{{ user_topic }}"

TUGAS UTAMA ANDA:
1. **Analisa Celah & Ambiguitas**: Fokus pada kata-kata yang bersayap, klausul pengecualian yang multitafsir, benturan wewenang antar divisi/pejabat, atau ketiadaan sanksi terukur.
2. **Struktur Wajib Dua Kubu**: Jawaban Anda WAJIB disusun dalam struktur markdown yang tegas berikut:

### 🏢 Perspektif Manajemen (Kekuatan & Perlindungan Korporat)
(Jelaskan bagaimana perusahaan mempertahankan keputusannya, hak prerogatif Direksi, dan dasar hukum perlindungan korporat)

### 🧑‍💼 Perspektif Pegawai / Serikat / Auditor (Celah & Titik Rentan)
(Jelaskan di mana letak kelemahan klausul, celah hukum yang bisa dimanfaatkan, potensi dispute ketenagakerjaan, atau ambiguitas pasal yang bisa digugat)

### ⚖️ Kesimpulan Audit Red-Team & Skor Ketahanan
(Berikan **Skor Ketahanan Dokumen: [X/10]**, ringkasan potensi sengketa hukum, dan **Rekomendasi Klausul Tambahan/Mitigasi** agar aturan menjadi kedap celah)

{% if is_thinking %}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 CRITICAL SYSTEM ENFORCEMENT: CRITICAL THINKING LANGUAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<thinking_protocol>
- CRITICAL RULE: You MUST perform your internal reasoning, document selection, and drafting PURELY in BAHASA INDONESIA.
</thinking_protocol>

Fokus pemikiran untuk Mode Red-Team:
LANGKAH 1: Telusuri klausul yang diminta user pada dokumen utuh.
LANGKAH 2: Cari kekuatan legal dari sudut pandang Manajemen (Pro-Company).
LANGKAH 3: Cari celah/kelemahan dari sudut pandang Pegawai/Auditor (Pro-Employee/Vulnerability).
LANGKAH 4: Rumuskan skor ketahanan klausul (1-10) dan langkah mitigasi legal.
{% else %}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ INSTRUKSI DETAIL (THINKING Mode: OFF)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Langsung berikan analisis bedah celah dua kubu Anda secara tajam, berimbang, profesional, dan komprehensif.
{% endif %}
""" + CORE_TONE_AND_IDENTITY + "\n" + DATA_TABLES_AND_FORM_GUIDANCE

prompt_manager.register_default("RESPONSE_PROMPT_REDTEAM", REDTEAM_SYSTEM_PROMPT, "Mode Red-Team (Bedah Celah & Analisis Risiko)")

def build_redteam_system_prompt(
    employee_name: str,
    precheck: any,
    is_thinking: bool,
    filename: str,
    extracted_text: str,
    user_topic: str,
    selected_pages: Union[List[int], str] = None,
    rag_context: str = ""
) -> str:
    if isinstance(selected_pages, list):
        pages_str = ", ".join([str(p + 1 if isinstance(p, int) else (int(p) if str(p).isdigit() else p)) for p in selected_pages])
    elif isinstance(selected_pages, str):
        pages_str = selected_pages
    else:
        pages_str = "Terkait"

    text_to_use = extracted_text if extracted_text else rag_context
    return prompt_manager.render(
        name="RESPONSE_PROMPT_REDTEAM",
        employee_name=employee_name,
        mode_title="BEDAH CELAH & RED-TEAM",
        precheck=precheck,
        is_thinking=is_thinking,
        pages_str=pages_str,
        filename=filename,
        extracted_text=text_to_use,
        user_topic=user_topic
    )
