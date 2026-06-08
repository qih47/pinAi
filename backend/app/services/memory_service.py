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
        print("🧠 [MEMORY SERVICE] Sektor pengelola ingatan taktis aktif, bolo!")

    async def get_employee_long_term_memory(self, npp: str) -> str:
        """
        Menarik ringkasan memori masa lalu terkait pegawai berdasarkan NPP.
        Hasilnya bakal disuntikkan ke System Prompt agar AI ingat preferensi user.
        """
        if npp == "GUEST" or not npp:
            return ""

        async with get_db() as conn:
            try:
                # Ambil 5 memori teratas yang paling relevan dan terbaru
                query = """
                    SELECT memory_summary FROM ai_memory 
                    WHERE npp = $1 
                    ORDER BY created_at DESC LIMIT 5;
                """
                rows = await conn.fetch(query, npp)
                if not rows:
                    return ""
                
                # Gabungkan ringkasan memori menjadi satu string konteks
                summaries = [row['memory_summary'] for row in rows]
                memory_context = "\n- ".join(summaries)
                print(f"🧠 [MEMORY RETRIEVAL] Sukses memuat {len(rows)} ingatan masa lalu untuk NPP: {npp}")
                return f"\n[INGATAN MASA LALU PEGAWAI]:\n- {memory_context}"
            except Exception as e:
                logger.error(f"💥 [MEMORY] Gagal menarik memori pegawai: {str(e)}")
                return ""

    async def consolidate_nightly_memory(self) -> Dict[str, Any]:
        """
        Job Konsolidasi Malam: Merangkum chat 24 jam terakhir dari setiap pegawai
        menjadi entitas memori padat via Qwen 2.5, lalu disimpan ke tabel ai_memory.
        """
        print("🕒 [MEMORY WORKER] Memulai siklus konsolidasi memori malam hari...")
        
        # Cari batas waktu chat 24 jam ke belakang
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        chats_per_employee: Dict[str, List[str]] = {}
        
        # PHASE 1: Ambil data chat mentah secepat mungkin, lalu langsung tutup koneksi DB awal
        async with get_db() as conn:
            try:
                query_get_chats = """
                    SELECT s.npp, m.message_text 
                    FROM chat_messages m
                    JOIN chat_sessions s ON m.session_id = s.session_uuid
                    WHERE m.role = 'user' AND m.created_at >= $1
                    ORDER BY s.npp, m.created_at ASC;
                """
                rows = await conn.fetch(query_get_chats, one_day_ago)
                if not rows:
                    print("💤 [MEMORY WORKER] Tidak ada obrolan baru dalam 24 jam terakhir. Siklus dilewati.")
                    return {"status": "skipped", "message": "No new chats to consolidate."}

                # Grouping teks obrolan per NPP (Bypass Guest)
                for row in rows:
                    npp = row['npp']
                    if npp == "GUEST" or not npp: 
                        continue
                    if npp not in chats_per_employee:
                        chats_per_employee[npp] = []
                    chats_per_employee[npp].append(row['message_text'])
            except Exception as read_err:
                logger.error(f"💥 [MEMORY WORKER] Gagal membaca data obrolan harian: {str(read_err)}")
                return {"status": "failed", "error": str(read_err)}

        if not chats_per_employee:
            return {"status": "skipped", "message": "No official employee chats to process."}

        # PHASE 2: Peras obrolan per pegawai via LLM Qwen 2.5 (DB Connection aman terbebas)
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        memories_to_save: List[Dict[str, str]] = []
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for npp, messages in chats_per_employee.items():
                full_chat_log = "\n".join([f"User: {msg}" for msg in messages])
                
                system_prompt = (
                    "Anda adalah modul ekstraksi memori jangka panjang CAKRA AI.\n"
                    "Tugas Anda adalah merangkum log obrolan pegawai menjadi 1-2 kalimat ringkas "
                    "berisi fakta penting seperti: proyek yang dikerjakan, error database yang dihadapi, "
                    "atau preferensi sistem mereka. Hilangkan basa-basi dan gunakan sudut pandang ketiga.\n\n"
                    "Contoh output: Pegawai sedang mengoptimasi database view_pengawasan_um dan mengalami masalah latensi tinggi."
                )

                payload = {
                    "model": settings.MODEL_ROUTER,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Rangkum log obrolan ini:\n{full_chat_log}"}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3}
                }

                try:
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        summary_text = response.json().get("message", {}).get("content", "").strip()
                        if summary_text:
                            memories_to_save.append({"npp": npp, "summary": summary_text})
                except Exception as llm_err:
                    logger.error(f"⚠️ [MEMORY WORKER] Gagal memproses LLM Summary untuk NPP {npp}: {str(llm_err)}")

        # PHASE 3: Buka kembali DB instant, eksekusi penyimpanan massal secara atomik
        processed_count = 0
        if memories_to_save:
            async with get_db() as conn:
                try:
                    async with conn.transaction(): # Gunakan transaksi biar super aman dan lurus
                        query_insert_memory = """
                            INSERT INTO ai_memory (npp, memory_summary, created_at)
                            VALUES ($1, $2, CURRENT_TIMESTAMP);
                        """
                        for mem in memories_to_save:
                            await conn.execute(query_insert_memory, mem["npp"], mem["summary"])
                            print(f"💾 [MEMORY CONSOLIDATED] Berhasil mengunci ingatan baru untuk NPP {mem['npp']}!")
                            processed_count += 1
                except Exception as write_err:
                    logger.error(f"💥 [MEMORY WORKER] Gagal dumping data memori ke database: {str(write_err)}")
                    return {"status": "failed", "error": str(write_err)}

        return {"status": "success", "processed_employees": processed_count}

memory_service = MemoryService()