import json
import logging
from typing import AsyncGenerator, List, Dict
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
        temperature: float = 0.6
    ) -> AsyncGenerator[str, None]:
        
        gpu_semaphore = request.app.state.gpu_limit
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        model_name = settings.MODEL_REASONING  # deepseek-r1:8b

        print(f"\n🧠 [COGNITIVE LOOP] Memasuki mode berpikir mendalam. Menunggu antrean GPU...")
        
        async with gpu_semaphore:
            print(f"🔓 [HARDWARE GPU] Slot didapatkan! {model_name} mulai menganalisis masalah...")
            
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 8192 # Context window kita naikin 2x lipat buat nampung dokumen RAG nanti
                }
            }
            
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            # Timeout dinaikkan ke 120 detik karena proses reasoning butuh mikir lama
            async with httpx.AsyncClient(limits=limits, timeout=120.0) as client:
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
                            
                            yield json.dumps({
                                "chunk": content,
                                "done": done
                            }) + "\n"
                            
                            if done:
                                print("\n" + "═"*50)
                                print(f"🧠 [DEEPSEEK REASONING COMPLETE]")
                                print("═"*50)
                                
                except httpx.TimeoutException:
                    print("🚨 [COGNITIVE LOOP] Timeout! DeepSeek mikirnya kelamaan.")
                    yield json.dumps({"error": "Reasoning timeout."}) + "\n"
                except Exception as e:
                    print(f"💥 [COGNITIVE CRITICAL] Error saat reasoning: {str(e)}")
                    yield json.dumps({"error": f"Reasoning Error: {str(e)}"}) + "\n"

cognitive_orchestrator = CognitiveLoop()