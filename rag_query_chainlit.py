import chainlit as cl
import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import subprocess, uuid, datetime

# ====================================================
# KONFIG DATABASE
# ====================================================
DB_CONFIG = {
    "host": "localhost",
    "database": "ragdb",
    "user": "pindadai",
    "password": "Pindad123!"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# ====================================================
# LOAD EMBEDDING MODEL
# ====================================================
embedder = SentenceTransformer("intfloat/multilingual-e5-base", device="cuda")

def search_similar(query_text, top_k=5):
    emb = embedder.encode([query_text], convert_to_numpy=True)[0].tolist()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, dokumen_id, chunk_id, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM dokumen_chunk
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """, (emb, emb, top_k))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

# ====================================================
# MODEL OLLAMA
# ====================================================
def get_ollama_models():
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        lines = result.stdout.strip().splitlines()
        models = [line.split()[0] for line in lines[1:] if line.strip()]
        return models or ["qwen2.5:7b", "deepseek-coder:6.7b","deepseek-coder-v2:16b"]
    except Exception as e:
        print(f"⚠️ Gagal membaca model Ollama: {e}")
        return ["qwen2.5:7b", "deepseek-coder:6.7b","deepseek-coder-v2:16b"]

def ask_ollama(model, context, question):
    prompt = f"""
Konteks:
{context}

Pertanyaan:
{question}

Jawablah secara rinci dan senatural mungkin berdasarkan konteks di atas, jika tidak ditemukan jawab sesingkat mungkin kesimpulanya.
"""
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE
    )
    return result.stdout.decode("utf-8")

# ====================================================
# DATABASE HANDLER
# ====================================================
def create_chat_session(model_name, user_name="anonymous"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_sessions (session_uuid, user_name, model_name, started_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id;
    """, (str(uuid.uuid4()), user_name, model_name))  # 🔧 UUID diubah ke string
    session_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return session_id


def save_chat_message(session_id, role, message_text):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (session_id, role, message_text, timestamp)
        VALUES (%s, %s, %s, NOW());
    """, (session_id, role, message_text))
    conn.commit()
    cur.close()
    conn.close()

# ====================================================
# CHAINLIT APP
# ====================================================
@cl.on_chat_start
async def on_chat_start():
    models = get_ollama_models()
    actions = [
        cl.Action(label=name, name=name, value=name, payload={"model": name})
        for name in models
    ]

    msg = cl.AskActionMessage(
        content="🧠 Pilih model Ollama yang ingin digunakan:",
        actions=actions
    )
    choice = await msg.send()

    selected_model = (
        choice.get("payload", {}).get("model") or choice.get("name") or models[0]
        if models else "qwen2.5:7b"
    )

    # ✅ buat session baru dan simpan ke DB
    session_id = create_chat_session(selected_model)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("selected_model", selected_model)

    await cl.Message(
        content=f"✅ Model terpilih: **{selected_model}**.\nKetik pertanyaanmu di bawah 👇"
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    model = cl.user_session.get("selected_model", "qwen2.5:7b")
    session_id = cl.user_session.get("session_id")
    question = message.content

    # ✅ simpan pertanyaan user
    save_chat_message(session_id, "user", question)

    await cl.Message(content="🔍 Mencari konteks relevan di database...").send()
    results = search_similar(question)
    context = "\n\n".join([r["content"] for r in results])

    await cl.Message(content=f"⚙️ Menjalankan inferensi dengan model **{model}** ...").send()
    answer = ask_ollama(model, context, question)

    # ✅ simpan jawaban LLM
    save_chat_message(session_id, "assistant", answer)

    await cl.Message(
        content=f"📚 **Konteks (Top 3):**\n\n{context[:500]}...\n\n💬 **Jawaban:**\n{answer}"
    ).send()
