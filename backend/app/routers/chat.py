from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import uuid
import logging
import traceback

# Relative imports
from ..database import get_db
from ..config import settings
from ..utils.embeddings import get_embedding
from ..utils.ai_helpers import (
    smart_chat_with_context,
    generate_judul_ai,
)
from ..utils.ocr_processing import process_pdf_attachment_to_ocr

router = APIRouter()
logger = logging.getLogger(__name__)


# --- HELPER FOR DEPENDENCY INJECTION ---
# Ini menjembatani @asynccontextmanager dengan FastAPI Depends
async def get_db_conn():
    async with get_db() as conn:
        yield conn


# --- PYDANTIC MODELS ---
class ChatRequest(BaseModel):
    message: Optional[str] = None
    file_id: Optional[str] = None
    mode: str = "normal"
    session_uuid: Optional[str] = None
    attachments: List[Dict] = []
    model: Optional[str] = None
    npp: Optional[str] = None
    role: Optional[str] = "GUEST"
    fullname: Optional[str] = "Guest"


# --- ENDPOINTS ---


@router.get("/available-models")
async def get_available_models():
    models = [
        {"id": "qwen3:8b", "name": "Qwen 3 (8B)"},
        {"id": "qwen2.5:14b-instruct", "name": "Qwen 2.5-Instruct (14b)"},
        {"id": "qwen3-vl:8b", "name": "qwen 3 vl (8b)"},
        {"id": "llama3.1:8b", "name": "Llama 3.1 (8b)"},
    ]
    return {"status": "success", "data": models}


