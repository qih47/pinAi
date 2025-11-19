import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import numpy as np
import subprocess
import json

# ==========================
# CONFIG DATABASE
# ==========================
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!"
}

# ==========================
# KONEKSI DATABASE
# ==========================
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# ==========================
# INISIALISASI MODEL EMBEDDING
# ==========================
print("🧠 Memuat model embedding untuk pencarian...")
embedder = SentenceTransformer("intfloat/multilingual-e5-base", device="cuda")

# ==========================
# AMBIL DOKUMEN SERUPA
# ==========================
def search_similar(query_text, top_k=3):
    """Cari chunk paling relevan dari PostgreSQL"""
    query_emb = embedder.encode([query_text], convert_to_numpy=True)[0].tolist()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id, dokumen_id, chunk_id, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM dokumen_chunk
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """, (query_emb, query_emb, top_k))

    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

# ==========================
# KIRIM KE OLLAMA UNTUK JAWABAN
# ==========================
def ask_ollama(context, question):
    """Panggil model deepseek-coder via ollama CLI"""
    prompt = f"""
Konteks:
{context}

Pertanyaan:
{question}

Berikan jawaban sejelas dan seakurat mungkin berdasarkan konteks di atas.
"""
    result = subprocess.run(
        ["ollama", "run", "qwen2.5:7b"],
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE
    )
    return result.stdout.decode("utf-8")

# ==========================
# MAIN TEST
# ==========================
if __name__ == "__main__":
    print("🧩 Tes sistem tanya jawab berbasis RAG")
    user_question = input("\n❓ Masukkan pertanyaanmu: ")

    # 1️⃣ Cari context dari DB
    results = search_similar(user_question)
    combined_context = "\n\n".join([r["content"] for r in results])

    print(f"\n📚 Mengambil {len(results)} konteks relevan dari database...")

    # 2️⃣ Kirim ke model Ollama
    answer = ask_ollama(combined_context, user_question)

    print("\n💬 Jawaban Model:")
    print("=" * 80)
    print(answer)
    print("=" * 80)
