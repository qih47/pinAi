import aiohttp
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from ..config import settings
from ..database import get_db, embedding_to_pgvector_str
from .embeddings import get_embedding, EMBEDDING_MODEL
from .web_scraping import scrape_pindad_website


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
    """Mengambil history percakapan terakhir"""
    history = []
    try:
        async with get_db() as conn:
            rows = await conn.fetch(
                """
                SELECT d.user_text, d.assistant_text 
                FROM ai_dialogue_corpus d
                JOIN chat_sessions s ON d.session_id = s.id
                WHERE s.session_uuid = $1
                ORDER BY d.created_at DESC, d.id DESC 
                LIMIT $2
            """,
                session_uuid,
                limit,
            )

            for row in reversed(rows):
                history.append({"role": "user", "content": row["user_text"]})
                history.append({"role": "assistant", "content": row["assistant_text"]})

            return history
    except Exception as e:
        logging.error(f"❌ Error fetch history: {e}")
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


async def upsert_ai_memory(mem_key, mem_value, npp, category="public"):
    """Upsert data ke AI memory"""
    print(f"[DEBUG] 🧠 Memproses memori untuk NPP {npp}: {mem_key}")

    content_to_embed = f"Informasi {category} untuk {mem_key}: {mem_value}"

    try:
        embedding = get_embedding(content_to_embed)
        async with get_db() as conn:
            await conn.execute(
                """
                    INSERT INTO ai_memory (mem_key, mem_value, npp, category, embedding, updated_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (mem_key, npp) 
                    DO UPDATE SET 
                        mem_value = EXCLUDED.mem_value,
                        embedding = EXCLUDED.embedding,
                        category = EXCLUDED.category,
                        updated_at = NOW();
                """,
                mem_key,
                mem_value,
                npp,
                category,
                embedding,
            )

            print(f"✅ [MEMORY] Tersimpan untuk NPP {npp}")
            return True
    except Exception as e:
        print(f"❌ [ERROR] Gagal simpan memori: {str(e)}")
        return False


async def search_universal_knowledge(query, npp, role, limit=4):
    """Universal search across chat, documents, and memory"""
    logging.info(f"🧠 [Universal Search] NPP: {npp} | Role: {role} | Query: '{query}'")
    try:
        query_embedding = EMBEDDING_MODEL.encode([query], normalize_embeddings=True)[
            0
        ].tolist()
        query_vector_str = embedding_to_pgvector_str(query_embedding)

        async with get_db() as conn:
            is_trainer = (role.upper() == "TRAINER") if role else False

            results = await conn.fetch(
                """
                WITH combined_knowledge AS (
                    -- Sumber A: History Chat
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
                        $2 = TRUE OR 
                        cs.npp = $3 OR 
                        cs.npp IS NULL OR cs.npp = '' OR 
                        u.role = 'TRAINER'
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
                        adc_chunks.npp IS NULL OR adc_chunks.npp = '' OR 
                        u.role = 'TRAINER'
                    )

                    UNION ALL

                    -- Sumber C: MEMORI PERMANEN (AI MEMORY)
                    SELECT 
                        'PERMANENT' as source,
                        mem_key as primary_content,
                        mem_value as secondary_content,
                        (embedding <=> $1::vector) as distance,
                        npp as owner_npp
                    FROM ai_memory
                    WHERE (
                        category = 'public' OR
                        npp = $3 OR
                        $2 = TRUE
                    )
                )
                SELECT * FROM combined_knowledge
                WHERE (1 - distance) >= 0.55
                ORDER BY 
                    (CASE WHEN source = 'PERMANENT' THEN 0 ELSE 1 END), 
                    distance ASC
                LIMIT $4
            """,
                query_vector_str,
                is_trainer,
                npp,
                limit,
            )

            return [dict(row) for row in results]

    except Exception as e:
        logging.error(f"Error in universal search: {e}")
        return []


