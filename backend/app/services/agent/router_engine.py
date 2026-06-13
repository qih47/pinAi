import json
import logging
from datetime import datetime
from typing import Dict, Any
import httpx
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_ROUTER_ENGINE")

class RouterEngine:
    """
    Slot 1: Otak Router Utama CAKRA AI.
    Memanfaatkan qwen2.5:7b-instruct untuk menganalisis intensi, sentimen, 
    dan kebutuhan tools secara terstruktur (JSON) sebelum dilempar ke engine lain.
    """
    
    def __init__(self):
        logger.info("[ROUTER_ENGINE] Router engine initialized")

    async def analyze_user_query(self, query: str) -> Dict[str, Any]:
        """
        Menganalisis kueri pegawai secara asinkronus menggunakan endpoint /api/chat
        yang lebih stabil untuk struktur JSON terisolasi.
        """
        router_start_time = datetime.now()
        # 🔥 FIX SAKTI: Ubah ke endpoint /api/chat agar payload data user terpisah dari instruksi system
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        
        system_instructions = (
            "Anda adalah modul klasifikasi kognitif tingkat tinggi untuk CAKRA AI di PT Pindad.\n"
            "Tugas Anda adalah menganalisis kueri dari user dan WAJIB mengembalikan jawaban "
            "dalam format JSON murni tanpa ada teks pembuka (seperti markdown ```json) atau penutup lainnya!\n\n"
            "Format JSON yang diwajibkan harus mengikuti struktur ini:\n"
            "{\n"
            '  "intent": "NORMAL" atau "RAG" atau "ANALYTICS" atau "TOOL_CALLING",\n'
            '  "sentiment": "NEUTRAL" atau "FRUSTRATED" atau "POSITIVE",\n'
            '  "extracted_entities": ["nama_proyek", "variabel_sistem", "npp_terkait"],\n'
            '  "reason": "Alasan singkat analisis taktis Anda"\n'
            "}\n\n"
            "Aturan Klasifikasi Intent:\n"
            "- RAG: Jika user menanyakan tentang SOP, SKEP, Instruksi Kerja, Prosedur, atau dokumen internal perusahaan.\n"
            "- ANALYTICS: Jika user meminta query SQL, optimasi database, refactoring kode, atau kalkulasi data.\n"
            "- TOOL_CALLING: Jika user meminta melakukan aksi sistem seperti 'hapus docker', 'generate file', dll.\n"
            "- NORMAL: Chit-chat biasa, sapaan, atau pertanyaan umum luar korporat."
        )

        # Ubah payload mengikuti format chat array
        payload = {
            "model": settings.MODEL_ROUTER,
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": f"Analisis kueri ini secara taktis: {query}"}
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1
            },
            "keep_alive": -1
        }

        # 🔥 FIX TIMEOUT: Longgarkan dari 20.0 ke 60.0 detik biar NVMe ke GPU gak kecekek pas cold-start
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    logger.error(f"[ROUTER_ENGINE] Ollama error {response.status_code}")
                    return self._get_fallback_analysis()

                result_json = response.json()
                message_content = result_json.get("message", {}).get("content", "{}")
                
                # Parsing teks response menjadi dictionary python aktif
                analysis_data = json.loads(message_content)
                
                router_end_time = datetime.now()
                elapsed_time = (router_end_time - router_start_time).total_seconds()
                logger.info(f"[ROUTER_ENGINE] Analysis: {analysis_data.get('intent')} | Sentiment: {analysis_data.get('sentiment')} | Time: {elapsed_time:.2f}s")
                logger.debug(f"[ROUTER_ENGINE] Reason: {analysis_data.get('reason')}")
                return analysis_data

            except json.JSONDecodeError:
                logger.warning("[ROUTER_ENGINE] JSON parse error - using fallback")
                return self._get_fallback_analysis()
            except Exception as e:
                logger.error(f"[ROUTER_ENGINE] Critical error: {str(e)}")
                import traceback
                traceback.print_exc()  # Tampilkan jejak mleduknya kalau masih bandel
                return self._get_fallback_analysis()

    def _get_fallback_analysis(self) -> Dict[str, Any]:
        return {
            "intent": "NORMAL",
            "sentiment": "NEUTRAL",
            "extracted_entities": [],
            "reason": "Fallback triggered due to connection or parsing failure."
        }
        
    async def warm_up_router(self) -> bool:
        """Memaksa Ollama nge-load model Qwen ke VRAM selamanya saat startup (Anti-Timeout)"""
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": settings.MODEL_ROUTER,
            "messages": [{"role": "user", "content": "warm up"}],
            "stream": False,
            "keep_alive": -1 # Kunci di background GPU selamanya bolo!
        }
        logger.info(f"[ROUTER_ENGINE] Warming up model {settings.MODEL_ROUTER}...")
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client: # Kasih nafas 2 menit khusus warm-up
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    logger.info(f"[ROUTER_ENGINE] Model {settings.MODEL_ROUTER} ready on background GPU")
                    return True
                return False
            except Exception as e:
                logger.warning(f"[ROUTER_ENGINE] Warmup failed: {str(e)}")
                return False

router_engine = RouterEngine()