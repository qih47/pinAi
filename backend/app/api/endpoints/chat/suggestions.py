import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, Depends

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.search.suggestion_service import suggestion_service

router = APIRouter()
logger = logging.getLogger("CAKRA_SUGGESTIONS_API")


@router.get("/suggestions")
async def get_chat_suggestions(
    mode: str = Query("documents", description="Mode saran: websearch, documents, code, focus, doc_questions"),
    q: str = Query("", description="Kueri pencarian teks langsung dari input bar"),
    limit: int = Query(6, ge=1, le=20, description="Batas maksimal saran yang dikembalikan"),
    doc_id: Optional[int] = Query(None, description="ID Dokumen untuk rekomendasi pertanyaan spesifik"),
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Endpoint penyedia rekomendasi kata kunci (hints & suggestions) real-time
    untuk mempercepat pencarian dan mendukung interaksi hybrid (klik langsung / ketik mandiri).
    """
    is_guest = (current_user_npp == "GUEST" or not current_user_npp)
    results = await suggestion_service.get_suggestions(
        mode=mode, 
        query=q, 
        limit=limit, 
        is_guest=is_guest,
        doc_id=doc_id
    )
    return {
        "status": "success",
        "mode": mode,
        "query": q,
        "doc_id": doc_id,
        "is_guest": is_guest,
        "data": results
    }
