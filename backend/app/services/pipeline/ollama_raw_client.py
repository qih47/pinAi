import httpx
import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request
from backend.app.core.config import settings
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

def _build_ollama_request_payload(
    model_name: str,
    raw_prompt: str,
    temperature: float,
    num_predict: int,
    num_ctx: int,
    stop_sequences: List[str] = None
) -> Dict[str, Any]:
    """
    Build exact payload structure for /api/generate.
    """
    options = {
        "temperature": temperature,
        "top_p": 0.95,
        "top_k": 64,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
    }
    if stop_sequences:
        options["stop"] = stop_sequences

    return {
        "model": model_name,
        "raw": True,
        "prompt": raw_prompt,
        "stream": True,
        "options": options,
        "keep_alive": -1
    }

@asynccontextmanager
async def _acquire_gpu_slot(request: Optional[Request]) -> AsyncGenerator:
    """
    Acquire GPU semaphore slot before calling model.
    """
    if request and hasattr(request.app.state, "gpu_semaphore"):
        async with request.app.state.gpu_semaphore:
            yield
    else:
        yield

async def call_ollama_generate_raw(
    model_name: str,
    raw_prompt: str,
    temperature: float = 1.0,
    num_predict: int = 2048,
    num_ctx: int = 32000,
    stop_sequences: List[str] = None,
    request: Optional[Request] = None  # For GPU semaphore
) -> AsyncGenerator[str, None]:
    """
    Call Ollama /api/generate endpoint with raw mode.
    
    Args:
        model_name: "gemma4:12b"
        raw_prompt: Exact raw prompt string from token_continuation_layer
        temperature: 0.1 (analysis) or 0.7 (response)
        num_predict: Max tokens to generate
        num_ctx: Context window
        stop_sequences: Stop on these markers (e.g., ["<channel|>"])
        request: FastAPI Request (acquire GPU semaphore)
    
    Yields:
        JSON lines: {"response": "token", "done": bool}
    
    Raises:
        httpx.TimeoutException
        httpx.HTTPStatusError
    """
    payload = _build_ollama_request_payload(
        model_name, raw_prompt, temperature, num_predict, num_ctx, stop_sequences
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
        payload = _build_ollama_request_payload(
            model_name=model_name,
            raw_prompt=raw_prompt,
            temperature=kwargs.get("temperature", 1.0),
            num_predict=kwargs.get("num_predict", 2048),
            num_ctx=kwargs.get("num_ctx", 32000),
            stop_sequences=kwargs.get("stop_sequences")
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
