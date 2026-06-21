import httpx
import json

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:12b"

# ── 1. FUNGSI UNTUK EMULASI PEMOTONGAN STREAM ──────────────────────────────────
def stream_and_truncate(messages, max_chunks=25):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 150},
    }
    collected_thinking = ""
    collected_content = ""
    chunk_count = 0
    
    with httpx.stream("POST", OLLAMA_CHAT_URL, json=payload, timeout=60.0) as response:
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            msg = chunk.get("message", {})
            
            # Mendukung format token internal Ollama untuk thinking/content
            thinking = msg.get("thinking", "")
            content = msg.get("content", "")
            
            if thinking:
                collected_thinking += thinking
                print(f"[THINK] {thinking}", end="", flush=True)
            if content:
                collected_content += content
                print(f"[CONTENT] {content}", end="", flush=True)
                
            chunk_count += 1
            if chunk_count >= max_chunks:
                print("\n\n[--- ✂️ DIPOTONG MANUAL DI SINI ---]\n")
                break
                
    return collected_thinking, collected_content


# ── 2. FUNGSI UNTUK GENERATE TEMPLATE RAW PREFILL ──────────────────────────────
def build_raw_prompt_with_prefill(user_instruction, truncated_thinking):
    # Injeksi manual sesuai struktur Chat Template Gemma 4
    prompt = (
        f"<start_of_turn>system\n"
        f"Kamu adalah asisten AI. Sebelum menjawab, WAJIB tulis analisis dalam tag <think>...</think>.\n"
        f"<end_of_turn>\n"
        f"<start_of_turn>user\n"
        f"{user_instruction}\n"
        f"<end_of_turn>\n"
        f"<start_of_turn>assistant\n"
        f"<think>{truncated_thinking}"  # Prefill disuntik di sini tanpa penutup
    )
    return prompt


# ======================================================================
# EXECUTION PHASE
# ======================================================================

print("=" * 70)
print("REQUEST 1: Generate awal, dipotong manual di tengah <thinking>")
print("=" * 70)

user_q = "Gimana proses rekrutmen di Pindad?"
messages_1 = [
    {"role": "system", "content": "Kamu adalah asisten AI. Sebelum menjawab, WAJIB tulis analisis dalam tag <think>...</think>."},
    {"role": "user", "content": user_q}
]

# Jalankan Request 1 dulu agar variabel terdefinisi secara nyata
truncated_thinking, truncated_content = stream_and_truncate(messages_1, max_chunks=25)

print("THINKING terpotong:", repr(truncated_thinking))
print("CONTENT terpotong:", repr(truncated_content))


print("\n" + "=" * 70)
print("REQUEST 2 - VARIAN C: True Prefill via /api/generate + raw=True")
print("=" * 70)

# Sekarang variable 'truncated_thinking' dijamin aman & aman dari NameError
raw_prompt = build_raw_prompt_with_prefill(user_q, truncated_thinking)

payload_2c = {
    "model": MODEL,
    "prompt": raw_prompt,
    "stream": True,
    "raw": True,  # Kunci utama bypass parser template
    "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 150},
}

print("\n--- OUTPUT VARIAN C (RESUMING THINKING) ---\n")
try:
    with httpx.stream("POST", OLLAMA_GENERATE_URL, json=payload_2c, timeout=60.0) as response:
        print("STATUS:", response.status_code)
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            text_chunk = chunk.get("response", "")
            print(text_chunk, end="", flush=True)
            
except Exception as e:
    print("ERROR VARIAN C:", e)

print("\n\n" + "=" * 70)
print("SELESAI - Cek terminal untuk melihat kelanjutan penalaran model!")
print("=" * 70)