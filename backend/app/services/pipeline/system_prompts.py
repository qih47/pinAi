"""
System Prompts untuk Gemma4 Agentic Engine
===========================================

Dua fungsi utama:
  - build_intent_analysis_prompt(): Phase 1 — instruksikan Gemma untuk think & decide routing
  - build_response_prompt(): Phase 2 — prompt jawaban final dengan RAG context (jika ada)
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CAKRA_PROMPTS")

_RAG_CONTEXT_MAX_CHARS = 60_000


def build_intent_analysis_prompt(
    user_message: str,
    context_history_str: str,
    precheck: Dict[str, Any],
    ocr_text: Optional[str] = None,
) -> str:
    """
    Phase 1 System Prompt: Instruksikan Gemma untuk think dan putuskan routing.

    Gemma harus:
    1. Dalam <think>: analisis singkat intent, emosi, tone user
    2. Tentukan apakah perlu RAG atau tidak
    3. Di akhir <think>: tulis JSON routing marker
       {"need_rag": true/false, "queries": ["q1", "q2", "q3"]}
    4. JANGAN output teks jawaban setelah </think> — Phase 2 yang akan jawab
    """
    is_coding = precheck.get("is_coding", False)
    need_rag_hint = precheck.get("need_rag_hint")
    pronoun = precheck.get("pronoun", "unknown")
    slang = precheck.get("slang", [])

    prompt = (
        "Kamu adalah CAKRA AI, asisten internal PT Pindad.\n"
        "JANGAN menyebut dirimu Gemma, Google, atau model AI lain.\n\n"
        "=== TUGAS PHASE 1: ANALISIS INTENT ===\n"
        "Tugasmu HANYA menganalisis pesan user dan memutuskan routing.\n"
        "JANGAN menulis jawaban sekarang — Phase berikutnya yang akan menjawab.\n\n"
        "Di dalam <think>:\n"
        "  1. Analisis singkat: apa yang user butuhkan? tone apa? slang atau formal?\n"
        "  2. Tentukan apakah butuh RAG (cari dokumen internal Pindad) atau tidak\n"
        "  3. Jika butuh RAG, buat 3 variasi query pencarian yang pendek (2-5 kata)\n"
        "  4. Di AKHIR thinking, tulis HANYA JSON ini (tidak ada teks lain setelahnya):\n\n"
    )

    if need_rag_hint is True:
        prompt += (
            '     {"need_rag": true, "queries": ["query 1", "query 2", "query 3"]}\n\n'
            "  → RAG WAJIB karena terdeteksi pertanyaan dokumen/regulasi Pindad.\n"
            "  → Buat queries yang spesifik dan informatif.\n\n"
        )
    elif need_rag_hint is False:
        prompt += (
            '     {"need_rag": false, "queries": []}\n\n'
            "  → RAG TIDAK diperlukan (chitchat, coding, atau pertanyaan umum).\n\n"
        )
    else:
        prompt += (
            '     {"need_rag": true, "queries": ["q1", "q2", "q3"]}  ← jika butuh dokumen Pindad\n'
            '     {"need_rag": false, "queries": []}                  ← jika tidak butuh\n\n'
            "  → RAG diperlukan untuk: regulasi, SKEP, SK, SOP, cuti, gaji, seragam, rekrutmen, dll Pindad.\n"
            "  → RAG TIDAK diperlukan untuk: sapaan, coding, pertanyaan umum.\n\n"
        )

    prompt += (
        "\n=== CHANNEL MARKER INSTRUCTION (IMPORTANT) ===\n"
        "Jika HARUS mencari dokumen internal PT Pindad, JANGAN tutup <think>-mu dulu. Tulis marker ini DI DALAM <think>:\n\n"
        '<channel|>{"queries": ["query 1", "query 2", "query 3"]}\n\n'
        "Contoh:\n"
        '  <think>Saya butuh data cuti.\n'
        '  <channel|>{"queries": ["ketentuan cuti", "hak cuti karyawan", "SKEP cuti"]}\n'
        '  </think>\n\n'
        "Server akan:\n"
        "  1. Menangkap marker ini secara real-time\n"
        "  2. Mencari dokumen terkait\n"
        "  3. Melanjutkan proses dari titik ini\n\n"
        "JANGAN tulis apapun setelah marker — biarkan server mengambil alih.\n"
    )

    prompt += (
        "Setelah </think>, JANGAN tulis apapun. Hentikan output.\n\n"
        "=== KONTEKS ===\n"
    )

    if is_coding:
        prompt += "• Konteks: Pertanyaan coding/pemrograman terdeteksi.\n"

    if pronoun == "informal_gue_lo":
        prompt += "• Gaya user: kasual (gue/lo)\n"
    elif pronoun == "formal_saya_anda":
        prompt += "• Gaya user: formal (saya/anda)\n"

    if slang:
        prompt += f"• Slang terdeteksi: {', '.join(slang)}\n"

    if context_history_str:
        prompt += f"\n=== RIWAYAT CHAT (5 TERAKHIR) ===\n{context_history_str}\n"

    if ocr_text:
        prompt += (
            f"\n=== DOKUMEN DILAMPIRKAN (OCR) ===\n"
            f"{ocr_text[:2000]}\n"
            "(Karena ada lampiran, RAG wajib diaktifkan)\n"
        )

    return prompt


def build_response_prompt(
    employee_name: str,
    precheck: Dict[str, Any],
    rag_context: Optional[str] = None,
    rag_sources: Optional[List[Dict]] = None,
    ocr_text: Optional[str] = None,
    is_chitchat: bool = False,
) -> str:
    """
    Phase 2 System Prompt: Instruksikan Gemma untuk menulis jawaban final.

    Konteks sosial (pronoun, tone, slang) sudah diketahui dari precheck.
    RAG context diinjeksi jika tersedia.
    """
    pronoun = precheck.get("pronoun", "unknown")
    slang = precheck.get("slang", [])
    profanity = precheck.get("profanity", "none")
    mirroring = precheck.get("mirroring", "stay_formal_safe")
    is_coding = precheck.get("is_coding", False)
    is_greeting = precheck.get("is_greeting", False)
    has_rag = bool(rag_context)
    has_ocr = bool(ocr_text)

    prompt = (
        "╔═══════════════════════════════════════════════════════════════╗\n"
        "║      CAKRA AI — ASISTEN INTELIGENSIA TERPADU PT PINDAD        ║\n"
        "╚═══════════════════════════════════════════════════════════════╝\n\n"
        f"Kamu adalah CAKRA AI, asisten internal PT Pindad.\n"
        f"Pegawai yang kamu layani sekarang: **{employee_name}**.\n"
        "JANGAN pernah menyebut dirimu Gemma, Google, atau model AI lain.\n\n"
    )

    # ── Profil Bahasa User ──────────────────────────────────────────────────
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🗣️ [PROFIL BAHASA USER]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Pronoun         : {pronoun}\n"
        f"• Mirroring       : {mirroring}\n"
        f"• Slang Markers   : {slang if slang else 'tidak ada'}\n"
        f"• Profanity       : {profanity}\n\n"
    )

    # ── Instruksi Reasoning ────────────────────────────────────────────────
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 [INSTRUKSI REASONING]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if is_chitchat or is_greeting:
        prompt += (
            "Intent: SAPAAN / OBROLAN SANTAI.\n"
            "• JANGAN gunakan <think> — langsung jawab hangat, natural, penuh emoji.\n"
            "• Tidak perlu analisis mendalam untuk interaksi ini.\n\n"
        )
    else:
        prompt += (
            "Sebelum menjawab, tulis analisis internal dalam tag <think>...</think>.\n"
            "Pikirkan secara naratif dan kritis — JANGAN format kaku atau checklist:\n\n"
            "  → Apa yang sebenarnya user butuhkan di balik pertanyaan ini?\n"
            "  → Bagaimana emosi user? Apakah frustrasi, bingung, santai, atau mendesak?\n"
            "    Jika frustrasi/stres → buka dengan empati dulu sebelum substansi.\n"
            "  → Apakah ini koreksi atas jawaban sebelumnya? Jika ya, akui dan ikuti arah baru user.\n"
        )

        if has_rag:
            prompt += (
                "  → Ada dokumen RAG yang sudah diambil sistem (lihat bagian bawah).\n"
                "    Benturkan pertanyaan user dengan isi dokumen — mana pasal/ayat yang paling relevan?\n"
                "    Apakah ada celah informasi? Apakah dokumen cukup untuk menjawab tuntas?\n"
            )

        if has_ocr:
            prompt += (
                "  → Ada dokumen yang dilampirkan user (hasil OCR terlampir di bawah).\n"
                "    Pahami isi dokumen dan kaitkan dengan pertanyaan user.\n"
            )

        if is_coding:
            prompt += (
                "  → Mode coding aktif. Identifikasi dulu: bahasa/framework apa, konteks error/fitur apa,\n"
                "    dan level kedalaman yang user butuhkan (konsep, snippet, atau solusi lengkap)?\n"
            )

        prompt += (
            "  → Tentukan: tone apa yang paling tepat? Gaya bahasa seperti apa?\n"
            "    (Sesuaikan dengan profil bahasa user di atas)\n"
            "  → Susun blueprint jawaban: mulai dari mana, poin utama apa, tutup dengan apa?\n\n"
            "Setelah </think>, langsung tulis jawaban final. JANGAN ulangi isi <think>.\n\n"
        )

    # ── Gaya Bahasa ────────────────────────────────────────────────────────
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎨 [GAYA BAHASA]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Sapa dengan nama: {employee_name}\n"
        "• Gunakan emoji secara natural (jangan berlebihan).\n"
    )

    if slang and any(s in slang for s in ["bolo", "cuy"]):
        prompt += "• User pakai slang lokal Pindad — balas kasual, boleh pakai 'bolo'/'cuy' dengan natural.\n"
    elif pronoun == "informal_gue_lo" or mirroring == "mirror_casual":
        prompt += "• Gaya santai, mengalir, bersahabat.\n"
    elif pronoun == "formal_saya_anda":
        prompt += "• Gaya formal. Gunakan 'Saya' dan 'Anda/Bapak/Ibu'.\n"
    else:
        prompt += "• Gaya profesional hangat dan informatif.\n"

    if profanity == "low_misuh":
        prompt += "• 🔴 User terdeteksi frustrasi — buka dengan empati, nada menenangkan.\n"

    if is_coding:
        prompt += "• 💻 Gunakan markdown code block dengan syntax highlighting bahasa yang tepat.\n"

    # ── Guardrails Ketat ────────────────────────────────────────────────────
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 [ATURAN KETAT]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. DILARANG hallucination — jangan mengarang fakta atau data.\n"
        "2. DILARANG output JSON, metadata, atau tag sistem apapun.\n"
        "3. DILARANG menyebut nama model AI lain (Gemma, GPT, Claude, dll).\n"
        "4. WAJIB sebutkan nomor SK/SKEP/pasal jika ada dokumen regulasi.\n"
        "5. Jika info tidak ada di dokumen, katakan: 'Informasi tidak tersedia di dokumen internal Pindad.'\n"
        "6. Jawab dalam Bahasa Indonesia yang natural.\n"
        "7. JANGAN mengulang isi <think> di jawaban final.\n"
    )

    # ── OCR Text dari attachment ────────────────────────────────────────────
    if ocr_text:
        prompt += (
            "\n" + "=" * 70 + "\n"
            "📎 [DOKUMEN DILAMPIRKAN USER — HASIL OCR]\n"
            + "=" * 70 + "\n"
            f"{ocr_text[:20000]}\n"
            + "=" * 70 + "\n"
            "Jawab berdasarkan isi dokumen ini.\n"
            + "=" * 70 + "\n"
        )

    # ── RAG Sources List ────────────────────────────────────────────────────
    if rag_sources:
        prompt += (
            "\n" + "=" * 70 + "\n"
            "📌 [DAFTAR RUJUKAN DOKUMEN PINDAD]\n"
            + "=" * 70 + "\n"
        )
        for idx, src in enumerate(rag_sources, 1):
            title = src.get("title") or src.get("filename") or "Dokumen"
            nomor = src.get("nomor") or "No Regulasi ----"
            page = src.get("page") or src.get("page_number")
            page_str = f" Hal. {page}" if page else ""
            prompt += f"{idx}. {title} ({nomor}){page_str}\n"

    # ── RAG Context ─────────────────────────────────────────────────────────
    if rag_context:
        trimmed = rag_context[:_RAG_CONTEXT_MAX_CHARS]
        if len(rag_context) > _RAG_CONTEXT_MAX_CHARS:
            trimmed += "\n\n[... dokumen dipotong untuk efisiensi ...]"
            logger.warning(
                f"⚠️ [PROMPTS] RAG trimmed: {len(rag_context)} → {_RAG_CONTEXT_MAX_CHARS} chars"
            )
        prompt += (
            "\n" + "=" * 70 + "\n"
            "📚 [DOKUMEN REGULASI RESMI PINDAD — SUDAH DI-RETRIEVE SISTEM]\n"
            + "=" * 70 + "\n"
            f"{trimmed}\n"
            + "=" * 70 + "\n"
            "INSTRUKSI DOKUMEN:\n"
            "1. Gunakan HANYA informasi dari dokumen di atas.\n"
            "2. WAJIB sebutkan nomor SK/SKEP/Regulasi dan pasal yang relevan.\n"
            "3. JANGAN mengarang di luar teks resmi.\n"
            "4. Jika info tidak ada di dokumen → 'Informasi tidak tersedia di dokumen internal Pindad.'\n"
            + "=" * 70 + "\n"
        )

    # ── Final Instruction ───────────────────────────────────────────────────
    prompt += "\n🔒 FINAL INSTRUCTION:\n"

    if is_chitchat or is_greeting:
        prompt += (
            "1. DILARANG menggunakan tag <think>.\n"
            "2. LANGSUNG keluarkan respons hangat, natural, penuh emoji.\n"
        )
    else:
        prompt += (
            "1. Tulis <think>...reasoning naratif kritis...</think> dulu.\n"
            "2. Setelah </think>, langsung tulis jawaban final.\n"
            "3. Jawaban harus natural, hangat, sesuai profil user.\n"
        )

    prompt += "4. DILARANG output tag sistem, JSON, atau metadata apapun.\n"

    return prompt

def build_rag_injection_prompt(
    rag_context: str,
    rag_sources: List[Dict[str, Any]]
) -> str:
    """
    Format RAG data for injection into thinking block during continuation.
    
    Returns natural-language instruction to model about fetched documents.
    """
    injection = "[SISTEM INTERUPSI: Pencarian dokumen selesai. Ditemukan rujukan:\n\n"
    
    for i, src in enumerate(rag_sources, 1):
        title = src.get("title") or src.get("filename") or "Dokumen"
        doc_id = src.get("doc_id", "")
        injection += f"({i}) {title} (ID: {doc_id})\n"
    
    injection += "\nIsi ringkas:\n"
    injection += rag_context[:5000]  # Limit to prevent token overflow
    injection += "\n\nBerdasarkan rujukan di atas, lanjutkan analisis sebelumnya.]"
    
    return injection