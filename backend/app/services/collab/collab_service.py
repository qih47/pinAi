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
                    f"Saya **CAKRA (AI Teammate)** siap mendampingi tim dalam membahas agenda *{topic or 'diskusi dan koordinasi kerja'}*. "
                    "Silakan berdiskusi bebas bersama tim, dan panggil saya kapan saja dengan menyebut **@cakra** jika memerlukan masukan, analisis, atau bantuan."
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
    async def summarize_room(room_id: str, npp: str) -> Dict[str, Any]:
        """
        Menyusun notulensi cerdas otomatis dari seluruh percakapan tim di ruangan
        dan memperbarui document_content di collab_rooms secara rapi & profesional.
        """
        async with get_db() as conn:
            # 1. Ambil detail room
            room_row = await conn.fetchrow(
                "SELECT id::text, name, topic FROM collab_rooms WHERE id = $1",
                uuid.UUID(room_id)
            )
            if not room_row:
                raise ValueError("Ruang diskusi tidak ditemukan.")

            # 2. Ambil daftar anggota
            member_rows = await conn.fetch(
                """
                SELECT m.npp, u.name, u.divisi
                FROM collab_room_members m
                LEFT JOIN users u ON m.npp = u.npp
                WHERE m.room_id = $1
                """,
                uuid.UUID(room_id)
            )
            members = [dict(r) for r in member_rows]

            # 3. Ambil riwayat chat
            msg_rows = await conn.fetch(
                """
                SELECT id::text, sender_type, sender_npp, sender_name, message_text, created_at
                FROM collab_messages
                WHERE room_id = $1
                ORDER BY created_at ASC
                LIMIT 100
                """,
                uuid.UUID(room_id)
            )
            messages = [dict(r) for r in msg_rows]

        # 4. Generate Notulensi via ModeCollab
        mode_collab_inst = ModeCollab()
        notulensi_content = await mode_collab_inst.generate_notulensi(
            room_name=room_row["name"],
            room_topic=room_row["topic"] or "",
            members=members,
            messages=messages
        )

        # 5. Simpan notulensi ke database
        async with get_db() as conn:
            await conn.execute(
                """
                UPDATE collab_rooms 
                SET document_content = $1, updated_at = NOW() 
                WHERE id = $2
                """,
                notulensi_content, uuid.UUID(room_id)
            )

        # 6. Broadcast SSE document_updated ke seluruh anggota
        await collab_broadcast_manager.broadcast(room_id, {
            "type": "document_updated",
            "document_content": notulensi_content,
            "updated_by": "CAKRA AI (Notulensi Otomatis)"
        })

        return {
            "status": "success",
            "document_content": notulensi_content
        }

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
        mode: Optional[str] = None,
        request: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Menyimpan pesan pengguna, membroadcast ke seluruh tim melalui SSE,
        dan memicu respons CAKRA AI Teammate (baik karena mention @cakra maupun proaktif).
        """
        attachments = attachments or []
        attachments_json = json.dumps(attachments)
        msg_id = str(uuid.uuid4())
        # Deteksi apakah ada mention @cakra atau panggil cakra secara langsung
        is_mention = bool(re.search(r"\b@?cakra\b", message_text, re.IGNORECASE))

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
                mode=mode,
                request=request
            )
        )

        return msg_dict

    @staticmethod
    async def edit_message(room_id: str, message_id: str, npp: str, new_text: str) -> Dict[str, Any]:
        """
        Mengedit pesan milik sendiri di ruang diskusi dan membroadcast perubahan via SSE.
        """
        async with get_db() as conn:
            msg = await conn.fetchrow(
                "SELECT id, sender_npp, sender_type FROM collab_messages WHERE id = $1 AND room_id = $2",
                uuid.UUID(message_id), uuid.UUID(room_id)
            )
            if not msg:
                raise ValueError("Pesan tidak ditemukan.")
            if str(msg["sender_npp"]).strip() != str(npp).strip():
                raise PermissionError("Anda hanya dapat mengedit pesan milik Anda sendiri.")

            row = await conn.fetchrow(
                """
                UPDATE collab_messages
                SET message_text = $1
                WHERE id = $2 AND room_id = $3
                RETURNING id::text, room_id::text, sender_type, sender_npp, sender_name, message_text, is_mention, interjection_type, attachments, created_at
                """,
                new_text, uuid.UUID(message_id), uuid.UUID(room_id)
            )

        msg_dict = dict(row)
        msg_dict["created_at"] = msg_dict["created_at"].isoformat() if msg_dict.get("created_at") else ""
        if isinstance(msg_dict.get("attachments"), str):
            try:
                msg_dict["attachments"] = json.loads(msg_dict["attachments"])
            except Exception:
                pass

        await collab_broadcast_manager.broadcast(room_id, {
            "type": "message_edited",
            "message": msg_dict
        })
        return msg_dict

    @staticmethod
    async def broadcast_typing(room_id: str, npp: str, user_name: str, is_typing: bool, photo_url: Optional[str] = None):
        """
        Menyebarkan indikator mengetik dari pengguna ke seluruh anggota ruangan.
        """
        await collab_broadcast_manager.send_typing(
            room_id=room_id,
            sender=user_name,
            sender_npp=npp,
            photo_url=photo_url,
            is_typing=is_typing
        )

    @staticmethod
    async def _handle_ai_teammate_trigger(
        room_id: str,
        trigger_message: Dict[str, Any],
        is_mention: bool,
        mode: Optional[str] = None,
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

                # Ambil daftar anggota tim di ruangan untuk Team Awareness
                members_rows = await conn.fetch(
                    """
                    SELECT m.npp, COALESCE(u.preferred_name, u.fullname, m.npp) as name, u.divisi
                    FROM collab_room_members m
                    LEFT JOIN users u ON m.npp = u.npp
                    WHERE m.room_id = $1
                    """,
                    uuid.UUID(room_id)
                )
                team_members = [
                    {"npp": m["npp"], "name": m["name"], "divisi": m["divisi"] or "PT Pindad"}
                    for m in members_rows
                ]

                # Ambil 15 riwayat pesan terakhir beserta lampiran
                rows = await conn.fetch(
                    """
                    SELECT id::text, sender_type, sender_npp, sender_name, message_text, is_mention, attachments, created_at
                    FROM collab_messages
                    WHERE room_id = $1
                    ORDER BY created_at DESC
                    LIMIT 15
                    """,
                    uuid.UUID(room_id)
                )
                recent_messages = []
                for r in reversed(rows):
                    item = dict(r)
                    if isinstance(item.get("attachments"), str):
                        try:
                            item["attachments"] = json.loads(item["attachments"])
                        except Exception:
                            item["attachments"] = []
                    recent_messages.append(item)

            # 1. Ekstrak rujukan dokumen aktif jika ada di lampiran pesan pemicu
            context_doc = None
            for att in trigger_message.get("attachments") or []:
                if isinstance(att, dict) and att.get("type") == "context_doc":
                    context_doc = att
                    break

            # 2. Jika tidak ada di pesan pemicu (misal rekan kerja lain yang menyuruh: "coba cakra bedah pointnya dulu"),
            # cari rujukan dokumen aktif dari pesan-pesan sebelumnya dalam ruangan diskusi
            if not context_doc:
                for msg in reversed(recent_messages):
                    msg_atts = msg.get("attachments")
                    if isinstance(msg_atts, list):
                        for att in msg_atts:
                            if isinstance(att, dict) and att.get("type") == "context_doc":
                                context_doc = att
                                break
                    if context_doc:
                        break

            mode_collab = ModeCollab()
            # Di ruang Collab, tag dokumen atau tag mode yang dikirim rekan kerja
            # tidak memaksa CAKRA langsung membalas jika pesan ditujukan ke sesama tim tanpa @cakra.
            should_intervene = is_mention
            if mode:
                interjection_type = f"MODE_{mode.upper()}"
            elif is_mention:
                interjection_type = "EXPLICIT_MENTION"
            else:
                interjection_type = None

            # Jika bukan mention langsung atau perintah ke CAKRA, evaluasi Call 1 apakah butuh intervensi proaktif
            eval_ok, eval_reason, routing_data = await mode_collab.should_intervene(
                recent_messages=recent_messages,
                room_topic=room["topic"] or "",
                is_mention=is_mention
            )
            is_followup = len(recent_messages) >= 2 and recent_messages[-2].get("sender_type") == "CAKRA"
            if is_mention:
                should_intervene = True
            else:
                should_intervene = eval_ok
                if eval_ok:
                    if is_followup:
                        interjection_type = "CONVERSATIONAL_FOLLOWUP"
                    else:
                        interjection_type = "PROACTIVE_SUGGESTION"

            if not should_intervene:
                return

            # 3. CAKRA memutuskan akan merespons:
            # Tampilkan indikator mengetik terlebih dahulu (belum membuat bubble kosong)
            await collab_broadcast_manager.send_typing(
                room_id=room_id,
                sender="CAKRA AI Teammate",
                sender_npp="CAKRA",
                is_typing=True
            )

            # 4. Jeda natural (human conversational pacing 1.2 detik)
            await asyncio.sleep(1.2)

            # 5. Pengecekan Balapan (Chat Race / Pre-emption Check)
            # Cek apakah selama jeda tersebut ada pesan baru dari anggota tim lain
            trigger_msg_id = uuid.UUID(trigger_message["id"])
            async with get_db() as conn:
                newer_rows = await conn.fetch(
                    """
                    SELECT id::text, sender_type, sender_npp, sender_name, message_text, is_mention, attachments, created_at
                    FROM collab_messages
                    WHERE room_id = $1 
                      AND created_at > (SELECT created_at FROM collab_messages WHERE id = $2)
                      AND id != $2
                    ORDER BY created_at ASC
                    """,
                    uuid.UUID(room_id), trigger_msg_id
                )

            if newer_rows:
                # Ada pesan tim baru yang mendahului respon CAKRA!
                for nr in newer_rows:
                    item_nr = dict(nr)
                    if isinstance(item_nr.get("attachments"), str):
                        try:
                            item_nr["attachments"] = json.loads(item_nr["attachments"])
                        except Exception:
                            item_nr["attachments"] = []
                    recent_messages.append(item_nr)

                last_new_msg = newer_rows[-1]
                last_new_text = last_new_msg.get("message_text", "")
                is_last_mention = bool(re.search(r"\b@?cakra\b", last_new_text, re.IGNORECASE))

                # Jika pesan terbaru tidak memanggil CAKRA secara langsung,
                # evaluasi ulang apakah respon CAKRA masih diperlukan atau tim sudah menjawab/berganti topik
                if not is_last_mention and interjection_type in ["PROACTIVE_SUGGESTION", "CONVERSATIONAL_FOLLOWUP"]:
                    re_eval_ok, re_reason, re_routing = await mode_collab.should_intervene(
                        recent_messages=recent_messages,
                        room_topic=room["topic"] or "",
                        is_mention=False
                    )
                    if not re_eval_ok:
                        logger.info(f"[COLLAB_AI] Pre-empted by teammate message in room {room_id}. CAKRA yields floor and stays silent.")
                        await collab_broadcast_manager.send_typing(
                            room_id=room_id,
                            sender="CAKRA AI Teammate",
                            sender_npp="CAKRA",
                            is_typing=False
                        )
                        return
                    else:
                        eval_reason = re_reason
                        routing_data = re_routing

            # 6. Pencarian RAG Otomatis jika topik membutuhkan rujukan dokumen internal PT Pindad
            rag_context = ""
            rag_sources = []
            if routing_data.get("need_rag") or (mode and mode.lower() in ["documents", "document"]):
                try:
                    from backend.app.services.rag.rag_service import rag_service
                    rag_queries = routing_data.get("queries") or []
                    rag_judul = routing_data.get("query_judul") or []
                    if rag_queries:
                        rag_query_str = " ".join(rag_queries)
                    elif rag_judul:
                        rag_query_str = " ".join(rag_judul)
                    else:
                        rag_query_str = trigger_message.get("message_text", "")

                    clean_rag_query = re.sub(r"@cakra\b", "", rag_query_str, flags=re.IGNORECASE).strip()
                    if clean_rag_query:
                        logger.info(f"[COLLAB_RAG] 🔍 Menjalankan RAG hybrid search untuk tim: '{clean_rag_query}'")
                        rag_context, rag_sources = await rag_service.assemble_powerful_context(
                            query=clean_rag_query,
                            limit=3
                        )
                        logger.info(f"[COLLAB_RAG] ✨ RAG context berhasil disiapkan (chars={len(rag_context)}, docs={len(rag_sources)})")
                except Exception as rag_err:
                    logger.warning(f"[COLLAB_RAG] Gagal mengambil konteks RAG: {rag_err}")

            # 7. Hentikan status mengetik tepat saat streaming bubble dimulai
            await collab_broadcast_manager.send_typing(
                room_id=room_id,
                sender="CAKRA AI Teammate",
                sender_npp="CAKRA",
                is_typing=False
            )

            cakra_msg_id = str(uuid.uuid4())

            # 8. Kirim stream start dari CAKRA
            await collab_broadcast_manager.broadcast(room_id, {
                "type": "cakra_stream_start",
                "message_id": cakra_msg_id,
                "interjection_type": interjection_type or "EXPLICIT_MENTION"
            })

            # 9. Stream & kumpulkan respons dari CAKRA token-by-token secara real-time
            full_response_text = ""
            async for chunk in mode_collab.generate_response(
                room_name=room["name"],
                room_topic=room["topic"] or "",
                document_content=room["document_content"] or "",
                recent_messages=recent_messages,
                is_mention=is_mention,
                interjection_type=interjection_type or "EXPLICIT_MENTION",
                mode=mode,
                context_doc=context_doc,
                members=team_members,
                rag_context=rag_context,
                rag_sources=rag_sources,
                eval_reason=eval_reason,
                request=request
            ):
                full_response_text += chunk
                await collab_broadcast_manager.broadcast(room_id, {
                    "type": "cakra_stream_chunk",
                    "message_id": cakra_msg_id,
                    "chunk": chunk
                })

            clean_response = full_response_text.strip()
            if not clean_response:
                clean_response = "Saya sedang menyimak diskusi tim. Silakan lanjutkan atau mention @cakra jika butuh bantuan formulasi aturan."

            # 10. Susun lampiran sumber rujukan RAG jika ada
            final_attachments = []
            if rag_sources:
                for src in rag_sources[:3]:
                    final_attachments.append({
                        "type": "rag_source",
                        "title": src.get("title", "Dokumen Internal Pindad"),
                        "page": src.get("page", 1),
                        "score": src.get("score", 0.0)
                    })
            attachments_json = json.dumps(final_attachments)

            # 11. Simpan respons CAKRA ke collab_messages
            async with get_db() as conn:
                cakra_row = await conn.fetchrow(
                    """
                    INSERT INTO collab_messages (
                        id, room_id, sender_type, sender_npp, sender_name,
                        message_text, is_mention, interjection_type, attachments, created_at
                    )
                    VALUES ($1, $2, 'CAKRA', NULL, 'CAKRA AI Teammate', $3, $4, $5, $6::jsonb, NOW())
                    RETURNING id::text, room_id::text, sender_type, sender_npp, sender_name, message_text, is_mention, interjection_type, attachments, created_at
                    """,
                    uuid.UUID(cakra_msg_id), uuid.UUID(room_id), clean_response, is_mention, interjection_type, attachments_json
                )
                await conn.execute("UPDATE collab_rooms SET updated_at = NOW() WHERE id = $1", uuid.UUID(room_id))

            cakra_dict = dict(cakra_row)
            cakra_dict["created_at"] = cakra_dict["created_at"].isoformat()
            cakra_dict["attachments"] = final_attachments

            # 4. Broadcast akhir streaming dan pesan final
            await collab_broadcast_manager.broadcast(room_id, {
                "type": "cakra_stream_end",
                "message": cakra_dict
            })
            await collab_broadcast_manager.broadcast(room_id, {
                "type": "new_message",
                "message": cakra_dict
            })
            logger.info(f"✅ [COLLAB_AI] Response streamed to room {room_id} ({interjection_type})")

        except Exception as e:
            logger.error(f"❌ [COLLAB_AI] Error in AI teammate background handler: {e}")
            await collab_broadcast_manager.send_typing(room_id, sender="CAKRA AI Teammate", is_typing=False)
