"""
Ollama Core LLM Client Integration Module
Optimized v3: Raw Passthrough Stream with Centralized Layer 2 Handling.
"""

import httpx
import json
import logging
from datetime import datetime
from fastapi import Request
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_LLM")


async def warm_up_model(model_name: str, prompt: str = "keep alive") -> bool:
    """Warm up a model on Ollama by hitting the /api/chat endpoint and keeping it alive."""
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "keep_alive": -1,
        "options": {"temperature": 0.1}
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        try:
            response = await client.post(url, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"⚠️ [LLM CLIENT] Warm up model {model_name} failed: {e}")
            return False


async def stream_ollama_chat(
    model_name: str,
    messages: List[Dict[str, str]],
    request: Request,
    temperature: float = 0.7,
    session_uuid: Optional[str] = None,
    keep_alive: int = -1,
    num_ctx: int = 4096,
    **kwargs,  # 🦾 INJECT KWARGS: Kirim opsi stop tokens, num_predict dll ke Ollama
) -> AsyncGenerator[str, None]:
    """
    Generator asinkronus murni (Passthrough).
    Mengalirkan string chunk mentah langsung dari Ollama menuju Layer 2 Executor
    agar tidak terjadi tabrakan state machine penahan token kognitif.
    """
    gpu_semaphore = request.app.state.gpu_limit
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    logger.info(f"\n⏳ [LLM CLIENT] Request masuk antrean GPU. Menunggu Slot Semaphore...\")

    async with gpu_semaphore:
        logger.info(
            f"🔓 [HARDWARE GPU] Slot didapatkan! Mulai inferensi model '{model_name}'..."
        )
        inference_start_time = datetime.now()

        # Gabungkan parameter default dengan parameter dinamis hulu pipa
        ollama_options = {
            "temperature": temperature,
            "num_ctx": num_ctx,
            **kwargs
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "options": ollama_options,
            "keep_alive": keep_alive, 
        }

        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(180.0, connect=10.0)) as client:
            try:
                logger.debug(
                    f"[LLM_CLIENT] Calling Ollama API: {url}"
                )
                async with client.stream("POST", url, json=payload) as response:

                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(
                            f"[LLM_CLIENT] Ollama error {response.status_code}: {error_text}"
                        )
                        yield json.dumps(
                            {"error": f"Ollama Error: {response.status_code}"}
                        ) + "\n"
                        return

                    full_response = ""
                    accumulated_thinking = ""

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        chunk = json.loads(line)
                        message_chunk = chunk.get("message", {})
                        
                        content = message_chunk.get("content", "")
                        thought = message_chunk.get("thought", "")
                        done = chunk.get("done", False)

                        # ── PASSTHROUGH LOGIC MURNI ─────────────────────────────────
                        # Jika ada data content atau thought, kembalikan dalam struktur JSON string minimal
                        # agar bisa dikonsumsi secara seragam oleh fungsi Layer 2 Executor.
                        if content or thought:
                            if content: full_response += content
                            if thought: accumulated_thinking += thought
                            
                            yield json.dumps({
                                "chunk": content,
                                "thought": thought,
                                "done": done
                            }, ensure_ascii=False) + "\n"

                        if done:
                            inference_end_time = datetime.now()
                            elapsed_time = (inference_end_time - inference_start_time).total_seconds()
                            
                            logger.debug(f"[LLM_CLIENT] Model thoughts: {accumulated_thinking.strip() if accumulated_thinking else 'None'}")
                            logger.debug(f"[LLM_CLIENT] Response: {full_response.strip()}")
                            logger.info(f"[LLM_CLIENT] Inference completed in {elapsed_time:.2f}s")

                            # Otomatisasi sinkronisasi data histori percakapan ke database
                            if session_uuid and session_uuid != "GLOBAL_SESSION":
                                try:
                                    from backend.app.services.chat_history_service import chat_history_service

                                    user_query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "Kueri tidak terdeteksi")

                                    await chat_history_service.save_chat_message(
                                        session_id=session_uuid,
                                        role="assistant",
                                        text=full_response,
                                        thought=accumulated_thinking if accumulated_thinking else "Processed via Layer 2 [Gemma Core Engine]"
                                    )

                                    await chat_history_service.save_dialogue_corpus(
                                        session_uuid=session_uuid,
                                        user_text=user_query,
                                        assistant_text=full_response,
                                    )
                                    logger.info(f"[LLM_CLIENT] Dialog history saved for session {session_uuid[:8]}")
                                except Exception as save_err:
                                    logger.warning(f"[LLM_CLIENT] Failed to save dialog history: {str(save_err)}")

            except httpx.TimeoutException:
                logger.error("[LLM_CLIENT] Timeout - cluster engine took too long")
                yield json.dumps({"error": "Inference timeout, cluster GPU penuh."}) + "\n"
            except Exception as e:
                logger.error(f"[LLM_CLIENT] Critical error: {str(e)}")
                yield json.dumps({"error": f"Internal LLM Client Error: {str(e)}"}) + "\n"


async def generate_json_response(
    model_name: str,
    messages: List[Dict[str, str]],
    request: Request,
    temperature: float = 0.3,
    keep_alive: int = 0,
    timeout: float = 60.0,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Generate JSON response (non-streaming) for Router/Orchestrator pipeline layers."""
    logger = logging.getLogger("CAKRA_LLM_CLIENT")
    gpu_semaphore = request.app.state.gpu_limit
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    
    logger.debug(f"[JSON_GEN] Waiting for GPU semaphore for model {model_name}...")
    
    async with gpu_semaphore:
        logger.debug(f"[JSON_GEN] GPU slot acquired for {model_name}")
        start_time = datetime.now()
        
        ollama_options = {
            "temperature": temperature, 
            "num_ctx": 2048,
            **kwargs 
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": ollama_options,
            "keep_alive": keep_alive,
        }
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"[JSON_GEN] Ollama error {response.status_code}: {error_text}")
                    return None
                
                result = response.json()
                message_content = result.get("message", {}).get("content", "{}")
                
                try:
                    parsed_json = json.loads(message_content)
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    logger.info(f"[JSON_GEN] Generated in {elapsed:.2f}s | Model: {model_name}")
                    return parsed_json
                except json.JSONDecodeError as je:
                    logger.warning(f"[JSON_GEN] Parse error: {str(je)}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"[JSON_GEN] Timeout on model {model_name}")
            return None
        except Exception as e:
            logger.error(f"[JSON_GEN] Error: {str(e)}")
            return None