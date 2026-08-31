import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class MessageRepository:
    
    async def _resolve_session_pk(self, conn, session_uuid: str) -> Optional[int]:
        """Resolve session_uuid (string) ke chat_sessions.id (integer FK)."""
        row = await conn.fetchrow(
            "SELECT id FROM chat_sessions WHERE session_uuid = $1 AND is_deleted = FALSE",
            session_uuid,
        )
        return row["id"] if row else None

    
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

    async def save_agent_step(
        self, session_id: str, step_number: int, tool_called: str, tool_input: str, observation: str
    ) -> bool:
        """Menyimpan langkah agen (Agentic Pipeline) ke database."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_id)
                if not session_pk:
                    return False
                
                # Cari message_id terakhir untuk sesi ini (yaitu pesan user terakhir)
                message_id = await conn.fetchval(
                    "SELECT id FROM chat_messages WHERE session_id = $1 ORDER BY timestamp DESC LIMIT 1", 
                    session_pk
                )
                if not message_id:
                    return False

                query = """
                    INSERT INTO ai_agent_steps (message_id, step_number, tool_called, tool_input, observation)
                    VALUES ($1, $2, $3, $4, $5)
                """
                await conn.execute(query, message_id, step_number, tool_called, tool_input, observation)
                return True
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to save agent step: {str(e)}")
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
        """Menghapus pesan-pesan setelah urutan tertentu (keep_count) saat user melakukan Edit/Regenerate, termasuk file artifact-nya."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_uuid)
                if session_pk is None:
                    return False
                
                # Ambil metadata dari pesan yang akan dihapus
                select_query = """
                    SELECT metadata FROM chat_messages 
                    WHERE session_id = $1 AND id NOT IN (
                        SELECT id FROM chat_messages 
                        WHERE session_id = $1 
                        ORDER BY timestamp ASC, id ASC 
                        LIMIT $2
                    )
                """
                rows_to_delete = await conn.fetch(select_query, session_pk, keep_count)
                
                # Hapus physical artifacts jika ada
                import os
                from backend.app.core.paths import ACCOUNTS_DIR
                from pathlib import Path
                base_dir = Path(ACCOUNTS_DIR).parent
                
                for row in rows_to_delete:
                    if row["metadata"]:
                        try:
                            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                            artifacts = meta.get("artifacts", [])
                            for art_item in artifacts:
                                try:
                                    # Handle both string paths and dictionary metadata
                                    art_path = art_item.get("file_path", "") if isinstance(art_item, dict) else art_item
                                    if not art_path:
                                        continue
                                    
                                    # art_path usually looks like accounts/npp/session/artifacts/filename
                                    full_path = base_dir / art_path
                                    if full_path.exists() and full_path.is_file():
                                        os.remove(full_path)
                                        logger.info(f"[CHAT_HISTORY] Deleted artifact file: {full_path}")
                                except Exception as e:
                                    logger.warning(f"[CHAT_HISTORY] Failed to delete artifact file {art_path}: {e}")
                        except Exception as e:
                            logger.warning(f"[CHAT_HISTORY] Failed to parse metadata for artifact deletion: {e}")
    
                # Hapus pesan dari DB
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
                    RETURNING id, file_name, file_path, mime_type, file_size, extracted_text;
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
                        "file_name": inserted_row["file_name"],
                        "file_path": inserted_row["file_path"],
                        "mime_type": inserted_row["mime_type"],
                        "file_size": inserted_row["file_size"],
                        "extracted_text": inserted_row["extracted_text"],
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

    async def get_session_document_chunks_with_meta(self, session_uuid: str) -> List[dict]:
        """Mengambil semua chunk beserta metadata-nya dan ID. Digunakan untuk ekstrak manifest dan visited_urls."""
        async with get_db() as conn:
            try:
                session_pk = await self._resolve_session_pk(conn, session_uuid)
                if session_pk is None:
                    return []
                rows = await conn.fetch(
                    """
                    SELECT id, content, metadata, created_at FROM ai_document_chunks
                    WHERE session_id = $1
                    ORDER BY created_at ASC;
                    """,
                    session_pk
                )
                result = []
                for row in rows:
                    meta = {}
                    if row["metadata"]:
                        try:
                            meta = json.loads(row["metadata"])
                        except Exception:
                            pass
                    result.append({
                        "id": row["id"],
                        "content": row["content"],
                        "metadata": meta,
                        "created_at": row["created_at"]
                    })
                return result
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to get session chunks with meta: {str(e)}")
                return []

    async def get_session_knowledge_manifest(self, session_uuid: str) -> str:
        """
        Menghasilkan katalog ringkas dari semua file / tautan yang pernah diunggah/dibaca di sesi ini.
        Hanya memakan ~50-100 token dibanding full-text dump puluhan ribu karakter.
        """
        chunks = await self.get_session_document_chunks_with_meta(session_uuid)
        if not chunks:
            return ""

        manifest_lines = ["[KNOWLEDGE DARI FILE SEBELUMNYA DI SESI INI]"]
        for idx, c in enumerate(chunks, 1):
            chunk_id = c.get("id")
            meta = c.get("metadata", {})
            item_type = meta.get("type", "file")
            title = meta.get("title") or meta.get("source") or f"Dokumen #{chunk_id}"
            summary = meta.get("summary")
            if not summary:
                # Fallback: Buat ringkasan ringkas dari 120 karakter pertama
                content_clean = c.get("content", "").replace("\n", " ").strip()
                summary = (content_clean[:120] + "...") if len(content_clean) > 120 else content_clean

            manifest_lines.append(f"{idx}. [{item_type.upper()}] {title} (Chunk ID: {chunk_id}) — Ringkasan: {summary}")

        return "\n".join(manifest_lines)

    async def get_document_chunks_by_ids(self, chunk_ids: List[int]) -> List[dict]:
        """Mengambil full content spesifik untuk chunk IDs tertentu secara on-demand."""
        if not chunk_ids:
            return []
        async with get_db() as conn:
            try:
                rows = await conn.fetch(
                    """
                    SELECT id, content, metadata FROM ai_document_chunks
                    WHERE id = ANY($1::int[])
                    ORDER BY id ASC;
                    """,
                    chunk_ids
                )
                result = []
                for row in rows:
                    meta = {}
                    if row["metadata"]:
                        try:
                            meta = json.loads(row["metadata"])
                        except Exception:
                            pass
                    result.append({"id": row["id"], "content": row["content"], "metadata": meta})
                return result
            except Exception as e:
                logger.error(f"[CHAT_HISTORY_ERROR] Failed to get chunks by IDs: {str(e)}")
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

