# pinAi/memory/user_memory.py
import json
from database.db import get_db
from embeddings.embedder import embedder
from psycopg2.extras import RealDictCursor

def save_user_memory(key, value):
    emb = embedder.encode([key])[0].tolist()
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM ai_user_profile WHERE key=%s", (key,))
    exists = cur.fetchone()

    if exists:
        cur.execute("""
            UPDATE ai_user_profile 
            SET value=%s, embedding=%s, updated_at=NOW()
            WHERE key=%s
        """, (value, emb, key))
    else:
        cur.execute("""
            INSERT INTO ai_user_profile (key, value, embedding)
            VALUES (%s, %s, %s)
        """, (key, value, emb))

    conn.commit()
    conn.close()

def get_relevant_user_memory(query, top_k=10):
    emb = embedder.encode([query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT key, value,
               1 - (embedding <=> %s::vector) AS similarity
        FROM ai_user_profile
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (emb, emb, top_k))

    rows = cur.fetchall()
    conn.close()
    return rows