async def generate_judul_ai(message):
    """Generate judul untuk chat session"""
    try:
        prompt = (
            f"Buat judul singkat 3-6 kata untuk pesan ini: '{message}'\n"
            "Judul harus mewakili topik utama. Hanya kembalikan judulnya saja."
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.ollama_generate_url,
                json={
                    "model": settings.primary_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("response", "").strip() or message[:30] + "..."
                return message[:30] + "..."

    except Exception as e:
        logging.error(f"Gagal generate judul: {e}")
        return message[:30] + "..."


async def smart_chat_with_context(
    user_message, active_file, mode, model, session_uuid, npp, role, attachments
):
    """Main smart chat function dengan logika sama persis"""
    # Load history dari DB
    history_context = ""
    if session_uuid:
        history_messages = await get_chat_history_from_db(session_uuid, limit=3)
        if history_messages:
            history_context = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in history_messages]
            )

    # 1. JALUR DOKUMEN AKTIF (BYPASS PDF/OCR) - PRIORITAS UTAMA
    if active_file and active_file.get("text"):
        print(f"[DEBUG] BYPASS: Menggunakan Teks PaddleOCR untuk PDF")
        prompt_ocr = f"""Tugas: {user_message if user_message else "Rangkum dokumen ini"}

Gunakan teks hasil scan OCR di bawah ini untuk menjawab pertanyaan/tugas tersebut.
---
[ISI DOKUMEN]:
{active_file["text"][:15000]} 
---
[HISTORY PERCAKAPAN]:
{history_context[-3000:]}

INSTRUKSI KHUSUS:
- Analisis teks di atas dan jawab pertanyaan user dengan detail.
- Jika user minta rangkuman, buatkan poin-poin pentingnya.
- Jika jawaban tidak ada di dokumen, beri tahu user secara jujur.
"""
        reply = await ask_qwen3_vl(prompt_ocr, stream=True, override_model=model)
        return reply, None, False

    # 2. MULTIMODAL LAYER (Handle Images)
    has_images = attachments and any(
        a and "image" in a.get("type", "").lower() for a in attachments
    )
    if has_images:
        try:
            img_obj = next(
                a for a in attachments if "image" in a.get("type", "").lower()
            )
            img_data = img_obj.get("data", "")
            raw_base64 = img_data.split(",")[1] if "," in img_data else img_data

            vlm_intent_prompt = f"""Tugas: Analisis apakah pertanyaan user tentang gambar ini memerlukan referensi data internal perusahaan atau hanya ekstraksi gambar biasa.
            User Message: {user_message}
            Jawab dengan format JSON: {{"use_rag": true, "focus_instruction": "instruksi"}}"""

            intent_res = await ask_qwen3_vl(
                vlm_intent_prompt, stream=False, override_model="qwen2.5:14b-instruct"
            )

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

            vlm_final_prompt = (
                f"{intent_data.get('focus_instruction')}\n\nUser: {user_message}"
            )
            reply = await ask_qwen3_vl(
                prompt=vlm_final_prompt,
                images=[raw_base64],
                stream=True,
                override_model=settings.vision_model,
            )
            return reply, None, False
        except Exception as e:
            print(f"[ERROR] Multimodal Layer Error: {e}")

    # MODE SEARCH (Pindad Website Scraper)
    if mode == settings.mode_search:
        refine_prompt = f"History:\n{history_context}\n\nUser: {user_message}\nBuat query search singkat untuk website."
        web_query = await ask_qwen3_vl(
            refine_prompt, stream=False, override_model=model
        )
        search_result = await scrape_pindad_website(
            web_query if web_query else user_message
        )

        search_prompt = f"""Kamu adalah asisten AI untuk PT Pindad. Berdasarkan informasi dari www.pindad.com:

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
        reply = await ask_qwen3_vl(search_prompt, stream=True, override_model=model)
        return reply, None, False

    # MODE DOCUMENT (RAG dengan Analisa & Verifikasi)
    elif mode == settings.mode_document:
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

        search_result = await search_documents(search_query)
        relevant_chunks = [
            c
            for c in search_result["chunks"]
            if c["similarity"] >= settings.similarity_threshold
        ]

        is_truly_relevant = False
        if relevant_chunks:
            eval_prompt = f"""User bertanya tentang: "{user_message}"
Hasil pencarian database: "{relevant_chunks[0]["content"][:500]}..."

