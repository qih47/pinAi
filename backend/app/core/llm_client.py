"""
Ollama Core LLM Client Integration Module.

Optimized for Gemma 4 (gemma4:12b).
Gemma 4 handles thinking natively via the `thought` field in Ollama responses —
no external thinking API params needed.
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
    Ekstrak JSON dari response Gemma 4.
    Support:
    - Output JSON langsung
    - JSON yang di-wrap dalam markdown ```json ... ```
    - JSON terpotong karena num_predict limit (partial recovery)
    - Sisa teks sebelum/sesudah JSON object
    """
    logger_local = logging.getLogger("CAKRA_LLM_CLIENT")

    # Step 1: Strip blok <think>...</think>
    cleaned = _THINK_PATTERN.sub("", raw).strip()

    # Step 2: Strip markdown code fence
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"```", "", cleaned).strip()

    # Step 3: Cari { pertama
    start_idx = cleaned.find("{")
    if start_idx == -1:
        logger_local.error(
            f"[JSON_GEN] No opening brace found. "
            f"Model: {model_name} | Raw (150c): {raw[:150]}"
        )
        raise ValueError(f"[JSON_GEN] Model {model_name} output contains no JSON object")

    # Step 4: Cari } terakhir — kalau tidak ada, coba repair JSON terpotong
    end_idx = cleaned.rfind("}")
    if end_idx == -1 or end_idx <= start_idx:
        logger_local.warning(
            f"[JSON_GEN] JSON terpotong (num_predict limit?). "
            f"Model: {model_name} | Mencoba repair..."
        )
        partial = cleaned[start_idx:]
        open_braces = partial.count("{") - partial.count("}")
        open_brackets = partial.count("[") - partial.count("]")

        repaired = partial.rstrip().rstrip(",")
        if open_brackets > 0:
            repaired += "]" * open_brackets
        if open_braces > 0:
            repaired += "}" * open_braces

        try:
            result = json.loads(repaired)
            logger_local.warning(
                f"[JSON_GEN] Partial JSON berhasil di-repair | Model: {model_name}"
            )
            return result
        except json.JSONDecodeError as je:
            logger_local.error(
                f"[JSON_GEN] Repair gagal. Model: {model_name} | "
                f"Error: {je.msg} | Repaired (200c): {repaired[:200]}"
            )
            raise ValueError(
                f"[JSON_GEN] Model {model_name} output truncated and repair failed: {je.msg}"
            )

    json_str = cleaned[start_idx:end_idx + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as je:
        logger_local.error(
            f"[JSON_GEN] JSON decode failed. Model: {model_name} | "
            f"Error: {je.msg} | Extracted (200c): {json_str[:200]}"
        )
        raise ValueError(f"[JSON_GEN] Model {model_name} output failed to decode: {je.msg}")


async def warm_up_model(model_name: str, prompt: str = "keep alive") -> bool:
    """Warm up Gemma 4 on Ollama dan keep loaded di VRAM."""
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
    temperature: float = 1.0,
    session_uuid: Optional[str] = None,
    keep_alive: int = -1,
    num_ctx: int = 4096,
    is_thinking: bool = False,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Generator asinkronus murni (Passthrough).
    Mengalirkan string chunk mentah langsung dari Ollama menuju Layer 2 Executor.
    Gemma 4 thinking dialirkan via field `thought` per chunk.
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

        # Hybrid Token Budget Processing
        # Mengambil token_budget (misal 1120 untuk PDF, 280 untuk Gambar biasa)
        token_budget = kwargs.pop("token_budget", None)
        num_predict = kwargs.pop("num_predict", 8192 if is_thinking else 2048)
        
        if token_budget:
            # Gemma akan dibatasi outputnya berdasarkan budget token agar tidak hallucination
            logger.info(f"🪙 [TOKEN HYBRID] Menerapkan Token Budget sebesar: {token_budget} (Model: {model_name})")
            # Jika budget di-set secara spesifik, kita bisa membatasi max tokens generation:
            num_predict = min(num_predict, token_budget * 2) # Mengijinkan sisa margin 

        ollama_options = {
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 64,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            **kwargs,
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "think": is_thinking,
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
                current_mode = None

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    chunk = json.loads(line)
                    message_chunk = chunk.get("message", {})
                    content = message_chunk.get("content", "")
                    thought = message_chunk.get("thinking", "")
                    done = chunk.get("done", False)

                    if content or thought:
                        if first_token:
                            ttft = (datetime.now() - inference_start_time).total_seconds()
                            logger.info(f"⚡ [LLM_CLIENT] First token received! TTFT: {ttft:.2f}s")
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

                        yield_data = {"chunk": content, "thinking": thought, "done": done, "event_type": "chunk"}
                        if done:
                            eval_count = chunk.get("eval_count", 0)
                            eval_duration = chunk.get("eval_duration", 0)
                            if eval_count and eval_duration:
                                yield_data["eval_count"] = eval_count
                                yield_data["eval_duration"] = eval_duration
                                
                        yield json.dumps(
                            yield_data,
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
                                # Log TPS if available
                                eval_count_stat = yield_data.get("eval_count")
                                eval_duration_stat = yield_data.get("eval_duration")
                                if eval_count_stat and eval_duration_stat:
                                    tps = eval_count_stat / (eval_duration_stat / 1e9)
                                    obs_dict = {
                                        "msg": "Inference completed",
                                        "stats": {
                                            "eval_count": eval_count_stat,
                                            "eval_duration_sec": eval_duration_stat / 1e9,
                                            "tps": tps
                                        }
                                    }
                                    await chat_history_service.save_agent_step(
                                        session_id=session_uuid,
                                        step_number=4,
                                        tool_called="INFERENCE_STATS",
                                        tool_input=f"Model: {model_name}",
                                        observation=json.dumps(obs_dict)
                                    )
                            except Exception as stat_err:
                                logger.warning(f"[LLM_CLIENT] Failed to save inference stats: {str(stat_err)}")

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
                                    metadata={"mode": "global_inference", "thought": accumulated_thinking.strip() if accumulated_thinking else None}
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
    num_predict: int = 2048,
    thinking_budget: int = 0,  # Retained for API compatibility, unused for Gemma 4
    **kwargs,
) -> Dict[str, Any]:
    """
    Generate JSON response (non-streaming) untuk pipeline layers.

    Gemma 4 specifics:
    - Thinking terjadi secara native, tidak perlu API param `thinking`
    - Response content bisa kosong jika Ollama memisahkan `thought` dan `content`
      → fallback ke field `thought` untuk recovery
    - `thinking_budget` diabaikan (Gemma 4 mengontrol thinking budget sendiri)
    - `num_predict` default 2048 — cukup untuk JSON schema 12 param Call 1

    Rekomendasi num_predict per caller:
    - Call 1 Router (12 param JSON)  : 2048  ← default sudah cukup
    - Layer 0 Gateway/Rewriter       : 512
    - Layer 1 Cognitive Analyzer     : 1024

    Raises:
        httpx.TimeoutException: Saat Ollama tidak merespons dalam batas timeout
        ValueError: Saat response kosong atau tidak mengandung JSON valid
        httpx.HTTPStatusError: Saat Ollama return status error
    """
    logger_local = logging.getLogger("CAKRA_LLM_CLIENT")
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    ollama_options = {
        "temperature": temperature,
        "top_p": 0.95,
        "top_k": 64,
        "num_ctx": num_ctx,
        "num_predict": num_predict,
        **kwargs,
    }

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": ollama_options,
        "keep_alive": keep_alive,
        "format": "json",
    }

    logger_local.debug(
        f"[JSON_GEN] Calling Gemma 4 | model: {model_name} | "
        f"num_ctx: {num_ctx} | num_predict: {num_predict}"
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
        message_obj = result.get("message", {})
        message_content = message_obj.get("content", "")

        # Gemma 4: jika content kosong, coba ambil dari field `thought`
        if not message_content or not message_content.strip():
            thought_content = message_obj.get("thought", "")
            if thought_content and thought_content.strip():
                logger_local.warning(
                    f"[JSON_GEN] content kosong, recovery dari field 'thought' | model: {model_name}"
                )
                message_content = thought_content
            else:
                logger_local.error(
                    f"[JSON_GEN] content DAN thought kosong. "
                    f"Full Ollama response: {json.dumps(result)[:500]}"
                )
                raise ValueError(f"[JSON_GEN] Model {model_name} returned empty content")

        parsed_json = _extract_json_from_response(message_content, model_name)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger_local.info(
            f"[JSON_GEN] Generated in {elapsed:.2f}s | Model: {model_name} | "
            f"num_predict: {num_predict}"
        )
        return parsed_json

    except httpx.TimeoutException as te:
        logger_local.error(f"[JSON_GEN] Timeout calling Ollama model {model_name}: {str(te)}")
        raise
    except Exception as e:
        logger_local.error(f"[JSON_GEN] Unexpected error during JSON inference: {str(e)}")
        raise


async def call_ollama_generate_raw(
    model_name: str,
    raw_prompt: str,
    temperature: float = 1.0,
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