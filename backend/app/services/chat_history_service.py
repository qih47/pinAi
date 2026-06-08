import uuid
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")


class ChatHistoryService:
    """
    Service untuk mengelola CRUD riwayat obrolan di tabel chat_sessions dan chat_messages.
    Mendukung fitur Sidebar: Create Session, Pin, Edit Judul, dan Soft Delete.
    """

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

                query = """
                    INSERT INTO chat_messages (session_id, role, message_text, timestamp, thought_process)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP, $4);
                """
                await conn.execute(query, session_pk, role, text, thought)
                return True
            except Exception as e:
                logger.error(f"❌ [CHAT HISTORY] Gagal menyimpan pesan: {str(e)}")
                return False

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
            # 🔥 FIX SAKTI: Ganti $2 menjadi $1 agar indeks parameter asyncpg lurus!
            await conn.execute(
                "UPDATE chat_sessions SET is_deleted = TRUE, is_active = FALSE WHERE session_uuid = $1",
                session_uuid,
            )
            return True

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

    async def get_session_messages(self, session_uuid: str):
        """Ambil semua pesan dalam sesi tertentu secara aman dari pool get_db"""
        query = """
            SELECT m.role, m.message_text, m.timestamp 
            FROM chat_messages m
            JOIN chat_sessions s ON m.session_id = s.id
            WHERE s.session_uuid = $1 AND s.is_deleted = FALSE
            ORDER BY m.timestamp ASC
        """
        # 🔥 FIX SAKTI: Ganti self.db.fetch dengan block async with get_db() bawaan core lu
        async with get_db() as conn:
            rows = await conn.fetch(query, session_uuid)
            return [{"role": row["role"], "content": row["message_text"]} for row in rows]


chat_history_service = ChatHistoryService()
