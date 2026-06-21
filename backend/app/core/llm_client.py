"""
Ollama Core LLM Client Integration Module.

Model-agnostic design: Auto-detect thinking capability via /api/show endpoint.
Support model thinking (Qwen3, DeepSeek-R1) dan non-thinking (Qwen2.5, Gemma).
"""

import re
import httpx
import json
import logging
from datetime import datetime
from fastapi import Request
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_LLM")

_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _extract_json_from_response(raw: str, model_name: str) -> Dict[str, Any]:
    """
    Ekstrak JSON dari response model, support:
    - Model biasa: langsung output JSON
    - Model think (Qwen3, DeepSeek-R1): <think>...</think> dulu baru JSON
    - Model yang wrap JSON dalam markdown ```json ... ```
    """
    logger_local = logging.getLogger("CAKRA_LLM_CLIENT")

    # Step 1: Strip semua blok <think>...</think>
    cleaned = _THINK_PATTERN.sub("", raw).strip()

    # Step 2: Strip markdown code fence
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"```", "", cleaned).strip()

    # Step 3: Ekstrak substring { ... } terluar
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")

    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        logger_local.error(
            f"[JSON_GEN] No JSON object found after cleanup. "
            f"Model: {model_name} | Raw (150c): {raw[:150]}"
        )
        raise ValueError(f"[JSON_GEN] Model {model_name} output contains no JSON object")

    json_str = cleaned[start_idx:end_idx + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as je:
        logger_local.error(
            f"[JSON_GEN] JSON decode failed. Model: {model_name} | "
            f"Error: {je.msg} | Extracted (200c): {json_str[:200]}"
        )
        raise ValueError(f"[JSON_GEN] Model {model_name} output failed to decode: {je.msg}")


async def _check_model_thinking_support(model_name: str) -> bool:
    """
    🔥 AUTO-DETECT: Cek apakah model support thinking mode via Ollama API.
    
    Query endpoint /api/show untuk lihat model capabilities.
    Kalau ada field "thinking" atau model name mengandung "think"/"r1", 
    anggap support thinking.
    """
    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/show"
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.post(url, json={"name": model_name})
            if response.status_code == 200:
                model_info = response.json()
                
                # Cek parameter/template yang mengindikasikan thinking support
                details = model_info.get("details", {})
                parameters = details.get("parameters", "")
                
                # Indikator thinking support:
                # 1. Ada "thinking" di parameters
                # 2. Model name mengandung "r1" (DeepSeek-R1) atau "think"
                # 3. Ada special tokens untuk thinking
                has_thinking_param = "thinking" in parameters.lower()
                has_thinking_name = any(x in model_name.lower() for x in ["r1", "think"])
                
                if has_thinking_param or has_thinking_name:
                    logger.debug(f"[MODEL_CHECK] {model_name} supports thinking mode")
                    return True
                
                logger.debug(f"[MODEL_CHECK] {model_name} does NOT support thinking mode")
                return False
            else:
                logger.warning(f"[MODEL_CHECK] Failed to fetch model info: {response.status_code}")
                return False
    except Exception as e:
        logger.warning(f"[MODEL_CHECK] Error checking thinking support for {model_name}: {e}")
        # Fallback: check model name patterns
        return any(x in model_name.lower() for x in ["r1", "think"])


async def warm_up_model(model_name: str, prompt: str = "keep alive") -> bool:
    """Warm up a model on Ollama dan keep loaded di VRAM."""
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "keep_alive": -1,
        "options": {"temperature": 0.1},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        try:
            response = await client.post(url, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"⚠️ [LLM CLIENT] Warm up model {model_name} failed: {e}")
            return False


_shared_client: Optional[httpx.AsyncClient] = None

def get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        # Connection reuse parameters optimized for low-latency localhost communication
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        _shared_client = httpx.AsyncClient(
            limits=limits,
            timeout=httpx.Timeout(180.0, connect=10.0)
        )
    return _shared_client


async def stream_ollama_chat(
    model_name: str,
    messages: List[Dict[str, str]],
    request: Request,
    temperature: float = 0.7,
    session_uuid: Optional[str] = None,
    keep_alive: int = -1,
    num_ctx: int = 4096,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Generator asinkronus murni (Passthrough).
    Mengalirkan string chunk mentah langsung dari Ollama menuju Layer 2 Executor.
    """
    gpu_semaphore = request.app.state.gpu_limit
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    logger.info("⏳ [LLM CLIENT] Request masuk antrean GPU. Menunggu Slot Semaphore...")
    queue_start_time = datetime.now()

    async with gpu_semaphore:
        queue_wait_time = (datetime.now() - queue_start_time).total_seconds()
        if queue_wait_time > 0.05:
            logger.info(f"🔓 [HARDWARE GPU] Slot didapatkan setelah antre {queue_wait_time:.2f}s! Mulai inferensi model '{model_name}'...")
        else:
            logger.info(f"🔓 [HARDWARE GPU] Slot didapatkan langsung (tanpa antre)! Mulai inferensi model '{model_name}'...")

        inference_start_time = datetime.now()

        ollama_options = {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": kwargs.pop("num_predict", 2048),
            **kwargs,
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "options": ollama_options,
            "keep_alive": keep_alive,
        }

        client = get_shared_client()
        try:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"[LLM_CLIENT] Ollama error {response.status_code}: {error_text}")
                    yield json.dumps({"error": f"Ollama Error: {response.status_code}"}) + "\n"
                    return

                full_response = ""
                accumulated_thinking = ""
                first_token = True
                current_mode = None  # Tracks 'thinking' or 'answering' mode for terminal log layout

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    chunk = json.loads(line)
                    message_chunk = chunk.get("message", {})
                    content = message_chunk.get("content", "")
                    thought = message_chunk.get("thought", "")
                    done = chunk.get("done", False)

                    if content or thought:
                        if first_token:
                            ttft = (datetime.now() - inference_start_time).total_seconds()
                            logger.info(f"⚡ [LLM_CLIENT] First token received! TTFT (Time to First Token): {ttft:.2f}s")
                            first_token = False

                        if thought:
                            accumulated_thinking += thought
                            if current_mode != "thinking":
                                current_mode = "thinking"
                                print("\n[GEMMA_THINK] ", end="", flush=True)
                            print(thought, end="", flush=True)

                        if content:
                            full_response += content
                            if current_mode != "answering":
                                current_mode = "answering"
                                print("\n[GEMMA_ANSWER] ", end="", flush=True)
                            print(content, end="", flush=True)

                        yield json.dumps(
                            {"chunk": content, "thought": thought, "done": done},
                            ensure_ascii=False,
                        ) + "\n"

                    if done:
                        print("\n", flush=True)
                        elapsed_time = (datetime.now() - inference_start_time).total_seconds()
                        logger.debug(f"[LLM_CLIENT] Thoughts: {accumulated_thinking.strip() or 'None'}")
                        logger.debug(f"[LLM_CLIENT] Response: {full_response.strip()}")
                        logger.info(f"[LLM_CLIENT] Inference completed in {elapsed_time:.2f}s")

                        if session_uuid and session_uuid != "GLOBAL_SESSION":
                            try:
                                from backend.app.services.chat_history_service import chat_history_service
                                user_query = next(
                                    (m["content"] for m in reversed(messages) if m["role"] == "user"),
                                    "Kueri tidak terdeteksi",
                                )
                                await chat_history_service.save_chat_message(
                                    session_id=session_uuid,
                                    role="assistant",
                                    text=full_response,
                                    thought=accumulated_thinking or "Processed via Layer 2 [Core Engine]",
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
    request: Optional[Request] = None,
    temperature: float = 0.3,
    keep_alive: int = -1,
    timeout: float = 60.0,
    num_ctx: int = 2048,
    thinking_budget: int = 0,
    **kwargs,
) -> Dict[str, Any]:
    """
    Generate JSON response (non-streaming) untuk pipeline layers.

    Auto-detect thinking capability via /api/show endpoint.
    Thinking distrip otomatis dari output sebelum JSON diekstrak.

    Args:
        thinking_budget: Max token untuk thinking. 0 = disable think.
                         Rekomendasi per layer:
                         - Layer 0 Gateway/Rewriter: 128 (klasifikasi sederhana)
                         - Layer 1 Cognitive Analyzer: 512 (analisis intent kompleks)

    Raises:
        httpx.TimeoutException: Saat Ollama tidak merespons dalam batas timeout
        ValueError: Saat response kosong atau tidak mengandung JSON valid
        httpx.HTTPStatusError: Saat Ollama return status error
    """
    logger_local = logging.getLogger("CAKRA_LLM_CLIENT")
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    # 🔥 AUTO-DETECT: Cek apakah model support thinking
    model_has_thinking = await _check_model_thinking_support(model_name)

    num_predict = (thinking_budget + 1024) if model_has_thinking else 1024

    ollama_options = {
        "temperature": temperature,
        "num_ctx": num_ctx,
        "num_predict": num_predict,
        **kwargs,
    }

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": ollama_options,
        "keep_alive": keep_alive,
    }

    # 🔥 Hanya tambahkan thinking budget kalau model support DAN budget > 0
    if model_has_thinking and thinking_budget > 0:
        payload["thinking"] = {"budget_tokens": thinking_budget}
        logger_local.debug(
            f"[JSON_GEN] Thinking enabled | budget: {thinking_budget} tokens | model: {model_name}"
        )
    else:
        logger_local.debug(
            f"[JSON_GEN] Thinking disabled | model: {model_name} | "
            f"reason: {'non-think model' if not model_has_thinking else 'zero budget'}"
        )

    start_time = datetime.now()
    client = get_shared_client()

    try:
        response = await client.post(url, json=payload, timeout=httpx.Timeout(timeout, connect=10.0))

        if response.status_code != 200:
            error_text = response.text
            logger_local.error(
                f"[JSON_GEN] Ollama HTTP error {response.status_code}: {error_text[:200]}"
            )
            raise httpx.HTTPStatusError(
                f"Ollama returned {response.status_code}",
                request=response.request,
                response=response,
            )

        result = response.json()
        message_content = result.get("message", {}).get("content", "")

        if not message_content or not message_content.strip():
            raise ValueError(f"[JSON_GEN] Model {model_name} returned empty content")

        parsed_json = _extract_json_from_response(message_content, model_name)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger_local.info(
            f"[JSON_GEN] Generated in {elapsed:.2f}s | Model: {model_name} | "
            f"thinking_budget: {thinking_budget} tokens | thinking_enabled: {model_has_thinking}"
        )
        return parsed_json

    # 🔥 FIX UTAMA: Menutup blok try dengan menangkap exception secara terstruktur
    except httpx.TimeoutException as te:
        logger_local.error(f"[JSON_GEN] Timeout calling Ollama model {model_name}: {str(te)}")
        raise
    except Exception as e:
        logger_local.error(f"[JSON_GEN] Unexpected error during JSON inference: {str(e)}")
        raise

async def call_ollama_generate_raw(
    model_name: str,
    raw_prompt: str,
    temperature: float = 0.7,
    num_predict: int = 2048,
    num_ctx: int = 32000,
    stop_sequences: List[str] = None,
    request: Optional[Request] = None
) -> AsyncGenerator[str, None]:
    """
    Call Ollama /api/generate endpoint with raw mode.
    Proxy to ollama_raw_client.py implementation.
    """
    from backend.app.services.pipeline.ollama_raw_client import call_ollama_generate_raw as _call
    async for chunk in _call(
        model_name, raw_prompt, temperature, num_predict, num_ctx, stop_sequences, request
    ):
        yield chunk

async def stream_ollama_generate_raw(*args, **kwargs):
    """Async streaming generator alias for backward compatibility."""
    async for chunk in call_ollama_generate_raw(*args, **kwargs):
        yield chunk