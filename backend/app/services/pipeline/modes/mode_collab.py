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

        # Filter cepat: Jika hanya obrolan umum/santai antar personil tanpa mention cakra,
        # CAKRA WAJIB DIAM dan tidak mengganggu.
        last_text = recent_messages[-1].get("message_text", "").strip().lower()
        casual_banter = [
            "makan siang yuk", "makan yuk", "makan dulu", "makan siang", "ngopi dulu", "ngopi yuk",
            "halo bro", "siap nanti ya", "nanti ya", "duluan ya", "rehat dulu", "istirahat dulu",
            "otw", "gas", "siap bro", "oke bro", "ok bro", "sip bro"
        ]
        if any(cb in last_text for cb in casual_banter) or (
            len(last_text) < 15 and last_text in ["ya", "iya", "siap", "ok", "oke", "sip", "mantap", "noted", "makasih", "terima kasih", "halo"]
        ):
            logger.info(f"[COLLAB_EVAL] Obrolan santai/basa-basi umum antar personil ('{last_text}'), CAKRA diam dan tidak mengganggu.")
            return False, ""

        transcript_str = "\n".join(transcript_lines)
        eval_prompt = (
            f"Topik Ruang Diskusi: {room_topic or 'Umum / Diskusi Kerja'}\n\n"
            f"Transkrip Percakapan Terbaru:\n{transcript_str}\n\n"
            f"Berdasarkan transkrip di atas, apakah tim sedang membuka diskusi dokumen/regulasi/topik kerja substantif sehingga CAKRA perlu nimbrung?"
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
        mode: Optional[str] = None,
        context_doc: Optional[Dict[str, Any]] = None,
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

        # Integrasi Rujukan Dokumen Aktif (Jika rekan tim melampirkan context tag dokumen)
        if context_doc:
            doc_title = context_doc.get("title", "")
            doc_cat = context_doc.get("category", "Regulasi / Acuan Resmi")
            doc_id = context_doc.get("doc_id")
            doc_content = ""

            # 1. Cari konten dari PostgreSQL dokumen_chunk (arsip dokumen RAG utama)
            try:
                from backend.app.core.database import get_db
                async with get_db() as pg_conn:
                    target_doc_id = None
                    if doc_id and str(doc_id).isdigit():
                        target_doc_id = int(doc_id)
                    elif doc_title:
                        row_d = await pg_conn.fetchrow(
                            "SELECT id FROM dokumen WHERE judul ILIKE $1 OR filename ILIKE $1 LIMIT 1",
                            f"%{doc_title[:50]}%"
                        )
                        if row_d:
                            target_doc_id = row_d["id"]

                    if target_doc_id:
                        c_rows = await pg_conn.fetch(
                            "SELECT content FROM dokumen_chunk WHERE dokumen_id = $1 ORDER BY chunk_id ASC LIMIT 25",
                            target_doc_id
                        )
                        if c_rows:
                            doc_content = "\n\n".join(r["content"] for r in c_rows if r.get("content")).strip()
            except Exception as e:
                logger.warning(f"[MODE_COLLAB] PostgreSQL dokumen_chunk lookup error: {e}")

            # 2. Fallback ke MySQL berita jika belum ditemukan di PostgreSQL
            if not doc_content and doc_id and str(doc_id).isdigit():
                try:
                    from backend.app.core.database import get_peraturan_db
                    async with get_peraturan_db() as conn_my:
                        async with conn_my.cursor() as cur:
                            await cur.execute("SELECT isi, judul, noper FROM berita WHERE id_berita = %s", (int(doc_id),))
                            row_doc = await cur.fetchone()
                            if row_doc and row_doc.get("isi"):
                                doc_content = re.sub(r"<[^>]+>", " ", str(row_doc.get("isi") or ""))[:4000].strip()
                except Exception as e:
                    logger.debug(f"[MODE_COLLAB] Note: Could not fetch DB snippet for doc {doc_id}: {e}")

            system_context += (
                f"\n--- RUJUKAN DOKUMEN AKTIF DISKUSI TIM ---\n"
                f"Judul / Nomor Dokumen: {doc_title}\n"
                f"Kategori: {doc_cat}\n"
            )
            if doc_content:
                system_context += (
                    f"\n--- ISI / EKSTRAK TEKS DOKUMEN RUJUKAN ---\n"
                    f"{doc_content[:6000]}\n"
                    f"--------------------------------------------\n"
                )
            system_context += (
                f"\nInstruksi Khusus untuk CAKRA:\n"
                f"- Dokumen rujukan di atas ('{doc_title}') SUDAH TERSEDIA dan aktif dibahas oleh tim.\n"
                f"- Jika rekan tim meminta Anda membedah poin-poinnya (seperti 'coba cakra bedah pointnya dulu' atau 'bedah isinya'), "
                f"lakukan analisis dan bedah poin-poin utama dokumen di atas secara mendalam, terstruktur, dan solutif bagi tim.\n"
                f"- JANGAN SEKALI-KALI menjawab bahwa dokumen belum terlampir, belum ada, atau meminta user mengunggah ulang! Bahan dokumen tersebut sudah Anda miliki di atas.\n"
                f"---------------------------------------------------\n\n"
            )

        if mode:
            mode_lower = mode.lower()
            if mode_lower == "code":
                system_context += (
                    "\n--- MODE AKTIF: KODING & SKRIP ---\n"
                    "Rekan tim meminta bantuan koding atau skrip pemrograman. "
                    "Sajikan kode lengkap, bersih, dengan blok kode markdown yang benar dan penjelasan ringkas.\n"
                )
            elif mode_lower == "diagram":
                system_context += (
                    "\n--- MODE AKTIF: DIAGRAM & FLOWCHART ---\n"
                    "Rekan tim meminta visualisasi arsitektur, workflow, atau proses kerja. "
                    "Sertakan blok kode Mermaid (```mermaid ... ```) yang valid dan sintaksnya presisi.\n"
                )
            elif mode_lower == "chart":
                system_context += (
                    "\n--- MODE AKTIF: GRAFIK & DATA ---\n"
                    "Rekan tim meminta analisis atau visualisasi data. "
                    "Sajikan tabel markdown terstruktur rapi dan ringkasan tren yang mudah dipahami tim.\n"
                )
            elif mode_lower in ["documents", "document"]:
                system_context += (
                    "\n--- MODE AKTIF: PENELUSURAN REGULASI & ARSIP ---\n"
                    "Fokuskan jawaban pada regulasi internal, kepatuhan, tata kerja, dan acuan resmi PT Pindad / BUMN.\n"
                )
            elif mode_lower == "create_file":
                system_context += (
                    "\n--- MODE AKTIF: PEMBUATAN DOKUMEN / BERKAS ---\n"
                    "Bantu tim menyusun draf berkas kerja terstruktur lengkap (seperti SOP, Term of Reference, atau template draf).\n"
                )
            elif mode_lower == "smart_mail":
                system_context += (
                    "\n--- MODE AKTIF: DRAFT NOTA DINAS & SURAT RESMI ---\n"
                    "Susun format surat resmi/nota dinas standar perusahaan dengan nomor, perihal, rujukan, dan butir isi yang rapi.\n"
                )
            elif mode_lower == "focus":
                system_context += (
                    "\n--- MODE AKTIF: AUDIT & INTEROGASI MENDALAM ---\n"
                    "Lakukan audit kritis, verifikasi klausul, dan identifikasi potensi celah atau inkonsistensi pada topik yang dibahas.\n"
                )

        if interjection_type == "PROACTIVE_SUGGESTION":
            system_context += (
                "Catatan: Anda nimbrung secara proaktif karena tim sedang membuka diskusi dokumen/regulasi/pekerjaan. "
                "Awali tanggapan dengan santun dan natural, misalnya: 'Oke ayo kita diskusi...', atau 'Izin menambahkan terkait poin tersebut...'."
            )
        elif is_mention:
            system_context += (
                "Catatan: Anda dipanggil/dimention secara langsung oleh rekan tim."
            )

        # Cek apakah pesan user terakhir bernada santai / ajakan makan / sapaan
        last_user_msg = ""
        for m in reversed(recent_messages):
            if m.get("sender_type") == "USER":
                last_user_msg = m.get("message_text", "").lower()
                break

        is_casual_topic = any(kw in last_user_msg for kw in ["makan siang", "makan", "ngopi", "halo bro", "rehat", "istirahat", "stay"])
        if is_casual_topic:
            system_context += (
                "\nInstruksi Khusus Obrolan Santai: Rekan tim menyapa atau mengajak santai (seperti makan siang, ngopi, istirahat). "
                "Tanggapi dengan sangat santai, akrab, dan bersahabat seperti kawan kantor yang asyik. "
                "Contoh respons: 'Santai aja bro, pada makan siang dulu, gw stay di sini nemenin ruangan.' atau 'Siap bro, selamat makan siang duluan rekan-rekan! Gw standby di sini jaga draf kita.' Jangan kaku atau formal!"
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

                # Tambahkan rujukan dokumen jika pesan ini menautkan dokumen
                doc_note = ""
                msg_atts = msg.get("attachments")
                if isinstance(msg_atts, list):
                    for att in msg_atts:
                        if isinstance(att, dict) and att.get("type") == "context_doc":
                            doc_note = f" (Menautkan Dokumen Rujukan: {att.get('title')})"
                            break
                        elif isinstance(att, dict) and att.get("type") == "context_mode":
                            doc_note = f" (Mode: {att.get('mode')})"
                            break

                messages.append({"role": "user", "content": f"[{sender}]{doc_note}: {clean_text}"})

        # Pastikan ada pesan user terakhir jika history kosong
        if len(messages) == 1:
            messages.append({"role": "user", "content": "Halo CAKRA, mohon bantu diskusi tim kami."})

        # Panggil streaming model persona
        try:
            async for raw_chunk in stream_ollama_chat(
                model_name=self.persona_model,
                messages=messages,
                request=request,
                temperature=0.7,
                num_ctx=getattr(settings, "NUM_CTX_CORE", 16384),
                is_thinking=False
            ):
                if not raw_chunk:
                    continue
                # stream_ollama_chat me-yield string line per line (atau buffer yang mungkin berisi beberapa baris)
                # Split baris untuk memastikan setiap objek JSON diparsing secara independen
                for line in str(raw_chunk).splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                        text_piece = parsed.get("chunk", "")
                        if text_piece:
                            yield text_piece
                    except Exception:
                        # Jika baris bukan JSON, cek apakah ini chunk teks langsung
                        if not line.startswith("{") and not line.endswith("}"):
                            yield line
        except Exception as e:
            logger.error(f"[COLLAB_GEN] Streaming response gagal: {e}")
            yield f"Mohon maaf rekan-rekan, terjadi kendala teknis saat memproses respons: {str(e)}"
