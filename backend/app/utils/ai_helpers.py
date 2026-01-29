import aiohttp
import json
import logging
import time
import numpy as np
from ..config import settings
from ..database import get_db, embedding_to_pgvector_str
from .embeddings import get_embedding, EMBEDDING_MODEL
from .web_scraping import scrape_pindad_website

logger = logging.getLogger(__name__)


async def ask_qwen3_vl(
    prompt, images=None, stream=False, file_type=None, override_model=None
):
    """Helper untuk bertanya ke model yang sesuai"""
    if images or (file_type and file_type in ["pdf", "png", "jpg", "jpeg"]):
        target_model = settings.vision_model
    else:
        target_model = override_model if override_model else settings.primary_model

    messages = [{"role": "user", "content": prompt}]
    if images:
        messages[0]["images"] = images

    print(f"--- Ollama Request: Using model {target_model} ---")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.ollama_url,
                json={
                    "model": target_model,
                    "messages": messages,
                    "stream": stream,
                    "options": {"temperature": 0.1},
                },
                timeout=120,
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
        print(f"Critical Error in ask_qwen3_vl: {str(e)}")
        return f"Sistem AI sedang sibuk atau error: {str(e)}"


async def get_chat_history_from_db(session_uuid, limit=5):
    """
    Mengambil history percakapan berdasarkan session_uuid.
    Ini aman buat GUEST karena session_uuid unik per sesi browser.
    """
    history = []
    if not session_uuid:
        return []

    try:
        async with get_db() as conn:
            # Kita filter murni pake session_uuid dari tabel chat_sessions
            rows = await conn.fetch(
                """
                SELECT d.user_text, d.assistant_text 
                FROM ai_dialogue_corpus d
                JOIN chat_sessions s ON d.session_id = s.id
                WHERE s.session_uuid = $1
                ORDER BY d.created_at DESC, d.id DESC 
                LIMIT $2
                """,
                str(session_uuid),  # Pastikan tipenya string/UUID
                limit,
            )

            # Pakai reversed supaya urutannya User -> AI (kronologis)
            for row in reversed(rows):
                if row["user_text"]:
                    history.append({"role": "user", "content": row["user_text"]})
                if row["assistant_text"]:
                    history.append(
                        {"role": "assistant", "content": row["assistant_text"]}
                    )

            return history
    except Exception as e:
        logging.error(f"❌ Error fetch history for session {session_uuid}: {e}")
        return []


