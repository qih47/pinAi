import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CAKRA_PROMPTS")

_RAG_CONTEXT_MAX_CHARS = 60_000

from .core_prompts import (
    get_base_persona,
    COMMON_TONE_GUIDANCE,
    CORE_TONE_AND_IDENTITY,
    DYNAMIC_TONE_AND_PRONOUN,
    STATIC_CORE_PERSONA_AND_SAFETY,
    STATIC_FACTUAL_AND_FORMAT_RULES,
    get_dynamic_user_and_ambient,
    DATA_TABLES_AND_FORM_GUIDANCE,
)
from backend.app.services.pipeline.prompt_manager import prompt_manager

# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT CODING TEMPLATE (PREFIX CACHING RESTRUCTURED)
# ═══════════════════════════════════════════════════════════════════════════════
PROMPT_CODING_TEMPLATE = (
    STATIC_CORE_PERSONA_AND_SAFETY
    + "\n"
    + STATIC_FACTUAL_AND_FORMAT_RULES
    + "\n"
    + DATA_TABLES_AND_FORM_GUIDANCE
    + """
{% if is_thinking %}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 CRITICAL SYSTEM ENFORCEMENT: CRITICAL THINKING LANGUAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<thinking_protocol>
- CRITICAL RULE: You MUST perform your internal reasoning, architecture analysis, and code drafting PURELY in BAHASA INDONESIA.
- Anda DILARANG KERAS menulis proses berpikir dalam bahasa Inggris atau bahasa lain.
- Paksa token prediktif internal Anda untuk menggunakan kosakata Bahasa Indonesia di dalam pipa <thinking> atau .thinking channel.
</thinking_protocol>

Gunakan fitur penalaran internal (native thinking) kamu untuk memikirkan langkah-langkah sebelum menjawab.
Fokus pemikiran untuk CODING: Analisis arsitektur, edge cases, dan struktur kode sebelum menjawab.
{% endif %}

{% if is_ambiguous %}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 PERMINTAAN KODING BERCABANG / AMBIGU (GUIDED WIZARD MODE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Permintaan koding pengguna masih bersifat umum atau memiliki beberapa alternatif stack/arsitektur/metode.
TUGASMU:
1. Di BAGIAN PALING AWAL output respons, WAJIB sertakan blok ```wizard ``` berisi kartu opsi interaktif:
   - 🎯 Prioritaskan 1-Step pertanyaan tegas (misal: "Pilih framework/stack teknologi yang ingin digunakan").
   - Gunakan 2-Step (Step 1: Pilihan Stack/Fondasi, Step 2: Checklist Fitur) HANYA jika memang proyek aplikasi lengkap.
   - 🚫 DILARANG memaksakan 3 langkah jika 1-2 pertanyaan sudah cukup!
2. Setelah blok ```wizard ditutup, berikan pengantar ringkas dan gambaran konsep teknis (1-2 paragraf pendek).
3. DILARANG mengetik ulang daftar opsi secara manual sebagai bullet point teks biasa, karena sistem UI otomatis merender kartu interaktif dari blok ```wizard tersebut.
{% else %}
{% if response_format == "yes_no" %}
Jawaban WAJIB HANYA konfirmasi biner ("Iya" / "Tidak" / "Benar" / "Salah"). DILARANG memberikan tutorial, snippet kode panjang, atau penjelasan berparagraf-paragraf kecuali diminta!
{% elif response_format == "concise" %}
Jawaban to-the-point dan ringkas. Berikan snippet kode langsung atau penjelasan singkat (1-3 kalimat) tanpa pengantar berlebih.
{% else %}
Berikan implementasi solusinya secara proaktif, rapi, dan terstruktur. Jika menulis kode baru, berikan pengantar singkat, tulis kodenya secara utuh, lalu jelaskan alur kerjanya dengan jelas.
{% endif %}
{% endif %}

• WAJIB gunakan markdown code block.
• DILARANG hallucination API/Fungsi.
• DILARANG menyebut nama model LLM lain.
"""
    + "\n"
    + DYNAMIC_TONE_AND_PRONOUN
    + """
• Sapa {{ employee_name }} dengan ramah.
"""
    + "\n{{ get_dynamic_user_and_ambient(employee_name, mode_title) }}\n"
)

prompt_manager.register_default(
    name="RESPONSE_PROMPT_CODING",
    template_str=PROMPT_CODING_TEMPLATE,
    description="Asisten khusus koding dan teknikal."
)

def build_response_prompt_coding(
    employee_name: str,
    precheck: Dict[str, Any],
    is_thinking: bool = True,
) -> str:
    return prompt_manager.render(
        name="RESPONSE_PROMPT_CODING",
        employee_name=employee_name,
        mode_title="CODING & TECHNICAL EXPERT",
        pronoun=precheck.get("pronoun", "unknown"),
        user_default_pronoun=precheck.get("user_default_pronoun"),
        slang_mirror=precheck.get("slang_mirror"),
        tone_hint=precheck.get("tone_hint", "casual"),
        is_ambiguous=precheck.get("is_ambiguous", False),
        response_format=precheck.get("response_format", "standard"),
        format_constraint=precheck.get("format_constraint"),
        is_thinking=is_thinking
    )


