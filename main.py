from flask import Flask, render_template, request, jsonify

# ==== IMPORT CONFIG ====
from app_config import SECRET_KEY, MODEL_LIST

# ==== IMPORT MODULE INTERNAL ====
from nlp.intent import is_memory_instruction, is_correction

from memory.user_memory import save_user_memory, get_relevant_user_memory
from memory.correction_memory import save_correction, search_learning
from memory.dialogue_memory import save_dialogue, search_dialogue

from rag.rag_search import search_rag
from tools.anti_halu import is_corporate_answer_possible

from llm.ollama_client import ask_ollama

from chat.chat_session import (
    create_chat,
    save_chat_message,
    get_chat_sessions,
    get_session_messages
)

from database.db import get_db

# ====================================================
# FLASK APP CONFIG
# ====================================================
app = Flask(__name__)
app.secret_key = SECRET_KEY


# ====================================================
# ROUTES
# ====================================================
@app.route("/")
def index():
    sessions = get_chat_sessions()
    return render_template("askIndex.html", sessions=sessions, models=MODEL_LIST)


@app.route("/chat/<int:session_id>")
def chat_session(session_id):
    sessions = get_chat_sessions()
    messages = get_session_messages(session_id)

    current = next((s for s in sessions if s["id"] == session_id), None)
    if not current:
        return "Session Not Found", 404

    return render_template(
        "chat.html",
        sessions=sessions,
        models=MODEL_LIST,
        current_session=current,
        messages=messages
    )


@app.route("/api/new_chat", methods=["POST"])
def new_chat():
    model = request.json["model"]
    session_id = create_chat(model)
    return jsonify({"success": True, "redirect_url": f"/chat/{session_id}"})


@app.route("/api/send_message", methods=["POST"])
def api_send_message():
    data = request.json
    session_id = data["session_id"]
    question = data["message"]
    model = data["model"]

    save_chat_message(session_id, "user", question)

    # 1. Memory instruction
    if is_memory_instruction(question):
        save_user_memory(question, question)
        reply = "Siap bro, sudah aku ingat!"
        save_chat_message(session_id, "assistant", reply)
        return jsonify({"success": True, "answer": reply})

    # 2. Correction
    if is_correction(question):
        save_correction(question, question)
        reply = "Oke bro, koreksi sudah aku simpan!"
        save_chat_message(session_id, "assistant", reply)
        return jsonify({"success": True, "answer": reply})

    # 3. Gather memory sources
    memory_items = get_relevant_user_memory(question)
    memory_text = "\n".join([f"- {m['value']}" for m in memory_items])

    learning_items = search_learning(question)
    learning_text = "\n".join([f"- {l['corrected_answer']}" for l in learning_items])

    dialog_items = search_dialogue(question)
    dialog_text = "\n".join(
        [f"USER: {d['user_text']}\nAI: {d['assistant_text']}" for d in dialog_items]
    )

    rag_items = search_rag(question)
    rag_text = "\n".join([r["content"] for r in rag_items])

    # 4. Anti halu
    if not is_corporate_answer_possible(rag_items, learning_items, memory_items):
        answer = (
            "Maaf bro, tidak ada informasi mengenai hal tersebut "
            "pada dokumen perusahaan maupun data pembelajaran yang tersedia."
        )
        save_chat_message(session_id, "assistant", answer)
        save_dialogue(question, answer)
        return jsonify({"success": True, "answer": answer})

    # 5. Generate final answer
    answer = ask_ollama(
        model,
        memory_text,
        learning_text,
        dialog_text,
        rag_text,
        question
    )

    save_chat_message(session_id, "assistant", answer)
    save_dialogue(question, answer)

    return jsonify({"success": True, "answer": answer})


@app.route("/api/switch_model", methods=["POST"])
def switch_model():
    data = request.json
    session_id = data["session_id"]
    new_model = data["model"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE chat_sessions SET model_name=%s WHERE id=%s",
                (new_model, session_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


# ====================================================
# RUN SERVER
# ====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