async def search_documents(query, limit=settings.search_limit):
    """Search documents in the database using Hybrid Search"""
    logging.info(f"🔍 [search_documents] Mencari (Hybrid): '{query}'")
    try:
        query_embedding = EMBEDDING_MODEL.encode([query], normalize_embeddings=True)[
            0
        ].tolist()
        query_vector_str = embedding_to_pgvector_str(query_embedding)

        async with get_db() as conn:
            # --- Full-Text Search ---
            raw_fts = await conn.fetch(
                """
                SELECT
                    dc.id, dc.dokumen_id, d.judul, d.nomor, d.tanggal, d.tempat,
                    d.filename, d.id_jenis, dc.content, dc.chunk_id,
                    ts_rank_cd(to_tsvector('indonesian', dc.content), plainto_tsquery('indonesian', $1), 1) as fts_score
                FROM dokumen_chunk dc
                JOIN dokumen d ON dc.dokumen_id = d.id
                WHERE to_tsvector('indonesian', dc.content) @@ plainto_tsquery('indonesian', $2)
                  AND d.status_ocr = 'rag_ready'
                ORDER BY fts_score DESC LIMIT $3
            """,
                query,
                query,
                limit,
            )

            # KONVERSI KE DICT (Hanya ini yang ditambah agar tidak error)
            fts_chunks = [dict(r) for r in raw_fts]
            logging.info(f"✅ FTS menemukan {len(fts_chunks)} chunk.")

            # --- Vector Search ---
            raw_vector = await conn.fetch(
                """
                SELECT
                    dc.id, dc.dokumen_id, d.judul, d.nomor, d.tanggal, d.tempat,
                    d.filename, d.id_jenis, dc.content, dc.chunk_id,
                    (dc.embedding <#> $1::vector) as cosine_distance
                FROM dokumen_chunk dc
                JOIN dokumen d ON dc.dokumen_id = d.id
                WHERE d.status_ocr = 'rag_ready'
                ORDER BY (dc.embedding <#> $1::vector) LIMIT $2
            """,
                query_vector_str,
                limit,
            )

            # KONVERSI KE DICT
            vector_chunks = [dict(r) for r in raw_vector]
            logging.info(f"✅ Vector Search menemukan {len(vector_chunks)} chunk.")

            # --- Gabungkan Hasil (Hybrid) ---
            combined_scores = {}
            id_to_chunk = {}

            for chunk in fts_chunks:
                chunk_id = chunk["id"]
                combined_scores[chunk_id] = {
                    "fts_score": chunk["fts_score"],
                    "vector_score": 0.0,
                    "similarity": 0.0,
                    "chunk_data": chunk,
                }
                id_to_chunk[chunk_id] = chunk
                # Sekarang baris ini AMAN karena chunk sudah dict
                combined_scores[chunk_id]["chunk_data"]["fts_score"] = None

            for chunk in vector_chunks:
                chunk_id = chunk["id"]
                cosine_distance = chunk["cosine_distance"]
                cosine_similarity = 1.0 - cosine_distance

                if chunk_id in combined_scores:
                    combined_scores[chunk_id]["vector_score"] = cosine_similarity
                    combined_scores[chunk_id]["similarity"] = cosine_similarity
                else:
                    combined_scores[chunk_id] = {
                        "fts_score": 0.0,
                        "vector_score": cosine_similarity,
                        "similarity": cosine_similarity,
                        "chunk_data": chunk,
                    }
                    id_to_chunk[chunk_id] = chunk

            WEIGHT_FTS = 0.4
            WEIGHT_VECTOR = 0.6

            def calculate_hybrid_score(scores):
                fts_norm = scores["fts_score"]
                vector_norm = scores["vector_score"]
                return (WEIGHT_FTS * fts_norm) + (WEIGHT_VECTOR * vector_norm)

            scored_chunks = [
                (cid, calculate_hybrid_score(scores))
                for cid, scores in combined_scores.items()
            ]
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            sorted_chunks = [
                id_to_chunk[cid] for cid, score in scored_chunks if cid in id_to_chunk
            ]

            # Filter berdasarkan threshold
            filtered_chunks = []
            for chunk in sorted_chunks:
                vector_similarity = combined_scores[chunk["id"]]["vector_score"]
                if vector_similarity >= settings.similarity_threshold:
                    chunk["similarity"] = vector_similarity  # AMAN
                    filtered_chunks.append(chunk)

            final_chunks = filtered_chunks[:limit]

            # --- Ambil info dokumen ---
            document_ids = list(set(chunk["dokumen_id"] for chunk in final_chunks))
            documents = []
            if document_ids:
                raw_docs = await conn.fetch(
                    """
                    SELECT id, judul, nomor, tanggal, tempat, filename, status, id_jenis
                    FROM dokumen WHERE id = ANY($1)
                """,
                    document_ids,
                )
                documents = [dict(row) for row in raw_docs]

            logging.info(
                f"✅ Ditemukan {len(final_chunks)} chunk yang melewati filter Hybrid Search."
            )

            for i, chunk in enumerate(final_chunks):
                logging.info(
                    f"[Hybrid] Chunk-{i} dokumen_id={chunk['dokumen_id']} judul={chunk['judul']} similarity: {chunk['similarity']:.4f}"
                )

            return {
                "documents": documents,
                "chunks": final_chunks,
            }

    except Exception as e:
        logging.error(f"Error searching documents (Hybrid): {e}")
        # --- Fallback ke vector search (Logika tetap sama) ---
        try:
            async with get_db() as conn:
                raw_fallback = await conn.fetch(
                    """
                    SELECT dc.id, dc.dokumen_id, d.judul, d.nomor, d.tanggal, d.tempat,
                           d.filename, d.id_jenis, dc.content, dc.chunk_id,
                           (dc.embedding <#> $1::vector) as cosine_distance
                    FROM dokumen_chunk dc
                    JOIN dokumen d ON dc.dokumen_id = d.id
                    WHERE d.status_ocr = 'rag_ready'
                    ORDER BY (dc.embedding <#> $1::vector) LIMIT $2
                """,
                    query_vector_str,
                    limit,
                )

                chunks = [dict(r) for r in raw_fallback]

                filtered_chunks = []
                for chunk in chunks:
                    cosine_similarity = 1.0 - chunk["cosine_distance"]
                    if cosine_similarity >= settings.similarity_threshold:
                        chunk["similarity"] = cosine_similarity
                        filtered_chunks.append(chunk)
                    chunk["cosine_distance"] = None

                final_chunks = filtered_chunks[:limit]
                # ... (logika ambil dokumen fallback sama seperti di atas)
                return {"documents": [], "chunks": final_chunks}  # Sesuai return lo
        except Exception as fallback_e:
            logging.error(f"Fallback search also failed: {fallback_e}")
            return {"documents": [], "chunks": []}


