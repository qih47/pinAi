import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class SessionRepository:
    
    # =========================================================================
    # 📌 SESSION MANAGEMENT
    # =========================================================================
    
    async def create_new_session(
        self, npp: str, username: str, model_name: str, judul: str = "Obrolan Baru"
    ) -> Dict[str, Any]:
        """Membuat sesi chat baru di tabel chat_sessions saat user klik 'New Chat'"""
        session_uuid = str(uuid.uuid4())
        logger.info(
            f"[CHAT_HISTORY] Creating new session for NPP: {npp} | UUID: {session_uuid[:8]}"
        )
    
        async with get_db() as conn:
            query = """
                INSERT INTO chat_sessions (session_uuid, user_name, model_name, judul, is_active, is_pinned, is_deleted, npp, started_at)
                VALUES ($1, $2, $3, $4, TRUE, FALSE, FALSE, $5, CURRENT_TIMESTAMP)
                RETURNING session_uuid, judul, started_at;
            """
            row = await conn.fetchrow(
                query, session_uuid, username, model_name, judul, npp
            )
            return dict(row)

    
    async def get_user_sessions(self, npp: str) -> List[Dict[str, Any]]:
        """Mengambil semua sesi chat aktif milik pegawai tertentu untuk dipasang di Sidebar Frontend"""
        logger.debug(f"[CHAT_HISTORY] Fetching active sessions for NPP: {npp}")
        async with get_db() as conn:
            query = """
                SELECT session_uuid, judul, is_pinned, started_at 
                FROM chat_sessions 
                WHERE npp = $1 AND is_deleted = FALSE 
                ORDER BY is_pinned DESC, started_at DESC;
            """
            rows = await conn.fetch(query, npp)
            return [dict(r) for r in rows]

    
    async def _resolve_session_pk(self, conn, session_uuid: str) -> Optional[int]:
        """Resolve session_uuid (string) ke chat_sessions.id (integer FK)."""
        row = await conn.fetchrow(
            "SELECT id FROM chat_sessions WHERE session_uuid = $1 AND is_deleted = FALSE",
            session_uuid,
        )
        return row["id"] if row else None

    
    async def toggle_pin_session(self, session_uuid: str, pin_status: bool) -> bool:
        """Fitur Sidebar: Menyematkan (Pin/Unpin) sesi obrolan penting"""
        logger.debug(
            f"[CHAT_HISTORY] Toggling PIN for session {session_uuid[:8]}: {pin_status}"
        )
        async with get_db() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET is_pinned = $1 WHERE session_uuid = $2",
                pin_status,
                session_uuid,
            )
            return True

    
    async def update_session_title(self, session_uuid: str, new_title: str) -> bool:
        """Fitur Sidebar: Mengedit judul sesi obrolan (Rename)"""
        logger.info(
            f'[CHAT_HISTORY] Updated session title for {session_uuid[:8]}: "{new_title}"'
        )
        async with get_db() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET judul = $1 WHERE session_uuid = $2",
                new_title,
                session_uuid,
            )
            return True

    
    async def soft_delete_session(self, session_uuid: str) -> bool:
        """Fitur Sidebar: Menghapus sesi (Soft delete dengan mengubah flag is_deleted)"""
        logger.info(f"[CHAT_HISTORY] Soft deleting session: {session_uuid[:8]}")
        async with get_db() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET is_deleted = TRUE, is_active = FALSE WHERE session_uuid = $1",
                session_uuid,
            )
            return True

    
    async def assign_session_to_user(self, session_uuid: str, npp: str, username: str) -> bool:
        """Mentransfer sesi GUEST ke user yang baru login."""
        async with get_db() as conn:
            try:
                row = await conn.fetchrow(
                    "SELECT npp FROM chat_sessions WHERE session_uuid = $1 AND is_deleted = FALSE",
                    session_uuid
                )
                if not row:
                    return False
                if row["npp"] == npp:
                    return True # Sudah di-assign ke user ini
                if row["npp"] != "GUEST":
                    return False # Milik orang lain
                
                await conn.execute(
                    "UPDATE chat_sessions SET npp = $1, user_name = $2 WHERE session_uuid = $3",
                    npp, username, session_uuid
                )
                logger.info(f"[CHAT_HISTORY] Session {session_uuid[:8]} assigned to NPP: {npp}")
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to assign session: {str(e)}")
                return False

    
    async def update_session_settings(self, session_uuid: str, settings: Dict[str, Any]) -> bool:
        """Fitur: Menyimpan state mode (chatMode, isThinkingMode) untuk sesi tertentu."""
        async with get_db() as conn:
            try:
                settings_json = json.dumps(settings)
                await conn.execute(
                    "UPDATE chat_sessions SET settings = $1 WHERE session_uuid = $2",
                    settings_json,
                    session_uuid,
                )
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to update session settings: {str(e)}")
                return False

    
    async def get_session_settings(self, session_uuid: str) -> Optional[Dict[str, Any]]:
        """Fitur: Mengambil state mode (chatMode, isThinkingMode) untuk sesi tertentu."""
        async with get_db() as conn:
            try:
                row = await conn.fetchrow(
                    "SELECT settings FROM chat_sessions WHERE session_uuid = $1 AND is_deleted = FALSE",
                    session_uuid,
                )
                if row and row["settings"]:
                    return json.loads(row["settings"]) if isinstance(row["settings"], str) else row["settings"]
                return {"chatMode": "auto", "isThinkingMode": False}
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to get session settings: {str(e)}")
                return None

    
    async def auto_update_session_title(self, session_uuid: str, trigger_text: str, first_response: str = "") -> Optional[str]:
        """
        Auto-generate judul sesi jika masih 'Obrolan Baru'.
        Mengembalikan judul baru jika berhasil di-update, atau None jika tidak perlu di-update.
        """
        async with get_db() as conn:
            try:
                check_title = await conn.fetchrow(
                    "SELECT judul FROM chat_sessions WHERE session_uuid = $1",
                    session_uuid,
                )
                if check_title and check_title["judul"] == "Obrolan Baru":
                    from backend.app.utils.title_generator import enqueue_title_generation
                    
                    # Lempar ke background task LLM title generation
                    await enqueue_title_generation(
                        session_uuid=session_uuid,
                        user_message=trigger_text,
                        first_response=first_response
                    )
                    
                    # Return string temporary untuk indikasi background process berjalan
                    return "Sedang membuat judul..."
                return None
            except Exception as e:
                logger.warning(f"[AUTO_TITLE_WARNING] Failed auto title update: {str(e)}")
                return None

