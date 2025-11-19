# pinAi/rag/rag_search.py
from database.db import get_db
from embeddings.embedder import embedder
from psycopg2.extras import RealDictCursor

def search_rag(query, top_k=15):
    emb = embedder.encode([query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT 'chunk' AS source,
               c.content, d.judul, d.nomor,
               1 - (c.embedding <=> %s::vector) AS similarity
        FROM dokumen_chunk c
        JOIN dokumen d ON d.id = c.dokumen_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT 20
    """, (emb, emb))
    chunks = cur.fetchall()

    cur.execute("""
        SELECT 'metadata' AS source,
               CONCAT(d.judul, ' ', d.nomor) AS content,
               d.judul, d.nomor,
               similarity((d.judul || ' ' || d.nomor), %s) AS similarity
        FROM dokumen d
        WHERE d.judul ILIKE %s OR d.nomor ILIKE %s
        ORDER BY similarity DESC
        LIMIT 20
    """, (query, f"%{query}%", f"%{query}%"))
    meta = cur.fetchall()

    conn.close()
    res = chunks + meta
    return sorted(res, key=lambda x: x["similarity"], reverse=True)[:top_k]
