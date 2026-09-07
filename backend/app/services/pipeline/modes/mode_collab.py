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
        room_topic: Optional[str] = None,
        is_mention: bool = False
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Mengevaluasi apakah CAKRA perlu merespons percakapan tim (proaktif atau karena mention)
        SERTA mengekstrak parameter pencarian dokumen regulasi (RAG).
        Menggunakan model router ringan (gemma4:e4b).
        """
        default_routing = {
            "need_rag": False,
            "queries": [],
            "query_judul": [],
            "search_tags": []
        }

        if not recent_messages:
            return is_mention, "No recent messages", default_routing

        # Deteksi apakah pesan saat ini adalah kelanjutan / respon balik langsung terhadap pernyataan CAKRA sebelumnya
        is_followup_to_cakra = False
        if len(recent_messages) >= 2 and recent_messages[-2].get("sender_type") == "CAKRA":
            is_followup_to_cakra = True

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

        # Jangan nimbrung jika pesan terakhir sudah dari CAKRA dan tidak ada mention baru
        last_sender_type = recent_messages[-1].get("sender_type", "USER")
        if last_sender_type == "CAKRA" and not is_mention:
            return False, "Pesan terakhir sudah dari CAKRA", default_routing

        # Filter cepat: Jika hanya obrolan umum/santai antar personil tanpa mention cakra
        # (Kecuali jika ini adalah respon balik langsung ke CAKRA, maka jangan disupresi)
        last_text = recent_messages[-1].get("message_text", "").strip().lower()
        casual_banter = [
            "makan siang yuk", "makan yuk", "makan dulu", "makan siang", "ngopi dulu", "ngopi yuk",
            "halo bro", "siap nanti ya", "nanti ya", "duluan ya", "rehat dulu", "istirahat dulu",
            "otw", "gas", "siap bro", "oke bro", "ok bro", "sip bro"
        ]
        if not is_mention and not is_followup_to_cakra and (any(cb in last_text for cb in casual_banter) or (
            len(last_text) < 15 and last_text in ["ya", "iya", "siap", "ok", "oke", "sip", "mantap", "noted", "makasih", "terima kasih", "halo"]
        )):
            logger.info(f"[COLLAB_EVAL] Obrolan santai/basa-basi umum antar personil ('{last_text}'), CAKRA diam dan tidak mengganggu.")
            return False, "Obrolan santai antar rekan kerja", default_routing

        if is_mention:
            dialog_status = "YA (DIPANGGIL / DIMENTION LANGSUNG OLEH ANGGOTA TIM)"
        elif is_followup_to_cakra:
            dialog_status = "YA (REKAN TIM MERESPON / MENGONFIRMASI LANGSUNG PERNYATAAN CAKRA SEBELUMNYA)"
        else:
            dialog_status = "TIDAK (DISKUSI TIM BEBAS ANTAR REKAN)"

        transcript_str = "\n".join(transcript_lines)
        eval_prompt = (
            f"Topik Ruang Diskusi: {room_topic or 'Umum / Diskusi Kerja'}\n"
            f"Status Keterlibatan Langsung CAKRA: {dialog_status}\n\n"
            f"Transkrip Percakapan Terbaru:\n{transcript_str}\n\n"
            f"Berdasarkan transkrip di atas:\n"
            f"1. Apakah CAKRA perlu menanggapi? (Jika mention langsung ATAU respon/konfirmasi atas ucapan CAKRA = WAJIB true; jika diskusi bebas antar rekan = nilai apakah substantif/butuh masukan)\n"
            f"2. Apakah topik memerlukan pencarian DOKUMEN REGULASI INTERNAL PT PINDAD (RAG) seperti PKB, SE, SOP, SK, aturan kerja, hak karyawan, atau data teknis internal? Tentukan need_rag, queries, query_judul, dan search_tags."
        )

        messages = [
            {"role": "system", "content": COLLAB_INTERVENTION_EVAL_PROMPT},
            {"role": "user", "content": eval_prompt}
        ]

        router_ctx = getattr(settings, "NUM_CTX_ROUTER", 4096)
        try:
            res = await generate_json_response(
                model_name=self.router_model,
                messages=messages,
                temperature=0.0,
                top_p=0.1,
                top_k=1,
                keep_alive=-1,
                num_ctx=router_ctx,
                timeout=60.0
            )
            should_intervene = bool(res.get("should_intervene", False)) or is_mention
            reason = str(res.get("reason", ""))
            need_rag = bool(res.get("need_rag", False))
            routing_dict = {
                "need_rag": need_rag,
                "queries": res.get("queries", []) if isinstance(res.get("queries"), list) else [],
                "query_judul": res.get("query_judul", []) if isinstance(res.get("query_judul"), list) else [],
                "search_tags": res.get("search_tags", []) if isinstance(res.get("search_tags"), list) else []
            }
            logger.info(f"[COLLAB_EVAL] should_intervene={should_intervene}, need_rag={need_rag}, reason='{reason}'")
            return should_intervene, reason, routing_dict
        except Exception as e:
            logger.warning(f"[COLLAB_EVAL] Evaluasi intervensi gagal/timeout: {e}")
            return is_mention, f"Fallback: {e}", default_routing

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
        members: Optional[List[Dict[str, Any]]] = None,
        rag_context: Optional[str] = None,
        rag_sources: Optional[List[Dict[str, Any]]] = None,
        eval_reason: Optional[str] = None,
        request: Optional[Any] = None
    ) -> AsyncGenerator[str, None]:
        """
        Menghasilkan respons CAKRA sebagai AI Teammate secara streaming.
        """
        # Format anggota tim di ruangan untuk Team Awareness
        members_str = ""
        if members:
            member_names = [f"{m.get('name', 'Anggota')} ({m.get('divisi', 'PT Pindad')})" for m in members]
            members_str = ", ".join(member_names)

        # Susun System Context
        system_context = (
            f"{COLLAB_TEAMMATE_SYSTEM_PROMPT}\n\n"
            f"--- KONTEKS RUANG DISKUSI SAAT INI ---\n"
            f"Nama Ruang: {room_name}\n"
            f"Topik / Agenda: {room_topic or 'Perumusan Konsep & Regulasi'}\n"
        )
        if members_str:
            system_context += f"Anggota Tim di Ruangan Ini: {members_str}\n"

        # Sinkronisasi Call 1 -> Call 2: Teruskan hasil evaluasi batin Call 1 ke System Context Call 2
        if eval_reason:
            system_context += (
                f"\n--- EVALUASI INTERVENSI TIM (CALL 1) ---\n"
                f"Tujuan Respon: {eval_reason}\n"
                f"-----------------------------------------\n"
            )

        if interjection_type == "CONVERSATIONAL_FOLLOWUP":
            system_context += (
                "\nCatatan Situasi: Rekan tim sedang merespons atau mengonfirmasi pernyataan/candaan Anda sebelumnya. "
                "Berikan tanggapan penutup atau balasan hangat yang santai, akrab, dan bersahabat (cukup 1 hingga 2 kalimat pendek yang asyik). Jangan kaku!\n"
            )

        system_context += (
            f"\n--- DRAF DOKUMEN KERJA SAAT INI (DOCUMENT PAD) ---\n"
            f"{document_content.strip() if document_content and document_content.strip() else '(Draf dokumen belum diisi oleh tim)'}\n"
            f"---------------------------------------------------\n\n"
        )

        # Integrasi Rujukan RAG (Jika ditemukan dari pencarian regulasi internal)
        if rag_context and rag_context.strip():
            system_context += (
                f"\n--- RUJUKAN DOKUMEN REGULASI INTERNAL PT PINDAD (HASIL PENCARIAN RAG RESMI) ---\n"
                f"{rag_context.strip()}\n"
                f"---------------------------------------------------------------------------------\n"
                f"Panduan Penggunaan Rujukan RAG:\n"
                f"- Teks di atas adalah kutipan resmi hasil pencarian RAG dari database dokumen/regulasi PT Pindad.\n"
                f"- Tanggapan Anda WAJIB berbasiskan data pasal, aturan, atau klausul di atas.\n"
                f"- DILARANG BERHALUSINASI atau mengarang aturan baru di luar dokumen yang tertera.\n"
                f"- Sebutkan nama dokumen atau nomor pasal terkait secara natural agar rekan tim mendapatkan kepastian regulasi.\n\n"
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

        # Cek intensitas permintaan (apakah user meminta detail atau sekadar berdiskusi santai)
        last_user_msg = ""
        for m in reversed(recent_messages):
            if m.get("sender_type") == "USER":
                last_user_msg = m.get("message_text", "").lower()
                break

        is_casual_topic = any(kw in last_user_msg for kw in ["makan siang", "makan", "ngopi", "halo bro", "rehat", "istirahat", "stay"])
        is_requesting_detail = any(kw in last_user_msg for kw in [
            "detail", "jelasin", "jelaskan", "kenapa", "alasannya", "bedah", "poin-poin", "poinnya",
            "uraikan", "jabarkan", "buatkan", "draf", "tulis kode", "bikin", "rincian", "komprehensif"
        ])

        if is_casual_topic:
            system_context += (
                "\nInstruksi Khusus Obrolan Santai: Rekan tim menyapa atau mengajak santai (seperti makan siang, ngopi, istirahat). "
                "Tanggapi dengan santai, akrab, dan bersahabat seperti kawan kantor yang asyik dengan kata ganti aku-kamu. "
                "Contoh respons: 'Santai aja bro, pada makan siang dulu, aku stay di sini nemenin ruangan.' atau 'Siap, selamat makan siang duluan rekan-rekan! Aku standby di sini jaga draf kerjaan kita.' DILARANG gunakan gw-elo!\n"
            )
        elif is_requesting_detail:
            system_context += (
                "\n[PANDUAN PANJANG RESPONS]: Rekan tim secara eksplisit meminta elaborasi mendalam, alasan detail, rincian, atau bedah dokumen. "
                "Berikan analisis yang lengkap, komprehensif, terstruktur, berbasis data dan poin-poin yang mendalam.\n"
            )
        else:
            system_context += (
                "\n[PANDUAN PANJANG RESPONS]: Diskusi tim sedang berlangsung normal atau bertukar pikiran singkat. "
                "Berikan tanggapan yang SINGKAT, PADAT, DAN TO-THE-POINT (cukup 1 hingga 3 kalimat saja) layaknya rekan kerja yang sedang mengobrol di ruang obrolan. "
                "JANGAN membuat esai panjang, ringkasan berlebihan, atau format kaku, kecuali nanti diminta detail lebih lanjut oleh rekan tim.\n"
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

    async def generate_notulensi(
        self,
        room_name: str,
        room_topic: str,
        members: List[Dict[str, Any]],
        messages: List[Dict[str, Any]]
    ) -> str:
        """
        Merangkum seluruh riwayat obrolan tim menjadi Notulensi Rapat & Diskusi resmi.
        """
        member_names = [f"{m.get('name', 'Anggota')} ({m.get('divisi', 'PT Pindad')})" for m in members] if members else ["Anggota Tim"]
        members_str = ", ".join(member_names)

        chat_lines = []
        for m in messages:
            sender = m.get("sender_name") or m.get("sender_npp") or "Peserta"
            text = (m.get("message_text") or "").strip()
            if not text:
                continue
            clean_text = " ".join(text.split())
            chat_lines.append(f"[{sender}]: {clean_text}")

        transcript = "\n".join(chat_lines[-60:]) if chat_lines else "(Belum ada obrolan)"

        prompt = f"""Anda adalah Notulis & Sekretaris Eksekutif Cerdas PT Pindad.
