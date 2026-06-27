import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")


class ChatHistoryService:
    """
    Service untuk mengelola CRUD riwayat obrolan di tabel chat_sessions, chat_messages, dan chat_attachments.
    Mendukung fitur Sidebar: Create Session, Pin, Edit Judul, Soft Delete, Upload Attachment, dan Auto-Title.
    """

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

    # =========================================================================
    # 💬 MESSAGE MANAGEMENT
    # =========================================================================

    async def save_chat_message(
        self, session_id: str, role: str, text: str, thought: Optional[str] = None, sources: Optional[list] = None, metadata: Optional[dict] = None
    ) -> bool:
        """Menyimpan pesan ke chat_messages. Param session_id menerima session_uuid, di-resolve ke PK integer."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_id)
                if session_pk is None:
                    logger.error(
                        f"[CHAT_HISTORY_ERROR] Session not found for UUID: {session_id[:8]}..."
                    )
                    return False

                # Thought process diubah menjadi thought sesuai sasis fisik tabel baru
                sources_json = json.dumps(sources) if sources is not None else None
                metadata_json = json.dumps(metadata) if metadata is not None else None
                query = """
                    INSERT INTO chat_messages (session_id, role, message_text, timestamp, thought, sources, metadata)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP, $4, $5, $6);
                """
                await conn.execute(query, session_pk, role, text, thought, sources_json, metadata_json)
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to save chat message: {str(e)}")
                return False
    async def update_chat_message(
        self, session_id: str, edit_index: int, role: str, text: str, thought: Optional[str] = None, sources: Optional[list] = None, metadata: Optional[dict] = None
    ) -> bool:
        """Melakukan In-Place update pada baris chat yang ada menggunakan offset index."""
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
                    logger.warning(f"[CHAT_HISTORY] Target message at index {edit_index} not found for update. Inserting instead.")
                    # Fallback ke insert jika index tidak valid
                    return await self.save_chat_message(session_id, role, text, thought, sources, metadata)
                
                sources_json = json.dumps(sources) if sources is not None else None
                metadata_json = json.dumps(metadata) if metadata is not None else None
                
                # Timpa (Update) isi pesannya
                update_query = """
                    UPDATE chat_messages 
                    SET message_text = $1, thought = $2, role = $3, sources = $5, metadata = $6
                    WHERE id = $4
                """
                await conn.execute(update_query, text, thought, role, target_id, sources_json, metadata_json)
                logger.info(f"[CHAT_HISTORY] Updated message at index {edit_index} (id: {target_id})")
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to update chat message: {str(e)}")
                return False

    async def trim_session_messages(self, session_uuid: str, keep_count: int) -> bool:
        """Menghapus pesan-pesan setelah urutan tertentu (keep_count) saat user melakukan Edit/Regenerate."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_uuid)
                if session_pk is None:
                    return False
                
                # Hapus pesan yang ID-nya tidak termasuk dalam top N pesan pertama (diurutkan by timestamp & id)
                query = """
                    DELETE FROM chat_messages 
                    WHERE session_id = $1 AND id NOT IN (
                        SELECT id FROM chat_messages 
                        WHERE session_id = $1 
                        ORDER BY timestamp ASC, id ASC 
                        LIMIT $2
                    )
                """
                await conn.execute(query, session_pk, keep_count)
                logger.info(f"[CHAT_HISTORY] Trimmed session {session_uuid[:8]} to keep first {keep_count} messages")
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to trim messages: {str(e)}")
                return False

    async def get_session_messages(self, session_uuid: str) -> List[Dict[str, Any]]:
        """
        Ambil semua pesan dalam sesi tertentu beserta file lampirannya.
        Memotong absolute path lama di level SQL agar output data selalu nama file murni.
        """
        query = """
            SELECT 
                m.role, 
                m.message_text, 
                m.thought,
                m.sources,
                m.metadata,
                m.timestamp,
                COALESCE(
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'id', a.id,
                            'file_name', a.file_name,
                            'mime_type', a.mime_type,
                            'file_size', a.file_size,
                            'file_path', CASE 
                                WHEN a.file_path LIKE 'accounts/%' THEN a.file_path
                                WHEN a.file_path LIKE '%/%' THEN SUBSTRING(a.file_path FROM '[^/]+$')
                                ELSE a.file_path
                            END
                        )
                    ) FILTER (WHERE a.id IS NOT NULL), '[]'
                ) AS attachments
            FROM chat_messages m
            JOIN chat_sessions s ON m.session_id = s.id
            LEFT JOIN chat_attachments a ON a.session_id = s.id 
                AND a.uploaded_at <= m.timestamp 
                AND a.uploaded_at >= (
                    SELECT COALESCE(MAX(timestamp), s.started_at) 
                    FROM chat_messages 
                    WHERE session_id = s.id AND timestamp < m.timestamp
                )
            WHERE s.session_uuid = $1 AND s.is_deleted = FALSE
            GROUP BY m.id, m.role, m.message_text, m.thought, m.sources, m.metadata, m.timestamp
            ORDER BY m.timestamp ASC
        """
        async with get_db() as conn:
            rows = await conn.fetch(query, session_uuid)
            return [
                {
                    "role": row["role"],
                    "content": row["message_text"],
                    "thought": row["thought"],
                    "sources": json.loads(row["sources"]) if row["sources"] and isinstance(row["sources"], str) else row.get("sources"),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] and isinstance(row["metadata"], str) else row.get("metadata"),
                    "attachments": json.loads(row["attachments"]) if isinstance(row["attachments"], str) else row["attachments"]
                } for row in rows
            ]

    # =========================================================================
    # 📎 ATTACHMENT MANAGEMENT
    # =========================================================================

    async def save_chat_attachment(
        self,
        session_uuid: Optional[str],
        original_filename: str,
        unique_filename: str,
        file_size: int,
        mime_type: str,
        extracted_text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Menyimpan metadata lampiran ke tabel chat_attachments.
        Mengembalikan row yang berhasil di-insert atau None jika gagal.
        """
        async with get_db() as conn:
            try:
                internal_session_pk = None
                if session_uuid and session_uuid != "new":
                    internal_session_pk = await self._resolve_session_pk(conn, session_uuid)

                inserted_row = await conn.fetchrow(
                    """
                    INSERT INTO chat_attachments (session_id, file_name, file_path, file_size, mime_type, extracted_text)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id, file_name, file_path, mime_type, file_size;
                    """,
                    internal_session_pk,
                    original_filename,
                    unique_filename,
                    file_size,
                    mime_type,
                    extracted_text,
                )

                if inserted_row:
                    return {
                        "id": inserted_row["id"],
                        "original_filename": inserted_row["file_name"],
                        "file_path": inserted_row["file_path"],
                        "mime_type": inserted_row["mime_type"],
                        "file_size": inserted_row["file_size"],
                        "status": "staged",
                    }
                return None
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to save chat attachment: {str(e)}")
                return None

    # =========================================================================
    # 📝 CORPUS, CHUNKS & AUTO-TITLE
    # =========================================================================

    async def save_document_chunk(
        self,
        session_uuid: str,
        npp: str,
        content: str,
        file_id: Optional[int] = None,
        chunk_metadata: Optional[dict] = None
    ) -> bool:
        """Menyimpan chunk teks hasil ekstraksi attachment ke ai_document_chunks."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_uuid)
                if session_pk is None:
                    return False
                
                metadata_json = json.dumps(chunk_metadata) if chunk_metadata else None
                await conn.execute(
                    """
                    INSERT INTO ai_document_chunks (session_id, npp, content, file_id, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP);
                    """,
                    session_pk, npp, content, file_id, metadata_json
                )
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to save document chunk: {str(e)}")
                return False

    async def get_session_document_chunks(self, session_uuid: str) -> List[str]:
        """Mengambil semua teks hasil ekstraksi untuk sesi tertentu sebagai memori jangka panjang."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_uuid)
                if session_pk is None:
                    return []
                
                rows = await conn.fetch(
                    """
                    SELECT content FROM ai_document_chunks
                    WHERE session_id = $1
                    ORDER BY created_at ASC;
                    """,
                    session_pk
                )
                return [row["content"] for row in rows]
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to get session chunks: {str(e)}")
                return []

    async def save_dialogue_corpus(
        self,
        session_uuid: str,
        user_text: str,
        assistant_text: Optional[str] = None,
        context_document: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Simpan ke ai_dialogue_corpus dengan session_id integer FK."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_uuid)
                if session_pk is None:
                    return False

                metadata_json = json.dumps(metadata) if metadata else None

                await conn.execute(
                    """
                    INSERT INTO ai_dialogue_corpus (session_id, user_text, assistant_text, context_document, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP);
                    """,
                    session_pk,
                    user_text,
                    assistant_text,
                    context_document,
                    metadata_json
                )
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to save dialogue corpus: {str(e)}")
                return False

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


chat_history_service = ChatHistoryService()
