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
        print(
            f"➕ [CHAT HISTORY] Membuat sesi baru untuk NPP: {npp} | UUID: {session_uuid[:8]}..."
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
        print(f"🔍 [CHAT HISTORY] Menarik daftar sesi aktif milik NPP: {npp}")
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
        print(
            f"📌 [CHAT HISTORY] Mengubah status PIN sesi {session_uuid[:8]} menjadi: {pin_status}"
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
        print(
            f'📝 [CHAT HISTORY] Mengubah judul sesi {session_uuid[:8]} -> "{new_title}"'
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
        print(f"🗑️  [CHAT HISTORY] Soft delete sesi obrolan: {session_uuid[:8]}")
        async with get_db() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET is_deleted = TRUE, is_active = FALSE WHERE session_uuid = $1",
                session_uuid,
            )
            return True

    # =========================================================================
    # 💬 MESSAGE MANAGEMENT
    # =========================================================================

    async def save_chat_message(
        self, session_id: str, role: str, text: str, thought: Optional[str] = None
    ) -> bool:
        """Menyimpan pesan ke chat_messages. Param session_id menerima session_uuid, di-resolve ke PK integer."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_id)
                if session_pk is None:
                    logger.error(
                        f"❌ [CHAT HISTORY] Sesi tidak ditemukan untuk UUID: {session_id[:8]}..."
                    )
                    return False

                # 🔥 FIX MUTLAK: thought_process diubah menjadi thought sesuai sasis fisik tabel baru
                query = """
                    INSERT INTO chat_messages (session_id, role, message_text, timestamp, thought)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP, $4);
                """
                await conn.execute(query, session_pk, role, text, thought)
                return True
            except Exception as e:
                logger.error(f"❌ [CHAT HISTORY] Gagal menyimpan pesan: {str(e)}")
                return False

    async def get_session_messages(self, session_uuid: str) -> List[Dict[str, Any]]:
        """
        Ambil semua pesan dalam sesi tertentu beserta file lampirannya.
        🔥 PROTEKSI REGEX: Memotong absolute path lama di level SQL agar output data selalu nama file murni.
        """
        query = """
            SELECT 
                m.role, 
                m.message_text, 
                m.timestamp,
                COALESCE(
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'id', a.id,
                            'file_name', a.file_name,
                            'mime_type', a.mime_type,
                            'file_path', CASE 
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
            GROUP BY m.id, m.role, m.message_text, m.timestamp
            ORDER BY m.timestamp ASC
        """
        async with get_db() as conn:
            rows = await conn.fetch(query, session_uuid)
            return [
                {
                    "role": row["role"],
                    "content": row["message_text"],
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
                    RETURNING id, file_name, file_path, mime_type;
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
                        "status": "staged",
                    }
                return None
            except Exception as e:
                logger.error(f"❌ [CHAT HISTORY] Gagal menyimpan attachment: {str(e)}")
                return None

    # =========================================================================
    # 📝 CORPUS & AUTO-TITLE
    # =========================================================================

    async def save_dialogue_corpus(
        self,
        session_uuid: str,
        user_text: str,
        assistant_text: Optional[str] = None,
        context_document: Optional[str] = None,
    ) -> bool:
        """Simpan ke ai_dialogue_corpus dengan session_id integer FK."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_uuid)
                if session_pk is None:
                    return False

                if context_document is not None:
                    await conn.execute(
                        """
                        INSERT INTO ai_dialogue_corpus (session_id, user_text, context_document, created_at)
                        VALUES ($1, $2, $3, CURRENT_TIMESTAMP);
                        """,
                        session_pk,
                        user_text,
                        context_document,
                    )
                elif assistant_text is not None:
                    await conn.execute(
                        """
                        INSERT INTO ai_dialogue_corpus (session_id, user_text, assistant_text, created_at)
                        VALUES ($1, $2, $3, CURRENT_TIMESTAMP);
                        """,
                        session_pk,
                        user_text,
                        assistant_text,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO ai_dialogue_corpus (session_id, user_text, created_at)
                        VALUES ($1, $2, CURRENT_TIMESTAMP);
                        """,
                        session_pk,
                        user_text,
                    )
                return True
            except Exception as e:
                logger.error(f"❌ [CHAT HISTORY] Gagal simpan korpus dialog: {str(e)}")
                return False

    async def auto_update_session_title(self, session_uuid: str, trigger_text: str) -> Optional[str]:
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
                    auto_title = " ".join(trigger_text.split()[:4]) + "..."
                    await conn.execute(
                        "UPDATE chat_sessions SET judul = $1 WHERE session_uuid = $2",
                        auto_title,
                        session_uuid,
                    )
                    print(f"📝 [AUTO TITLE] Berhasil merubah judul sesi: {auto_title}")
                    return auto_title
                return None
            except Exception as e:
                logger.warning(f"⚠️ [AUTO TITLE] Gagal update judul otomatis: {str(e)}")
                return None


chat_history_service = ChatHistoryService()