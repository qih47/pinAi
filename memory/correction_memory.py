# pinAi/memory/correction_memory.py
from database.db import get_db
from embeddings.embedder import embedder
from psycopg2.extras import RealDictCursor

def save_correction(question, corrected):
    emb = embedder.encode([question])[0].tolist()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ai_learning (question_text, corrected_answer, embedding)
        VALUES (%s, %s, %s)
    """, (question, corrected, emb))
    conn.commit()
    conn.close()

def search_learning(query, top_k=10):
    emb = embedder.encode([query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT question_text, corrected_answer,
               1 - (embedding <=> %s::vector) AS similarity
        FROM ai_learning
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (emb, emb, top_k))

    rows = cur.fetchall()
    conn.close()
    return rows
