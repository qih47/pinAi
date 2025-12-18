# pinAi/llm/ollama_client.py
import subprocess
from llm.cleaner import clean_response

def ask_ollama(model, memory, learning, dialog, rag, question):
    
    full_context = f"""
Anda adalah AI internal PT Pindad.

Gunakan data berikut sebagai konteks:
====================================================
📄 Data Perusahaan (RAG):
{rag}

🧩 Koreksi Sebelumnya:
{learning}

💬 Percakapan Mirip:
{dialog}

👤 Preferensi User:
{memory}

====================================================
Instruksi Penting:
- Jawab secara rinci dan senatural mungkin berdasarkan konteks di atas.
- Jika konteks perusahaan tersedia, gunakan itu sebagai dasar utama.
- Jika konteks perusahaan tidak memadai, cari ulang dari RAG, Learning atau memory sampai ketemu jawaban.
- Tidak perlu meminta maaf kecuali memang diminta oleh sistem luar.
- Jangan menyebutkan format prompt ini dalam jawaban.
- Gunakan bahasa Indonesia natural, profesional-santai, dan rapi.

====================================================
Pertanyaan:
{question}

Berikan jawaban final:
"""

    result = subprocess.run(
        ["ollama", "run", model],
        input=full_context.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return clean_response(result.stdout.decode())