Tugas Anda adalah merangkum obrolan tim di bawah ini menjadi DRAF NOTULENSI RAPAT & KESEPAKATAN TIM yang rapi, profesional, terstruktur, dan objektif.

INFORMASI RUANG DISKUSI:
- Nama Ruang: {room_name}
- Agenda / Topik: {room_topic or 'Diskusi & Koordinasi Tim'}
- Peserta: {members_str}

RIWAYAT PERCAKAPAN TIM:
\"\"\"
{transcript}
\"\"\"

PANDUAN PENYUSUNAN NOTULENSI:
1. Format wajib Markdown terstruktur rapi:
# 📋 Notulensi Diskusi Tim: {room_name}
**Topik:** {room_topic or 'Koordinasi Kerja'}  
**Peserta:** {members_str}  

---

## 1. Ringkasan Eksekutif
(Sajikan 2-3 kalimat ringkas intisari pertemuan/diskusi)

## 2. Poin-Poin Utama Pembahasan
- (Rangkum topik, usulan, dan pandangan penting yang dibahas)
- (Abaikan sapaan basa-basi santai seperti ajakan makan siang/ngopi)

## 3. Keputusan & Kesepakatan Bersama
- (Poin keputusan atau konsensus yang disepakati)

## 4. Tindak Lanjut (Action Items)
- [ ] (Tugas atau tindak lanjut konkret beserta PIC jika ada)