async def search_universal_knowledge(query, npp, role, limit=4):
    """Universal search optimized for Guest and Public Memory"""
    logging.info(f"🧠 [Universal Search] NPP: {npp} | Role: {role} | Query: '{query}'")
    try:
        # 1. Embedding logic tetap sama
        query_embedding = EMBEDDING_MODEL.encode([query], normalize_embeddings=True)[
            0
        ].tolist()
        query_vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

        async with get_db() as conn:
            # 2. Pastikan role di-handle dengan aman
            role_upper = role.upper() if role else "GUEST"
            is_trainer = role_upper == "TRAINER"

            results = await conn.fetch(
                """
                WITH combined_knowledge AS (
                    -- Sumber A: History Chat (Ambil yang public atau milik sendiri)
                    SELECT 
                        'CHAT' as source,
                        adc.user_text as primary_content,
                        adc.assistant_text as secondary_content,
                        (adc.embedding_user <=> $1::vector) as distance,
                        cs.npp as owner_npp
                    FROM ai_dialogue_corpus adc
                    JOIN chat_sessions cs ON adc.session_id = cs.id
                    LEFT JOIN users u ON cs.npp = u.npp
                    WHERE (
                        $2 = TRUE OR                           -- Trainer bisa liat semua
                        cs.npp = $3 OR                         -- Milik sendiri
                        (cs.npp IS NULL AND $3 IS NULL) OR     -- Sama-sama Guest
                        u.role = 'TRAINER' OR                  -- Ilmu dari Trainer itu publik
                        cs.npp = ''                            -- String kosong dianggap publik
                    )

                    UNION ALL

                    -- Sumber B: Isi Dokumen OCR
                    SELECT 
                        'DOCUMENT' as source,
                        content as primary_content,
                        metadata->>'filename' as secondary_content,
                        (embedding <=> $1::vector) as distance,
                        adc_chunks.npp as owner_npp
                    FROM ai_document_chunks adc_chunks
                    LEFT JOIN users u ON adc_chunks.npp = u.npp
                    WHERE (
                        $2 = TRUE OR 
                        adc_chunks.npp = $3 OR 
                        (adc_chunks.npp IS NULL AND $3 IS NULL) OR
                        u.role = 'TRAINER'
                    )

                    UNION ALL

                    -- Sumber C: AI MEMORY (DIPERKETAT UNTUK GUEST)
                    SELECT 
                        'PERMANENT' as source,
                        mem_key as primary_content,
                        mem_value as secondary_content,
                        (embedding <=> $1::vector) as distance,
                        npp as owner_npp
                    FROM ai_memory
                    WHERE (
                        category = 'public' OR                 -- Pastikan memory tersimpan sebagai public
                        npp = $3 OR                            -- Milik sendiri
                        (npp IS NULL) OR                       -- Memory tanpa owner adalah public
                        $2 = TRUE                              -- Trainer bypass
                    )
                )
                SELECT * FROM combined_knowledge
                WHERE (1 - distance) >= 0.45                   -- Threshold diturunkan dikit biar lebih sensitif
                ORDER BY 
                    (CASE WHEN source = 'PERMANENT' THEN 0 ELSE 1 END), -- Prioritaskan Memory
                    distance ASC
                LIMIT $4
                """,
                query_vector_str,
                is_trainer,
                npp,  # Bisa NULL
                limit,
            )

            return [dict(row) for row in results]

    except Exception as e:
        logging.error(f"Error in universal search: {e}")
        return []


async def generate_judul_ai(message):
    """Generate judul untuk chat session dengan fallback yang lebih aman"""
    fallback_title = message[:30] + "..." if len(message) > 30 else message

    try:
        prompt = (
            f"Tugas: Buat judul singkat 3-5 kata.\n"
            f"Topik: '{message}'\n"
            "Aturan: Hanya kembalikan teks judul, tanpa tanda kutip, tanpa penjelasan."
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.ollama_generate_url,
                json={
                    "model": settings.primary_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 20,
                        "temperature": 0.3,
                    },
                },
                timeout=15,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    title = result.get("response", "").strip()

                    title = title.replace('"', "").replace("Title:", "").strip()

                    return title if title else fallback_title

                logging.warning(
                    f"⚠️ Ollama return status {resp.status}, using fallback."
                )
                return fallback_title

    except Exception as e:
        logging.error(f"❌ Gagal generate judul: {type(e).__name__} - {e}")
        return fallback_title


