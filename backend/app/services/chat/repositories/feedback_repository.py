import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class FeedbackRepository:
    
    async def _resolve_session_pk(self, conn, session_uuid: str) -> Optional[int]:
        """Resolve session_uuid (string) ke chat_sessions.id (integer FK)."""
        row = await conn.fetchrow(
            "SELECT id FROM chat_sessions WHERE session_uuid = $1 AND is_deleted = FALSE",
            session_uuid,
        )
        return row["id"] if row else None

    
    
    # =========================================================================
    # ⭐ FEEDBACK & RATING MANAGEMENT
    # =========================================================================
    
    async def save_message_feedback(
        self,
        message_id: int,
        rating: int,
        comment: Optional[str],
        rated_by_npp: str,
    ) -> bool:
        """
        Simpan rating/feedback dari user untuk pesan tertentu.
        Gunakan untuk quality monitoring dan improvement AI responses.
        """
        logger.info(
            f"[FEEDBACK_SAVE] Message ID: {message_id} | "
            f"Rating: {rating}/5 | User: {rated_by_npp}"
        )
    
        async with get_db() as conn:
            try:
                query = """
                    UPDATE chat_messages 
                    SET rating = $1, feedback_comment = $2, rated_by_npp = $3, rated_at = CURRENT_TIMESTAMP
                    WHERE id = $4
                    RETURNING id;
                """
                result = await conn.fetchrow(
                    query, rating, comment, rated_by_npp, message_id
                )
    
                if result:
                    logger.info(f"[FEEDBACK_SAVE_SUCCESS] Saved for message ID: {message_id}")
                    return True
                else:
                    logger.warning(
                        f"[FEEDBACK_SAVE_WARNING] Message ID {message_id} not found"
                    )
                    return False
    
            except Exception as e:
                logger.error(f"[FEEDBACK_SAVE_ERROR] Error saving feedback: {e}")
                return False

    
    async def update_message_feedback(
        self, session_id: str, edit_index: int, feedback_data: dict
    ) -> bool:
        """
        Menyimpan status feedback (Good/Bad) menggunakan JSONB berdasarkan offset index pesan di frontend.
        """
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_id)
                if session_pk is None:
                    return False
                
                # Cari ID pesan ke-N (berdasarkan urutan waktu)
                find_query = """
                    SELECT id FROM chat_messages 
                    WHERE session_id = $1 
                    ORDER BY timestamp ASC, id ASC 
                    OFFSET $2 LIMIT 1
                """
                target_id = await conn.fetchval(find_query, session_pk, edit_index)
                
                if target_id is None:
                    logger.warning(f"[CHAT_HISTORY] Target message at index {edit_index} not found for feedback.")
                    return False
                
                feedback_json = json.dumps(feedback_data)
                
                update_query = """
                    UPDATE chat_messages 
                    SET feedback = $1
                    WHERE id = $2
                """
                await conn.execute(update_query, feedback_json, target_id)
                logger.info(f"[CHAT_HISTORY] Saved feedback {feedback_json} for message index {edit_index} (id: {target_id})")
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to update message feedback: {str(e)}")
                return False

