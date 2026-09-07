"""
CAKRA AI — Mode Collab Pipeline
===============================
Mode pipeline untuk memproses partisipasi CAKRA sebagai AI Teammate
di dalam ruang diskusi tim (Collab Space).

Mendukung:
1. should_intervene(): Silent evaluator (gemma4:e4b) untuk intervensi proaktif cerdas.
2. generate_response(): Streaming generator (gemma4:31b) dengan persona rekan kerja setara
   serta pemahaman draf regulasi/dokumen kerja bersama.
"""

import logging
import json
import re
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple
from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response, stream_ollama_chat
from backend.app.services.pipeline.prompts.collab_prompts import (
    COLLAB_TEAMMATE_SYSTEM_PROMPT,
    COLLAB_INTERVENTION_EVAL_PROMPT
)

logger = logging.getLogger("MODE_COLLAB")


class ModeCollab:
    """
    Handler pipeline mandiri untuk Collab Space.
    Didaftarkan ke ModeHub (mode_hub.py) dengan key 'collab'.
    """

    def __init__(self):
        self.router_model = getattr(settings, "MODEL_ROUTER", "gemma4:e4b")
        self.persona_model = getattr(settings, "MODEL_PERSONA", "gemma4:31b")

    async def should_intervene(
        self,
        recent_messages: List[Dict[str, Any]],
        room_topic: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Mengevaluasi apakah CAKRA perlu nimbrung secara proaktif pada percakapan tim.
        Menggunakan model router ringan (gemma4:e4b) untuk menghemat VRAM dan komputasi.
        """
        if not recent_messages or len(recent_messages) < 2:
            return False, ""

        # Format 5-8 pesan terakhir
        transcript_lines = []
        for msg in recent_messages[-8:]:
            sender = msg.get("sender_name", "Anggota")
            text = msg.get("message_text", "").strip()
            sender_type = msg.get("sender_type", "USER")
            if sender_type == "CAKRA":
                transcript_lines.append(f"[CAKRA (AI Teammate)]: {text}")
            else:
                transcript_lines.append(f"[{sender}]: {text}")

        # Jangan nimbrung jika pesan terakhir sudah dari CAKRA
        last_sender_type = recent_messages[-1].get("sender_type", "USER")
        if last_sender_type == "CAKRA":
            return False, ""

        # Jangan nimbrung jika pesan terakhir terlalu pendek (misal "ok", "siap", "iya")
        last_text = recent_messages[-1].get("message_text", "").strip().lower()
        if len(last_text) < 10 and last_text in ["ya", "iya", "siap", "ok", "oke", "sip", "mantap", "noted", "makasih", "terima kasih"]:
            return False, ""

        transcript_str = "\n".join(transcript_lines)
        eval_prompt = (
            f"Topik Ruang Diskusi: {room_topic or 'Umum / Diskusi Kerja'}\n\n"
            f"Transkrip Percakapan Terbaru:\n{transcript_str}\n\n"
            f"Berdasarkan transkrip di atas, apakah CAKRA perlu nimbrung untuk memberikan masukan/klarifikasi regulasi?"
        )

        messages = [
            {"role": "system", "content": COLLAB_INTERVENTION_EVAL_PROMPT},
            {"role": "user", "content": eval_prompt}
        ]

        try:
            res = await generate_json_response(
                model_name=self.router_model,
                messages=messages,
                temperature=0.1,
                num_ctx=2048,
                timeout=10.0
            )
            should_intervene = bool(res.get("should_intervene", False))
            reason = str(res.get("reason", ""))
            logger.info(f"[COLLAB_EVAL] should_intervene={should_intervene}, reason='{reason}'")
            return should_intervene, reason
        except Exception as e:
            logger.warning(f"[COLLAB_EVAL] Evaluasi intervensi gagal/timeout: {e}")
            return False, ""

    async def generate_response(
        self,
        room_name: str,
        room_topic: str,
        document_content: str,
        recent_messages: List[Dict[str, Any]],
        is_mention: bool = False,
        interjection_type: str = "EXPLICIT_MENTION",
        request: Optional[Any] = None
    ) -> AsyncGenerator[str, None]:
        """
        Menghasilkan respons CAKRA sebagai AI Teammate secara streaming.
        """
        # Susun System Context
        system_context = (
            f"{COLLAB_TEAMMATE_SYSTEM_PROMPT}\n\n"
            f"--- KONTEKS RUANG DISKUSI SAAT INI ---\n"
            f"Nama Ruang: {room_name}\n"
            f"Topik / Agenda: {room_topic or 'Perumusan Konsep & Regulasi'}\n\n"
            f"--- DRAF DOKUMEN KERJA SAAT INI (DOCUMENT PAD) ---\n"
            f"{document_content.strip() if document_content and document_content.strip() else '(Draf dokumen belum diisi oleh tim)'}\n"
            f"---------------------------------------------------\n\n"
        )

        if interjection_type == "PROACTIVE_SUGGESTION":
            system_context += (
                "Catatan: Anda nimbrung secara proaktif karena melihat kebutuhan klarifikasi pada diskusi rekan-rekan. "
                "Awali tanggapan dengan santun dan ramah, misalnya: 'Izin menambahkan rekan-rekan...' atau 'Terkait poin yang sedang dibahas...'."
            )
        elif is_mention:
            system_context += (
                "Catatan: Anda dipanggil/dimention secara langsung oleh rekan tim. Berikan jawaban komprehensif, lugas, dan solutif."
            )

        messages = [{"role": "system", "content": system_context}]

        # Tambahkan riwayat obrolan (maks 15 pesan terakhir)
        history_window = recent_messages[-15:]
        for msg in history_window:
            sender = msg.get("sender_name", "Anggota")
            text = msg.get("message_text", "")
            sender_type = msg.get("sender_type", "USER")

            if sender_type == "CAKRA":
                messages.append({"role": "assistant", "content": text})
            else:
                # Bersihkan tag @cakra agar tidak redundan bagi LLM
                clean_text = re.sub(r"@cakra\b", "", text, flags=re.IGNORECASE).strip()
                messages.append({"role": "user", "content": f"[{sender}]: {clean_text}"})

        # Pastikan ada pesan user terakhir jika history kosong
        if len(messages) == 1:
            messages.append({"role": "user", "content": "Halo CAKRA, mohon bantu diskusi tim kami."})

        # Panggil streaming model persona
        try:
            async for chunk in stream_ollama_chat(
                model_name=self.persona_model,
                messages=messages,
                request=request,
                temperature=0.7,
                num_ctx=getattr(settings, "NUM_CTX_CORE", 16384),
                is_thinking=False
            ):
                yield chunk
        except Exception as e:
            logger.error(f"[COLLAB_GEN] Streaming response gagal: {e}")
            yield f"Mohon maaf rekan-rekan, terjadi kendala teknis saat memproses respons: {str(e)}"
