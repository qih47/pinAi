# pinAi/memory/dialogue_memory.py
import json
from database.db import get_db
from embeddings.embedder import embedder
from psycopg2.extras import RealDictCursor

def save_dialogue(user_text, assistant_text):
    emb_user = embedder.encode([user_text])[0].tolist()
    emb_ai = embedder.encode([assistant_text])[0].tolist()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ai_dialogue_corpus
        (user_text, assistant_text, embedding_user, embedding_assistant, metadata)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_text, assistant_text, emb_user, emb_ai, json.dumps({"source": "live"})))
    conn.commit()
    conn.close()

def search_dialogue(query, top_k=10):
    emb = embedder.encode([query])[0].tolist()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT user_text, assistant_text,
               1 - (embedding_user <=> %s::vector) AS similarity
        FROM ai_dialogue_corpus
        ORDER BY embedding_user <=> %s::vector
        LIMIT %s
    """, (emb, emb, top_k))
    rows = cur.fetchall()
    conn.close()
    return rows
