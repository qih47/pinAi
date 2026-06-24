import asyncio
import httpx
import json

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma4:12b"

async def test_native_thinking(enable_thinking: bool):
    print(f"\n🚀 ===== MENGETES MODEL: {MODEL_NAME} (THINKING: {enable_thinking}) =====")
    
    # 🔴 PERBAIKAN 1: Pindahkan "think" ke root level payload utama!
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": "Tuliskan 3 langkah singkat implementasi audit logging database."}
        ],
        "stream": True,
        "think": enable_thinking,  # 🔥 SEKARANG DI SINI JALUR RESMI OLLAMA API
        "options": {
            "temperature": 1.0,  # Gemma 4 direkomendasikan temp 1.0 untuk reasoning
            "top_p": 0.95,
            "top_k": 64
        }
    }

    timeout = httpx.Timeout(120.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("POST", OLLAMA_URL, json=payload) as response:
                if response.status_code != 200:
                    print(f"❌ HTTP Error {response.status_code}")
                    return

                print("⌛ Menerima stream data dari Ollama...\n")
                has_printed_thinking_header = False
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    chunk = json.loads(line)
                    message = chunk.get("message", {})
                    
                    # 🔴 PERBAIKAN 2: Ganti key "thought" menjadi "thinking" sesuai API resmi Ollama!
                    thought_chunk = message.get("thinking", "")
                    content_chunk = message.get("content", "")
                    
                    if thought_chunk:
                        if not has_printed_thinking_header:
                            print("\n[TERMINAL OLLAMA] Thinking...")
                            print("[TERMINAL OLLAMA] Thinking Process:\n", end="", flush=True)
                            has_printed_thinking_header = True
                        print(thought_chunk, end="", flush=True)
                        
                    if content_chunk:
                        if has_printed_thinking_header:
                            print("\n[TERMINAL OLLAMA] ...done thinking.\n")
                            has_printed_thinking_header = False 
                        print(content_chunk, end="", flush=True)

                print("\n\n✅ Stream selesai dijalankan dengan aman.")
        except Exception as e:
            print(f"❌ Terjadi gangguan koneksi: {e}")

if __name__ == "__main__":
    asyncio.run(test_native_thinking(enable_thinking=False))