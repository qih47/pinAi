import os
from database.db import get_db
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import numpy as np


# ==========================
# AMBIL CHUNK YANG BELUM EMBEDDING
# ==========================
def get_unembedded_chunks(limit=100):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, dokumen_id, chunk_id, content
        FROM dokumen_chunk
        WHERE embedding IS NULL
        ORDER BY created_at ASC
        LIMIT %s;
    """, (limit,))
    chunks = cur.fetchall()
    cur.close()
    conn.close()
    return chunks

# ==========================
# NORMALISASI TEKS
# ==========================
def normalize_text(text):
    t = text.strip().replace("\n", " ").replace("\r", " ")
    return " ".join(t.split())

# ==========================
# INISIALISASI MODEL EMBEDDING
# ==========================
print("🧠 Memuat model embedding (GPU ready)...")
try:
    model = SentenceTransformer("intfloat/multilingual-e5-base", device="cuda")
except Exception as e:
    print(f"⚠️ Gagal memuat model GPU, fallback ke CPU: {e}")
    model = SentenceTransformer("intfloat/multilingual-e5-base", device="cpu")

# ==========================
# GENERATE EMBEDDING
# ==========================
def get_embedding(texts):
    """Menghasilkan vektor embedding untuk list of text"""
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    return embeddings.tolist()

# ==========================
# PROSES EMBEDDING TIAP CHUNK
# ==========================
def process_embeddings():
    chunks = get_unembedded_chunks()
    if not chunks:
        print("⚠️ Tidak ada chunk yang perlu di-embedding.")
        return

    conn = get_db()
    cur = conn.cursor()

    texts = [normalize_text(c["content"]) for c in chunks]
    embeddings = get_embedding(texts)

    for idx, chunk in enumerate(chunks):
        emb = embeddings[idx]
        cur.execute("""
            UPDATE dokumen_chunk
            SET embedding = %s
            WHERE id = %s
        """, (emb, chunk["id"]))

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Selesai embed {len(chunks)} chunk ke database.")

# ==========================
# WRAPPER UNTUK DIPANGGIL DARI FLASK
# ==========================
def process_all_embeddings():
    """Wrapper agar bisa dipanggil langsung dari app.py"""
    print("🚀 Menjalankan Embedding Processor...")
    process_embeddings()
    print("🏁 Embedding Processor selesai.")

# ==========================
# MAIN STANDALONE MODE
# ==========================
if __name__ == "__main__":
    process_all_embeddings()
