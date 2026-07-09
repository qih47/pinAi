import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.config import settings
from backend.app.services.chat.chat_history_service import chat_history_service
from backend.app.api.schemas.chat import TitleUpdateSchema

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")

@router.get("/sessions")
async def get_history_sessions(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    if not current_user_npp:
        return {"status": "success", "data": []}
    sessions = await chat_history_service.get_user_sessions(current_user_npp)
    return {"status": "success", "data": sessions}

@router.get("/sessions/{session_uuid}")
async def get_chat_session(
    session_uuid: str,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    session = await chat_history_service.get_session(session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "data": session}
@router.post("/sessions/create")
async def create_new_chat_session(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
    judul: Optional[str] = Query("Obrolan Baru"),
):
    npp_target = current_user_npp if current_user_npp else "GUEST"
    name_target = "Pegawai Pindad" if current_user_npp else "Guest User"
    
    # Just use 'Obrolan Baru' or the provided string, without blocking for LLM
    initial_title = "Obrolan Baru"

    new_session = await chat_history_service.create_new_session(
        npp=npp_target,
        username=name_target,
        model_name=settings.MODEL_PERSONA,
        judul=initial_title,
    )
    # UI uses this to initialize the sidebar
    if "judul" not in new_session:
        new_session["judul"] = initial_title
        
    return {"status": "success", "data": new_session}


@router.put("/sessions/{session_uuid}/title")
async def rename_chat_title(session_uuid: str, payload: TitleUpdateSchema):
    success = await chat_history_service.update_session_title(
        session_uuid, payload.judul
    )
    if not success:
        raise HTTPException(status_code=500, detail="Gagal memperbarui judul sesi.")
    return {"status": "success", "message": "Judul sesi berhasil diperbarui!"}


@router.put("/sessions/{session_uuid}/pin")
async def pin_chat_session(session_uuid: str, is_pinned: bool = Query(...)):
    success = await chat_history_service.toggle_pin_session(session_uuid, is_pinned)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal merubah status sematan.")
    return {"status": "success", "message": "Status sematan berhasil diperbarui!"}


@router.delete("/sessions/{session_uuid}")
async def delete_chat_session(session_uuid: str):
    success = await chat_history_service.soft_delete_session(session_uuid)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal menghapus sesi.")
    return {"status": "success", "message": "Sesi berhasil dihapus!"}


@router.get("/sessions/{session_uuid}/messages")
async def get_session_messages_endpoint(session_uuid: str):
    messages = await chat_history_service.get_session_messages(session_uuid)
    return {"status": "success", "data": messages}

@router.put("/sessions/{session_uuid}/assign")
async def assign_chat_session(
    session_uuid: str,
    current_user_npp: Optional[str] = Depends(get_current_user_npp)
):
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Karena API ini dipanggil setelah login, auth_store punya informasi user yang komplit.
    # Namun demi kepraktisan, "Pegawai Pindad" bisa digunakan sementara, 
    # karena integrasi NPP ke `npp` sudah cukup untuk menghubungkan riwayat obrolan.
    success = await chat_history_service.assign_session_to_user(
        session_uuid, current_user_npp, "Pegawai Pindad"
    )
    if not success:
        raise HTTPException(status_code=400, detail="Gagal mentransfer sesi atau sesi bukan milik GUEST.")
    return {"status": "success", "message": "Sesi berhasil ditransfer!"}

@router.delete("/{session_uuid}/messages/trim")
async def trim_session_messages(
    session_uuid: str, 
    keep_count: int
):
    """Memotong percakapan setelah keep_count pesan (untuk fitur edit/regenerate)."""
    success = await chat_history_service.trim_session_messages(session_uuid, keep_count)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal memangkas histori percakapan.")
    return {"status": "success", "message": f"Histori dipangkas menjadi {keep_count} pesan terawal."}


@router.get("/sessions/{session_uuid}/settings")
async def get_session_settings_endpoint(session_uuid: str):
    """Mengambil toggle settings (chatMode, isThinkingMode) untuk sesi tertentu."""
    settings_data = await chat_history_service.get_session_settings(session_uuid)
    if settings_data is None:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan atau gagal mengambil settings.")
    return {"status": "success", "data": settings_data}


from pydantic import BaseModel
from typing import Dict, Any

class SessionSettingsSchema(BaseModel):
    settings: Dict[str, Any]

@router.patch("/sessions/{session_uuid}/settings")
async def update_session_settings_endpoint(
    session_uuid: str, 
    payload: SessionSettingsSchema
):
    """Menyimpan perubahan toggle settings (chatMode, isThinkingMode)."""
    success = await chat_history_service.update_session_settings(session_uuid, payload.settings)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal menyimpan setelan sesi.")
    return {"status": "success", "message": "Setelan sesi berhasil disimpan!"}

class FeedbackSchema(BaseModel):
    message_index: int
    feedback: Dict[str, Any]

@router.patch("/sessions/{session_uuid}/messages/feedback")
async def update_message_feedback_endpoint(
    session_uuid: str, 
    payload: FeedbackSchema
):
    """Menyimpan status feedback (Good/Bad) untuk pesan tertentu di Frontend."""
    success = await chat_history_service.update_message_feedback(
        session_uuid, payload.message_index, payload.feedback
    )
    if not success:
        raise HTTPException(status_code=500, detail="Gagal menyimpan feedback pesan.")
    return {"status": "success", "message": "Feedback berhasil disimpan!"}
