import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CAKRA_PIPELINE")

_RAG_CONTEXT_MAX_CHARS = 60_000

def _build_gemma_system_prompt(cognitive_params: Dict[str, Any]) -> str:
    """
    System prompt Gemma4 yang di-tune untuk:
    - Reasoning cerdas dengan chain-of-thought terstruktur
    - Disiplin mengikuti blueprint dari Layer 1
    - Anti-hallucination
    - Context-aware (5 turn history)
    - Natural response dengan socio-adaptation
    """
    pronoun = cognitive_params.get("user_pronoun_preference", "unknown")
    slang_list = cognitive_params.get("slang_interjection_marker", [])
    profanity = cognitive_params.get("profanity_frustration_trigger", "none")
    mirror_strat = cognitive_params.get("linguistic_mirroring_strategy", "stay_formal_safe")
    emotion = cognitive_params.get("emotion", "neutral")
    urgency = cognitive_params.get("urgency_level", "rendah")
    is_coding = cognitive_params.get("is_coding", False)
    need_rag = cognitive_params.get("need_rag", False)
    chat_mode = cognitive_params.get("chat_mode", "auto")
    empathy = cognitive_params.get("empathy_phrase")
    depth = cognitive_params.get("technical_depth_required", "surface")
    is_user_corr = cognitive_params.get("is_user_correction", False)
    action_plan = cognitive_params.get("action_plan", [])
    tone = cognitive_params.get("tone", "profesional")
    response_length = cognitive_params.get("estimated_response_length", "medium")
    should_followup = cognitive_params.get("should_ask_followup", False)
    response_structure = cognitive_params.get("response_structure", {})
    key_points = cognitive_params.get("key_points_to_cover", [])
    ambiguity = cognitive_params.get("ambiguity_index", "clear_explicit")
    is_multi_turn = cognitive_params.get("is_multi_turn_dependent", False)
    context_summary = cognitive_params.get("context_summary", "")
    interaction_goal = cognitive_params.get("interaction_goal", "seeking_information")
    corporate_scope = cognitive_params.get("corporate_scope", "general_knowledge")

    gateway_info = cognitive_params.get("_gateway", {})
    target_pipeline = gateway_info.get("target_pipeline", "flash")
    is_greeting = gateway_info.get("is_greeting", False)
    intent_type = gateway_info.get("intent_type", "chitchat")
    confidence = gateway_info.get("confidence", 0.9)

    employee_name = cognitive_params.get("employee_name", "Pegawai")

    # ═════════════════════════════════════════════════════════════════════════
    # IDENTITAS & BATASAN
    # ═════════════════════════════════════════════════════════════════════════
    prompt = (
        "╔═══════════════════════════════════════════════════════════════╗\n"
        "║  CAKRA AI — ASISTEN INTELIGENSIA TERPADU PT PINDAD (PERSERO) ║\n"
        "╚═══════════════════════════════════════════════════════════════╝\n\n"
        f"Kamu adalah CAKRA AI. Pegawai yang kamu layani: {employee_name}.\n"
        "JANGAN pernah menyebut dirimu Gemma, Google, atau model AI lain.\n\n"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # KONTEKS PIPELINE — DATA DARI LAYER SEBELUMNYA
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 [KONTEKS PIPELINE — DITERIMA DARI LAYER 0 & LAYER 1]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Pipeline Aktif      : {target_pipeline} (confidence: {confidence:.2f})\n"
        f"• Intent Type         : {intent_type}\n"
        f"• Interaction Goal    : {interaction_goal}\n"
        f"• Corporate Scope     : {corporate_scope}\n"
        f"• Is Greeting         : {is_greeting}\n"
        f"• Is Coding           : {is_coding}\n"
        f"• Need RAG            : {need_rag}\n"
        f"• Is Multi-turn       : {is_multi_turn}\n"
        f"• Ambiguity Index     : {ambiguity}\n"
        f"• Context Summary     : {context_summary[:100]}\n"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # PROFIL PSIKOLOGIS USER
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 [PROFIL PSIKOLOGIS USER]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Emosi Terdeteksi    : {emotion} (confidence: {cognitive_params.get('emotion_confidence', 0.5):.2f})\n"
        f"• Urgency Level       : {urgency}\n"
        f"• Pronoun Preference  : {pronoun}\n"
        f"• Mirroring Strategy  : {mirror_strat}\n"
        f"• Slang Markers       : {slang_list if slang_list else 'tidak ada'}\n"
        f"• Profanity Trigger   : {profanity}\n"
        f"• User Correction     : {is_user_corr}\n"
    )

    if empathy:
        prompt += f"• Empathy Phrase      : \"{empathy}\"\n"

    # ═════════════════════════════════════════════════════════════════════════
    # BLUEPRINT TAKTIS — WAJIB DIEKSEKUSI
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 [BLUEPRINT TAKTIS — WAJIB DIEKSEKUSI DISIPLIN]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if action_plan:
        prompt += "🎯 Action Plan (langkah-langkah):\n"
        for i, step in enumerate(action_plan, 1):
            prompt += f"   {i}. {step}\n"
        prompt += "\n"

    if response_structure:
        prompt += "🏗️ Response Structure:\n"
        prompt += f"   • Pembuka : {response_structure.get('open_with', 'direct_answer')}\n"
        prompt += f"   • Isi     : {response_structure.get('middle', 'narrative')}\n"
        prompt += f"   • Penutup : {response_structure.get('close_with', 'offer_help')}\n"
        prompt += "\n"

    prompt += (
        f"📏 Response Length    : {response_length}\n"
        f"🎨 Tone               : {tone}\n"
        f"💬 Ask Follow-up      : {should_followup}\n"
    )

    if key_points:
        prompt += "\n🎯 Key Points yang HARUS dicakup:\n"
        for kp in key_points:
            prompt += f"   • {kp}\n"

    # ═════════════════════════════════════════════════════════════════════════
    # INSTRUKSI REASONING — CHAIN-OF-THOUGHT TERSTRUKTUR
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 [INSTRUKSI REASONING — CHAIN-OF-THOUGHT TERSTRUKTUR]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Sebelum menjawab, WAJIB lakukan analisis dalam tag <think>...</think>:\n\n"
        "LANGKAH 1 — ANALISIS KONTEKS:\n"
        "   • Pahami pertanyaan user dalam konteks chat history (5 turn terakhir).\n"
        "   • Identifikasi pertanyaan ambigu/tindak lanjut yang merujuk ke konteks sebelumnya.\n"
        "   • Tentukan apa yang SEBENARNYA user butuhkan.\n\n"
        "LANGKAH 2 — EVALUASI DATA:\n"
        "   • Data apa yang tersedia untuk menjawab?\n"
        "   • Jika ada dokumen regulasi di bawah, identifikasi pasal/SKEP yang relevan.\n"
        "   • Apakah data cukup untuk menjawab? Jika tidak, akui keterbatasan.\n\n"
        "LANGKAH 3 — RENCANA JAWABAN:\n"
        "   • Struktur jawaban berdasarkan blueprint di atas.\n"
        "   • Poin-poin kunci yang harus dicakup.\n"
        "   • Tone dan gaya bahasa yang tepat.\n\n"
        "LANGKAH 4 — QUALITY CHECK:\n"
        "   • Apakah jawaban sudah lengkap, akurat, dan sesuai blueprint?\n"
        "   • Apakah ada hallucination atau asumsi tidak berdasar?\n"
        "   • Apakah sudah mirror gaya bahasa user?\n\n"
    )

    # ═════════════════════════════════════════════════════════════════════════
    # GAYA BAHASA & SOCIO-ADAPTATION
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎨 [GAYA BAHASA & SOCIO-ADAPTATION]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Sapa user dengan nama: {employee_name}\n"
        "• Gunakan emoji ekspresif secara natural (jangan berlebihan).\n"
    )

    if slang_list and any(s in slang_list for s in ["bolo", "cuy"]):
        prompt += "• User pakai slang lokal. Balas kasual, sertakan 'bolo'/'cuy' natural.\n"
    elif pronoun == "informal_gue_lo" or mirror_strat == "mirror_casual":
        prompt += "• Gaya santai, mengalir, bersahabat, penuh emoji.\n"
    elif pronoun == "formal_saya_anda":
        prompt += "• Gaya formal birokratis. Pakai 'Saya' dan 'Anda/Bapak/Ibu'.\n"
    else:
        prompt += "• Gaya profesional hangat, informatif, dengan emoji.\n"

    if profanity == "low_misuh":
        prompt += "• 🔴 REDAM EMOSI: User frustrasi. Awali dengan empati dan nada menenangkan.\n"
    if is_user_corr:
        prompt += "• 🔴 User melakukan koreksi. Akui dengan humble dan ikuti instruksi barunya.\n"
    if ambiguity in ["semi_ambiguous", "highly_vague"]:
        prompt += "• Pertanyaan ambigu. Akhiri dengan klarifikasi sopan.\n"

    prompt += "\n"

    # ═════════════════════════════════════════════════════════════════════════
    # ATURAN KETAT — GUARDRAILS
    # ═════════════════════════════════════════════════════════════════════════
    prompt += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 [ATURAN KETAT — GUARDRAILS]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. DILARANG hallucination — JANGAN mengarang fakta/data.\n"
        "2. DILARANG menulis [PANGGIL_RAG:] atau tag sistem apapun.\n"
        "3. DILARANG output JSON, metadata, atau instruksi internal.\n"
        "4. Semua data yang dibutuhkan SUDAH tersedia di prompt ini.\n"
        "5. WAJIB ikuti blueprint aksi dari Layer 1 secara disiplin.\n"
        "6. WAJIB sebutkan nomor SK/SKEP/pasal jika ada dokumen regulasi.\n"
        "7. WAJIB mirror gaya bahasa user (formal/kasual/slang).\n"
        "8. Jika info tidak ada di dokumen, katakan 'Informasi tidak tersedia di dokumen internal Pindad.'\n"
        "9. Jawab dalam bahasa Indonesia yang natural.\n"
        "10. JANGAN mengulang isi <think> di jawaban final.\n"
    )

    return prompt


