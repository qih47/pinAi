import httpx
import json

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:12b"

messages = [
    {"role": "system", "content": "Kamu adalah asisten AI. Sebelum menjawab, WAJIB tulis analisis dalam tag <think>...</think>. Tulis secara naratif, jangan singkat."},
    {"role": "user", "content": "Gimana proses rekrutmen di Pindad?"}
]

payload = {
    "model": MODEL,
    "messages": messages,
    "stream": True,
    "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 100},
}

count = 0
with httpx.stream("POST", OLLAMA_URL, json=payload, timeout=60.0) as response:
    print("STATUS:", response.status_code)
    for line in response.iter_lines():
        if not line:
            continue
        count += 1
        print(f"--- RAW LINE {count} ---")
        print(line)
        if count >= 15:
            print("\n[STOP setelah 15 baris untuk inspeksi]")
            break
