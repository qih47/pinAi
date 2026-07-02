import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CAKRA_PROMPTS")

_RAG_CONTEXT_MAX_CHARS = 60_000

from .core_prompts import _get_base_persona, _get_tone_guidance



def build_response_prompt_coding(
    employee_name: str,
    precheck: Dict[str, Any],
    is_thinking: bool = True,
) -> str:
    pronoun = precheck.get("pronoun", "unknown")
    prompt = _get_base_persona(employee_name, "CODING & TECHNICAL EXPERT")
    
    if is_thinking:
        prompt += """
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
"""
    else:
        prompt += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ INSTRUKSI DETAIL (THINKING MODE: OFF)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Jawaban akhir WAJIB komprehensif dan panjang.
Jika ada kode, JANGAN sekadar menaruh snippet. Berikan pengantar, tulis kodenya, lalu jelaskan alurnya (step-by-step) agar user paham cara kerjanya.
"""

    prompt += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 GAYA BAHASA & ATURAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_get_tone_guidance(pronoun)}
• Sapa {employee_name} dengan ramah.
• WAJIB gunakan markdown code block.
• DILARANG hallucination API/Fungsi.
• DILARANG menyebut nama model LLM lain.
"""
    return prompt