@router.post("/chat")
async def chat(request: ChatRequest, conn=Depends(get_db_conn)):
    try:
        user_message = request.message or ""
        selected_model = request.model if request.npp else settings.primary_model
        session_uuid = request.session_uuid
        username = request.fullname
        npp = request.npp
        role = request.role

        print(
            f"\n🚀 CHAT INCOMING | User: {username} | NPP: {npp} | Attachments: {len(request.attachments)}"
        )

        current_session_id = None
        judul_baru = None

        # 1. Handle Session
        if session_uuid:
            sess = await conn.fetchrow(
                "SELECT id FROM chat_sessions WHERE session_uuid = $1", session_uuid
            )
            if sess:
                current_session_id = sess["id"]

        if not current_session_id:
            if not session_uuid:
                session_uuid = str(uuid.uuid4())
            judul_baru = await generate_judul_ai(user_message)
            current_session_id = await conn.fetchval(
                """
                INSERT INTO chat_sessions (session_uuid, user_name, npp, judul, model_name, is_active)
                VALUES ($1, $2, $3, $4, $5, TRUE) RETURNING id
                """,
                session_uuid,
                username,
                npp,
                judul_baru,
                selected_model,
            )

        # 2. OCR Logic
        ocr_context = ""
        for att in request.attachments:
            mime_type = att.get("type", "").lower()
            if "application/pdf" in mime_type or att.get("name", "").endswith(".pdf"):
                extracted_text = await process_pdf_attachment_to_ocr(
                    attachment=att,
                    npp=npp,
                    session_id=current_session_id,
                    get_embedding_func=get_embedding,
                )
                if extracted_text:
                    ocr_context += extracted_text

        # 3. Final Message Prep
        active_file = None
        final_message_to_ai = user_message

        if ocr_context and len(ocr_context.strip()) > 10:
            active_file = {"text": ocr_context, "name": "Dokumen Terlampir"}
            final_message_to_ai = f"INSTRUKSI USER: {user_message}\n\nDATA DOKUMEN HASIL SCAN:\n{ocr_context}"

        # 4. Get AI Response
        reply, pdf_info, should_include_pdf = await smart_chat_with_context(
            user_message=final_message_to_ai,
            active_file=active_file,
            mode=request.mode,
            model=selected_model,
            session_uuid=session_uuid,
            npp=npp,
            role=role,
            attachments=request.attachments,
        )

        # 5. Handle Embeddings
        try:
            # Gunakan helper format dari database.py jika perlu,
            # atau pastikan string format vector sesuai '[0.1, 0.2, ...]'
            v_user = get_embedding(user_message) or ([0.0] * 768)
            v_assistant = get_embedding(reply) or ([0.0] * 768)
            vector_user = f"[{','.join(map(str, v_user))}]"
            vector_assistant = f"[{','.join(map(str, v_assistant))}]"
        except Exception as emb_e:
            logger.warning(f"Gagal embedding: {emb_e}")
            vector_user = vector_assistant = f"[{','.join(['0.0'] * 768)}]"

        # 6. Simpan ke ai_dialogue_corpus
        await conn.execute(
            """
            INSERT INTO ai_dialogue_corpus (
                session_id, user_text, assistant_text, 
                embedding_user, embedding_assistant, metadata, files
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            current_session_id,
            user_message,
            reply,
            vector_user,
            vector_assistant,
            json.dumps({"mode": request.mode, "model": selected_model}),
            json.dumps(request.attachments),
        )

        return {
            "reply": reply,
            "session_uuid": session_uuid,
            "judul": judul_baru,
            "pdf_info": pdf_info if (should_include_pdf and npp) else None,
            "is_from_document": (should_include_pdf or ocr_context != ""),
            "model_used": selected_model,
            "attachments": request.attachments,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-history/{npp}")
async def get_chat_history(npp: str, conn=Depends(get_db_conn)):
    rows = await conn.fetch(
        """
        SELECT session_uuid, judul, started_at, is_pinned  
        FROM chat_sessions 
        WHERE npp = $1 AND is_active = TRUE AND is_deleted = false  
        ORDER BY is_pinned DESC, started_at DESC 
        """,
        npp,
    )
    return {"status": "success", "data": [dict(r) for r in rows]}


@router.get("/chat-messages/{session_uuid}")
async def get_session_messages(session_uuid: str, conn=Depends(get_db_conn)):
    sess = await conn.fetchrow(
        "SELECT id FROM chat_sessions WHERE session_uuid = $1", session_uuid
    )
    if not sess:
        return {"status": "error", "message": "Sesi tidak ditemukan"}

    rows = await conn.fetch(
        "SELECT user_text, assistant_text, created_at, files FROM ai_dialogue_corpus WHERE session_id = $1 ORDER BY created_at ASC",
        sess["id"],
    )

    formatted_messages = []
    for row in rows:
        ts = row["created_at"].strftime("%H:%M")

        # --- PERBAIKAN DI SINI ---
        raw_files = row.get("files")
        attachments = []

        if raw_files:
            try:
                # Jika data berupa string (JSON), kita parse jadi list
                if isinstance(raw_files, str):
                    attachments = json.loads(raw_files)
                # Jika sudah berupa list (otomatis diparse asyncpg)
                elif isinstance(raw_files, list):
                    attachments = raw_files
            except Exception as e:
                logger.error(f"Gagal parse attachments: {e}")
                attachments = []
        # --------------------------

        formatted_messages.append(
            {
                "id": f"u-{row['created_at'].timestamp()}",
                "sender": "user",
                "text": row["user_text"],
                "attachments": attachments,  # Pastikan ini selalu LIST []
                "timestamp": ts,
            }
        )
        formatted_messages.append(
            {
                "id": f"a-{row['created_at'].timestamp()}",
                "sender": "ai",
                "text": row["assistant_text"],
                "attachments": [],  # Assistant biasanya kosong
                "timestamp": ts,
            }
        )

    return {"status": "success", "data": formatted_messages}


@router.post("/chat/pin/{session_uuid}")
async def toggle_pin_chat(session_uuid: str, conn=Depends(get_db_conn)):
    row = await conn.fetchrow(
        "UPDATE chat_sessions SET is_pinned = NOT is_pinned WHERE session_uuid = $1 RETURNING is_pinned",
        session_uuid,
    )
    if row:
        return {"status": "success", "is_pinned": row["is_pinned"]}
    return {"status": "error", "message": "Session tidak ditemukan"}


@router.post("/chat/rename/{session_uuid}")
async def rename_chat(
    session_uuid: str, data: dict = Body(...), conn=Depends(get_db_conn)
):
    await conn.execute(
        "UPDATE chat_sessions SET judul = $1 WHERE session_uuid = $2",
        data.get("judul"),
        session_uuid,
    )
    return {"status": "success"}


@router.post("/chat/delete/{session_uuid}")
async def delete_chat(session_uuid: str, conn=Depends(get_db_conn)):
    await conn.execute(
        "UPDATE chat_sessions SET is_deleted = true WHERE session_uuid = $1",
        session_uuid,
    )
    return {"status": "success"}
