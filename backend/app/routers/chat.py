import uuid
import json
import traceback
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict

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


# --- DATABASE DEPENDENCY ---
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
        {"id": "qwen3-vl:8b", "name": "Qwen 3 VL (8B)"},
        {"id": "llama3.1:8b", "name": "Llama 3.1 (8B)"},
    ]
    return {"status": "success", "data": models}


@router.post("/chat")
async def chat(
    request: Request,
    chat_data: ChatRequest,
    background_tasks: BackgroundTasks,
    conn=Depends(get_db_conn),
):
    gpu_limit = request.app.state.gpu_limit

    try:
        user_message = chat_data.message or ""
        selected_model = chat_data.model if chat_data.npp else settings.primary_model
        session_uuid = chat_data.session_uuid
        username = chat_data.fullname
        npp = chat_data.npp
        role = chat_data.role

        current_session_id = None
        judul_baru = "Percakapan Baru"

        # 1. Handle Session
        if session_uuid:
            sess = await conn.fetchrow(
                "SELECT id, judul FROM chat_sessions WHERE session_uuid = $1",
                session_uuid,
            )
            if sess:
                current_session_id = sess["id"]
                judul_baru = sess["judul"]

        if not current_session_id:
            if not session_uuid:
                session_uuid = str(uuid.uuid4())

            # ✅ Optimasi: Hanya generate judul AI untuk user login
            if npp:
                judul_baru = await generate_judul_ai(user_message)
            else:
                judul_baru = (
                    (user_message[:30] + "...")
                    if user_message.strip()
                    else "Percakapan Baru"
                )

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

        # --- AREA ANTREAN GPU (Semaphore) ---
        async with gpu_limit:
            logger.info(f"🔒 [GPU LOCK] Processing request for: {username}")

            # 2. OCR Logic (✅ Optimasi validasi)
            ocr_context = ""
            for att in chat_data.attachments:
                if not att or not isinstance(att, dict):
                    continue

                mime_type = att.get("type", "").lower()
                file_name = att.get("name", "")

                if mime_type == "application/pdf" or (
                    file_name and file_name.lower().endswith(".pdf")
                ):
                    extracted_text = await process_pdf_attachment_to_ocr(
                        attachment=att,
                        npp=npp,
                        session_id=current_session_id,
                        get_embedding_func=get_embedding,
                    )
                    if extracted_text:
                        ocr_context += extracted_text

            # 3. Message Prep
            active_file = None
            final_message_to_ai = user_message
            if ocr_context and len(ocr_context.strip()) > 10:
                active_file = {"text": ocr_context, "name": "Dokumen Terlampir"}
                final_message_to_ai = (
                    f"INSTRUKSI USER: {user_message}\n\nDATA DOKUMEN:\n{ocr_context}"
                )

            # 4. Get AI Response
            reply, pdf_info, should_include_pdf = await smart_chat_with_context(
                user_message=final_message_to_ai,
                active_file=active_file,
                mode=chat_data.mode,
                model=selected_model,
                session_uuid=session_uuid,
                npp=npp,
                role=role,
                attachments=chat_data.attachments,
                background_tasks=background_tasks,
            )

            logger.info(f"🔓 [GPU UNLOCK] Finished request for: {username}")

        # --- END AREA ANTREAN GPU ---

        # 5. Simpan Dialogue DULU tanpa embedding (isi dummy)
        dummy_vector = str([0.0] * 1024)
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
            dummy_vector,
            dummy_vector,
            json.dumps({"mode": chat_data.mode, "model": selected_model}),
            json.dumps(chat_data.attachments),
        )

        # 6. Jalankan embedding di background
        from ..services.background_tasks import update_dialogue_embeddings

        background_tasks.add_task(
            update_dialogue_embeddings, current_session_id, user_message, reply
        )

        return {
            "reply": reply,
            "session_uuid": session_uuid,
            "judul": judul_baru,
            "pdf_info": pdf_info if (should_include_pdf and npp) else None,
            "is_from_document": (should_include_pdf or ocr_context != ""),
            "model_used": selected_model,
            "attachments": chat_data.attachments,
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

        # Parse Attachments safely
        raw_files = row.get("files")
        attachments = []
        if raw_files:
            try:
                attachments = (
                    raw_files if isinstance(raw_files, list) else json.loads(raw_files)
                )
            except:
                attachments = []

        formatted_messages.append(
            {
                "id": f"u-{row['created_at'].timestamp()}",
                "sender": "user",
                "text": row["user_text"],
                "attachments": attachments,
                "timestamp": ts,
            }
        )
        formatted_messages.append(
            {
                "id": f"a-{row['created_at'].timestamp()}",
                "sender": "ai",
                "text": row["assistant_text"],
                "attachments": [],
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
