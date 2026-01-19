import asyncio
import json
import uuid
import logging
from typing import Tuple, Optional, Dict, Any
import aiohttp
from backend.database.connection import db_manager
from backend.utils.embedding_utils import embedding_manager
from backend.config.settings import settings
from backend.services.document_service import DocumentService


class ChatService:
    @staticmethod
    async def get_chat_history_from_db(session_uuid: str, limit: int = 5) -> list:
        """Mengambil history percakapan terakhir"""
        history = []
        conn_hist = None
        try:
            conn_hist = await db_manager.get_rag_connection()

            # Query join ke sessions untuk memastikan session_uuid yang dipakai
            query = """
                SELECT d.user_text, d.assistant_text
                FROM ai_dialogue_corpus d
                JOIN chat_sessions s ON d.session_id = s.id
                WHERE s.session_uuid = $1
                ORDER BY d.created_at DESC
                LIMIT $2
            """
            rows = await conn_hist.fetch(query, session_uuid, limit)

            # Balik urutan agar kronologis: Lama -> Baru
            for row in reversed(rows):
                history.append({"role": "user", "content": row["user_text"]})
                history.append({"role": "assistant", "content": row["assistant_text"]})

            return history
        except Exception as e:
            logging.error(f"❌ Error fetch history: {e}")
            return []
        finally:
            if conn_hist:
                await db_manager.release_rag_connection(conn_hist)

    @staticmethod
    async def generate_judul_ai(message: str) -> str:
        try:
            prompt = (
                f"Buat judul singkat 3-6 kata untuk pesan ini: '{message}'\n"
                "Judul harus mewakili topik utama. Hanya kembalikan judulnya saja."
            )

            # Menggunakan requests (Synchronous) - perlu diganti ke async
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.OLLAMA_GENERATE_URL,
                    json={"model": settings.PRIMARY_MODEL, "prompt": prompt, "stream": False},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return (result.get("response", "")).strip() or message[:30] + "..."
                    return message[:30] + "..."
        except Exception as e:
            logging.error(f"Gagal generate judul via requests: {e}")
            return message[:30] + "..."

    @staticmethod
    async def ask_ollama(
        prompt: str, 
        images: Optional[list] = None, 
        stream: bool = False, 
        file_type: str = None, 
        override_model: str = None
    ) -> str:
        """Helper untuk bertanya ke model Ollama"""
        
        # 1. LOGIKA PEMILIHAN MODEL
        if images or (file_type and file_type in ["pdf", "png", "jpg", "jpeg"]):
            target_model = settings.VISION_MODEL
        else:
            target_model = override_model if override_model else settings.PRIMARY_MODEL

        messages = [{"role": "user", "content": prompt}]
        if images:
            messages[0]["images"] = images

        print(f"--- Ollama Request: Using model {target_model} ---")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.OLLAMA_URL,
                    json={
                        "model": target_model,
                        "messages": messages,
                        "stream": stream,
                        "options": {"temperature": 0.1},
                    },
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        err_msg = await resp.text()
                        print(f"Ollama Error ({resp.status}): {err_msg}")
                        return f"Error dari Ollama: {resp.status}"

                    if stream:
                        full_reply = ""
                        async for line in resp.content:
                            if line:
                                try:
                                    obj = json.loads(line.decode("utf-8"))
                                    chunk = obj.get("message", {}).get("content", "")
                                    full_reply += chunk
                                    if obj.get("done"):
                                        break
                                except:
                                    continue
                        return (
                            full_reply
                            if full_reply
                            else "Model memberikan respon kosong (stream)."
                        )
                    else:
                        result = await resp.json()
                        return result.get("message", {}).get(
                            "content", "Model memberikan respon kosong."
                        )
        except Exception as e:
            print(f"Critical Error in ask_ollama: {str(e)}")
            return f"Sistem AI sedang sibuk atau error: {str(e)}"

    @staticmethod
    async def smart_chat_with_context(
        user_message: str, 
        active_file: Optional[Dict], 
        mode: str, 
        model: str, 
        session_uuid: Optional[str], 
        npp: Optional[str], 
        role: str
    ) -> Tuple[str, Optional[Dict], bool]:
        # --- 0. LOAD HISTORY DARI DB ---
        history_context = ""
        if session_uuid:
            history_messages = await ChatService.get_chat_history_from_db(session_uuid, limit=3)
            if history_messages:
                history_context = "\n".join(
                    [f"{m['role'].upper()}: {m['content']}" for m in history_messages]
                )

        # =========================================================================
        # 1. JALUR DOKUMEN AKTIF (BYPASS PDF/OCR) - PRIORITAS UTAMA
        # =========================================================================
        if active_file and active_file.get("text"):
            print(f"[DEBUG] BYPASS: Menggunakan Teks PaddleOCR untuk PDF")

            # Gabungkan instruksi di sini agar AI fokus
            prompt_ocr = f"""Tugas: {user_message if user_message else "Rangkum dokumen ini"}

Gunakan teks hasil scan OCR di bawah ini untuk menjawab pertanyaan/tugas tersebut.
---
[ISI DOKUMEN]:
{active_file["text"][:15000]}
---
[HISTORY PERCAKAPAN]:
{history_context[-500:]}

INSTRUKSI KHUSUS:
- Analisis teks di atas dan jawab pertanyaan user dengan detail.
- Jika user minta rangkuman, buatkan poin-poin pentingnya.
- Jika jawaban tidak ada di dokumen, beri tahu user secara jujur.
"""
            # Panggil AI dengan instruksi lengkap
            reply = await ChatService.ask_ollama(prompt_ocr, stream=True, override_model=model)
            return reply, None, False

        # =========================================================================
        # MODE SEARCH (Pindad Website Scraper) - IMPLEMENTASI akan ditambahkan nanti
        # =========================================================================
        if mode == "search":
            # Untuk saat ini, kita kembalikan pesan bahwa fitur ini belum sepenuhnya diimplementasikan
            search_result = "Fitur pencarian website belum sepenuhnya diimplementasikan dalam versi FastAPI ini"
            search_prompt = f"""Kamu adalah asisten AI untuk PT Pindad. 
{search_result}

KONTEKS PERCAKAPAN SEBELUMNYA:
{history_context}

Tolong jawab pertanyaan pengguna:
    PERTANYAAN: "{user_message}"

    INSTRUKSI:
    1. Jika jawaban ada, berikan jawaban detail
    2. Jika tidak ada, JAWAB: "Tidak ditemukan informasi spesifik tentang hal ini dalam dokumen perusahaan"
    3. Gunakan Bahasa Indonesia yang baik dan benar dan jawab dengan natural
"""
            reply = await ChatService.ask_ollama(search_prompt, stream=True, override_model=model)
            return reply, None, False

        # =========================================================================
        # MODE DOCUMENT (RAG dengan Analisa & Verifikasi)
        # =========================================================================
        elif mode == "document":
            # --- 1. TAHAP ANALISA AWAL (Contextual / History Aware) ---
            analysis_prompt = f"""Analisis pertanyaan pengguna.
HISTORY PERCAKAPAN:
{history_context}

PERTANYAAN BARU: "{user_message}"

Tugas:
1. Hubungkan dengan history jika masih relevan.
2. Berikan kata kunci pencarian (search query) yang efektif.

Jawaban format: ANALISIS | KATA_KUNCI
"""
            analysis_res = await ChatService.ask_ollama(
                analysis_prompt, stream=False, override_model=model
            )

            # Parsing Analisa 1
            parts = (
                analysis_res.split("|")
                if "|" in analysis_res
                else ["Tidak ada analisa", user_message]
            )
            reasoning = parts[0].strip()
            search_query = parts[1].strip()

            print("\n🔍 " + "─" * 40)
            print(f"🤖 AI ANALYSIS 1 (With Context)")
            print(f"🧠 Reasoning : {reasoning}")
            print(f"🔑 Query 1   : {search_query}")

            # --- 2. TAHAP CARI 1 ---
            search_result = await DocumentService.search_documents(search_query)
            relevant_chunks = [
                c
                for c in search_result["chunks"]
                if c["similarity"] >= settings.SIMILARITY_THRESHOLD
            ]

            # --- 3. VERIFIKASI RELEVANSI (SELF-CORRECTION) ---
            # Kita cek apakah hasil pencarian tahap 1 benar-benar mengandung inti dari pertanyaan user
            is_truly_relevant = False
            if relevant_chunks:
                # AI mengevaluasi hasil database sendiri
                eval_prompt = f"""User bertanya tentang: "{user_message}"
Hasil pencarian database: "{relevant_chunks[0]['content'][:500]}..."

Tugas: Apakah hasil pencarian tersebut BENAR-BENAR relevan dan menjawab pertanyaan user?
Contoh: Jika user tanya 'efisiensi' tapi hasilnya 'mesin painting', maka JAWAB: TIDAK.
Jawaban: YA atau TIDAK"""

                eval_res = await ChatService.ask_ollama(
                    eval_prompt, stream=False, override_model=model
                )
                if "YA" in eval_res.upper():
                    is_truly_relevant = True

            # --- 4. TAHAP RE-ANALISA (Jika Cari 1 Gagal atau Gak Nyambung) ---
            if not is_truly_relevant:
                print(
                    f"⚠️  [VERIFIKASI 2] Hasil Tahap 1 tidak relevan. Melakukan Re-Analisa..."
                )

                # Reset Analisa: AI dipaksa membuat query baru TANPA history
                re_analysis_prompt = f"""Pertanyaan user: "{user_message}"
Hasil pencarian sebelumnya tidak relevan karena tercampur konteks lama.
Tugas: Buat kata kunci pencarian baru yang murni hanya fokus pada pertanyaan user tersebut (abaikan topik sebelumnya).

Jawaban format: ANALISIS_ULANG | KATA_KUNCI_MURNI
"""
                re_analysis_res = await ChatService.ask_ollama(
                    re_analysis_prompt, stream=False, override_model=model
                )
                re_parts = (
                    re_analysis_res.split("|")
                    if "|" in re_analysis_res
                    else ["Cari ulang", user_message]
                )

                search_query = re_parts[1].strip()
                print(f"🧠 Re-Analisa : {re_parts[0].strip()}")
                print(f"🔑 Query Baru : {search_query}")

                # Cari ulang menggunakan query murni
                search_result = await DocumentService.search_documents(search_query)
                relevant_chunks = [
                    c
                    for c in search_result["chunks"]
                    if c["similarity"] >= settings.SIMILARITY_THRESHOLD
                ]

            # Logging Hit Akhir
            if relevant_chunks:
                top_chunk = relevant_chunks[0]
                print(
                    f"✅ HIT FINAL: {top_chunk.get('judul')} ({top_chunk.get('similarity'):.4f})"
                )
            else:
                print(f"❌ [LOG] Tetap tidak ada data relevan di database.")
            print("─" * 43 + "\n")

            # --- 5. TAHAP RESPONS ---
            # Deteksi Greeting (tetap ada agar asisten ramah)
            user_message_lower = user_message.lower()
            greeting_keywords = ["hai", "halo", "selamat pagi", "thanks", "terima kasih"]
            if (
                any(kw in user_message_lower for kw in greeting_keywords)
                and not relevant_chunks
            ):
                reply = await ChatService.ask_ollama(
                    f"Sapa user dengan ramah: {user_message}", stream=True
                )
                return reply, None, False

            # Fallback jika benar-benar tidak ada data
            if not relevant_chunks:
                prompt = f"Beritahu user bahwa dokumen terkait '{user_message}' tidak ditemukan di database internal."
                reply = await ChatService.ask_ollama(prompt, stream=True, override_model=model)
                return reply, None, False

            # Ambil Metadata Dokumen
            document_info = None
            target_doc_id = relevant_chunks[0]["dokumen_id"]
            if search_result.get("documents"):
                for doc in search_result["documents"]:
                    if doc["id"] == target_doc_id:
                        document_info = doc
                        break

            referensi_doc = ""
            if document_info:
                jenis_map = {
                    1: "SURAT KEPUTUSAN",
                    2: "SURAT EDARAN",
                    3: "INSTRUKSI KERJA",
                    4: "PROSEDUR",
                }
                jenis = jenis_map.get(document_info.get("id_jenis"), "DOKUMEN")
                referensi_doc = f"{jenis} {document_info.get('judul')} Nomor {document_info.get('nomor')}"

            # Susun Jawaban Akhir
            context_text = "\n".join(
                [f"DOKUMEN: {c.get('judul')}\n{c['content']}" for c in relevant_chunks[:3]]
            )
            doc_prompt = f"""Anda adalah AI internal PT Pindad.
DOKUMEN TERBARU:
{context_text}

PERTANYAAN USER: "{user_message}"

INSTRUKSI:
1. Gunakan informasi dari DOKUMEN TERBARU di atas untuk menjawab
2. JANGAN bahas topik lama (seperti mesin painting) jika dokumen ini membahas hal baru (seperti efisiensi).
3. Di akhir sebutkan: "Informasi ini berdasarkan dokumen {referensi_doc}"
4. Jawab dalam Bahasa Indonesia yang natural
"""
            reply = await ChatService.ask_ollama(doc_prompt, stream=True, override_model=model)

            # --- 6. LOGIK DISPLAY PDF (VALIDASI AKHIR) ---
            reply_lower = reply.lower()
            doc_match = False
            if document_info:
                nomor_doc = str(document_info.get("nomor", "")).lower()
                judul_doc = str(document_info.get("judul", "")).lower()
                if (nomor_doc != "" and nomor_doc in reply_lower) or (
                    judul_doc != "" and judul_doc in reply_lower
                ):
                    doc_match = True

            final_pdf_info = None
            if doc_match and document_info:
                final_pdf_info = {
                    "filename": document_info["filename"],
                    "title": document_info.get("judul", document_info["filename"]),
                    "nomor": document_info.get("nomor", ""),
                    "tanggal": document_info.get("tanggal", ""),
                    "tempat": document_info.get("tempat", ""),
                    "url": f"/db_doc/{document_info['filename']}",
                    "download_url": f"/db_doc/{document_info['filename']}",
                }

            return reply, final_pdf_info, doc_match

        # =========================================================================
        # MODE NORMAL
        # =========================================================================
        elif mode == "normal":
            print(f"\n[DEBUG] === MEMULAI ANALISIS PESAN (MODE NORMAL) ===")

            # --- LAYER 1: ANALISIS NIAT USER ---
            analysis_prompt = f"""
                Tugas: Analisis apakah pesan user memerlukan pencarian data di database perusahaan (aturan/dokumen/history).
                History: {history_context[-500:]}
                User: {user_message}

                Jawab hanya dengan format JSON:
                {{
                "perlu_cari": true/false,
                "keyword_pencarian": "kata kunci search"
                }}
            """

            analysis_res = await ChatService.ask_ollama(
                analysis_prompt, stream=False, override_model="qwen2.5:14b-instruct"
            )

            try:
                clean_json = analysis_res.replace("```json", "").replace("```", "").strip()
                analysis_data = json.loads(clean_json)
            except Exception:
                analysis_data = {"perlu_cari": True, "keyword_pencarian": user_message}

            # --- LAYER 2: UNIVERSAL SEARCH (SYNC CHUNKS & CORPUS) ---
            corpus_context = ""
            if analysis_data.get("perlu_cari"):
                search_query = analysis_data.get("keyword_pencarian", user_message)

                # Ini fungsi sakti yang kita buat tadi (UNION SQL)
                # TODO: Implementasi search_universal_knowledge
                # universal_refs = await search_universal_knowledge(search_query, npp, role)

                if False:  # Replace with actual search results
                    formatted_refs = []
                    # for ref in universal_refs:
                    #     # Bedakan cara menampilkan info Chunks vs History
                    #     if ref["source"] == "CHAT":
                    #         formatted_refs.append(
                    #             f"[MEMORI CHAT]: User tanya '{ref['primary_content']}' -> AI jawab '{ref['secondary_content']}'"
                    #         )
                    #     else:
                    #         formatted_refs.append(
                    #             f"[DOKUMEN {ref['secondary_content']}]: {ref['primary_content']}"
                    #         )

                    corpus_context = (
                        "REFERENSI DATA INTERNAL PERUSAHAAN:\n"
                        + "\n---\n".join(formatted_refs)
                        + "\n\n"
                    )
                else:
                    corpus_context = (
                        "INFO: Tidak ada referensi dokumen lama yang relevan.\n"
                    )

            # --- LAYER 3: GENERATE RESPON AKHIR ---
            # Jika ada file yang sedang di-upload (Active File), ia jadi prioritas #1
            if active_file:
                context_text = active_file.get("text", "")[
                    :7000
                ]  # Gue naikin dikit limitnya karena A40 kuat
                file_name = active_file.get("name", "Dokumen Terlampir")

                prompt = f"""Kamu adalah CAKRA (Cerdas Terpercaya), AI PT Pindad.

DOKUMEN YANG SEDANG DIBUKA (PRIORITAS UTAMA):
Nama File: {file_name}
Konten: {context_text}

{corpus_context}

HISTORY CHAT TERAKHIR:
{history_context}

INSTRUKSI:
1. Jawab pertanyaan user: "{user_message}"
2. Berikan jawaban paling akurat berdasarkan 'DOKUMEN YANG SEDANG DIBUKA'.
3. Jika tidak ada di dokumen tersebut, gunakan 'REFERENSI DATA INTERNAL PERUSAHAAN'.
4. Gunakan gaya bahasa yang profesional namun membantu.
"""
            else:
                # Jika tidak ada file upload, murni pakai Universal RAG
                prompt = f"""Kamu adalah CAKRA, AI PT Pindad.

{corpus_context}

HISTORY CHAT TERAKHIR:
{history_context}

User: {user_message}

Tugas: Jawab dengan jujur berdasarkan referensi data internal yang tersedia.
"""

            # EKSEKUSI FINAL
            reply = await ChatService.ask_ollama(prompt, stream=True, override_model=model)

            if reply is None:
                reply = "Maaf bro, sistem sedang sibuk. Coba ulangi lagi ya."

            return reply, None, False

        # Default fallback
        reply = await ChatService.ask_ollama(user_message, stream=True, override_model=model)
        return reply, None, False