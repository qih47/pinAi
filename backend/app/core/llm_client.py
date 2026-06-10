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
) -> AsyncGenerator[str, None]:
    """
    Generator asinkronus untuk melakukan streaming response dari Ollama secara real-time.
    Mengamankan antrean VRAM menggunakan global GPU Semaphore (limit maks: 2).
    
    Args:
        model_name: Model Ollama yang digunakan
        messages: List pesan format chat
        request: FastAPI request object (untuk akces gpu_semaphore)
        temperature: Kreativitas model (0.0-1.0)
        session_uuid: Session ID untuk logging
        keep_alive: Durasi model tetap di VRAM (-1=permanent, 0=instant unload)
        num_ctx: Context window size
    """
    gpu_semaphore = request.app.state.gpu_limit
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    print(f"\n⏳ [LLM CLIENT] Request masuk antrean GPU. Menunggu Slot Semaphore...")

    async with gpu_semaphore:
        print(
            f"🔓 [HARDWARE GPU] Slot didapatkan! Mulai inferensi model '{model_name}'..."
        )
        inference_start_time = datetime.now()

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
            "keep_alive": keep_alive,  # Tiered: 0 (instant unload) atau -1 (lock permanent)
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

                    # Tampungan untuk mencetak jawaban utuh ke log journalctl
                    full_response = ""

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
                        # 🦾 SINKRONISASI COGNITIVE SAKTI MULTI-TABEL AMAN KENDALI (SLOT 3)
                        # ==============================================================================
                        if done:
                            inference_end_time = datetime.now()
                            elapsed_time = (inference_end_time - inference_start_time).total_seconds()
                            print("\n" + "═" * 50)
                            print(f"🤖 [AI RESPONSE] \n{full_response.strip()}")
                            print("═" * 50)
                            print(f"✨ [LLM CLIENT] Inferensi model '{model_name}' selesai dalam {elapsed_time:.2f} detik.")

                            # Proteksi: Jalankan simpan database hanya jika session_uuid valid dan bukan guest/kosong
                            if session_uuid and session_uuid != "GLOBAL_SESSION":
                                try:
                                    from backend.app.services.chat_history_service import chat_history_service

                                    user_query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "Kueri tidak terdeteksi")

                                    # 1. Simpan history chat harian untuk dipasang di komponen UI
                                    await chat_history_service.save_chat_message(
                                        session_id=session_uuid,
                                        role="assistant",
                                        text=full_response,
                                        thought="Processed via Slot 3 [Gemma Core Persona Engine]"
                                    )

                                    # 2. Simpan korpus dialog (session_id = integer FK)
                                    await chat_history_service.save_dialogue_corpus(
                                        session_uuid=session_uuid,
                                        user_text=user_query,
                                        assistant_text=full_response,
                                    )
                                    print(f"📝 [PERSONA SAVE SUCCESS] Multi-tabel untuk sesi {session_uuid[:8]} sukses dikunci!")
                                except Exception as save_err:
                                    print(f"⚠️ [MULTI-TABEL WARNING] Gagal auto-save Slot 3: {str(save_err)}")

            except httpx.TimeoutException:
                print(
                    "🚨 [LLM CLIENT] Timeout! Model terlalu lama merespons (di atas 120 detik)."
                )
                yield json.dumps(
                    {"error": "Inference timeout, server LLM sibuk."}
                ) + "\n"
            except Exception as e:
                print(f"💥 [LLM CLIENT] Critical error saat streaming LLM: {str(e)}")
                yield json.dumps(
                    {"error": f"Internal LLM Client Error: {str(e)}"}
                ) + "\n"


async def generate_json_response(
    model_name: str,
    messages: List[Dict[str, str]],
    request: Request,
    temperature: float = 0.3,
    keep_alive: int = 0,
    timeout: float = 60.0,
) -> Optional[Dict[str, Any]]:
    """
    Generate JSON response (non-streaming) untuk Layer 1 (Cognitive Analyzer) dan Layer 2 (Strategic Planner)
    
    Args:
        model_name: Model Ollama
        messages: Pesan format chat
        request: FastAPI request
        temperature: Kreativitas (lebih rendah untuk JSON consistency)
        keep_alive: Durasi di VRAM (0=instant unload)
        timeout: Timeout dalam detik
        
    Returns:
        Parsed JSON dict atau None jika error
    """
    gpu_semaphore = request.app.state.gpu_limit
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    
    print(f"\n⏳ [JSON GEN] Menunggu GPU semaphore untuk {model_name}...")
    
    async with gpu_semaphore:
        print(f"🔓 [JSON GEN] GPU slot acquired. Generating JSON from {model_name}...")
        start_time = datetime.now()
        
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_ctx": 2048},
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
                
                # Parse JSON murni
                try:
                    parsed_json = json.loads(message_content)
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    print(f"✅ [JSON GEN] JSON generated in {elapsed:.2f}s | Model: {model_name}")
                    return parsed_json
                except json.JSONDecodeError as je:
                    print(f"⚠️ [JSON GEN] JSON parse error: {str(je)}")
                    print(f"Raw content: {message_content[:200]}...")
                    return None
                    
        except httpx.TimeoutException:
            print(f"🚨 [JSON GEN] Timeout saat menghasilkan JSON dari {model_name}")
            return None
        except Exception as e:
            print(f"💥 [JSON GEN] Error: {str(e)}")
            return None
