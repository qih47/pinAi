"""
CAKRA AI — Collab Endpoints
===========================
Rute API untuk Collab Space (Diskusi Tim & AI Teammate).
- Seluruh endpoint diamankan dengan auth dependency get_current_user_npp.
- Mengalirkan event real-time melalui Server-Sent Events (SSE).
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.collab.collab_service import CollabService
from backend.app.services.collab.collab_broadcast_manager import collab_broadcast_manager
from backend.app.core.database import get_db

logger = logging.getLogger("COLLAB_API")
router = APIRouter()


class CreateRoomRequest(BaseModel):
    name: str
    topic: Optional[str] = ""
    initial_members: Optional[List[str]] = []
    document_content: Optional[str] = ""


class UpdateDocumentRequest(BaseModel):
    document_content: str


class InviteMembersRequest(BaseModel):
    npps: List[str]


class SendMessageRequest(BaseModel):
    message_text: str
    attachments: Optional[List[Dict[str, Any]]] = []


@router.get("/rooms", tags=["Collab"])
async def get_my_rooms(current_user_npp: str = Depends(get_current_user_npp)):
    """Mengambil daftar ruang diskusi tim milik user."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    try:
        rooms = await CollabService.get_user_rooms(current_user_npp)
        return {"status": "success", "rooms": rooms}
    except Exception as e:
        logger.error(f"[COLLAB_API] Error fetching rooms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms", tags=["Collab"])
async def create_room(payload: CreateRoomRequest, current_user_npp: str = Depends(get_current_user_npp)):
    """Membuat ruang diskusi baru."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Nama ruang diskusi wajib diisi.")
    try:
        room = await CollabService.create_room(
            name=payload.name.strip(),
            topic=payload.topic.strip() if payload.topic else "",
            created_by=current_user_npp,
            initial_members=payload.initial_members,
            document_content=payload.document_content or ""
        )
        return {"status": "success", "room": room}
    except Exception as e:
        logger.error(f"[COLLAB_API] Error creating room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}", tags=["Collab"])
async def get_room_detail(room_id: str, current_user_npp: str = Depends(get_current_user_npp)):
    """Mengambil detail ruang diskusi dan anggota tim."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    try:
        room = await CollabService.get_room_detail(room_id, current_user_npp)
        return {"status": "success", "room": room}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"[COLLAB_API] Error fetching room detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rooms/{room_id}/document", tags=["Collab"])
async def update_document(
    room_id: str,
    payload: UpdateDocumentRequest,
    current_user_npp: str = Depends(get_current_user_npp)
):
    """Menyimpan draf dokumen di Document Pad dan menyinkronkan ke seluruh tim."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    try:
        result = await CollabService.update_document(room_id, current_user_npp, payload.document_content)
        return result
    except Exception as e:
        logger.error(f"[COLLAB_API] Error updating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/invite", tags=["Collab"])
async def invite_members(
    room_id: str,
    payload: InviteMembersRequest,
    current_user_npp: str = Depends(get_current_user_npp)
):
    """Mengundang rekan kerja ke ruang diskusi."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    try:
        result = await CollabService.invite_members(room_id, current_user_npp, payload.npps)
        return result
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        logger.error(f"[COLLAB_API] Error inviting members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/messages", tags=["Collab"])
async def get_messages(
    room_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user_npp: str = Depends(get_current_user_npp)
):
    """Mengambil riwayat obrolan di dalam ruangan."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    try:
        messages = await CollabService.get_room_messages(room_id, current_user_npp, limit=limit)
        return {"status": "success", "messages": messages}
    except Exception as e:
        logger.error(f"[COLLAB_API] Error fetching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/messages", tags=["Collab"])
async def send_message(
    room_id: str,
    payload: SendMessageRequest,
    request: Request,
    current_user_npp: str = Depends(get_current_user_npp)
):
    """Mengirim pesan baru ke ruang diskusi tim."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    if not payload.message_text.strip():
        raise HTTPException(status_code=400, detail="Isi pesan tidak boleh kosong.")

    # Ambil nama pengirim dari database
    sender_name = current_user_npp
    try:
        async with get_db() as conn:
            user_row = await conn.fetchrow(
                "SELECT preferred_name, fullname FROM users WHERE npp = $1",
                current_user_npp
            )
            if user_row:
                sender_name = user_row["preferred_name"] or user_row["fullname"] or current_user_npp
    except Exception:
        pass

    try:
        message = await CollabService.post_message(
            room_id=room_id,
            sender_npp=current_user_npp,
            sender_name=sender_name,
            message_text=payload.message_text.strip(),
            attachments=payload.attachments,
            request=request
        )
        return {"status": "success", "message": message}
    except Exception as e:
        logger.error(f"[COLLAB_API] Error posting message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/stream", tags=["Collab"])
async def stream_room_events(
    room_id: str,
    request: Request,
    token: Optional[str] = Query(None)
):
    """
    Stream Server-Sent Events (SSE) untuk update pesan, typing, dan dokumen real-time.
    """
    return StreamingResponse(
        collab_broadcast_manager.subscribe(room_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@router.get("/personnel/search", tags=["Collab"])
async def search_personnel(
    q: str = Query("", min_length=1),
    current_user_npp: str = Depends(get_current_user_npp)
):
    """Mencari personil PT Pindad untuk diundang ke ruang diskusi."""
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=401, detail="Sesi login tidak valid.")
    search_term = f"%{q.strip()}%"
    query = """
        SELECT npp, fullname, preferred_name, divisi, profile_photo_url
        FROM users
        WHERE (npp ILIKE $1 OR fullname ILIKE $1 OR preferred_name ILIKE $1)
        ORDER BY fullname ASC
        LIMIT 20
    """
    async with get_db() as conn:
        rows = await conn.fetch(query, search_term)
        return {
            "status": "success",
            "results": [
                {
                    "npp": r["npp"],
                    "name": r["preferred_name"] or r["fullname"] or r["npp"],
                    "fullname": r["fullname"],
                    "divisi": r["divisi"] or "PT Pindad",
                    "profile_photo_url": r["profile_photo_url"] or ""
                }
                for r in rows
            ]
        }
