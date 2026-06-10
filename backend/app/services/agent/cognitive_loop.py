import json
import logging
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Optional
import httpx
from fastapi import Request
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_COGNITIVE_LOOP")

class CognitiveLoop:
    """
    Slot 2: Orkestrator DeepSeek-R1.
    Bertugas menangani kueri analitik dan RAG. Model ini secara alami 
    akan menghasilkan tag <think>...</think> sebelum memberikan jawaban final.
    """
    def __init__(self):
        print("⚙️  [COGNITIVE LOOP] Orkestrator DeepSeek-R1 (Slot 2) siap merajut pemikiran, bolo!")

    async def stream_reasoning_engine(
        self,
        messages: List[Dict[str, str]],
        request: Request,
        temperature: float = 0.6,
        session_uuid: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        
        gpu_semaphore = request.app.state.gpu_limit
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        model_name = settings.MODEL_REASONING  # deepseek-r1:8b

        print(f"\n🧠 [COGNITIVE LOOP] Memasuki mode berpikir mendalam. Menunggu antrean GPU...")
        reasoning_start_time = datetime.now()
        
        async with gpu_semaphore:
            print(f"🔓 [HARDWARE GPU] Slot didapatkan! {model_name} mulai menganalisis masalah...")
            
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 8192 # Context window kita naikin 2x lipat buat nampung dokumen RAG nanti
                },
                "keep_alive": -1
            }
            
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            # Timeout dinaikkan ke 180 detik karena proses reasoning butuh mikir lama tanpa auto-timeout prematurely
            async with httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                try:
                    full_response = ""
                    async with client.stream("POST", url, json=payload) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            print(f"💥 [COGNITIVE] Ollama Error {response.status_code}: {error_text}")
                            yield json.dumps({"error": f"Ollama Error: {response.status_code}"}) + "\n"
                            return

                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            
                            chunk = json.loads(line)
                            message_chunk = chunk.get("message", {})
                            content = message_chunk.get("content", "")
                            done = chunk.get("done", False)
                            
                            full_response += content
                            yield json.dumps({"chunk": content, "done": done}) + "\n"
                            
                            # ==============================================================================
                            # 🦾 SINKRONISASI COGNITIVE SAKTI MULTI-TABEL AMAN KENDALI (SLOT 2)
                            # ==============================================================================
                            if done:
                                reasoning_end_time = datetime.now()
                                elapsed_time = (reasoning_end_time - reasoning_start_time).total_seconds()
                                print("\n" + "═"*50)
                                print(f"🧠 [DEEPSEEK REASONING COMPLETE] dalam {elapsed_time:.2f} detik")
                                print("═"*50)
                                
                                if session_uuid and session_uuid != "GLOBAL_SESSION":
                                    try:
                                        from backend.app.services.chat_history_service import chat_history_service

                                        user_query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "Kueri analitik")

                                        await chat_history_service.save_chat_message(
                                            session_id=session_uuid,
                                            role="assistant",
                                            text=full_response,
                                            thought="Processed via Slot 2 [DeepSeek-R1 Reasoning Engine]",
                                        )

                                        await chat_history_service.save_dialogue_corpus(
                                            session_uuid=session_uuid,
                                            user_text=user_query,
                                            assistant_text=full_response,
                                        )
                                        print(f"📝 [COGNITIVE SAVE SUCCESS] Data analitik sesi {session_uuid[:8]} aman di database!")
                                    except Exception as save_err:
                                        print(f"⚠️ [MULTI-TABEL WARNING] Gagal auto-save Slot 2: {str(save_err)}")
                                
                except httpx.TimeoutException:
                    print("🚨 [COGNITIVE LOOP] Timeout! DeepSeek mikirnya kelamaan.")
                    yield json.dumps({"error": "Reasoning timeout."}) + "\n"
                except Exception as e:
                    print(f"💥 [COGNITIVE CRITICAL] Error saat reasoning: {str(e)}")
                    yield json.dumps({"error": f"Reasoning Error: {str(e)}"}) + "\n"

cognitive_orchestrator = CognitiveLoop()