async def smart_chat_with_context(
    user_message,
    active_file,
    mode,
    model,
    session_uuid,
    npp,
    role,
    attachments,
    background_tasks,
):
    """Main smart chat function dengan logika sama persis + robust timing & logging"""
    start_time = time.time()
    session_id_log = session_uuid or "NEW_SESSION"
    log_prefix = f"[SESSION:{session_id_log}|NPP:{npp or 'GUEST'}|MODE:{mode}]"
    print(f"\n{log_prefix} 🚀 SMART_CHAT_STARTED | Message: {user_message[:60]}...")

    # Load history dari DB
    history_context = ""
    if session_uuid:
        hist_start = time.time()
        history_messages = await get_chat_history_from_db(session_uuid, limit=3)
        hist_duration = time.time() - hist_start
        if history_messages:
            history_context = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in history_messages]
            )
        print(
            f"{log_prefix} ⏱️ History loaded ({len(history_messages)} msgs) in {hist_duration:.2f}s"
        )

    # 1. JALUR DOKUMEN AKTIF (BYPASS PDF/OCR) - PRIORITAS UTAMA
    if active_file and active_file.get("text"):
        print(f"{log_prefix} 📄 ACTIVE_FILE_DETECTED | Using OCR text")
        prompt_ocr = f"""Tugas: {user_message if user_message else "Rangkum dokumen ini"}

Gunakan teks hasil scan OCR di bawah ini sebagai sumber data utama.
---
[ISI DOKUMEN]:
{active_file["text"][:15000]} 
---
[HISTORY PERCAKAPAN]:
{history_context[-3000:]}

INSTRUKSI KETAT:
1. Perbaiki semua kesalahan baca OCR (typo, kata terputus, atau simbol aneh) secara otomatis di dalam pikiranmu.
2. JANGAN tampilkan catatan koreksi, JANGAN tampilkan daftar kesalahan OCR, dan JANGAN bahas proses perbaikan teks tersebut kepada user.
3. Langsung sajikan jawaban atau rangkuman yang sudah bersih, rapi, dan profesional.
4. Jika user minta rangkuman, gunakan poin-poin.
5. Jika informasi tidak ada di dokumen, katakan sejujurnya tanpa bertele-tele.
"""
        ocr_gen_start = time.time()
        reply = await ask_qwen3_vl(prompt_ocr, stream=True, override_model=model)
        ocr_gen_duration = time.time() - ocr_gen_start
        total_duration = time.time() - start_time
        print(
            f"{log_prefix} ✅ OCR_PATH_DONE | AI Gen: {ocr_gen_duration:.2f}s | Total: {total_duration:.2f}s"
        )
        return reply, None, False

    # 2. MULTIMODAL LAYER (Handle Images)
    has_images = attachments and any(
        a and "image" in a.get("type", "").lower() for a in attachments
    )
    if has_images:
        try:
            print(f"{log_prefix} 🖼️ IMAGE_ATTACHED | Processing multimodal")
            img_obj = next(
                a for a in attachments if "image" in a.get("type", "").lower()
            )
            img_data = img_obj.get("data", "")
            raw_base64 = img_data.split(",")[1] if "," in img_data else img_data

            intent_start = time.time()
            vlm_intent_prompt = f"""Tugas: Analisis apakah pertanyaan user tentang gambar ini memerlukan referensi data internal perusahaan atau hanya ekstraksi gambar biasa.
            User Message: {user_message}
            Jawab dengan format JSON: {{"use_rag": true, "focus_instruction": "instruksi"}}"""

            intent_res = await ask_qwen3_vl(
                vlm_intent_prompt,
                stream=False,
                override_model="qwen2.5:7b-instruct",
            )
            intent_duration = time.time() - intent_start

            try:
                clean_json = (
                    intent_res.replace("```json", "").replace("```", "").strip()
                )
                intent_data = json.loads(clean_json)
            except:
                intent_data = {
                    "use_rag": False,
                    "focus_instruction": "Ekstrak data secara objektif.",
                }

            gen_start = time.time()
            vlm_final_prompt = (
                f"{intent_data.get('focus_instruction')}\n\nUser: {user_message}"
            )
            reply = await ask_qwen3_vl(
                prompt=vlm_final_prompt,
                images=[raw_base64],
                stream=True,
                override_model=settings.vision_model,
            )
            gen_duration = time.time() - gen_start
            total_duration = time.time() - start_time
            print(
                f"{log_prefix} ✅ MULTIMODAL_DONE | Intent: {intent_duration:.2f}s | Gen: {gen_duration:.2f}s | Total: {total_duration:.2f}s"
            )
            return reply, None, False
        except Exception as e:
            print(f"{log_prefix} ❌ Multimodal Layer Error: {e}")

    # MODE SEARCH (Pindad Website Scraper - Two Stage Logic)
    if mode == settings.mode_search:
        print(f"{log_prefix} 🔍 SEARCH_MODE_ACTIVATED")
        refine_start = time.time()
        refine_prompt = f"History:\n{history_context}\n\nUser: {user_message}\nBuat query search singkat (maksimal 3 kata) untuk mencari informasi di website PT Pindad."
        web_query = await ask_qwen3_vl(
            refine_prompt, stream=False, override_model=model
        )
        refine_duration = time.time() - refine_start

        clean_query = (
            web_query.strip().replace('"', "").replace("'", "")
            if web_query
            else user_message
        )
        print(
            f"{log_prefix} 🔎 Refined Query: '{clean_query}' (took {refine_duration:.2f}s)"
        )

        scrape_start = time.time()
        search_result = await scrape_pindad_website(clean_query)
        scrape_duration = time.time() - scrape_start
        print(f"{log_prefix} 🌐 Scraping done in {scrape_duration:.2f}s")

        search_prompt = f"""Kamu adalah asisten AI resmi PT Pindad. 
Gunakan data hasil scraping di bawah ini untuk menjawab pertanyaan: "{user_message}"

DATA DARI WEBSITE (www.pindad.com):
---
{search_result}
---

INSTRUKSI JAWABAN:
1. Jika pertanyaan bersifat umum (misal: "apa saja senjata Pindad"), buatkan daftar produk yang ditemukan dalam data, kategorikan jika mungkin (misal: Senjata Genggam, Senjata Laras Panjang).
2. Jika pertanyaan bersifat spesifik (misal: "berat Anoa 2"), ambil detail teknis dari tabel atau deskripsi yang tersedia.
3. Selalu sebutkan bahwa informasi ini berdasarkan data terbaru dari situs resmi Pindad.
4. Jika ada URL di dalam data, sertakan di akhir jawaban sebagai referensi tambahan.
5. Jika data tidak relevan dengan pertanyaan, sampaikan dengan sopan bahwa informasi tersebut belum tersedia di database saat ini.
"""
        gen_start = time.time()
        reply = await ask_qwen3_vl(search_prompt, stream=True, override_model=model)
        gen_duration = time.time() - gen_start
        total_duration = time.time() - start_time
        print(
            f"{log_prefix} ✅ SEARCH_MODE_DONE | Refine: {refine_duration:.2f}s | Scrape: {scrape_duration:.2f}s | Gen: {gen_duration:.2f}s | Total: {total_duration:.2f}s"
        )
        return reply, None, False

    # MODE DOCUMENT (RAG dengan Analisa & Verifikasi)
    elif mode == settings.mode_document:
        print(f"{log_prefix} 📚 DOCUMENT_MODE_ACTIVATED")
        intent_start = time.time()
        intent_prompt = f"""Analisis percakapan berikut.
HISTORY:
{history_context[-2000:]}

PESAN TERBARU USER: "{user_message}"

Tugas: 
1. Klasifikasikan 'intent': 
   - 'BASA_BASI': Sapaan awal, tes koneksi, atau salam penutup.
   - 'DISKUSI': User mengomentari, menanggapi, atau berterima kasih terkait info dokumen yang sudah diberikan sebelumnya (Contoh: "Wih panjang juga ya", "Oke makasih infonya").
   - 'PERTANYAAN': User menanyakan informasi spesifik baru atau meminta detail dari dokumen.
   
2. Tentukan 'is_pdf_info': 
   - Set TRUE: Hanya jika user bertanya hal spesifik yang butuh referensi dokumen baru/ulang.
   - Set FALSE: Jika user hanya berkomentar, menguji, atau menanggapi jawaban sebelumnya (DISKUSI/BASA_BASI).

Jawab hanya JSON:
{{
  "intent": "BASA_BASI/DISKUSI/PERTANYAAN",
  "is_pdf_info": true/false
}}"""

        intent_res = await ask_qwen3_vl(
            intent_prompt, stream=False, override_model=model
        )
        intent_duration = time.time() - intent_start

        try:
            clean_json = intent_res.replace("```json", "").replace("```", "").strip()
            intent_data = json.loads(clean_json)
        except:
            intent_data = {"intent": "PERTANYAAN", "is_pdf_info": True}

        is_basa_basi = intent_data.get("intent") == "BASA_BASI"
        is_pdf_info_allowed = intent_data.get("is_pdf_info", False)

        if is_basa_basi:
            print(f"{log_prefix} 💬 BASA_BASI_DETECTED | Skipping RAG")
            gen_start = time.time()
            reply = await ask_qwen3_vl(
                f"User bilang: {user_message}. Berdasarkan percakapan sebelumnya: {history_context[-1000:]}, berikan respon penutup atau sapaan yang nyambung dan ramah.",
                stream=True,
            )
            gen_duration = time.time() - gen_start
            total_duration = time.time() - start_time
            print(
                f"{log_prefix} ✅ BASA_BASI_DONE | Intent: {intent_duration:.2f}s | Gen: {gen_duration:.2f}s | Total: {total_duration:.2f}s"
            )
            return reply, None, False

        # ANALISIS QUERY
        analysis_start = time.time()
        analysis_prompt = f"""Analisis pertanyaan pengguna.
HISTORY PERCAKAPAN:
{history_context}

PERTANYAAN BARU: "{user_message}"

Tugas:
1. Hubungkan dengan history jika masih relevan.
2. Berikan kata kunci pencarian (search query) yang efektif.

Jawaban format: ANALISIS | KATA_KUNCI
"""
        analysis_res = await ask_qwen3_vl(
            analysis_prompt, stream=False, override_model=model
        )
        analysis_duration = time.time() - analysis_start
        parts = (
            analysis_res.split("|")
            if "|" in analysis_res
            else ["Tidak ada analisa", user_message]
        )
        search_query = parts[1].strip()
        print(
            f"{log_prefix} 🔑 Initial Query: '{search_query}' (analysis took {analysis_duration:.2f}s)"
        )

        # SEARCH & VERIFIKASI
        search_start = time.time()
        search_result = await search_documents(search_query)
        search_duration = time.time() - search_start
        relevant_chunks = [
            c
            for c in search_result["chunks"]
            if c["similarity"] >= settings.similarity_threshold
        ]

        eval_duration = 0
        is_truly_relevant = False
        if relevant_chunks:
            eval_start = time.time()
            eval_prompt = f"""User bertanya tentang: "{user_message}"
Hasil pencarian database: "{relevant_chunks[0]["content"][:1000]}..."

Tugas: Apakah hasil pencarian tersebut BENAR-BENAR relevan dan menjawab pertanyaan user?
Contoh: Jika user tanya 'efisiensi' tapi hasilnya 'mesin painting', maka JAWAB: TIDAK.
Jawaban: YA atau TIDAK"""
            eval_res = await ask_qwen3_vl(
                eval_prompt, stream=False, override_model=model
            )
            eval_duration = time.time() - eval_start
            is_truly_relevant = "YA" in eval_res.upper()

        re_analysis_duration = 0
        if not is_truly_relevant and relevant_chunks:
            print(f"{log_prefix} ⚠️ Re-analyzing query...")
            re_analysis_start = time.time()
            re_analysis_prompt = f"""Pertanyaan user: "{user_message}"
Tugas: Buat kata kunci pencarian baru yang murni hanya fokus pada pertanyaan user tersebut.

Jawaban format: ANALISIS_ULANG | KATA_KUNCI_MURNI
"""
            re_analysis_res = await ask_qwen3_vl(
                re_analysis_prompt, stream=False, override_model=model
            )
            re_analysis_duration = time.time() - re_analysis_start
            search_query = (
                re_analysis_res.split("|")[1].strip()
                if "|" in re_analysis_res
                else user_message
            )
            search_result = await search_documents(search_query)
            relevant_chunks = [
                c
                for c in search_result["chunks"]
                if c["similarity"] >= settings.similarity_threshold
            ]

        # GENERATE FINAL RESPONSE
        if not relevant_chunks:
            fallback_start = time.time()
            fallback_prompt = f"Beritahu user secara profesional bahwa data resmi tidak ditemukan untuk: {user_message}"
            reply = await ask_qwen3_vl(
                fallback_prompt, stream=True, override_model=model
            )
            fallback_duration = time.time() - fallback_start
            total_duration = time.time() - start_time
            print(
                f"{log_prefix} ❌ NO_RELEVANT_DOCS | Fallback: {fallback_duration:.2f}s | Total: {total_duration:.2f}s"
            )
            return reply, None, False

        context_text = "\n".join(
            [f"DOKUMEN: {c.get('judul')}\n{c['content']}" for c in relevant_chunks[:3]]
        )
        doc_prompt = f"""Anda adalah AI internal PT Pindad.
DOKUMEN TERBARU:
{context_text}

PERTANYAAN USER: "{user_message}"

INSTRUKSI:
1. Gunakan informasi dokumen untuk menjawab.
2. Jika menggunakan informasi tersebut, wajib tulis [DOC_VALIDATED] di akhir jawaban.
"""
        gen_start = time.time()
        reply = await ask_qwen3_vl(doc_prompt, stream=True, override_model=model)
        gen_duration = time.time() - gen_start

        is_validated_by_ai = "[DOC_VALIDATED]" in reply
        clean_reply = reply.replace("[DOC_VALIDATED]", "").strip()

        doc_match = False
        final_pdf_info = None
        if (
            is_validated_by_ai
            and is_pdf_info_allowed
            and search_result.get("documents")
        ):
            doc_info = search_result["documents"][0]
            doc_match = True
            final_pdf_info = {
                "filename": doc_info["filename"],
                "title": doc_info.get("judul", doc_info["filename"]),
                "nomor": doc_info.get("nomor", ""),
                "tanggal": doc_info.get("tanggal", ""),
                "tempat": doc_info.get("tempat", ""),
                "url": f"/db_doc/{doc_info['filename']}",
                "download_url": f"/db_doc/{doc_info['filename']}",
            }
            clean_reply += f"\n\nInformasi ini berdasarkan dokumen {doc_info.get('jenis', 'DOKUMEN')} {doc_info.get('judul')} Nomor {doc_info.get('nomor')}."

        total_duration = time.time() - start_time
        print(
            f"{log_prefix} ✅ DOCUMENT_MODE_DONE | Intent: {intent_duration:.2f}s | Analysis: {analysis_duration:.2f}s | Search: {search_duration:.2f}s | Eval: {eval_duration:.2f}s | ReAnalyze: {re_analysis_duration:.2f}s | Gen: {gen_duration:.2f}s | Total: {total_duration:.2f}s"
        )
        return clean_reply, final_pdf_info, doc_match

    # MODE NORMAL
    elif mode == settings.mode_normal:
        print(f"{log_prefix} 💬 NORMAL_MODE_ACTIVATED")

        # --- ANALISIS TUNGGAL: DETEKSI SEMUA KASUS DALAM 1 PROMPT ---
        analysis_start = time.time()
        analysis_prompt = f"""
        Tugas: Analisis pesan user secara komprehensif dalam SATU langkah.
        
        PENTING: User mungkin melakukan typo (salah ketik), menggunakan bahasa gaul, atau singkatan. 
        Lakukan normalisasi teks di dalam pikiranmu sebelum menentukan kategori (Contoh: "apa abar" -> "apa kabar", "spek anoa" -> "spesifikasi anoa").

        KATEGORI 1 - DETEKSI SUMBER DATA RESMI:
        - Jika pertanyaan tentang: Produk (senjata, kendaraan, amunisi), Spesifikasi teknis, Sejarah, Profil perusahaan, Alamat/Kontak/Hubungi kami, Visi Misi, Berita terbaru, Direksi/Direktur, Budaya perusahaan → set 'is_need_search': true.

        KATEGORI 2 - DETEKSI KOREKSI DATA:
        - Jika user mengoreksi data (contoh: "yang bener adalah...", "web pindad itu .com"), set 'is_update_memory': true.
        - Buat 'extracted_value' berupa kalimat deklaratif tegas untuk menindih info lama.

        KATEGORI 3 - DETEKSI KEBUTUHAN RAG INTERNAL:
        - Jika pertanyaan memerlukan data perusahaan/history internal → set 'perlu_cari': true.
        - Berikan 'keyword_pencarian' yang efektif.

        KATEGORI 4 - DETEKSI BASA-BASI / UMUM / GLOBAL:
        - Jika pertanyaan bersifat: sapaan, terima kasih, permintaan coding, pertanyaan umum (misal: "apa itu AI?"), atau tidak relevan dengan PT Pindad → set 'is_general': true.

        History: {history_context[-3000:]}
        User Message: "{user_message}"

        Jawab hanya JSON:
        {{
        "is_need_search": true/false,
        "is_update_memory": true/false,
        "extracted_key": "snake_case_label",
        "extracted_value": "isi_lengkap_dan_tegas",
        "perlu_cari": true/false,
        "keyword_pencarian": "keyword_setelah_perbaikan_typo",
        "is_general": true/false
        }}
        """

        try:
            analysis_res = await ask_qwen3_vl(
                analysis_prompt, stream=False, override_model="qwen2.5:7b-instruct"
            )
            # ✅ LOG HASIL MENTAH DARI AI
            print(f"{log_prefix} 🤖 RAW_AI_RESPONSE:\n{analysis_res}\n{'─' * 50}")

            analysis_data = json.loads(
                analysis_res.replace("```json", "").replace("```", "").strip()
            )
        except Exception as e:
            print(f"{log_prefix} ❌ JSON Parse Failed: {e}")
            analysis_data = {
                "is_need_search": False,
                "is_update_memory": False,
                "perlu_cari": True,
                "keyword_pencarian": user_message,
                "is_general": False,
            }

        analysis_duration = time.time() - analysis_start
        print(f"{log_prefix} 🔍 Unified Analysis done in {analysis_duration:.2f}s")

        # --- ✅ JALUR BARU: FALBACK LANGSUNG KE MODEL UNTUK PERTANYAAN UMUM ---
        if analysis_data.get("is_general"):
            print(f"{log_prefix} 💬 GENERAL_QUERY_DETECTED | Skipping RAG/Search")
            gen_start = time.time()
            reply = await ask_qwen3_vl(
                f"User bilang: '{user_message}'. Berikan respon yang ramah dan sesuai konteks percakapan.",
                stream=True,
                override_model=model,
            )
            gen_duration = time.time() - gen_start
            total_duration = time.time() - start_time
            print(
                f"{log_prefix} ✅ GENERAL_MODE_DONE | Gen: {gen_duration:.2f}s | Total: {total_duration:.2f}s"
            )
            return reply, None, False

        # --- JALUR 1: FALLBACK KE SEARCH WEBSITE ---
        if analysis_data.get("is_need_search"):
            print(f"{log_prefix} 🔄 FALLBACK_TO_SEARCH_MODE | Official Info Detected")
            refine_start = time.time()
            refine_prompt = f"History:\n{history_context}\n\nUser: {user_message}\nBuat query search singkat (maksimal 3 kata) untuk mencari informasi di website PT Pindad."
            web_query = await ask_qwen3_vl(
                refine_prompt, stream=False, override_model=model
            )
            refine_duration = time.time() - refine_start

            clean_query = (
                web_query.strip().replace('"', "").replace("'", "")
                if web_query
                else user_message
            )
            print(
                f"{log_prefix} 🔎 Refined Query: '{clean_query}' (took {refine_duration:.2f}s)"
            )

            scrape_start = time.time()
            search_result = await scrape_pindad_website(clean_query)
            scrape_duration = time.time() - scrape_start
            print(f"{log_prefix} 🌐 Scraping done in {scrape_duration:.2f}s")

            search_prompt = f"""Kamu adalah asisten AI resmi PT Pindad. 
    Gunakan data hasil scraping di bawah ini untuk menjawab pertanyaan: "{user_message}"

    DATA DARI WEBSITE (www.pindad.com):
    ---
    {search_result}
    ---

    INSTRUKSI JAWABAN:
    1. Jika pertanyaan bersifat umum (misal: "apa saja senjata Pindad"), buatkan daftar produk yang ditemukan dalam data, kategorikan jika mungkin.
    2. Jika pertanyaan bersifat spesifik, ambil detail teknis dari tabel atau deskripsi yang tersedia.
    3. Selalu sebutkan bahwa informasi ini berdasarkan data terbaru dari situs resmi Pindad.
    4. Jika ada URL di dalam data, sertakan di akhir jawaban sebagai referensi tambahan.
    5. Jika data tidak relevan, sampaikan dengan sopan.
    """
            gen_start = time.time()
            reply = await ask_qwen3_vl(search_prompt, stream=True, override_model=model)
            gen_duration = time.time() - gen_start
            total_duration = time.time() - start_time
            print(
                f"{log_prefix} ✅ NORMAL_TO_SEARCH_DONE | Refine: {refine_duration:.2f}s | Scrape: {scrape_duration:.2f}s | Gen: {gen_duration:.2f}s | Total: {total_duration:.2f}s"
            )
            return reply, None, False

        # --- JALUR 2: SIMPAN MEMORI JIKA ADA KOREKSI ---
        memory_duration = 0
        if analysis_data.get("is_update_memory"):
            mem_start = time.time()
            from ..services.background_tasks import upsert_ai_memory_background

            background_tasks.add_task(
                upsert_ai_memory_background,
                analysis_data.get("extracted_key"),
                analysis_data.get("extracted_value"),
                npp,
            )
            memory_duration = time.time() - mem_start
            print(f"{log_prefix} 🔄 Memory save scheduled in background for NPP: {npp}")

        # --- JALUR 3: RAG INTERNAL ---
        rag_duration = 0
        corpus_context = ""
        if analysis_data.get("perlu_cari"):
            search_query = analysis_data.get("keyword_pencarian", user_message)
            rag_start = time.time()
            universal_refs = await search_universal_knowledge(search_query, npp, role)
            rag_duration = time.time() - rag_start
            print(
                f"{log_prefix} 📚 RAG search done in {rag_duration:.2f}s ({len(universal_refs)} refs)"
            )

            if universal_refs:
                permanent_data = []
                chat_history_data = []
                document_data = []
                for ref in universal_refs:
                    if ref.get("source") == "PERMANENT":
                        permanent_data.append(
                            f"[DATA TERVERIFIKASI PERUSAHAAN]: {ref['primary_content']} ADALAH {ref['secondary_content']}"
                        )
                    elif ref.get("source") == "CHAT":
                        chat_history_data.append(
                            f"[MEMORI CHAT]: User pernah tanya '{ref['primary_content']}' -> AI jawab '{ref['secondary_content']}'"
                        )
                    else:
                        document_data.append(
                            f"[DOKUMEN {ref['secondary_content']}]: {ref['primary_content']}"
                        )
                formatted_refs = permanent_data + document_data + chat_history_data
                corpus_context = (
                    "### REFERENSI DATA INTERNAL PERUSAHAAN (PRIORITAS TINGGI):\nGunakan data di bawah ini sebagai dasar jawaban utama. Data [DATA TERVERIFIKASI] adalah kebenaran mutlak.\n"
                    + "\n---\n".join(formatted_refs)
                    + "\n\n"
                )
            else:
                corpus_context = "INFO: Tidak ada referensi internal/memori permanen yang ditemukan untuk topik ini.\n"

        # --- GENERATE JAWABAN AKHIR ---
        base_instruction = """
                INSTRUKSI SANGAT KETAT:
                1. Kamu adalah CAKRA, AI internal PT Pindad. 
                2. Gunakan HANYA informasi dari 'REFERENSI DATA INTERNAL' untuk menjawab pertanyaan teknis/operasional (alamat, kontak, dll).
                3. JANGAN PERNAH gunakan pengetahuan umummu jika ada datanya di referensi.
                4. Jika data di referensi berbeda dengan apa yang kamu tahu, WAJIB ikuti referensi dari data internal.
                5. Jika data tidak ada di referensi, baru kamu boleh pakai pengetahuan umummu (Fallback).
                6. Jawab dengan tegas dan detail sesuai isi referensi.
                """

        if active_file:
            context_text = active_file.get("text", "")[:7000]
            file_name = active_file.get("name", "Dokumen Terlampir")
            prompt = f"""Kamu adalah CAKRA (Cerdas Terpercaya), AI PT Pindad.
    {base_instruction}
    DOKUMEN YANG SEDANG DIBUKA (PRIORITAS UTAMA):
    Nama File: {file_name}
    Konten: {context_text}

    {corpus_context}

    HISTORY CHAT TERAKHIR:
    {history_context}

    User Message: "{user_message}"
    """
        else:
            prompt = f"""Kamu adalah CAKRA, AI PT Pindad.
    {base_instruction}
    {corpus_context}

    HISTORY CHAT TERAKHIR:
    {history_context}

    User: {user_message}

    Tugas: Jawab dengan jujur berdasarkan referensi data internal yang tersedia.
    """

        gen_start = time.time()
        reply = await ask_qwen3_vl(prompt, stream=True, override_model=model)
        gen_duration = time.time() - gen_start

        if reply is None:
            reply = "Maaf bro, sistem sedang sibuk. Coba ulangi lagi ya."

        total_duration = time.time() - start_time
        print(
            f"{log_prefix} ✅ NORMAL_MODE_DONE | Analysis: {analysis_duration:.2f}s | Memory: {memory_duration:.2f}s | RAG: {rag_duration:.2f}s | Gen: {gen_duration:.2f}s | Total: {total_duration:.2f}s"
        )
        return reply, None, False

    # ✅ JAMIN SELALU ADA RETURN (antisipasi mode tidak dikenali)
    total_duration = time.time() - start_time
    print(f"{log_prefix} ❌ UNKNOWN_MODE | Total: {total_duration:.2f}s")
    return "Maaf, terjadi kesalahan dalam pemrosesan.", None, False
