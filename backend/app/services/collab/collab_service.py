"""
CAKRA AI — Collab Service
=========================
Logika bisnis utama untuk Collab Space:
- CRUD Ruang Diskusi Tim (Rooms)
- Manajemen Keanggotaan Tim (Members)
- Draf Dokumen Kolaboratif (Document Pad)
- Pengiriman & Riwayat Pesan Tim (Messages)
- Trigger Asinkronus CAKRA AI Teammate (Explicit Mention & Proactive Interjection)
"""

import re
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from backend.app.core.database import get_db
from backend.app.services.collab.collab_broadcast_manager import collab_broadcast_manager
from backend.app.services.pipeline.modes.mode_collab import ModeCollab

logger = logging.getLogger("COLLAB_SERVICE")


class CollabService:
    @staticmethod
    async def get_user_rooms(npp: str) -> List[Dict[str, Any]]:
        """
        Mengambil daftar ruang diskusi tim di mana user terdaftar sebagai anggota.
        """
        query = """
            SELECT 
                r.id::text as id,
                r.name,
                r.topic,
                r.document_content,
                r.created_by,
                r.is_active,
                r.created_at,
                r.updated_at,
                m.role_in_room,
                m.last_read_at,
                (SELECT COUNT(*) FROM collab_room_members WHERE room_id = r.id) as member_count,
                (
                    SELECT jsonb_build_object(
                        'sender_name', lm.sender_name,
                        'message_text', lm.message_text,
                        'created_at', lm.created_at
                    )
                    FROM collab_messages lm
                    WHERE lm.room_id = r.id
                    ORDER BY lm.created_at DESC
                    LIMIT 1
                ) as last_message
            FROM collab_rooms r
            JOIN collab_room_members m ON r.id = m.room_id
            WHERE m.npp = $1 AND r.is_active = TRUE
            ORDER BY r.updated_at DESC
        """
        async with get_db() as conn:
            rows = await conn.fetch(query, npp)
            results = []
            for r in rows:
                item = dict(r)
                if item.get("created_at"):
                    item["created_at"] = item["created_at"].isoformat()
                if item.get("updated_at"):
                    item["updated_at"] = item["updated_at"].isoformat()
                if item.get("last_read_at"):
                    item["last_read_at"] = item["last_read_at"].isoformat()
                if item.get("last_message") and isinstance(item["last_message"], str):
                    try:
                        item["last_message"] = json.loads(item["last_message"])
                    except Exception:
                        pass
                results.append(item)
            return results

    @staticmethod
    async def create_room(
        name: str,
        topic: str,
        created_by: str,
        initial_members: Optional[List[str]] = None,
        document_content: str = ""
    ) -> Dict[str, Any]:
        """
        Membuat ruang diskusi baru dan menambahkan anggota awal.
        """
        initial_members = initial_members or []
        room_id = str(uuid.uuid4())

        async with get_db() as conn:
            async with conn.transaction():
                # 1. Insert room
                await conn.execute(
                    """
                    INSERT INTO collab_rooms (id, name, topic, document_content, created_by)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    uuid.UUID(room_id), name, topic, document_content, created_by
                )

                # 2. Insert creator as OWNER
                await conn.execute(
                    """
                    INSERT INTO collab_room_members (room_id, npp, role_in_room)
                    VALUES ($1, $2, 'OWNER')
                    ON CONFLICT (room_id, npp) DO NOTHING
                    """,
                    uuid.UUID(room_id), created_by
                )

                # 3. Insert other initial members
                for member_npp in initial_members:
                    if member_npp and member_npp != created_by:
                        await conn.execute(
                            """
                            INSERT INTO collab_room_members (room_id, npp, role_in_room)
                            VALUES ($1, $2, 'MEMBER')
                            ON CONFLICT (room_id, npp) DO NOTHING
                            """,
                            uuid.UUID(room_id), member_npp
                        )

                # 4. Insert initial welcome message from CAKRA
                welcome_text = (
                    f"Halo rekan-rekan! Selamat datang di ruang diskusi **{name}**.\n\n"
                    f"Saya **CAKRA (AI Teammate)** siap mendampingi tim dalam membahas agenda *{topic or 'regulasi dan dokumen kerja'}*. "
                    "Anda dapat berdiskusi bebas dengan tim, menyusun draf di panel dokumen samping, "
                    "atau memanggil saya kapan saja dengan menyebut **@cakra**."
                )
                await conn.execute(
                    """
                    INSERT INTO collab_messages (room_id, sender_type, sender_npp, sender_name, message_text, interjection_type)
                    VALUES ($1, 'CAKRA', NULL, 'CAKRA AI Teammate', $2, 'WELCOME')
                    """,
                    uuid.UUID(room_id), welcome_text
                )

        return await CollabService.get_room_detail(room_id, created_by)

    @staticmethod
    async def get_room_detail(room_id: str, npp: str) -> Dict[str, Any]:
        """
        Mengambil informasi lengkap ruang, termasuk daftar anggota dan profilnya.
        """
        async with get_db() as conn:
            # Pastikan user adalah member atau admin
            membership = await conn.fetchrow(
                "SELECT role_in_room FROM collab_room_members WHERE room_id = $1 AND npp = $2",
                uuid.UUID(room_id), npp
            )
            if not membership:
                raise PermissionError("Anda bukan anggota ruang diskusi ini.")

            room = await conn.fetchrow(
                "SELECT id::text, name, topic, document_content, created_by, is_active, created_at, updated_at FROM collab_rooms WHERE id = $1",
                uuid.UUID(room_id)
            )
            if not room:
                raise ValueError("Ruang diskusi tidak ditemukan.")

            members_query = """
                SELECT 
                    m.npp,
                    m.role_in_room,
                    m.joined_at,
                    COALESCE(u.preferred_name, u.fullname, m.npp) as name,
                    u.divisi,
                    u.profile_photo_url
                FROM collab_room_members m
                LEFT JOIN users u ON m.npp = u.npp
                WHERE m.room_id = $1
                ORDER BY (m.role_in_room = 'OWNER') DESC, m.joined_at ASC
            """
            members_rows = await conn.fetch(members_query, uuid.UUID(room_id))

            room_dict = dict(room)
            room_dict["created_at"] = room_dict["created_at"].isoformat() if room_dict.get("created_at") else ""
            room_dict["updated_at"] = room_dict["updated_at"].isoformat() if room_dict.get("updated_at") else ""
            room_dict["current_user_role"] = membership["role_in_room"]
            room_dict["members"] = [
                {
                    "npp": m["npp"],
                    "name": m["name"],
                    "divisi": m["divisi"] or "PT Pindad",
                    "role_in_room": m["role_in_room"],
                    "profile_photo_url": m["profile_photo_url"] or "",
                    "joined_at": m["joined_at"].isoformat() if m.get("joined_at") else ""
                }
                for m in members_rows
            ]
            return room_dict

    @staticmethod
    async def update_document(room_id: str, npp: str, document_content: str) -> Dict[str, Any]:
        """
        Memperbarui isi draf dokumen bersama di Document Pad dan membroadcast ke semua anggota.
        """
        async with get_db() as conn:
            await conn.execute(
                """
                UPDATE collab_rooms 
                SET document_content = $1, updated_at = NOW() 
                WHERE id = $2
                """,
                document_content, uuid.UUID(room_id)
            )

        # Broadcast pembaruan dokumen real-time
        await collab_broadcast_manager.broadcast(room_id, {
            "type": "document_updated",
            "document_content": document_content,
            "updated_by": npp
        })

        return {"status": "success", "document_content": document_content}

    @staticmethod
    async def invite_members(room_id: str, requester_npp: str, npps_to_invite: List[str]) -> Dict[str, Any]:
        """
        Menambahkan anggota baru ke dalam ruang diskusi.
        """
        async with get_db() as conn:
            membership = await conn.fetchrow(
                "SELECT role_in_room FROM collab_room_members WHERE room_id = $1 AND npp = $2",
                uuid.UUID(room_id), requester_npp
            )
            if not membership:
                raise PermissionError("Hanya anggota yang dapat mengundang rekan kerja.")

            added = []
            for target_npp in npps_to_invite:
                if target_npp:
                    res = await conn.execute(
                        """
                        INSERT INTO collab_room_members (room_id, npp, role_in_room)
                        VALUES ($1, $2, 'MEMBER')
                        ON CONFLICT (room_id, npp) DO NOTHING
                        """,
                        uuid.UUID(room_id), target_npp
                    )
                    if "INSERT 0 1" in res:
                        added.append(target_npp)

        await collab_broadcast_manager.broadcast(room_id, {
            "type": "members_updated",
            "room_id": room_id,
            "added_npps": added
        })

        return {"status": "success", "added_members": added}

    @staticmethod
    async def get_room_messages(room_id: str, npp: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Mengambil riwayat obrolan di ruang diskusi.
        """
        async with get_db() as conn:
            # Update last_read_at
            await conn.execute(
                "UPDATE collab_room_members SET last_read_at = NOW() WHERE room_id = $1 AND npp = $2",
                uuid.UUID(room_id), npp
            )

            query = """
                SELECT 
                    id::text,
                    room_id::text,
                    sender_type,
                    sender_npp,
                    sender_name,
                    message_text,
                    is_mention,
                    interjection_type,
                    attachments,
                    created_at
                FROM collab_messages
                WHERE room_id = $1
                ORDER BY created_at ASC
                LIMIT $2
            """
            rows = await conn.fetch(query, uuid.UUID(room_id), limit)
            messages = []
            for r in rows:
                item = dict(r)
                if item.get("created_at"):
                    item["created_at"] = item["created_at"].isoformat()
                if isinstance(item.get("attachments"), str):
                    try:
                        item["attachments"] = json.loads(item["attachments"])
                    except Exception:
                        item["attachments"] = []
                messages.append(item)
            return messages

    @staticmethod
    async def post_message(
        room_id: str,
        sender_npp: str,
        sender_name: str,
        message_text: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        request: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Menyimpan pesan pengguna, membroadcast ke seluruh tim melalui SSE,
        dan memicu respons CAKRA AI Teammate (baik karena mention @cakra maupun proaktif).
        """
        attachments = attachments or []
        attachments_json = json.dumps(attachments)
        msg_id = str(uuid.uuid4())
        is_mention = bool(re.search(r"@cakra\b", message_text, re.IGNORECASE))

        async with get_db() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO collab_messages (
                    id, room_id, sender_type, sender_npp, sender_name,
                    message_text, is_mention, attachments, created_at
                )
                VALUES ($1, $2, 'USER', $3, $4, $5, $6, $7::jsonb, NOW())
                RETURNING id::text, room_id::text, sender_type, sender_npp, sender_name, message_text, is_mention, interjection_type, attachments, created_at
                """,
                uuid.UUID(msg_id), uuid.UUID(room_id), sender_npp, sender_name, message_text, is_mention, attachments_json
            )
            await conn.execute("UPDATE collab_rooms SET updated_at = NOW() WHERE id = $1", uuid.UUID(room_id))

        msg_dict = dict(row)
        msg_dict["created_at"] = msg_dict["created_at"].isoformat()
        if isinstance(msg_dict.get("attachments"), str):
            try:
                msg_dict["attachments"] = json.loads(msg_dict["attachments"])
            except Exception:
                pass

        # 1. Broadcast pesan user secara instan
        await collab_broadcast_manager.broadcast(room_id, {
            "type": "new_message",
            "message": msg_dict
        })

        # 2. Trigger AI Teammate handling di background task agar user tidak menunggu response POST
        asyncio.create_task(
            CollabService._handle_ai_teammate_trigger(
                room_id=room_id,
                trigger_message=msg_dict,
                is_mention=is_mention,
                request=request
            )
        )

        return msg_dict

    @staticmethod
    async def _handle_ai_teammate_trigger(
        room_id: str,
        trigger_message: Dict[str, Any],
        is_mention: bool,
        request: Optional[Any] = None
    ):
        """
        Background task: Mengevaluasi dan menghasilkan jawaban dari CAKRA AI Teammate.
        """
        try:
            async with get_db() as conn:
                room = await conn.fetchrow(
                    "SELECT name, topic, document_content FROM collab_rooms WHERE id = $1",
                    uuid.UUID(room_id)
                )
                if not room:
                    return

                # Ambil 15 riwayat pesan terakhir
                rows = await conn.fetch(
                    """
                    SELECT sender_type, sender_npp, sender_name, message_text, is_mention, created_at
                    FROM collab_messages
                    WHERE room_id = $1
                    ORDER BY created_at DESC
                    LIMIT 15
                    """,
                    uuid.UUID(room_id)
                )
                recent_messages = [dict(r) for r in reversed(rows)]

            mode_collab = ModeCollab()
            should_intervene = False
            interjection_type = "EXPLICIT_MENTION" if is_mention else None

            if is_mention:
                should_intervene = True
            else:
                # Silent evaluation oleh model ringan gemma4:e4b
                eval_ok, eval_reason = await mode_collab.should_intervene(
                    recent_messages=recent_messages,
                    room_topic=room["topic"]
                )
                if eval_ok:
                    should_intervene = True
                    interjection_type = "PROACTIVE_SUGGESTION"

            if not should_intervene:
                return

            # 1. Kirim typing indicator dari CAKRA
            await collab_broadcast_manager.send_typing(room_id, sender="CAKRA AI Teammate", is_typing=True)

            # 2. Stream & kumpulkan respons dari CAKRA
            full_response_text = ""
            async for chunk in mode_collab.generate_response(
                room_name=room["name"],
                room_topic=room["topic"] or "",
                document_content=room["document_content"] or "",
                recent_messages=recent_messages,
                is_mention=is_mention,
                interjection_type=interjection_type or "EXPLICIT_MENTION",
                request=request
            ):
                full_response_text += chunk

            clean_response = full_response_text.strip()
            if not clean_response:
                clean_response = "Saya sedang menyimak diskusi tim. Silakan lanjutkan atau mention @cakra jika butuh bantuan formulasi aturan."

            # 3. Simpan respons CAKRA ke collab_messages
            cakra_msg_id = str(uuid.uuid4())
            async with get_db() as conn:
                cakra_row = await conn.fetchrow(
                    """
                    INSERT INTO collab_messages (
                        id, room_id, sender_type, sender_npp, sender_name,
                        message_text, is_mention, interjection_type, created_at
                    )
                    VALUES ($1, $2, 'CAKRA', NULL, 'CAKRA AI Teammate', $3, $4, $5, NOW())
                    RETURNING id::text, room_id::text, sender_type, sender_npp, sender_name, message_text, is_mention, interjection_type, attachments, created_at
                    """,
                    uuid.UUID(cakra_msg_id), uuid.UUID(room_id), clean_response, is_mention, interjection_type
                )
                await conn.execute("UPDATE collab_rooms SET updated_at = NOW() WHERE id = $1", uuid.UUID(room_id))

            cakra_dict = dict(cakra_row)
            cakra_dict["created_at"] = cakra_dict["created_at"].isoformat()
            cakra_dict["attachments"] = []

            # 4. Hentikan typing indicator & broadcast pesan CAKRA
            await collab_broadcast_manager.send_typing(room_id, sender="CAKRA AI Teammate", is_typing=False)
            await collab_broadcast_manager.broadcast(room_id, {
                "type": "new_message",
                "message": cakra_dict
            })
            logger.info(f"✅ [COLLAB_AI] Response sent to room {room_id} ({interjection_type})")

        except Exception as e:
            logger.error(f"❌ [COLLAB_AI] Error in AI teammate background handler: {e}")
            await collab_broadcast_manager.send_typing(room_id, sender="CAKRA AI Teammate", is_typing=False)
