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

    print(f"\n⏳ [LLM CLIENT] Request masuk antrean GPU. Menunggu Slot Semaphore...")

    async with gpu_semaphore:
        print(
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
                print(
                    f"📡 [LLM CLIENT] Menembak API Ollama (Background Lock Active): {url}"
                )
                async with client.stream("POST", url, json=payload) as response:

                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(
                            f"💥 [LLM CLIENT] Ollama mengembalikan error HTTP {response.status_code}: {error_text}"
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
                            
                            print("\n" + "═" * 60)
                            if accumulated_thinking:
                                print(f"🧠 [LLM CLIENT TERMINAL LOG - MODEL NATIVE THOUGHTS]\n{accumulated_thinking.strip()}\n" + "─" * 60)
                            print(f"🤖 [LLM CLIENT TERMINAL LOG - CORE RESPONSE]\n{full_response.strip()}")
                            print("═" * 60)
                            print(f"✨ [LLM CLIENT] Inferensi model '{model_name}' sukses diselesaikan dalam {elapsed_time:.2f} detik.")

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
                                    print(f"📝 [DATABASE PERSISTENCE] Sinkronisasi rekam dialog sesi {session_uuid[:8]} berhasil diamankan.")
                                except Exception as save_err:
                                    print(f"⚠️ [DATABASE WARNING] Gagal mengunci penyimpanan riwayat otomatis: {str(save_err)}")

            except httpx.TimeoutException:
                print("🚨 [LLM CLIENT] Timeout! Cluster engine hardware terlalu lama merespons.")
                yield json.dumps({"error": "Inference timeout, cluster GPU penuh."}) + "\n"
            except Exception as e:
                print(f"💥 [LLM CLIENT] Critical failure pada sirkuit internal client: {str(e)}")
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
    gpu_semaphore = request.app.state.gpu_limit
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    
    print(f"\n⏳ [JSON GEN] Menunggu antrean GPU semaphore untuk model {model_name}...")
    
    async with gpu_semaphore:
        print(f"🔓 [JSON GEN] GPU slot acquired. Generating data structure from {model_name}...")
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
                    print(f"💥 [JSON GEN] Ollama error {response.status_code}: {error_text}")
                    return None
                
                result = response.json()
                message_content = result.get("message", {}).get("content", "{}")
                
                try:
                    parsed_json = json.loads(message_content)
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    print(f"✅ [JSON GEN] JSON generated successfully in {elapsed:.2f}s | Model: {model_name}")
                    return parsed_json
                except json.JSONDecodeError as je:
                    print(f"⚠️ [JSON GEN] Structure broken / parse error: {str(je)}")
                    return None
                    
        except httpx.TimeoutException:
            print(f"🚨 [JSON GEN] Timeout limit exceeded on model {model_name}")
            return None
        except Exception as e:
            print(f"💥 [JSON GEN] Error critical: {str(e)}")
            return None