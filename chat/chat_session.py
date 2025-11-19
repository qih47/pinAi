# pinAi/chat/chat_session.py
from database.db import get_db
from psycopg2.extras import RealDictCursor
import uuid
from embeddings.embedder import embedder

def create_chat(model):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_sessions(session_uuid, user_name, model_name, started_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id
    """, (str(uuid.uuid4()), "anonymous", model))
    session_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return session_id

def save_chat_message(session_id, role, text):
    emb = embedder.encode([text])[0].tolist()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages(session_id, role, message_text, embedding, timestamp)
        VALUES (%s, %s, %s, %s, NOW())
    """, (session_id, role, text, emb))
    conn.commit()
    conn.close()

def get_chat_sessions():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT cs.id, cs.session_uuid, cs.model_name, cs.started_at,
               COUNT(cm.id) AS message_count
        FROM chat_sessions cs
        LEFT JOIN chat_messages cm ON cm.session_id = cs.id
        GROUP BY cs.id
        ORDER BY cs.started_at DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_session_messages(session_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT role, message_text, timestamp
        FROM chat_messages
        WHERE session_id=%s
        ORDER BY timestamp ASC
    """, (session_id,))
    rows = cur.fetchall()
    conn.close()
    return rows
