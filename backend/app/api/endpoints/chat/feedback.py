import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.chat_history_service import chat_history_service
from backend.app.api.schemas.chat import FeedbackSchema

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")

@router.post("/messages/{message_id}/feedback")
async def submit_message_feedback(
    message_id: int,
    feedback: FeedbackSchema,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Terima feedback/rating dari user terhadap respon AI.
    Simpan ke database untuk quality monitoring.
    
    Args:
        message_id: ID pesan yang di-feedback
        feedback: Rating (1-5) dan comment opsional
        current_user_npp: NPP user yang submit feedback
    
    Returns:
        {"status": "success", "message": "..."}
    """
    
    user_label = f"NPP: {current_user_npp}" if current_user_npp else "GUEST"
    logger.info(
        f"⭐ [FEEDBACK] Message ID: {message_id} | "
        f"Rating: {feedback.rating}/5 | User: {user_label}"
    )
    
    try:
        # Simpan feedback ke database melalui chat_history_service
        success = await chat_history_service.save_message_feedback(
            message_id=message_id,
            rating=feedback.rating,
            comment=feedback.comment,
            rated_by_npp=current_user_npp or "GUEST",
        )
        
        if not success:
            logger.warning(f"⚠️ [FEEDBACK] Gagal menyimpan feedback untuk message {message_id}")
            raise HTTPException(
                status_code=500,
                detail="Gagal menyimpan feedback. Coba lagi nanti."
            )
        
        logger.info(f"✅ [FEEDBACK] Berhasil tersimpan untuk message {message_id}")
        return {
            "status": "success",
            "message": f"Terima kasih! Rating {feedback.rating}/5 berhasil disimpan.",
            "message_id": message_id,
            "rating": feedback.rating,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [FEEDBACK] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan saat memproses feedback."
        )
