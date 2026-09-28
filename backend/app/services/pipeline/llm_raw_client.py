import httpx
import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request
from backend.app.core.config import settings
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

def _build_raw_request_payload(
    model_name: str,
    raw_prompt: str,
    temperature: float,
    num_predict: int,
    num_ctx: int,
    stop_sequences: Optional[List[str]] = None,
    images: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Build exact payload structure for raw LLM generation (/api/generate).
    Agnostic to model vendor.
    """
    options = {
        "temperature": temperature,
        "top_p": 0.95,
        "top_k": 64,
        "num_ctx": num_ctx,
        "num_batch": 512,
    }
    if num_predict > 0:
        options["num_predict"] = num_predict
    if stop_sequences:
        options["stop"] = stop_sequences

    payload = {
        "model": model_name,
        "raw": True,
        "prompt": raw_prompt,
        "stream": True,
        "options": options,
        "keep_alive": -1
    }
    if images:
        payload["images"] = images
    return payload

# Alias for backward compatibility
_build_ollama_request_payload = _build_raw_request_payload


@asynccontextmanager
async def _acquire_gpu_slot(request: Optional[Request]) -> AsyncGenerator:
    """
    Acquire GPU semaphore slot before calling model.
    Checks both gpu_semaphore and gpu_limit for maximum compatibility across runners.
    """
    sem = None
    if request and hasattr(request, "app") and hasattr(request.app, "state"):
        sem = getattr(request.app.state, "gpu_limit", None) or getattr(request.app.state, "gpu_semaphore", None)

    if sem is not None:
        async with sem:
            yield
    else:
        yield


async def call_llm_generate_raw(
    model_name: str,
    raw_prompt: str,
    temperature: float = 1.0,
    num_predict: int = 2048,
    num_ctx: int = 16384,
    stop_sequences: Optional[List[str]] = None,
    request: Optional[Request] = None,  # For GPU semaphore
    images: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    """
    Call raw generation endpoint with stream mode.
    
    Args:
        model_name: Model identifier (e.g. "gemma4:12b")
        raw_prompt: Exact raw prompt string
        temperature: 0.1 (analysis) or 0.7 (response)
        num_predict: Max tokens to generate
        num_ctx: Context window size
        stop_sequences: Stop markers
        request: FastAPI Request (for GPU semaphore)
        images: Optional list of base64 images
    
    Yields:
        JSON lines: {"response": "token", "done": bool}
    """
    payload = _build_raw_request_payload(
        model_name, raw_prompt, temperature, num_predict, num_ctx, stop_sequences, images
    )
    
    base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url.rstrip('/')}/api/generate"
    
    timeout_s = getattr(settings, "OLLAMA_GENERATE_TIMEOUT_S", 180.0)
    timeout = httpx.Timeout(timeout_s)
    
    async with _acquire_gpu_slot(request):
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield line

# Backward-compatible alias
call_ollama_generate_raw = call_llm_generate_raw


class RawGenerateClient:
    """Stateful client for /api/generate with connection pooling."""
    
    def __init__(self, base_url: str, pool_size: int = 10):
        self.base_url = base_url
        self.pool_size = pool_size
        self._client = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create async client with pooling."""
        if self._client is None:
            timeout_s = getattr(settings, "OLLAMA_GENERATE_TIMEOUT_S", 180.0)
            timeout = httpx.Timeout(timeout_s)
            limits = httpx.Limits(max_connections=self.pool_size)
            self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return self._client
    
    async def generate(
        self,
        model_name: str,
        raw_prompt: str,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate with automatic retry and timeout handling."""
        client = await self.get_client()
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = _build_raw_request_payload(
            model_name=model_name,
            raw_prompt=raw_prompt,
            temperature=kwargs.get("temperature", 1.0),
            num_predict=kwargs.get("num_predict", 2048),
            num_ctx=kwargs.get("num_ctx", 16384),
            stop_sequences=kwargs.get("stop_sequences"),
            images=kwargs.get("images")
        )
        
        request_obj = kwargs.get("request")
        async with _acquire_gpu_slot(request_obj):
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield line
                        
    async def close(self):
        """Close connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
