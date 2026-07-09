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

    async def get_employee_long_term_memory(self, npp: str) -> str:
        """
        Menarik ringkasan memori masa lalu terkait pegawai berdasarkan NPP.
        Hasilnya bakal disuntikkan ke System Prompt agar AI ingat preferensi user.
        """
        if npp == "GUEST" or not npp:
            return ""

        async with get_db() as conn:
            try:
                # Ambil mem_key dan mem_value yang asli dari fisik tabel ai_memory
                query = """
                    SELECT mem_key, mem_value FROM ai_memory 
                    WHERE npp = $1 
                    ORDER BY (CASE WHEN mem_key = 'Karakter Komunikasi' THEN 1 ELSE 2 END) ASC, created_at DESC 
                    LIMIT 6;
                """
                rows = await conn.fetch(query, npp)
                if not rows:
                    return ""
                
                # Gabungkan key dan value menjadi satu string narasi ringkas
                summaries = [f"{row['mem_key']}: {row['mem_value']}" for row in rows]
                memory_context = "\n- ".join(summaries)
                logger.debug(f"[MEMORY_SERVICE] Loaded {len(rows)} memories for NPP: {npp}")
                return f"\n[INGATAN MASA LALU PEGAWAI]:\n- {memory_context}"
            except Exception as e:
                logger.error(f"[MEMORY_RETRIEVAL_ERROR] Failed to retrieve employee memory: {str(e)}")
                return ""

    async def update_communication_style_memory(self, npp: str, pronoun: str) -> None:
        """
        Background task: Update memori gaya bahasa user secara real-time ke database 
        berdasarkan deteksi pronoun dari Router AI.
        """
        if npp == "GUEST" or not npp or not pronoun:
            return
            
        mem_value = ""
        if pronoun == "informal_gue_lo":
            mem_value = "User terbiasa dengan gaya bahasa santai/slang (cuy, bro, lo, gue, kang, boss). Balas dengan gaya setara yang asik, ramah, dan boleh gunakan humor natural."
        elif pronoun == "formal_saya_anda":
            mem_value = "User lebih suka gaya bahasa baku, formal, dan profesional. Jangan gunakan slang."
        else:
            # Jika netral, tidak perlu update atau over-write
            return
            
        async with get_db() as conn:
            try:
                query_insert_memory = """
                    INSERT INTO ai_memory (npp, mem_key, mem_value, category, created_at, updated_at)
                    VALUES ($1, 'Karakter Komunikasi', $2, 'personal', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (mem_key, npp) 
                    DO UPDATE SET mem_value = EXCLUDED.mem_value, updated_at = CURRENT_TIMESTAMP;
                """
                await conn.execute(query_insert_memory, npp, mem_value)
                logger.debug(f"[MEMORY_SERVICE] Real-time tone memory updated for NPP {npp}: {pronoun}")
            except Exception as write_err:
                logger.error(f"[MEMORY_SERVICE_ERROR] Failed to write tone memory: {str(write_err)}")

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
                    "options": {"temperature": 0.2}
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
