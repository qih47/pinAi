import httpx
import json

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:12b"

def stream_and_truncate(messages, max_tokens=40):
    """Generate dan stop manual setelah ~max_tokens token, return teks terpotong."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 200},
    }
    collected = ""
    token_count = 0
    with httpx.stream("POST", OLLAMA_URL, json=payload, timeout=60.0) as response:
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            content = chunk.get("message", {}).get("content", "")
            if content:
                collected += content
                token_count += 1
                print(content, end="", flush=True)
            if token_count >= max_tokens:
                print("\n\n[--- DIPOTONG MANUAL DI SINI ---]\n")
                break
    return collected


print("=" * 70)
print("REQUEST 1: Generate awal, akan dipotong manual")
print("=" * 70)

messages_1 = [
    {"role": "system", "content": "Kamu adalah asisten AI. Sebelum menjawab, WAJIB tulis analisis dalam tag <think>...</think>. Tulis secara naratif, jangan singkat."},
    {"role": "user", "content": "Gimana proses rekrutmen di Pindad?"}
]

truncated_thinking = stream_and_truncate(messages_1, max_tokens=40)

print("\n" + "=" * 70)
print("TEKS YANG DIPOTONG (akan dipakai sebagai prefill):")
print("=" * 70)
print(repr(truncated_thinking))

print("\n" + "=" * 70)
print("REQUEST 2: Kirim balik sebagai assistant prefill, minta lanjut")
print("=" * 70)

messages_2 = [
    {"role": "system", "content": "Kamu adalah asisten AI. Sebelum menjawab, WAJIB tulis analisis dalam tag <think>...</think>. Tulis secara naratif, jangan singkat."},
    {"role": "user", "content": "Gimana proses rekrutmen di Pindad?"},
    {"role": "assistant", "content": truncated_thinking}
]

payload_2 = {
    "model": MODEL,
    "messages": messages_2,
    "stream": True,
    "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 200},
}

print("\n--- OUTPUT REQUEST 2 (perhatikan: nyambung atau mulai ulang?) ---\n")
with httpx.stream("POST", OLLAMA_URL, json=payload_2, timeout=60.0) as response:
    for line in response.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        content = chunk.get("message", {}).get("content", "")
        if content:
            print(content, end="", flush=True)

print("\n\n" + "=" * 70)
print("SELESAI — analisis manual: apakah output Request 2 MELANJUTKAN")
print("kalimat dari Request 1, atau malah mulai <think> baru dari nol?")
print("=" * 70)
