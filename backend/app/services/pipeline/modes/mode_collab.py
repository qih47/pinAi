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

import os
from pathlib import Path
import logging
import json
import re
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple
from backend.app.core.config import settings
from backend.app.core.paths import ROOT_DIR, ACCOUNTS_DIR
from backend.app.core.llm_client import generate_json_response, stream_ollama_chat
from backend.app.services.pipeline.prompts.collab_prompts import (
    COLLAB_TEAMMATE_SYSTEM_PROMPT,
    COLLAB_INTERVENTION_EVAL_PROMPT,
    COLLAB_AUTO_NOTE_EVAL_PROMPT
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

        # Ekstrak informasi lampiran pada pesan terakhir
        last_msg = recent_messages[-1]
        last_sender = last_msg.get("sender_name", "Anggota")
        last_text = last_msg.get("message_text", "").strip().lower()
        last_attachments = last_msg.get("attachments") or []
        last_att_names = []
        for att in last_attachments:
            if isinstance(att, dict):
                aname = att.get("name") or att.get("title") or att.get("filename")
                if aname:
                    last_att_names.append(aname)
        has_last_attachment = bool(last_att_names)

        # ATURAN EMAS 1: Jika rekan kerja melampirkan berkas/dokumen setelah diminta oleh CAKRA sebelumnya
        # CAKRA WAJIB langsung merespons dan membedah berkas tersebut (DILARANG diam / ghosting)
        if has_last_attachment and is_followup_to_cakra:
            logger.info(f"[COLLAB_EVAL] Rekan kerja [{last_sender}] melampirkan berkas {last_att_names} sebagai respon atas permintaan CAKRA. CAKRA wajib merespons!")
            return True, f"Rekan kerja melampirkan berkas ({', '.join(last_att_names)}) menanggapi permintaan/pembicaraan CAKRA", default_routing

        # ATURAN EMAS 2: Jika rekan kerja mengunggah berkas ke ruangan dan menyertakan teks penunjuk ("ini", "nih", "cek ini", "ini datanya", dll.)
        if has_last_attachment and (len(last_text) < 30 or any(kw in last_text for kw in ["ini", "nih", "cek", "tolong", "bedah", "lihat", "file", "slide", "dokumen", "lampiran", "data"])):
            logger.info(f"[COLLAB_EVAL] Rekan kerja [{last_sender}] mengunggah berkas {last_att_names} dengan teks penunjuk ('{last_text}'). CAKRA wajib merespons!")
            return True, f"Rekan kerja mengunggah berkas ({', '.join(last_att_names)}) untuk ditinjau tim", default_routing

        # ATURAN EMAS 3: Dialog Aktif & Menjawab / Mengonfirmasi Pembicaraan CAKRA
        # Cek apakah CAKRA berbicara di pesan sebelumnya atau dalam 3 pesan terakhir tanpa disela topik lain
        recent_cakra_msg = None
        for m in reversed(recent_messages[:-1]):
            if m.get("sender_type") == "CAKRA":
                recent_cakra_msg = m
                break
            if len(recent_messages) - recent_messages.index(m) > 3:
                break

        if recent_cakra_msg:
            cakra_text = recent_cakra_msg.get("message_text", "")
            # Apakah CAKRA baru saja melempar pertanyaan, kuis/tebakan, polling, atau ajakan diskusi?
            is_cakra_asking = "?" in cakra_text or any(k in cakra_text.lower() for k in [
                "tebak", "gimana", "menurut", "coba", "silakan", "kira-kira", "ada yang",
                "setuju", "pilihan", "ide", "apakah", "kenapa", "hayo", "lanjut", "siapa", "mana"
            ])

            # Cek apakah pesan rekan kerja saat ini jelas memanggil nama rekan manusia lain
            other_member_names = [
                m.get("sender_name", "").lower().strip()
                for m in recent_messages
                if m.get("sender_type") != "CAKRA" and m.get("sender_name") != last_sender
            ]
            addressing_other_human = any(len(n) >= 3 and n in last_text for n in other_member_names)

            if not addressing_other_human:
                # 1. Jika CAKRA baru saja melempar pertanyaan / tebakan, rekan kerja yang menjawab/menebak WAJIB direspons & dikonfirmasi!
                if is_cakra_asking:
                    logger.info(f"[COLLAB_EVAL] Rekan kerja [{last_sender}] menjawab tebakan/pertanyaan CAKRA: '{last_text}'. CAKRA wajib merespons dan mengonfirmasi!")
                    return True, f"Rekan kerja [{last_sender}] menjawab tebakan atau pertanyaan yang diajukan CAKRA ('{last_text}')", default_routing

                # 2. Jika pesan adalah respon lanjutan langsung ke CAKRA (is_followup_to_cakra)
                if is_followup_to_cakra:
                    confirmation_words = [
                        "bener", "benar", "betul", "salah", "iya", "ya", "nggak", "gak", "bukan",
                        "oke", "ok", "siap", "mantap", "setuju", "ikut", "ayo", "gas", "boleh",
                        "rudal", "tank", "tebak", "makasih", "keren", "seru", "wkwk", "haha",
                        "gimana", "udah", "sudah", "bisa", "paham", "noted", "tapi", "coba"
                    ]
                    if any(cw in last_text for cw in confirmation_words) or "?" in last_text or len(last_text) <= 50:
                        logger.info(f"[COLLAB_EVAL] Rekan kerja [{last_sender}] berdialog / merespons langsung perkataan CAKRA ('{last_text}'). CAKRA merespons!")
                        return True, f"Rekan kerja [{last_sender}] merespons atau mengonfirmasi langsung perkataan CAKRA ('{last_text}')", default_routing

        # Format 5-8 pesan terakhir lengkap dengan rincian berkas lampiran
        transcript_lines = []
        for msg in recent_messages[-8:]:
            sender = msg.get("sender_name", "Anggota")
            text = msg.get("message_text", "").strip()
            sender_type = msg.get("sender_type", "USER")

            att_labels = []
            for a in msg.get("attachments") or []:
                if isinstance(a, dict):
                    an = a.get("name") or a.get("title") or a.get("filename")
                    if an:
                        att_labels.append(an)
            att_info = f" [Melampirkan Berkas: {', '.join(att_labels)}]" if att_labels else ""

            if sender_type == "CAKRA":
                transcript_lines.append(f"[CAKRA (AI Teammate)]: {text}")
            else:
                transcript_lines.append(f"[{sender}]: {text}{att_info}")

        # Jangan nimbrung jika pesan terakhir sudah dari CAKRA dan tidak ada mention baru
        last_sender_type = recent_messages[-1].get("sender_type", "USER")
        if last_sender_type == "CAKRA" and not is_mention:
            return False, "Pesan terakhir sudah dari CAKRA", default_routing

        # Filter cepat: Jika hanya obrolan umum/santai antar personil tanpa mention cakra
        casual_banter = [
            "makan siang yuk", "makan yuk", "makan dulu", "makan siang", "ngopi dulu", "ngopi yuk",
            "halo bro", "siap nanti ya", "nanti ya", "duluan ya", "rehat dulu", "istirahat dulu",
            "otw", "gas", "siap bro", "oke bro", "ok bro", "sip bro"
        ]
        if not is_mention and not is_followup_to_cakra and not has_last_attachment and (
            any(cb in last_text for cb in casual_banter) or (
                len(last_text) < 15 and last_text in ["ya", "iya", "siap", "ok", "oke", "sip", "mantap", "noted", "makasih", "terima kasih", "halo"]
            )
        ):
            logger.info(f"[COLLAB_EVAL] Obrolan santai/basa-basi umum antar personil ('{last_text}'), CAKRA diam dan tidak mengganggu.")
            return False, "Obrolan santai antar rekan kerja", default_routing

        if is_mention:
            dialog_status = "YA (DIPANGGIL / DIMENTION LANGSUNG OLEH ANGGOTA TIM)"
        elif is_followup_to_cakra:
            dialog_status = "YA (REKAN TIM MERESPON / MENGONFIRMASI LANGSUNG PERNYATAAN ATAU PERMINTAAN CAKRA SEBELUMNYA)"
        else:
            dialog_status = "TIDAK (DISKUSI TIM BEBAS ANTAR REKAN)"

        transcript_str = "\n".join(transcript_lines)
        eval_prompt = (
            f"Topik Ruang Diskusi: {room_topic or 'Umum / Diskusi Kerja'}\n"
            f"Status Keterlibatan Langsung CAKRA: {dialog_status}\n\n"
            f"Transkrip Percakapan Terbaru:\n{transcript_str}\n\n"
            f"Berdasarkan transkrip di atas:\n"
            f"1. Apakah CAKRA perlu menanggapi? (Jika mention langsung, ada lampiran berkas yang diminta, ATAU respon/konfirmasi atas ucapan CAKRA = WAJIB true; jika diskusi bebas antar rekan = nilai apakah substantif/butuh masukan)\n"
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

            # Safety Net: Jika rekan kerja merespon langsung CAKRA, jangan biarkan model router salah menolak
            if not should_intervene and is_followup_to_cakra:
                should_intervene = True
                reason = f"Safety Net: Rekan kerja sedang berdialog langsung / merespons pesan CAKRA sebelumnya ('{last_text}')"

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
            fallback_intervene = is_mention or (is_followup_to_cakra and has_last_attachment)
            return fallback_intervene, f"Fallback: {e}", default_routing

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
        request: Optional[Any] = None,
        room_id: Optional[str] = None,
        master_npp: Optional[str] = None
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

        # Injeksi Live Document Snapshot (CAKRA Document Studio di Collab)
        if room_id:
            try:
                from backend.app.services.document_writer.doc_writer_service import doc_writer_service
                from backend.app.services.document_writer.document_structure_parser import document_structure_parser
                from pathlib import Path

                active_doc = doc_writer_service.get_active_document(room_id=room_id, master_npp=master_npp or "")
                if active_doc and active_doc.get("file_path"):
                    doc_path = Path(active_doc["file_path"])
                    if doc_path.exists():
                        doc_snapshot = document_structure_parser.get_prompt_snapshot(doc_path)
                        if doc_snapshot:
                            system_context += f"\n\n{doc_snapshot}\n\n"
                            logger.info(f"[MODE_COLLAB] Injected live DocWriter snapshot for {doc_path.name} in room {room_id}")
            except Exception as e:
                logger.warning(f"[MODE_COLLAB] Gagal mengambil snapshot DocWriter untuk room {room_id}: {e}")

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

        # Ekstrak teks berkas lampiran yang diunggah oleh rekan kerja (PDF, PPT, DOCX, XLSX, TXT, gambar, dll.)
        extracted_file_sections = []
        has_uploaded_attachment = False
        for m in reversed(recent_messages[-6:]):
            m_atts = m.get("attachments") or []
            if isinstance(m_atts, list):
                for att in m_atts:
                    if not isinstance(att, dict):
                        continue
                    if att.get("type") in ["context_doc", "context_mode"]:
                        continue

                    file_name = att.get("name") or att.get("title") or att.get("filename") or "Dokumen Lampiran"
                    file_rel = att.get("file_path") or att.get("filename")
                    if not file_rel:
                        continue

                    has_uploaded_attachment = True
                    # Cari lokasi absolut file di storage
                    candidate_paths = [
                        Path(str(file_rel)),
                        Path(ROOT_DIR) / str(file_rel).lstrip("/"),
                        Path(ACCOUNTS_DIR) / str(file_rel).replace("accounts/", "").lstrip("/"),
                    ]
                    actual_path = None
                    for cp in candidate_paths:
                        if cp.exists() and cp.is_file():
                            actual_path = str(cp)
                            break

                    if actual_path:
                        try:
                            from backend.app.services.tools.unified_extractor import extract_document
                            extracted_doc = await extract_document(actual_path, render_images=False)
                            content_text = (extracted_doc.full_text or "").strip()
                            if content_text:
                                extracted_file_sections.append(
                                    f"--- ISI LENGKAP BERKAS LAMPIRAN: {file_name} ---\n"
                                    f"{content_text[:35000]}\n"
                                    f"------------------------------------------------"
                                )
                                logger.info(f"[MODE_COLLAB] Berhasil mengekstrak {len(content_text)} karakter dari berkas '{file_name}'")
                        except Exception as ext_err:
                            logger.warning(f"[MODE_COLLAB] Gagal mengekstrak berkas {actual_path}: {ext_err}")
            if extracted_file_sections:
                break

        if extracted_file_sections:
            system_context += (
                f"\n\n--- DOKUMEN / BERKAS LAMPIRAN AKTIF YANG DIUNGGAH OLEH TIM ---\n"
                + "\n\n".join(extracted_file_sections) +
                f"\n\nInstruksi Khusus Bedah Dokumen untuk CAKRA:\n"
                f"- Berkas lampiran di atas baru saja diunggah oleh rekan kerja ke dalam ruang diskusi.\n"
                f"- Seluruh isi teks/konten berkas tersebut SUDAH LENGKAP Anda baca dan miliki pada rujukan di atas.\n"
                f"- Lakukan pembedahan mendalam, analisis, atau penyusunan draf teknis sesuai topik diskusi atau janji Anda sebelumnya.\n"
                f"- DILARANG KERAS mengatakan Anda tidak punya akses, file belum di-upload, atau meminta user mengunggah ulang! Semua isi dokumen sudah tertera jelas di atas.\n"
                f"------------------------------------------------------------------\n\n"
            )

        # Cek intensitas permintaan (apakah user meminta detail atau sekadar berdiskusi santai)
        last_user_msg = ""
        for m in reversed(recent_messages):
            if m.get("sender_type") == "USER":
                last_user_msg = m.get("message_text", "").lower()
                break

        is_casual_topic = any(kw in last_user_msg for kw in ["makan siang", "makan", "ngopi", "halo bro", "rehat", "istirahat", "stay"])
        is_requesting_detail = has_uploaded_attachment or any(kw in last_user_msg for kw in [
            "detail", "jelasin", "jelaskan", "kenapa", "alasannya", "bedah", "poin-poin", "poinnya",
            "uraikan", "jabarkan", "buatkan", "draf", "tulis kode", "bikin", "rincian", "komprehensif"
        ])

        if is_casual_topic and not has_uploaded_attachment:
            system_context += (
                "\nInstruksi Khusus Obrolan Santai: Rekan tim menyapa atau mengajak santai (seperti makan siang, ngopi, istirahat). "
                "Tanggapi dengan santai, akrab, dan bersahabat seperti kawan kantor yang asyik dengan kata ganti aku-kamu. "
                "Contoh respons: 'Santai aja bro, pada makan siang dulu, aku stay di sini nemenin ruangan.' atau 'Siap, selamat makan siang duluan rekan-rekan! Aku standby di sini jaga draf kerjaan kita.' DILARANG gunakan gw-elo!\n"
            )
        elif is_requesting_detail:
            system_context += (
                "\n[PANDUAN PANJANG RESPONS]: Rekan tim meminta elaborasi mendalam, mengirimkan berkas untuk dibedah, atau meminta draf teknis. "
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

                # Tambahkan rujukan dokumen jika pesan ini menautkan dokumen atau berkas
                doc_note = ""
                msg_atts = msg.get("attachments")
                if isinstance(msg_atts, list):
                    for att in msg_atts:
                        if isinstance(att, dict):
                            if att.get("type") == "context_doc":
                                doc_note = f" (Menautkan Dokumen Rujukan: {att.get('title')})"
                                break
                            elif att.get("type") == "context_mode":
                                doc_note = f" (Mode: {att.get('mode')})"
                                break
                            else:
                                aname = att.get("name") or att.get("filename")
                                if aname:
                                    doc_note = f" (Melampirkan Berkas: {aname})"
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
        messages: List[Dict[str, Any]],
        existing_document: Optional[str] = ""
    ) -> str:
        """
        Merangkum seluruh riwayat obrolan tim menjadi Notulensi Rapat & Diskusi resmi.
        Mencakup poin-poin dari setiap anggota tim yang berbicara (bukan hanya CAKRA AI)
        dan mengintegrasikan draf/catatan yang sudah ada tanpa menimpa atau menghilangkannya.
        """
        member_names = [f"{m.get('name', 'Anggota')} ({m.get('divisi', 'PT Pindad')})" for m in members] if members else ["Anggota Tim"]
        members_str = ", ".join(member_names)

        chat_lines = []
        user_speakers = set()
        for m in messages:
            sender_type = m.get("sender_type") or ("CAKRA" if m.get("sender_npp") == "CAKRA" else "USER")
            sender = m.get("sender_name") or m.get("sender_npp") or "Peserta"
            text = (m.get("message_text") or "").strip()
            if not text:
                continue
            clean_text = " ".join(text.split())
            if sender_type == "CAKRA":
                chat_lines.append(f"[CAKRA AI]: {clean_text}")
            else:
                chat_lines.append(f"[{sender} (Anggota Tim)]: {clean_text}")
                user_speakers.add(sender)

        transcript = "\n".join(chat_lines[-80:]) if chat_lines else "(Belum ada obrolan)"

        existing_notes_section = ""
        if existing_document and existing_document.strip():
            existing_notes_section = f"""
CATATAN / DRAF DOKUMEN SEBELUMNYA YANG SUDAH ADA DI RUANGAN:
\"\"\"
{existing_document.strip()}
\"\"\"
INSTRUKSI INTEGRASI: Integrasikan catatan sebelumnya di atas dengan obrolan terbaru di bawah. JANGAN MENGHAPUS poin penting atau kesepakatan yang sudah ada sebelumnya! Gabungkan secara harmonis menjadi notulensi komprehensif.
"""

        speakers_note = f"Anggota tim yang aktif berdiskusi: {', '.join(user_speakers)}" if user_speakers else "Seluruh peserta ruang diskusi."

        prompt = f"""Anda adalah Notulis & Sekretaris Eksekutif Cerdas PT Pindad.
Tugas Anda adalah merangkum seluruh percakapan tim di bawah ini menjadi DRAF NOTULENSI RAPAT & KESEPAKATAN TIM yang rapi, profesional, terstruktur, dan objektif.

PENTING - KONTRIBUSI SETIAP ANGGOTA:
Notulensi ini adalah rangkuman dari SELURUH TIM, BUKAN HANYA dari asisten CAKRA AI!
Anda WAJIB mengekstrak dan mencantumkan poin-poin ide, argumen, pertanyaan, dan masukan dari SETIAP anggota tim/rekan kerja yang berbicara.
{speakers_note}

INFORMASI RUANG DISKUSI:
- Nama Ruang: {room_name}
- Agenda / Topik: {room_topic or 'Diskusi & Koordinasi Tim'}
- Peserta: {members_str}
{existing_notes_section}
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
(Sajikan 2-3 kalimat ringkas intisari pertemuan dan fokus utama diskusi)

## 2. Masukan & Gagasan Anggota Tim
(WAJIB: Sebutkan poin-poin pandangan, gagasan, atau usulan dari masing-masing rekan tim yang berbicara)
- **[Nama Rekan/User]:** (Poin usulan/masukan utama)
- (Cantumkan setiap anggota yang menyampaikan ide/masukan)

## 3. Rekomendasi & Analisis Pendukung (CAKRA AI)
(Rangkum saran teknis, data acuan, regulasi, atau solusi yang diajukan oleh CAKRA jika ada)

## 4. Keputusan & Kesepakatan Bersama
- (Poin keputusan atau konsensus yang telah disepakati tim)

## 5. Tindak Lanjut (Action Items)
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

    async def evaluate_and_extract_key_note(
        self,
        message_text: str,
        sender_name: str,
        room_topic: Optional[str] = "",
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        existing_document: Optional[str] = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Mengevaluasi apakah pesan percakapan di ruang kerja kolaborasi mengandung POIN PENTING
        (Keputusan, Tindak Lanjut/PIC, Deadline, Solusi Regulasi/Teknis) yang harus otomatis dicatat.
        Mengembalikan dict dengan bullet_note dan kategori jika layak, atau None jika bukan poin penting.
        """
        clean_text = (message_text or "").strip()
        if not clean_text or len(clean_text) < 15:
            return None

        # Filter cepat: sapaan dan obrolan kasual umum tanpa substansi
        lower_text = clean_text.lower()
        casual_greetings = [
            "halo", "hai", "pagi", "siang", "sore", "malam", "terima kasih", "makasih",
            "makan yuk", "ngopi dulu", "siap pak", "siap mas", "oke deh", "mantap",
            "wkwk", "haha", "hehe"
        ]
        if any(lower_text == g or lower_text.startswith(g + " ") for g in casual_greetings) and len(clean_text) < 40:
            return None

        # Jika teks sudah persis ada di existing document, skip
        if existing_document:
            norm_new = re.sub(r'[\s\*\#\_\-]+', ' ', clean_text).strip().lower()
            norm_exist = re.sub(r'[\s\*\#\_\-]+', ' ', existing_document).strip().lower()
            if norm_new and norm_new in norm_exist:
                return None

        recent_context_lines = []
        if recent_messages:
            for m in recent_messages[-5:]:
                s_name = m.get("sender_name") or m.get("sender_npp") or "Peserta"
                s_txt = (m.get("message_text") or "").strip()
                if s_txt:
                    recent_context_lines.append(f"[{s_name}]: {s_txt}")
        recent_context_str = "\n".join(recent_context_lines) if recent_context_lines else "(Tidak ada konteks sebelumnya)"

        eval_prompt = (
            f"Topik Ruang Diskusi: {room_topic or 'Umum / Kolaborasi Kerja'}\n\n"
            f"Konteks Percakapan Terakhir:\n{recent_context_str}\n\n"
            f"Pesan yang Dievaluasi:\n"
            f"Pengirim: {sender_name}\n"
            f"Isi Pesan: \"{clean_text}\"\n\n"
            f"Catatan Tim yang Sudah Ada Saat Ini:\n\"\"\"\n{(existing_document or '')[:500]}\n\"\"\"\n\n"
            f"Instruksi: Tentukan apakah pesan di atas mengandung poin penting (kesepakatan rapat, action items/PIC, deadline, arahan regulasi/kebijakan, kendala kritis/blocker, manajemen risiko/mitigasi, perubahan scope/budget, atau temuan data/evaluasi krusial). "
            f"Jika ya, buat 'bullet_note' dengan format: '• **[Kategori]**: (Ringkasan intisari padat dan jelas)'. Jika tidak, kembalikan is_noteworthy: false."
        )

        messages = [
            {"role": "system", "content": COLLAB_AUTO_NOTE_EVAL_PROMPT},
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
                timeout=45.0
            )
            is_noteworthy = bool(res.get("is_noteworthy", False))
            if not is_noteworthy:
                return None

            category = str(res.get("category", "Poin Penting")).strip()
            bullet_note = str(res.get("bullet_note", "")).strip()
            if not bullet_note:
                bullet_note = f"• **{category}**: {clean_text}"

            return {
                "is_noteworthy": True,
                "category": category,
                "bullet_note": bullet_note,
                "reason": str(res.get("reason", ""))
            }
        except Exception as e:
            logger.warning(f"[AUTO_NOTE_EVAL] Evaluasi auto-note gagal/timeout: {e}")
            return None


