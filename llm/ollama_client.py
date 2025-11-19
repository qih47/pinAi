# pinAi/llm/ollama_client.py
import subprocess
from llm.cleaner import clean_response

def ask_ollama(model, memory, learning, dialog, rag, question):
    full_context = f"""
MEMORY USER:
{memory}

KOREKSI YANG PERNAH DISIMPAN:
{learning}

PERCAKAPAN MIRIP SEBELUMNYA:
{dialog}

REFERENSI DARI DOKUMEN:
{rag}

PERTANYAAN:
{question}

Instruksi:
- Jawablah secara rinci, akurat dan senatural mungkin berdasarkan konteks di atas.
- Jawab singkat senatural mungkin jika itu percakapan sehari-hari.
- Gunakan memori user dan koreksi.
- Jangan halu; gunakan data perusahaan sebagai prioritas.
- Bahasa Indonesia natural dan rapi.
"""
    result = subprocess.run(
        ["ollama", "run", model],
        input=full_context.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return clean_response(result.stdout.decode())