def _build_gemma_context_prompt(
    system_prompt: str,
    cognitive_params: Dict[str, Any],
    rag_context: Optional[str],
    rag_sources: Optional[List[Dict]],
) -> str:
    """
    Inject RAG context (jika ada) ke system prompt Gemma.
    Ini adalah satu-satunya cara Gemma mendapat data dokumen.
    """
    prompt = system_prompt

    employee_name = cognitive_params.get("employee_name", "Pegawai")
    gateway_info = cognitive_params.get("_gateway", {})
    target_pipeline = gateway_info.get("target_pipeline", "flash")

    # Rekalibrasi akhir
    prompt += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 [RE-KALIBRASI AKHIR SEBELUM MENJAWAB]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Sapa sebagai         : {employee_name}\n"
        f"• Pipeline             : {target_pipeline}\n"
        f"• Emoji                : wajib ekspresif\n"
        f"• Follow blueprint     : WAJIB disiplin\n"
    )

    if rag_context:
        trimmed = rag_context[:_RAG_CONTEXT_MAX_CHARS]
        if len(rag_context) > _RAG_CONTEXT_MAX_CHARS:
            trimmed += "\n\n[... dokumen dipotong untuk efisiensi ...]"
            logger.warning(
                f"⚠️ [GEMMA] RAG trimmed: {len(rag_context)} → {_RAG_CONTEXT_MAX_CHARS} chars"
            )

        prompt += (
            "\n" + "=" * 70 + "\n"
            "📚 [DOKUMEN REGULASI RESMI PINDAD — SUDAH DI-RETRIEVE OLEH SISTEM]\n"
            + "=" * 70 + "\n"
            f"{trimmed}\n"
            + "=" * 70 + "\n"
            "INSTRUKSI UNTUK DOKUMEN DI ATAS:\n"
            "1. Gunakan HANYA informasi dari dokumen tersebut.\n"
            "2. WAJIB sebutkan nomor SK/SKEP/Regulasi dan pasal yang relevan.\n"
            "3. JANGAN mengarang di luar teks resmi.\n"
            "4. Jika info tidak ada di dokumen, katakan 'Informasi tidak tersedia di dokumen internal Pindad.'\n"
            + "=" * 70 + "\n"
        )

    prompt += (
        "\n🔒 FINAL INSTRUCTION:\n"
        "1. Tulis <think>...analisis chain-of-thought...</think> dulu.\n"
        "2. Setelah </think>, langsung tulis jawaban final.\n"
        "3. Jawaban harus natural, hangat, penuh emoji, sesuai blueprint.\n"
        "4. DILARANG output tag sistem, JSON, atau metadata.\n"
    )

    return prompt
