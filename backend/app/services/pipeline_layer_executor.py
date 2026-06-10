"""
Sequential Cognitive Pipeline Layer Execution Module
Handles all layer logic for chat processing with 34 Cognitive Parameters
"""

import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response, stream_ollama_chat
from backend.app.services.vision_service import extract_text_from_files
from backend.app.services.rag_service import rag_service
from backend.app.services.memory_service import memory_service

logger = logging.getLogger("CAKRA_PIPELINE")


async def execute_layer_0_vision(
    request: Request,
    file_paths: List[str]
) -> Dict[str, Any]:
    """
    Layer 0: Vision Preprocessor (MiniCPM-V)
    Ekstraksi teks dari gambar/PDF
    """
    logger.info("📄 [LAYER 0] Vision Preprocessor starting...")
    result = await extract_text_from_files(file_paths)
    logger.info(f"✅ [LAYER 0] Complete | Status: {result['status']} | Pages: {result['page_count']}")
    return result


async def execute_layer_1_analyzer(
    request: Request,
    messages: List[Dict[str, str]],
    chat_history: List[Dict],
    employee_npp: Optional[str],
    ocr_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Layer 1: Cognitive Analyzer (Qwen 2.5)
    Gerbang utama orkestrator yang menghasilkan 34 Parameter Kognitif Super Kaya.
    """
    logger.info("🧠 [LAYER 1] Cognitive Analyzer starting...")
    
    system_prompt = (
        "Anda adalah Gerbang Utama & Orkestrator Utama CAKRA AI. Tugas Anda adalah melakukan analisis mendalam "
        "secara instan terhadap kueri user dan mengeluarkan output berupa JSON murni berisi 34 parameter kognitif.\n\n"
        "Output WAJIB berupa JSON murni (dilarang memunculkan teks pembuka, penutup, markdown, atau tag apa pun).\n\n"
        "STRUKTUR KONTRAK JSON 34 PARAMETER YANG WAJIB DIHASILKAN:\n"
        "1. emotion (frustrasi|confused|stressed|neutral|positive|anxious)\n"
        "2. emotion_confidence (float 0.0-1.0)\n"
        "3. empathy_phrase (string kalimat empati awal, atau null jika chit-chat sapaan ringan)\n"
        "4. need_rag (true|false)\n"
        "5. rag_query (string kueri pencarian dokumen)\n"
        "6. need_analytics (true|false)\n"
        "7. is_user_correction (true|false)\n"
        "8. previous_response_was_wrong (true|false)\n"
        "9. what_went_wrong (string deskripsi kesalahan sebelumnya)\n"
        "10. urgency_level (rendah|sedang|tinggi|kritis)\n"
        "11. context_summary (ringkasan pendek konteks masalah)\n"
        "12. detected_intent (CHITCHAT|RAG|ANALYTICS|NORMAL|SELF_CORRECTION)\n"
        "    * ATURAN KRITIS VALUE: Setel menjadi 'CHITCHAT' jika user hanya menyapa, basa-basi, atau menggunakan kata sapaan kasual ringan.\n"
        "13. extracted_entities (array of strings)\n"
        "14. requires_follow_up (true|false)\n"
        "15. security_clearance_required (low|medium|high|restricted)\n"
        "16. corporate_scope (internal_regulation|general_knowledge|personal_activity|technical_troubleshooting)\n"
        "17. is_policy_query (true|false)\n"
        "18. technical_depth_required (surface|conceptual|code_implementation|root_cause_analysis)\n"
        "19. is_multi_turn_dependent (true|false)\n"
        "20. data_extraction_needed (true|false)\n"
        "21. user_persona_style (casual_informal|formal_bureaucratic|defensive_frustrated|direct_to_the_point)\n"
        "22. cultural_nuance (pindad_internal|general_indonesian|technical_english)\n"
        "23. assumed_knowledge_level (novice|intermediate|expert)\n"
        "24. interaction_goal (seeking_information|solving_problem|validation_seeking|greeting_casual)\n"
        "25. pindad_division_affinity (senjata|amunisi|kendaraan_khusus|produk_industrial|korporat_umum|unknown)\n"
        "26. regulation_hierarchy_target (skep_direksi|instruksi_kerja|peraturan_perusahaan|sop_divisi|undang_undang|null)\n"
        "27. estimated_vram_urgency (low_bypass_safe|heavy_reasoning_required)\n"
        "28. rag_retrieval_strategy (exact_match_keyword|semantic_broad_search|multi_document_cross_reference|none)\n"
        "29. user_authority_level (pejabat_struktural|pegawai_pelaksana|fungsional_teknis|guest_user)\n"
        "30. ambiguity_index (clear_explicit|semi_ambiguous|highly_vague)\n"
        "31. user_pronoun_preference (informal_gue_lo|familiar_aku_kamu|formal_saya_anda|collective_kita_kami|unknown)\n"
        "    * Deteksi penggunaan kata ganti seperti gue, lo, saya, anda, aku, kamu secara presisi.\n"
        "32. slang_interjection_marker (array kata sapaan/seru lokal yang terdeteksi, contoh: ['bolo', 'cuy', 'p'])\n"
        "33. profanity_frustration_trigger (none|low_misuh|intense_angry)\n"
        "    * Deteksi kata umpatan lokal seperti 'asu', 'jancuk', dll. Jika luapan kekesalan biasa, setel 'low_misuh'.\n"
        "34. linguistic_mirroring_strategy (mirror_casual|stay_formal_safe|defuse_aggression|supportive_empathic)\n"
        "35. is_coding (true|false)\n"
        "    * ATURAN KRITIS VALUE: Setel menjadi true jika kueri user mengandung potongan kode pemrograman (React, Python, SQL, CSS, dll) atau menanyakan instruksi revisi kodingan secara spesifik."
    )
    
    user_message = messages[-1]["content"] if messages else ""
    
    memory_context = ""
    if employee_npp and employee_npp != "GUEST":
        mem = await memory_service.get_employee_long_term_memory(employee_npp)
        memory_context = f"\n[EMPLOYEE MEMORY]\n{mem}" if mem else ""
    
    ocr_context = ""
    if ocr_text:
        ocr_context = f"\n[OCR EXTRACTED TEXT FROM FILES]\n{ocr_text}\n"
    
    analyze_messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Analisis kueri user secara taktis:\n\nUSER QUERY:\n{user_message}{ocr_context}{memory_context}"
        }
    ]
    
    json_result = await generate_json_response(
        model_name=settings.MODEL_ROUTER,
        messages=analyze_messages,
        request=request,
        temperature=0.2,
        keep_alive=0,
        timeout=30.0
    )
    
    if not json_result:
        logger.warning("⚠️ [LAYER 1] Failed to generate JSON, using fallback")
        # 🔥 FIX: Mengoper kueri fisik asli agar parameter pencarian tidak hilang saat timeout
        json_result = _get_fallback_cognitive_params(user_message)
        
    fallback_ref = _get_fallback_cognitive_params(user_message)
    for key in fallback_ref:
        if key not in json_result:
            json_result[key] = fallback_ref[key]
    
    logger.info(f"✅ [LAYER 1] Complete | Intent: {json_result.get('detected_intent')} | RAG: {json_result.get('need_rag')}")
    return json_result


async def execute_layer_2_planner(
    request: Request,
    messages: List[Dict[str, str]],
    cognitive_params: Dict[str, Any],
    employee_npp: Optional[str]
) -> Dict[str, Any]:
    """
    Layer 2: Strategic Planner - sekarang include rag_sources
    """
    logger.info("📋 [LAYER 2] Strategic Planner starting...")
    
    rag_context = None
    rag_sources = []  # 🔥 NEW
    
    if cognitive_params.get("need_rag"):
        logger.info(f"📚 [LAYER 2] Executing RAG search...")

        raw_rag_query = cognitive_params.get("rag_query") or messages[-1]["content"]
        rag_query = raw_rag_query.strip()[:200]

        # 🔥 MODIFIED: Terima tuple (context, sources)
        rag_context, rag_sources = await rag_service.assemble_powerful_context(
            query=rag_query,
            limit=5
        )
        logger.info(f"✅ [LAYER 2] RAG complete | Context: {len(rag_context) if rag_context else 0} chars | Sources: {len(rag_sources)}")
    
    system_prompt = (
        "Anda adalah Strategic Planner CAKRA AI. Anda menerima data orkestrasi logika dan RAG dari gerbang utama.\n"
        "Tugas Anda adalah memproses petunjuk teknis tersebut dan merumuskan rencana aksi strategis struktural.\n\n"
        "Output WAJIB berupa JSON murni.\n\n"
        "Field JSON wajib include:\n"
        "- action_plan: [array of action steps]\n"
        "- response_structure: {open_with, middle, close_with}\n"
        "- key_points_to_cover: [array]\n"
        "- tone: suportif|profesional|empathetic|humble|encouraging|neutral\n"
        "- estimated_response_length: brief|medium|detailed\n"
        "- should_ask_followup: true|false\n"
        "- rag_utilized: true|false\n"
    )
    
    cluster_1_keys = [
        "detected_intent", "estimated_vram_urgency", "need_rag", "rag_query", 
        "rag_retrieval_strategy", "regulation_hierarchy_target", "pindad_division_affinity", 
        "security_clearance_required", "corporate_scope", "is_policy_query", 
        "technical_depth_required", "data_extraction_needed", "is_multi_turn_dependent"
    ]
    cluster_1_params = {k: cognitive_params.get(k) for k in cluster_1_keys if k in cognitive_params}
    
    cognitive_json_str = json.dumps(cluster_1_params, indent=2)
    rag_context_str = f"\n[RAG CONTEXT]\n{rag_context}\n" if rag_context else ""
    
    plan_messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Buat rencana tindakan berdasarkan parameter logis ini:\n\n{cognitive_json_str}{rag_context_str}\n\nGenerate strategy JSON."
        }
    ]
    
    json_result = await generate_json_response(
        model_name=settings.MODEL_REASONING,
        messages=plan_messages,
        request=request,
        temperature=0.4,
        keep_alive=0,
        timeout=120.0
    )
    
    if not json_result:
        logger.warning("⚠️ [LAYER 2] Failed to generate JSON, using fallback")
        json_result = _get_fallback_strategy_params()
    
    # 🔥 MODIFIED: Include rag_sources
    if rag_context:
        json_result["rag_context"] = rag_context
        json_result["rag_sources"] = rag_sources  # 🔥 NEW
        json_result["rag_utilized"] = True
    
    logger.info(f"✅ [LAYER 2] Complete | Tone: {json_result.get('tone')} | Sources: {len(rag_sources)}")
    return json_result


async def execute_layer_3_executor(
    request: Request,
    messages: List[Dict[str, str]],
    cognitive_params: Dict[str, Any],
    strategy_params: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    Layer 3: Social Executor (Gemma4)
    """
    logger.info("✍️ [LAYER 3] Social Executor starting...")
    
    pronoun = cognitive_params.get("user_pronoun_preference", "formal_saya_anda")
    slang_list = cognitive_params.get("slang_interjection_marker", [])
    profanity = cognitive_params.get("profanity_frustration_trigger", "none")
    mirror_strat = cognitive_params.get("linguistic_mirroring_strategy", "stay_formal_safe")
    emotion = cognitive_params.get("emotion", "neutral")
    urgency = cognitive_params.get("urgency_level", "rendah")
    style = cognitive_params.get("user_persona_style", "casual_informal")
    authority = cognitive_params.get("user_authority_level", "pegawai_pelaksana")
    goal = cognitive_params.get("interaction_goal", "seeking_information")
    ambiguity = cognitive_params.get("ambiguity_index", "clear_explicit")
    
    # 🔥 BASE PROMPT YANG LEBIH TEGAS DAN EKSPLISIT
    base_prompt = (
        "Anda adalah Social Executor CAKRA AI, asisten pintar PT Pindad.\n"
        "Tugas Anda adalah mengubah rencana kerja dari Strategic Planner menjadi jawaban natural bahasa Indonesia.\n\n"
        "⚠️ INSTRUKSI KRITIS WAJIB DIPATUHI:\n"
        "1. JAWABAN ANDA HARUS 100% BERDASARKAN DOKUMEN RAG YANG DIBERIKAN DI BAWAH.\n"
        "2. DILARANG KERAS mengarang, berasumsi, atau menambahkan informasi di luar konteks dokumen.\n"
        "3. Jika informasi tidak ada di dokumen, katakan: 'Informasi tersebut tidak tersedia di dokumen internal.'\n"
        "4. WAJIB sebutkan nomor regulasi/SKEP dan pasal yang relevan saat menjawab.\n"
        "5. Ikuti struktur action_plan dari Strategic Planner secara ketat.\n\n"
    )
    
    # Socio-linguistic adaptation (tetap sama)
    if len(slang_list) > 0 and ("bolo" in slang_list or "cuy" in slang_list):
        base_prompt += (
            "- GAYA BAHASA: Casual akrab, boleh pakai 'bolo' atau 'cuy' secukupnya.\n"
        )
    elif pronoun == "informal_gue_lo" or mirror_strat == "mirror_casual":
        base_prompt += (
            "- GAYA BAHASA: Santai dan bersahabat, tapi tetap sopan. Jangan pakai slang lokal.\n"
        )
    elif pronoun == "formal_saya_anda" or authority == "pejabat_struktural":
        base_prompt += (
            "- GAYA BAHASA: Formal birokratis, gunakan 'Saya' dan 'Anda/Bapak/Ibu'.\n"
        )
    else:
        base_prompt += (
            "- GAYA BAHASA: Profesional suportif, ramah, tanpa slang.\n"
        )
        
    if profanity == "low_misuh":
        base_prompt += (
            "- RESPON RENDAH HATI: User frustrasi, redam suasana dengan empati dan solidaritas.\n"
        )
        
    if ambiguity == "highly_vague" or ambiguity == "semi_ambiguous":
        base_prompt += "- TANYAKAN KONFIRMASI: Di akhir jawaban, ajukan pertanyaan klarifikasi.\n"

    base_prompt += f"\n[KONDISI PSIKOLOGIS USER]:\n- Emosi: {emotion} | Urgensi: {urgency} | Gaya: {style} | Goal: {goal}\n"

    # 🔥 PERBAIKAN: Extract action_plan dengan lebih robust
    raw_action_plan = strategy_params.get("action_plan", [])
    processed_actions = []
    
    def extract_action_text(item, depth=0):
        """Recursive extraction untuk nested action_plan"""
        if depth > 3:  # Prevent infinite recursion
            return None
            
        if isinstance(item, str):
            return item
        elif isinstance(item, dict):
            # Coba ambil dari key yang paling relevan
            for key in ["action", "step", "description", "text"]:
                if key in item:
                    val = item[key]
                    if isinstance(val, str):
                        return val
                    elif isinstance(val, dict):
                        result = extract_action_text(val, depth + 1)
                        if result:
                            return result
            # Fallback: ambil value pertama yang string
            for val in item.values():
                if isinstance(val, str):
                    return val
                elif isinstance(val, dict):
                    result = extract_action_text(val, depth + 1)
                    if result:
                        return result
        return None
    
    for item in raw_action_plan:
        action_text = extract_action_text(item)
        if action_text:
            processed_actions.append(action_text)

    if processed_actions:
        actions_text = "\n".join(f"• {a}" for a in processed_actions)
        base_prompt += f"\n[STRUKTUR JAWABAN WAJIB DIKUTI]:\n{actions_text}\n"
        
    empathy = cognitive_params.get("empathy_phrase")
    if empathy:
        base_prompt += f"• Kalimat empati pembuka: {empathy}\n"
    
    # 🔥 CRITICAL: RAG context dengan instruksi yang SANGAT TEGAS
    rag_ctx = strategy_params.get("rag_context")
    if rag_ctx:
        base_prompt += (
            f"\n{'='*70}\n"
            f"[SUMBER DATA RESMI - WAJIB DIRUJUK]\n"
            f"{'='*70}\n"
            f"{rag_ctx}\n"
            f"{'='*70}\n"
            f"INSTRUKSI PENTING:\n"
            f"1. Gunakan HANYA informasi dari dokumen di atas.\n"
            f"2. Sebutkan nomor regulasi, pasal, dan halaman saat mengutip.\n"
            f"3. JANGAN tambahkan informasi eksternal atau asumsi pribadi.\n"
            f"4. Jika user tanya hal di luar dokumen, katakan tidak tersedia.\n"
            f"{'='*70}\n"
        )

    if cognitive_params.get("is_coding"):
        base_prompt += (
            "\n[KONTEKS PEMROGRAMAN]:\n"
            "User minta bantuan koding. Gunakan riwayat pesan untuk memahami kode asli.\n"
            "Berikan solusi kode yang lengkap dan bisa langsung dipakai.\n"
        )

    base_prompt += (
        "\n\nOUTPUT HARUS berupa teks obrolan natural bahasa Indonesia.\n"
        "DILARANG memunculkan JSON, tag <think>, atau metadata sistem!\n"
        "Mulai menjawab sekarang berdasarkan instruksi di atas."
    )
    
    system_message = {"role": "system", "content": base_prompt}
    exec_messages = [system_message]
    exec_messages.extend(messages)
    
    logger.info("📤 [LAYER 3] Streaming response...")
    
    async for chunk_line in stream_ollama_chat(
        model_name=settings.MODEL_PERSONA,
        messages=exec_messages,
        request=request,
        temperature=0.5,  # 🔥 TURUNKAN dari 0.7 ke 0.5 biar lebih fokus
        keep_alive=-1,
        num_ctx=8192
    ):
        yield chunk_line


def _get_fallback_cognitive_params(user_message: str = "") -> Dict[str, Any]:
    """
    Fallback Layer 1 output dengan penyelamatan kueri fisik user.

    [FIX #2] need_rag diset False dan detected_intent CHITCHAT agar pipeline
    tidak memaksa RAG + DeepSeek-R1 ketika Layer 1 (Qwen) timeout.
    Chat mode 'documents' di chat.py akan override need_rag=True jika memang diperlukan.
    """
    return {
        "emotion": "neutral",
        "emotion_confidence": 0.5,
        "empathy_phrase": None,
        "need_rag": False,
        "rag_query": user_message if user_message else "",
        "need_analytics": False,
        "is_user_correction": False,
        "previous_response_was_wrong": False,
        "what_went_wrong": None,
        "urgency_level": "rendah",
        "context_summary": "Query dianalisis dengan parameter fallback 34 parameter.",
        "detected_intent": "CHITCHAT",
        "extracted_entities": [],
        "security_clearance_required": "low",
        "corporate_scope": "general_knowledge",
        "is_policy_query": False,
        "technical_depth_required": "surface",
        "is_multi_turn_dependent": False,
        "data_extraction_needed": False,
        "user_persona_style": "casual_informal",
        "cultural_nuance": "general_indonesian",
        "assumed_knowledge_level": "intermediate",
        "interaction_goal": "seeking_information",
        "pindad_division_affinity": "korporat_umum",
        "regulation_hierarchy_target": None,
        "estimated_vram_urgency": "low_bypass_safe",
        "rag_retrieval_strategy": "none",
        "user_authority_level": "pegawai_pelaksana",
        "ambiguity_index": "clear_explicit",
        "user_pronoun_preference": "unknown",
        "slang_interjection_marker": [],
        "profanity_frustration_trigger": "none",
        "linguistic_mirroring_strategy": "stay_formal_safe",
        "is_coding": False
    }


def _get_fallback_strategy_params() -> Dict[str, Any]:
    """Fallback Layer 2 output jika DeepSeek error"""
    return {
        "action_plan": [
            "Berikan respons natural berdasarkan kueri user",
            "Gunakan pendekatan profesional dan suportif"
        ],
        "response_structure": {
            "open_with": "direct_answer",
            "middle": "narrative",
            "close_with": "offer_help"
        },
        "key_points_to_cover": [],
        "tone": "profesional",
        "estimated_response_length": "medium",
        "should_ask_followup": False,
        "rag_context": None,
        "rag_utilized": False
    }