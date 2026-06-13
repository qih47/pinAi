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
        logger.info("[COGNITIVE_LOOP] Orchestrator ready for deep thinking")

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

        logger.debug(f"[COGNITIVE_LOOP] Entering deep thinking mode, waiting for GPU queue...")
        reasoning_start_time = datetime.now()
        
        async with gpu_semaphore:
            logger.debug(f"[COGNITIVE_LOOP] GPU slot acquired, {model_name} starting analysis...")
            
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
                            logger.error(f"[COGNITIVE_LOOP] Ollama error {response.status_code}: {error_text}")
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
                                logger.debug(f"[COGNITIVE_LOOP] Deep reasoning completed in {elapsed_time:.2f}s")
                                
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
                                        logger.info(f"[COGNITIVE_LOOP] Analytics saved for session {session_uuid[:8]}")
                                    except Exception as save_err:
                                        logger.warning(f"[COGNITIVE_LOOP] Failed to auto-save: {str(save_err)}")
                                
                except httpx.TimeoutException:
                    logger.warning("[COGNITIVE_LOOP] Timeout - deep thinking took too long")
                    yield json.dumps({"error": "Reasoning timeout."}) + "\n"
                except Exception as e:
                    logger.error(f"[COGNITIVE_LOOP] Error during reasoning: {str(e)}")
                    yield json.dumps({"error": f"Reasoning Error: {str(e)}"}) + "\n"

cognitive_orchestrator = CognitiveLoop()