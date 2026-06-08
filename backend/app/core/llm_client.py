import httpx
import json
import logging
from fastapi import Request
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_LLM")


async def stream_ollama_chat(
    model_name: str,
    messages: List[Dict[str, str]],
    request: Request,
    temperature: float = 0.7,
    session_uuid: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Generator asinkronus untuk melakukan streaming response dari Ollama secara real-time.
    Mengamankan antrean VRAM menggunakan global GPU Semaphore (limit maks: 2).
    Serta mengunci model di background agar tidak terkena auto-unload.
    """
    gpu_semaphore = request.app.state.gpu_limit
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    print(f"\n⏳ [LLM CLIENT] Request masuk antrean GPU. Menunggu Slot Semaphore...")

    async with gpu_semaphore:
        print(
            f"🔓 [HARDWARE GPU] Slot didapatkan! Mulai inferensi model '{model_name}'..."
        )

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": 4096},
            "keep_alive": -1,  # Model dikunci di VRAM agar siaga terus di background
        }

        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(limits=limits, timeout=120.0) as client:
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
                            print("\n" + "═" * 50)
                            print(f"🤖 [AI RESPONSE] \n{full_response.strip()}")
                            print("═" * 50)
                            print(f"✨ [LLM CLIENT] Inferensi model '{model_name}' selesai.")

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