2. Tulis dalam Bahasa Indonesia formal, lugas, dan profesional.
3. JANGAN menduplikasi kalimat atau teks yang sama berulang kali.
4. JANGAN mengarang obrolan yang tidak terjadi. Langsung hasilkan naskah Notulensi Markdown tanpa kalimat pengantar atau basa-basi percakapan."""

        system_msg = {"role": "system", "content": "Anda adalah Notulis Eksekutif profesional PT Pindad yang ahli menyusun notulensi rapat berkualitas tinggi."}
        user_msg = {"role": "user", "content": prompt}

        full_response = []
        try:
            async for raw_chunk in stream_ollama_chat(
                model_name=self.persona_model,
                messages=[system_msg, user_msg],
                temperature=0.2,
                num_ctx=getattr(settings, "NUM_CTX_CORE", 16384),
                is_thinking=False
            ):
                if not raw_chunk:
                    continue
                for line in str(raw_chunk).splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                        text_piece = parsed.get("chunk", "")
                        if text_piece:
                            full_response.append(text_piece)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"[NOTULENSI_ERROR] Failed to generate notulensi: {e}")
            return f"# 📋 Notulensi Diskusi Tim: {room_name}\n\n**Topik:** {room_topic}\n\nGagal membuat notulensi otomatis: {str(e)}"

        result = "".join(full_response).strip()
        return result or f"# 📋 Notulensi Diskusi Tim: {room_name}\n\n(Belum cukup data obrolan untuk menyusun notulensi rapat)"