Tugas: Apakah hasil pencarian tersebut BENAR-BENAR relevan dan menjawab pertanyaan user?
Contoh: Jika user tanya 'efisiensi' tapi hasilnya 'mesin painting', maka JAWAB: TIDAK.
Jawaban: YA atau TIDAK"""

            eval_res = await ask_qwen3_vl(
                eval_prompt, stream=False, override_model=model
            )
            if "YA" in eval_res.upper():
                is_truly_relevant = True

        if not is_truly_relevant:
            print(
                f"⚠️  [VERIFIKASI 2] Hasil Tahap 1 tidak relevan. Melakukan Re-Analisa..."
            )
            re_analysis_prompt = f"""Pertanyaan user: "{user_message}"
Hasil pencarian sebelumnya tidak relevan karena tercampur konteks lama.
Tugas: Buat kata kunci pencarian baru yang murni hanya fokus pada pertanyaan user tersebut (abaikan topik sebelumnya).

Jawaban format: ANALISIS_ULANG | KATA_KUNCI_MURNI
"""
            re_analysis_res = await ask_qwen3_vl(
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

            search_result = await search_documents(search_query)
            relevant_chunks = [
                c
                for c in search_result["chunks"]
                if c["similarity"] >= settings.similarity_threshold
            ]

        if relevant_chunks:
            top_chunk = relevant_chunks[0]
            print(
                f"✅ HIT FINAL: {top_chunk.get('judul')} ({top_chunk.get('similarity'):.4f})"
            )
        else:
            print(f"❌ [LOG] Tetap tidak ada data relevan di database.")
        print("─" * 43 + "\n")

        # Deteksi Greeting
        user_message_lower = user_message.lower()
        greeting_keywords = ["hai", "halo", "selamat pagi", "thanks", "terima kasih"]
        if (
            any(kw in user_message_lower for kw in greeting_keywords)
            and not relevant_chunks
        ):
            reply = await ask_qwen3_vl(
                f"Sapa user dengan ramah: {user_message}", stream=True
            )
            return reply, None, False

        if not relevant_chunks:
            prompt = f"Beritahu user bahwa dokumen terkait '{user_message}' tidak ditemukan di database internal."
            reply = await ask_qwen3_vl(prompt, stream=True, override_model=model)
            return reply, None, False

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
        reply = await ask_qwen3_vl(doc_prompt, stream=True, override_model=model)

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

    # MODE NORMAL
    elif mode == settings.mode_normal:
        print(f"\n[DEBUG] === 🚀 MEMULAI ANALISIS PESAN (MODE NORMAL) ===")
        print(f"[DEBUG] User Message: {user_message}")

        analysis_prompt = f"""
                    Tugas: 
                    1. Analisis apakah pesan user memerlukan data perusahaan/history.
                    2. DETEKSI KOREKSI: Jika user mengoreksi data (contoh: "yang bener adalah...", "web pindad itu .com"), set 'is_update_memory': true.
                    3. BUAT NARASI TEGAS: Jika 'is_update_memory' true, buat 'extracted_value' berupa kalimat deklaratif yang sangat jelas untuk menindih info lama.
                    
                    History: {history_context[-3000:]}
                    User Message: "{user_message}"

                    Jawab hanya JSON:
                    {{
                    "perlu_cari": true/false, 
                    "is_update_memory": true/false,
                    "keyword_pencarian": "keyword baku",
                    "extracted_key": "snake_case_label",
                    "extracted_value": "isi_informasi_lengkap_dan_tegas"
                    }}
                """

        print(f"[DEBUG] --- [LOG LAYER 1: ANALISIS NIAT] ---")
        analysis_res = await ask_qwen3_vl(
            analysis_prompt, stream=False, override_model="qwen2.5:14b-instruct"
        )
        print(f"[DEBUG] Raw AI Result: {analysis_res.strip()}")

        try:
            clean_json = analysis_res.replace("```json", "").replace("```", "").strip()
            analysis_data = json.loads(clean_json)
            print(
                f"[DEBUG] Parsing Sukses: Perlu Cari={analysis_data.get('perlu_cari')}, Update Memory={analysis_data.get('is_update_memory')}"
            )
        except Exception as e:
            print(f"[DEBUG] ❌ Parsing Gagal: {str(e)}")
            analysis_data = {
                "perlu_cari": True,
                "keyword_pencarian": user_message,
                "is_update_memory": False,
            }

        if analysis_data.get("is_update_memory"):
            print(
                f"[DEBUG] 💾 KOREKSI TERDETEKSI! Key: {analysis_data.get('extracted_key')} | Val: {analysis_data.get('extracted_value')}"
            )
            success = await upsert_ai_memory(
                analysis_data.get("extracted_key"),
                analysis_data.get("extracted_value"),
                npp,
            )
            if success:
                print(
                    f"[DEBUG] ✅ Berhasil menyimpan ke Permanent Memory (Hard Disk) untuk NPP: {npp}"
                )
            else:
                print(f"[DEBUG] ❌ Gagal menyimpan ke Permanent Memory")

        corpus_context = ""
        if analysis_data.get("perlu_cari"):
            search_query = analysis_data.get("keyword_pencarian", user_message)
            print(f"[DEBUG] --- [LOG LAYER 2: RAG SEARCH] ---")
            print(f"[DEBUG] Searching for: '{search_query}'")

            universal_refs = await search_universal_knowledge(search_query, npp, role)

            if universal_refs:
                print(
                    f"[DEBUG] ✅ Berhasil menarik {len(universal_refs)} data referensi."
                )
                formatted_refs = []
                for ref in universal_refs:
                    source_type = ref.get("source")
                    if source_type == "PERMANENT":
                        print(
                            f"[DEBUG] -> [FOUND IN HARD DISK]: {ref['primary_content']}"
                        )
                        formatted_refs.append(
                            f"[DATA TERVERIFIKASI]: {ref['primary_content']} adalah {ref['secondary_content']}"
                        )
                    elif source_type == "CHAT":
                        print(
                            f"[DEBUG] -> [FOUND IN CHAT HISTORY]: {ref['primary_content'][:50]}..."
                        )
                        formatted_refs.append(
                            f"[MEMORI CHAT]: User tanya '{ref['primary_content']}' -> AI jawab '{ref['secondary_content']}'"
                        )
                    else:
                        print(
                            f"[DEBUG] -> [FOUND IN DOCUMENT]: {ref['secondary_content']}"
                        )
                        formatted_refs.append(
                            f"[DOKUMEN {ref['secondary_content']}]: {ref['primary_content']}"
                        )

                corpus_context = (
                    "REFERENSI DATA INTERNAL PERUSAHAAN (UTAMAKAN DATA TERVERIFIKASI):\n"
                    + "\n---\n".join(formatted_refs)
                    + "\n\n"
                )
            else:
                print(f"[DEBUG] ⚠️ Tidak ada referensi relevan ditemukan.")
                corpus_context = (
                    "INFO: Tidak ada referensi dokumen lama yang relevan.\n"
                )
        else:
            print(f"[DEBUG] ⏭️ Skip RAG Search: AI merasa tidak butuh data eksternal.")

        print(f"[DEBUG] --- [LOG LAYER 3: GENERATING FINAL RESPONSE] ---")

        base_instruction = """
        INSTRUKSI KHUSUS:
        1. Jika ada perbedaan antara 'REFERENSI DATA INTERNAL' dengan pengetahuan umummu, gunakan DATA INTERNAL.
        2. Jangan memberikan informasi domain atau data yang sudah dinyatakan TIDAK BERLAKU dalam referensi.
        """

        if active_file:
            print(f"[DEBUG] Priority: Active File ({active_file.get('name')})")
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
            print(f"[DEBUG] Priority: Universal RAG")
            prompt = f"""Kamu adalah CAKRA, AI PT Pindad.
{base_instruction}
{corpus_context}

HISTORY CHAT TERAKHIR:
{history_context}

User: {user_message}

Tugas: Jawab dengan jujur berdasarkan referensi data internal yang tersedia.
"""

        reply = await ask_qwen3_vl(prompt, stream=True, override_model=model)

        if reply is None:
            print(f"[DEBUG] ❌ Final Response is None")
            reply = "Maaf bro, sistem sedang sibuk. Coba ulangi lagi ya."

        print(f"[DEBUG] === ✅ ANALISIS SELESAI ===\n")
        return reply, None, False

    return "Maaf, terjadi kesalahan dalam pemrosesan.", None, False
