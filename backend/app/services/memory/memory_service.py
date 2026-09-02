import logging
import json
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_MEMORY_SERVICE")

class MemoryService:
    """
    Sektor Pengelola Memori Jangka Panjang CAKRA AI.
    Mengurus tabel ai_memory dan mengonsolidasikan obrolan pegawai PT Pindad.
    """
    
    def __init__(self):
        logger.info("[MEMORY_SERVICE_INIT] Memory management service initialized.")

    async def get_employee_long_term_memory(self, npp: str, current_session_uuid: Optional[str] = None) -> str:
        """
        Menarik ringkasan memori masa lalu terkait pegawai berdasarkan NPP.
        Hasilnya bakal disuntikkan ke System Prompt agar AI ingat preferensi user dan topik obrolan di sesi lain.
        """
        if npp == "GUEST" or not npp:
            return ""

        async with get_db() as conn:
            try:
                # 1. Ambil memori terstruktur permanen dari ai_memory
                query = """
                    SELECT mem_key, mem_value FROM ai_memory 
                    WHERE npp = $1 
                    ORDER BY (CASE WHEN mem_key = 'Karakter Komunikasi' THEN 1 ELSE 2 END) ASC, created_at DESC 
                    LIMIT 6;
                """
                rows = await conn.fetch(query, npp)
                summaries = [f"{row['mem_key']}: {row['mem_value']}" for row in rows] if rows else []

                # 2. 🔥 REAL-TIME CROSS-SESSION SYNC: Ambil topik dari 4 sesi obrolan terbaru milik user (selain sesi aktif saat ini)
                recent_sessions = await conn.fetch("""
                    SELECT s.session_uuid, s.judul, s.memory_summary, s.started_at,
                           (SELECT m.message_text 
                            FROM chat_messages m 
                            WHERE m.session_id = s.id AND m.role = 'user' 
                            ORDER BY m.timestamp DESC LIMIT 1) as last_user_query
                    FROM chat_sessions s
                    WHERE s.npp = $1 AND s.is_deleted = false 
                      AND ($2::text IS NULL OR s.session_uuid::text != $2::text)
                      AND s.judul IS NOT NULL AND s.judul != 'Obrolan Baru'
                    ORDER BY s.started_at DESC
                    LIMIT 4;
                """, npp, str(current_session_uuid) if current_session_uuid else None)
                
                if recent_sessions:
                    session_topics = []
                    for s in recent_sessions:
                        title = s['judul']
                        summary = s['memory_summary']
                        last_q = s['last_user_query']
                        if summary and len(summary.strip()) > 5:
                            session_topics.append(f"Topik '{title}': {summary.strip()}")
                        elif last_q and len(last_q.strip()) > 3:
                            clean_q = last_q.strip()[:80] + "..." if len(last_q.strip()) > 80 else last_q.strip()
                            session_topics.append(f"Topik '{title}' (Membahas: \"{clean_q}\")")
                        elif title:
                            session_topics.append(f"Membahas '{title}'")
                    
                    if session_topics:
                        summaries.append("Riwayat Pembahasan di Sesi Lain:\n  • " + "\n  • ".join(session_topics[:4]))

                if not summaries:
                    return ""

                memory_context = "\n- ".join(summaries)
                logger.debug(f"[MEMORY_SERVICE] Loaded cross-session memories for NPP: {npp}")
                return f"\n[INGATAN MASA LALU PEGAWAI & RIWAYAT SESI LAIN]:\n- {memory_context}"
            except Exception as e:
                logger.error(f"[MEMORY_RETRIEVAL_ERROR] Failed to retrieve employee memory: {str(e)}")
                return ""

    async def get_employee_communication_preference(self, npp: str) -> str:
        """
        Membaca preferensi kata ganti & gaya komunikasi default pegawai dari database lintas sesi (cross-session).
        Jika user memiliki rekam jejak sering memakai bahasa santai (>= 5x pesan slang di DB), default-nya informal_gue_lo.
        """
        if not npp or npp == "GUEST":
            return "formal_saya_anda"

        async with get_db() as conn:
            try:
                # 0. PRIORITAS UTAMA: Baca pengaturan gaya bahasa akun dari user_settings
                settings_row = await conn.fetchrow("SELECT settings FROM user_settings WHERE npp = $1", npp)
                if settings_row and settings_row["settings"]:
                    s_data = json.loads(settings_row["settings"]) if isinstance(settings_row["settings"], str) else settings_row["settings"]
                    style = s_data.get("communication_style")
                    if style in ["informal_gue_lo", "formal_saya_anda", "familiar_aku_kamu"]:
                        return style

                # 1. Cek dari memori yang sudah terkunci di ai_memory
                row = await conn.fetchrow(
                    "SELECT mem_value FROM ai_memory WHERE npp = $1 AND mem_key = 'Karakter Komunikasi'",
                    npp
                )
                if row and any(w in row["mem_value"].lower() for w in ["santai", "slang", "gue", "lo", "cuy", "bro"]):
                    return "informal_gue_lo"

                # 2. Cek akumulasi riwayat pesan pengguna di seluruh sesi (cross-session)
                count_row = await conn.fetchrow("""
                    SELECT COUNT(*) as slang_count
                    FROM chat_messages m
                    JOIN chat_sessions s ON m.session_id = s.id
                    WHERE s.npp = $1 AND m.role = 'user'
                      AND m.message_text ~* '\\b(gue|gw|gua|lo|lu|elu|cuy|bro|boss|bos)\\b';
                """, npp)
                
                slang_total = count_row["slang_count"] if count_row else 0
                if slang_total >= 5:
                    # Kunci profil di ai_memory agar tidak perlu re-count terus menerus
                    mem_value = "User terbiasa dan konsisten menggunakan gaya bahasa santai/slang (lo, gue, bro, cuy, boss). Balas dengan gaya santai akrab yang asik dan bersahabat."
                    await conn.execute("""
                        INSERT INTO ai_memory (npp, mem_key, mem_value, category, created_at, updated_at)
                        VALUES ($1, 'Karakter Komunikasi', $2, 'personal', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (mem_key, npp) DO UPDATE SET mem_value = EXCLUDED.mem_value, updated_at = CURRENT_TIMESTAMP;
                    """, npp, mem_value)
                    return "informal_gue_lo"

                return "formal_saya_anda"
            except Exception as e:
                logger.error(f"[MEMORY_PREFERENCE_ERROR] Failed to fetch communication preference: {e}")
                return "formal_saya_anda"

    async def update_communication_style_memory(self, npp: str, user_message: str) -> None:
        """
        Background task: Update memori gaya bahasa user secara adaptif berbasis pesan yang masuk.
        Pesan netral (tanpa slang & tanpa formal eksplisit) TIDAK AKAN mereset profil santai user.
        """
        if npp == "GUEST" or not npp or not user_message:
            return
            
        import re
        msg_lower = user_message.lower()
        has_slang = bool(re.search(r'\b(gue|gw|gua|lo|lu|elu|cuy|bro|boss|bos)\b', msg_lower))
        has_strict_formal = bool(re.search(r'\b(saya|anda|bapak|ibu|mohon|terima kasih|hormat)\b', msg_lower))

        if not has_slang and not has_strict_formal:
            # Pesan netral (misal "buatkan data dummy", "carikan info") -> Jangan ubah profil yang sudah ada
            return

        async with get_db() as conn:
            try:
                row_count = await conn.fetchrow(
                    "SELECT mem_value FROM ai_memory WHERE npp = $1 AND mem_key = 'slang_frequency_count'",
                    npp
                )
                current_slang_count = int(row_count["mem_value"]) if row_count and row_count["mem_value"].isdigit() else 0

                if has_slang:
                    current_slang_count += 1
                    await conn.execute("""
                        INSERT INTO ai_memory (npp, mem_key, mem_value, category, created_at, updated_at)
                        VALUES ($1, 'slang_frequency_count', $2, 'personal', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (mem_key, npp) DO UPDATE SET mem_value = EXCLUDED.mem_value, updated_at = CURRENT_TIMESTAMP;
                    """, npp, str(current_slang_count))

                    if current_slang_count >= 5:
                        mem_value = "User terbiasa dan konsisten menggunakan gaya bahasa santai/slang (lo, gue, bro, cuy, boss). Balas dengan gaya santai akrab yang asik dan bersahabat."
                        await conn.execute("""
                            INSERT INTO ai_memory (npp, mem_key, mem_value, category, created_at, updated_at)
                            VALUES ($1, 'Karakter Komunikasi', $2, 'personal', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT (mem_key, npp) DO UPDATE SET mem_value = EXCLUDED.mem_value, updated_at = CURRENT_TIMESTAMP;
                        """, npp, mem_value)
                        logger.info(f"[MEMORY_SERVICE] User {npp} has reached threshold ({current_slang_count}x). Slang personality locked.")

            except Exception as write_err:
                logger.error(f"[MEMORY_SERVICE_ERROR] Failed to update tone memory: {str(write_err)}")

    async def consolidate_nightly_memory(self) -> Dict[str, Any]:
        """
        Job Konsolidasi Malam: Merangkum chat 24 jam terakhir dari setiap pegawai
        menjadi entitas memori padat via Qwen 2.5, lalu disimpan ke tabel ai_memory.
        """
        logger.info("[MEMORY_SERVICE] Starting nightly memory consolidation cycle...")
        
        # Cari batas waktu chat 24 jam ke belakang
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        chats_per_employee: Dict[str, List[str]] = {}
        
        # PHASE 1: Ambil data chat mentah
        async with get_db() as conn:
            try:
                query_get_chats = """
                    SELECT s.npp, m.message_text 
                    FROM chat_messages m
                    JOIN chat_sessions s ON m.session_id = s.id
                    WHERE m.role = 'user' AND m.timestamp >= $1
                    ORDER BY s.npp, m.timestamp ASC;
                """
                rows = await conn.fetch(query_get_chats, one_day_ago)
                if not rows:
                    logger.debug("[MEMORY_SERVICE] No new chats in 24h - cycle skipped")
                    return {"status": "skipped", "message": "No new chats to consolidate."}

                # Grouping teks obrolan per NPP
                for row in rows:
                    npp = row['npp']
                    if npp == "GUEST" or not npp: 
                        continue
                    if npp not in chats_per_employee:
                        chats_per_employee[npp] = []
                    chats_per_employee[npp].append(row['message_text'])
            except Exception as read_err:
                logger.error(f"[MEMORY_CONSOLIDATION_READ_ERROR] Failed to read daily chat logs: {str(read_err)}")
                return {"status": "failed", "error": str(read_err)}

        if not chats_per_employee:
            return {"status": "skipped", "message": "No official employee chats to process."}

        # PHASE 2: Peras obrolan per pegawai via LLM Qwen 2.5
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        memories_to_save: List[Dict[str, str]] = []
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for npp, messages in chats_per_employee.items():
                full_chat_log = "\n".join([f"User: {msg}" for msg in messages])
                
                # Atur prompt agar Qwen memuntahkan subjek singkat (key) dan ringkasan ringkas (value)
                system_prompt = (
                    "Anda adalah modul ekstraksi memori jangka panjang CAKRA AI.\n"
                    "Tugas Anda adalah merangkum log obrolan pegawai menjadi format JSON murni dengan dua field:\n"
                    "1. 'key': Topik/Proyek utama yang dibahas (singkat, maks 3 kata, contoh: 'Optimasi Database', 'Project Web Material').\n"
                    "2. 'value': Ringkasan fakta krusial dalam 1-2 kalimat menggunakan sudut pandang ketiga (contoh: 'Pegawai sedang melakukan debugging fungsional pada form registrasi material menggunakan CodeIgniter 4.').\n\n"
                    "Output WAJIB berupa JSON murni tanpa markdown!"
                )

                payload = {
                    "model": settings.MODEL_ROUTER,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Ekstrak memori dari log obrolan ini:\n{full_chat_log}"}
                    ],
                    "stream": False,
                    "keep_alive": -1,
                    "options": {
                        "temperature": 0.2,
                        "num_ctx": 4096,
                        "num_batch": 512,
                    }
                }

                try:
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        content_text = response.json().get("message", {}).get("content", "").strip()
                        # Bersihkan tag markdown if any
                        if content_text.startswith("```json"):
                            content_text = content_text.split("```json")[1].split("```")[0].strip()
                        
                        parsed_json = json.loads(content_text)
                        mem_key = parsed_json.get("key", "Aktivitas Umum")
                        mem_value = parsed_json.get("value")
                        
                        if mem_value:
                            memories_to_save.append({
                                "npp": npp, 
                                "mem_key": mem_key, 
                                "mem_value": mem_value
                            })
                except Exception as llm_err:
                    logger.error(f"[MEMORY_CONSOLIDATION_LLM_WARNING] Failed LLM summary for NPP {npp}: {str(llm_err)}")

        # PHASE 3: Buka kembali DB instant, eksekusi penyimpanan massal secara atomik
        processed_count = 0
        if memories_to_save:
            async with get_db() as conn:
                try:
                    async with conn.transaction():
                        query_insert_memory = """
                            INSERT INTO ai_memory (npp, mem_key, mem_value, category, created_at, updated_at)
                            VALUES ($1, $2, $3, 'personal', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT (mem_key, npp) 
                            DO UPDATE SET mem_value = EXCLUDED.mem_value, updated_at = CURRENT_TIMESTAMP;
                        """
                        for mem in memories_to_save:
                            await conn.execute(query_insert_memory, mem["npp"], mem["mem_key"], mem["mem_value"])
                            logger.info(f"[MEMORY_SERVICE] Consolidated memory for NPP {mem['npp']}: {mem['mem_key']}")
                            processed_count += 1
                except Exception as write_err:
                    logger.error(f"[MEMORY_CONSOLIDATION_WRITE_ERROR] Failed to write consolidated memory: {str(write_err)}")
                    return {"status": "failed", "error": str(write_err)}

        return {"status": "success", "processed_employees": processed_count}

memory_service = MemoryService()
