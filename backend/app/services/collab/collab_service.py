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

import os
import time
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
from backend.app.services.session.room_brain_service import RoomBrainService
from backend.app.core.paths import UPLOAD_DIR
from backend.app.utils.upload_validator import validate_uploaded_file, UploadValidationError
from backend.app.utils.security_firewall import validate_attachment_security

logger = logging.getLogger("COLLAB_SERVICE")


def clean_and_deduplicate_document(content: str) -> str:
    """
    Membersihkan teks dokumen notulensi secara otomatis di backend:
    - Menghilangkan paragraf atau blok teks berulang yang identik (case-insensitive & whitespace trimmed).
    - Mempertahankan struktur markdown, pemisah horizontal (---), headers, dan poin bullet.
    - Menghindari penumpukan duplikasi teks secara otomatis tanpa perlu tombol manual di frontend.
    """
    if not content or not content.strip():
        return ""

    # Sanitasi simbol matematika / LaTeX mentah agar rapi di notulensi
    content = re.sub(r'\$\s*\\?ightarrow\s*\$', ' → ', content)
    content = re.sub(r'\$\s*\\rightarrow\s*\$', ' → ', content)
    content = re.sub(r'\\rightarrow\b', ' → ', content)
    content = re.sub(r'\$\\([a-zA-Z]+)\$', lambda m: {'rightarrow': '→', 'leftarrow': '←', 'Rightarrow': '⇒', 'times': '×'}.get(m.group(1), m.group(0)), content)

    # Format butir bernomor (1., 2., 3., dst) yang ditulis bersambung menjadi baris list markdown terpisah
    content = re.sub(r'(?:^|\n|\s)\.\s*(\d+\.\s+)', r'\n\n\1', content)
    content = re.sub(r'([:：])\s*(1\.\s+)', r'\1\n\n\2', content)
    content = re.sub(r'([.!?;)]|```)\s*(\d+\.\s+[A-Za-z0-9_*])', r'\1\n\n\2', content)

    raw_blocks = re.split(r'\n\s*\n', content.strip())
    seen = set()
    unique_blocks = []

    for block in raw_blocks:
        b_clean = block.strip()
        if not b_clean:
            continue

        if b_clean in ("---", "***", "___"):
            if unique_blocks and unique_blocks[-1] != "---":
                unique_blocks.append("---")
            continue

        norm = re.sub(r'[\s\*\#\_\-]+', ' ', b_clean).strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            unique_blocks.append(b_clean)

    return "\n\n".join(unique_blocks)


class CollabService:
    @staticmethod
    def clean_document(content: str) -> str:
        return clean_and_deduplicate_document(content)

    @staticmethod
    async def get_user_rooms(npp: str, is_archived: bool = False) -> List[Dict[str, Any]]:
        """
        Mengambil daftar ruang diskusi tim di mana user terdaftar sebagai anggota aktif (ACCEPTED).
        """
        archive_cond = "AND r.is_archived = TRUE" if is_archived else "AND (r.is_archived = FALSE OR r.is_archived IS NULL)"
        query = f"""
            SELECT 
                r.id::text as id,
                r.name,
                r.topic,
                r.document_content,
                r.created_by,
                r.is_active,
                COALESCE(r.is_archived, FALSE) as is_archived,
                r.created_at,
                r.updated_at,
                m.role_in_room,
                m.last_read_at,
                (SELECT COUNT(*) FROM collab_room_members WHERE room_id = r.id AND COALESCE(status, 'ACCEPTED') = 'ACCEPTED') as member_count,
                (
                    SELECT COUNT(*)
                    FROM collab_messages cm
                    WHERE cm.room_id = r.id
                      AND cm.created_at > COALESCE(m.last_read_at, m.joined_at, r.created_at)
                      AND (cm.sender_npp != $1 OR cm.sender_npp IS NULL)
                ) as unread_count,
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
            WHERE m.npp = $1 AND r.is_active = TRUE AND COALESCE(m.status, 'ACCEPTED') = 'ACCEPTED' {archive_cond}
            ORDER BY (
                (
                    SELECT COUNT(*)
                    FROM collab_messages cm
                    WHERE cm.room_id = r.id
                      AND cm.created_at > COALESCE(m.last_read_at, m.joined_at, r.created_at)
                      AND (cm.sender_npp != $1 OR cm.sender_npp IS NULL)
                ) > 0
            ) DESC, r.updated_at DESC
        """
        async with get_db() as conn:
            rows = await conn.fetch(query, npp)
            results = []
            for r in rows:
                item = dict(r)
                item["unread_count"] = int(item.get("unread_count") or 0)
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
        Membuat ruang diskusi baru, menyetel creator sebagai OWNER (ACCEPTED),
        dan mengundang anggota awal (PENDING). Inisialisasi Room Brain SSOT.
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

                # 2. Insert creator as OWNER with status ACCEPTED
                await conn.execute(
                    """
                    INSERT INTO collab_room_members (room_id, npp, role_in_room, status, invited_by, invited_at, responded_at)
                    VALUES ($1, $2, 'OWNER', 'ACCEPTED', $2, NOW(), NOW())
                    ON CONFLICT (room_id, npp) DO UPDATE
                    SET role_in_room = 'OWNER', status = 'ACCEPTED', responded_at = NOW()
                    """,
                    uuid.UUID(room_id), created_by
                )

                # 3. Insert other initial members with status PENDING
                for member_npp in initial_members:
                    if member_npp and member_npp != created_by:
                        await conn.execute(
                            """
                            INSERT INTO collab_room_members (room_id, npp, role_in_room, status, invited_by, invited_at)
                            VALUES ($1, $2, 'MEMBER', 'PENDING', $3, NOW())
                            ON CONFLICT (room_id, npp) DO NOTHING
                            """,
                            uuid.UUID(room_id), member_npp, created_by
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

        # 5. Inisialisasi Room Brain SSOT di bawah Master NPP
        try:
            room_brain = RoomBrainService(created_by, room_id)
            room_brain.ensure_structure()
        except Exception as brain_err:
            logger.warning(f"[COLLAB] Gagal inisialisasi room brain structure: {brain_err}")

        return await CollabService.get_room_detail(room_id, created_by)

    @staticmethod
    async def rename_room(room_id: str, new_name: str, npp: str) -> bool:
        """Mengubah nama/judul ruang diskusi."""
        logger.info(f"[COLLAB] User {npp} renaming room {room_id} to '{new_name}'")
        async with get_db() as conn:
            await conn.execute(
                "UPDATE collab_rooms SET name = $1, updated_at = NOW() WHERE id = $2",
                new_name.strip(), uuid.UUID(room_id)
            )
            return True

    @staticmethod
    async def archive_room(room_id: str, is_archived: bool, npp: str) -> bool:
        """Mengarsipkan atau membatalkan arsip ruang diskusi."""
        logger.info(f"[COLLAB] User {npp} set archive={is_archived} for room {room_id}")
        async with get_db() as conn:
            await conn.execute(
                "UPDATE collab_rooms SET is_archived = $1, updated_at = NOW() WHERE id = $2",
                is_archived, uuid.UUID(room_id)
            )
            return True

    @staticmethod
    async def delete_room(room_id: str, npp: str) -> bool:
        """Menghapus ruang diskusi beserta anggota dan pesannya (CASCADE)."""
        logger.info(f"[COLLAB] User {npp} deleting room {room_id}")
        async with get_db() as conn:
            await conn.execute(
                "DELETE FROM collab_rooms WHERE id = $1",
                uuid.UUID(room_id)
            )
            return True

    @staticmethod
    async def get_room_detail(room_id: str, npp: str) -> Dict[str, Any]:
        """
        Mengambil informasi lengkap ruang, termasuk daftar anggota dan status undangannya.
        """
        async with get_db() as conn:
            # Pastikan user adalah member aktif (ACCEPTED)
            membership = await conn.fetchrow(
                "SELECT role_in_room, status FROM collab_room_members WHERE room_id = $1 AND npp = $2",
                uuid.UUID(room_id), npp
            )
            if not membership or membership.get("status") != "ACCEPTED":
                raise PermissionError("Anda bukan anggota aktif ruang diskusi ini.")

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
                    COALESCE(m.status, 'ACCEPTED') as status,
                    m.invited_by,
                    m.invited_at,
                    m.responded_at,
                    m.joined_at,
                    COALESCE(u.preferred_name, u.fullname, m.npp) as name,
                    u.divisi,
                    u.profile_photo_url
                FROM collab_room_members m
                LEFT JOIN users u ON m.npp = u.npp
                WHERE m.room_id = $1
                ORDER BY (m.role_in_room = 'OWNER') DESC, (COALESCE(m.status, 'ACCEPTED') = 'ACCEPTED') DESC, m.joined_at ASC
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
                    "status": m["status"],
                    "profile_photo_url": m["profile_photo_url"] or "",
                    "joined_at": m["joined_at"].isoformat() if m.get("joined_at") else "",
                    "invited_at": m["invited_at"].isoformat() if m.get("invited_at") else "",
                    "responded_at": m["responded_at"].isoformat() if m.get("responded_at") else ""
                }
                for m in members_rows
            ]
            return room_dict

    @staticmethod
    async def update_document(room_id: str, npp: str, document_content: str) -> Dict[str, Any]:
        """
        Memperbarui isi draf dokumen bersama di Document Pad dan membroadcast ke semua anggota.
        Otomatis menjalankan pembersihan dan deduplikasi di backend.
        """
        cleaned_doc = clean_and_deduplicate_document(document_content)
        async with get_db() as conn:
            await conn.execute(
                """
                UPDATE collab_rooms 
                SET document_content = $1, updated_at = NOW() 
                WHERE id = $2
                """,
                cleaned_doc, uuid.UUID(room_id)
            )

        # Broadcast pembaruan dokumen real-time
        await collab_broadcast_manager.broadcast(room_id, {
            "type": "document_updated",
            "document_content": cleaned_doc,
            "updated_by": npp
        })

        return {"status": "success", "document_content": cleaned_doc}

    @staticmethod
    async def append_to_document(
        room_id: str,
        npp: str,
        text: str,
        sender_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Menambahkan poin catatan baru (addition) ke dokumen secara atomic di database.
        Mencegah penimpaan (overwrite) atau hilangnya catatan sebelumnya.
        Melakukan deduplikasi otomatis di backend sehingga poin yang sama tidak masuk dua kali.
        """
        if not text or not text.strip():
            raise ValueError("Teks catatan tidak boleh kosong.")

        clean_text = text.strip()
        # Sanitasi simbol matematika / LaTeX mentah agar rapi di notulensi
        clean_text = re.sub(r'\$\s*\\?ightarrow\s*\$', ' → ', clean_text)
        clean_text = re.sub(r'\$\s*\\rightarrow\s*\$', ' → ', clean_text)
        clean_text = re.sub(r'\\rightarrow\b', ' → ', clean_text)
        clean_text = re.sub(r'\$\\([a-zA-Z]+)\$', lambda m: {'rightarrow': '→', 'leftarrow': '←', 'Rightarrow': '⇒', 'times': '×'}.get(m.group(1), m.group(0)), clean_text)

        # Format butir bernomor (1., 2., 3., dst) yang ditulis bersambung menjadi baris list markdown terpisah
        clean_text = re.sub(r'(?:^|\n|\s)\.\s*(\d+\.\s+)', r'\n\n\1', clean_text)
        clean_text = re.sub(r'([:：])\s*(1\.\s+)', r'\1\n\n\2', clean_text)
        clean_text = re.sub(r'([.!?;)]|```)\s*(\d+\.\s+[A-Za-z0-9_*])', r'\1\n\n\2', clean_text)

        async with get_db() as conn:
            # 1. Ambil dokumen terkini dari database
            row = await conn.fetchrow(
                "SELECT document_content FROM collab_rooms WHERE id = $1",
                uuid.UUID(room_id)
            )
            if not row:
                raise ValueError("Ruang diskusi tidak ditemukan.")

            current_doc = row["document_content"] or ""

            # 2. Cek apakah teks sudah ada di dalam dokumen (pencegahan duplikasi otomatis)
            text_norm = re.sub(r'[\s\*\#\_\-]+', ' ', clean_text).strip().lower()
            current_norm = re.sub(r'[\s\*\#\_\-]+', ' ', current_doc).strip().lower()

            if text_norm and text_norm in current_norm:
                return {
                    "status": "already_exists",
                    "document_content": current_doc,
                    "message": "Poin ini sudah tercatat di dalam Catatan Tim."
                }

            # 3. Format timestamp dan header kontributor
            time_str = datetime.now().strftime("%H:%M")
            if sender_name and sender_name.strip() and sender_name.strip().upper() != 'CAKRA':
                header = f"Catatan dari {sender_name.strip()} ({time_str} WIB)"
            else:
                header = f"Rekomendasi CAKRA AI ({time_str} WIB)"

            formatted_addition = f"**{header}:**\n{clean_text}"

            if current_doc.strip():
                new_doc = f"{current_doc.strip()}\n\n---\n{formatted_addition}"
            else:
                new_doc = formatted_addition

            # 4. Bersihkan dan deduplikasi otomatis di backend
            final_doc = clean_and_deduplicate_document(new_doc)

            # 5. Simpan atomic ke database
            await conn.execute(
                """
                UPDATE collab_rooms 
                SET document_content = $1, updated_at = NOW() 
                WHERE id = $2
                """,
                final_doc, uuid.UUID(room_id)
            )

        # 6. Broadcast perubahan dokumen via SSE ke seluruh anggota tim
        await collab_broadcast_manager.broadcast(room_id, {
            "type": "document_updated",
            "document_content": final_doc,
            "updated_by": sender_name or npp
        })

        return {"status": "success", "document_content": final_doc}

    @staticmethod
    async def summarize_room(room_id: str, npp: str) -> Dict[str, Any]:
        """
        Menyusun notulensi cerdas otomatis dari seluruh percakapan tim di ruangan
        dan memperbarui document_content di collab_rooms secara rapi & profesional.
        Mengintegrasikan draf dokumen yang ada tanpa menghilangkannya.
        """
        async with get_db() as conn:
            # 1. Ambil detail room
            room_row = await conn.fetchrow(
                "SELECT id::text, name, topic, document_content FROM collab_rooms WHERE id = $1",
                uuid.UUID(room_id)
            )
            if not room_row:
                raise ValueError("Ruang diskusi tidak ditemukan.")

            existing_doc = room_row["document_content"] or ""

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
            messages=messages,
            existing_document=existing_doc
        )

        # Bersihkan & deduplikasi otomatis di backend
        final_notulensi = clean_and_deduplicate_document(notulensi_content)

        # 5. Simpan notulensi ke database
        async with get_db() as conn:
            await conn.execute(
                """
                UPDATE collab_rooms 
                SET document_content = $1, updated_at = NOW() 
                WHERE id = $2
                """,
                final_notulensi, uuid.UUID(room_id)
            )

        # 6. Broadcast SSE document_updated ke seluruh anggota
        await collab_broadcast_manager.broadcast(room_id, {
            "type": "document_updated",
            "document_content": final_notulensi,
            "updated_by": "CAKRA AI (Notulensi Otomatis)"
        })

        return {"status": "success", "document_content": final_notulensi}

    @staticmethod
    async def invite_members(room_id: str, requester_npp: str, npps_to_invite: List[str]) -> Dict[str, Any]:
        """
        Menambahkan undangan anggota baru ke dalam ruang diskusi (status PENDING).
        """
        async with get_db() as conn:
            membership = await conn.fetchrow(
                "SELECT role_in_room FROM collab_room_members WHERE room_id = $1 AND npp = $2 AND COALESCE(status, 'ACCEPTED') = 'ACCEPTED'",
                uuid.UUID(room_id), requester_npp
            )
            if not membership:
                raise PermissionError("Hanya anggota aktif yang dapat mengundang rekan kerja.")

            invited = []
            for target_npp in npps_to_invite:
                if target_npp and target_npp != requester_npp:
                    res = await conn.execute(
                        """
                        INSERT INTO collab_room_members (room_id, npp, role_in_room, status, invited_by, invited_at, responded_at)
                        VALUES ($1, $2, 'MEMBER', 'PENDING', $3, NOW(), NULL)
                        ON CONFLICT (room_id, npp) DO UPDATE
                        SET status = 'PENDING', invited_by = EXCLUDED.invited_by, invited_at = NOW(), responded_at = NULL
                        WHERE collab_room_members.status = 'REJECTED'
                        """,
                        uuid.UUID(room_id), target_npp, requester_npp
                    )
                    if "INSERT 0 1" in res or "UPDATE 1" in res:
                        invited.append(target_npp)

        await collab_broadcast_manager.broadcast(room_id, {
            "type": "members_updated",
            "room_id": room_id,
            "invited_npps": invited
        })

        return {"status": "success", "invited_members": invited}

    @staticmethod
    async def get_pending_invitations(npp: str) -> List[Dict[str, Any]]:
        """
        Mengambil daftar undangan ruang diskusi yang berstatus PENDING untuk pengguna.
        """
        query = """
            SELECT 
                r.id::text as room_id,
                r.name as room_name,
                r.topic as room_topic,
                r.created_by as room_creator,
                m.invited_by,
                m.invited_at,
                COALESCE(u_inv.preferred_name, u_inv.fullname, m.invited_by) as inviter_name,
                u_inv.divisi as inviter_divisi,
                u_inv.profile_photo_url as inviter_photo_url,
                (
                    SELECT COUNT(*) FROM collab_room_members 
                    WHERE room_id = r.id AND COALESCE(status, 'ACCEPTED') = 'ACCEPTED'
                ) as member_count
            FROM collab_room_members m
            JOIN collab_rooms r ON r.id = m.room_id
            LEFT JOIN users u_inv ON u_inv.npp = m.invited_by
            WHERE m.npp = $1 
              AND m.status = 'PENDING' 
              AND r.is_active = TRUE 
              AND (r.is_archived = FALSE OR r.is_archived IS NULL)
            ORDER BY m.invited_at DESC
        """
        async with get_db() as conn:
            rows = await conn.fetch(query, npp)
            results = []
            for r in rows:
                item = dict(r)
                if item.get("invited_at"):
                    item["invited_at"] = item["invited_at"].isoformat()
                results.append(item)
            return results

    @staticmethod
    async def get_invitations_count(npp: str) -> int:
        """
        Menghitung total undangan pending untuk badge notifikasi counter.
        """
        query = """
            SELECT COUNT(*)
            FROM collab_room_members m
            JOIN collab_rooms r ON r.id = m.room_id
            WHERE m.npp = $1 
              AND m.status = 'PENDING' 
              AND r.is_active = TRUE 
              AND (r.is_archived = FALSE OR r.is_archived IS NULL)
        """
        async with get_db() as conn:
            count = await conn.fetchval(query, npp)
            return int(count or 0)

    @staticmethod
    async def get_total_unread_count(npp: str) -> int:
        """
        Menghitung total seluruh pesan baru yang belum dibaca pengguna di seluruh ruang kolaborasi aktif.
        """
        query = """
            SELECT COALESCE(SUM(sub.cnt), 0)
            FROM (
                SELECT COUNT(*) as cnt
                FROM collab_messages cm
                JOIN collab_room_members m ON m.room_id = cm.room_id
                JOIN collab_rooms r ON r.id = cm.room_id
                WHERE m.npp = $1 
                  AND COALESCE(m.status, 'ACCEPTED') = 'ACCEPTED'
                  AND r.is_active = TRUE
                  AND (r.is_archived = FALSE OR r.is_archived IS NULL)
                  AND cm.created_at > COALESCE(m.last_read_at, m.joined_at, r.created_at)
                  AND (cm.sender_npp != $1 OR cm.sender_npp IS NULL)
                GROUP BY cm.room_id
            ) sub
        """
        async with get_db() as conn:
            count = await conn.fetchval(query, npp)
            return int(count or 0)

    @staticmethod
    async def mark_room_read(room_id: str, npp: str) -> Dict[str, Any]:
        """
        Menandai seluruh pesan di ruangan sudah dibaca oleh user.
        """
        async with get_db() as conn:
            await conn.execute(
                "UPDATE collab_room_members SET last_read_at = NOW() WHERE room_id = $1 AND npp = $2",
                uuid.UUID(room_id), npp
            )
        return {"status": "success", "room_id": room_id}

    @staticmethod
    async def respond_invitation(room_id: str, npp: str, action: str) -> Dict[str, Any]:
        """
        Merespons undangan ruang diskusi: 'accept' atau 'reject'.
        """
        action_clean = (action or "").strip().lower()
        if action_clean not in ["accept", "reject"]:
            raise ValueError("Aksi tidak valid. Harus 'accept' atau 'reject'.")

        async with get_db() as conn:
            member = await conn.fetchrow(
                "SELECT role_in_room, status FROM collab_room_members WHERE room_id = $1 AND npp = $2",
                uuid.UUID(room_id), npp
            )
            if not member:
                raise PermissionError("Undangan tidak ditemukan.")
            if member["status"] != "PENDING":
                return {"status": "success", "message": f"Status undangan sudah '{member['status']}'."}

            room = await conn.fetchrow(
                "SELECT created_by, name FROM collab_rooms WHERE id = $1",
                uuid.UUID(room_id)
            )
            master_npp = room["created_by"] if room else npp

            if action_clean == "accept":
                await conn.execute(
                    """
                    UPDATE collab_room_members 
                    SET status = 'ACCEPTED', responded_at = NOW(), joined_at = NOW()
                    WHERE room_id = $1 AND npp = $2
                    """,
                    uuid.UUID(room_id), npp
                )
                try:
                    room_brain = RoomBrainService(master_npp, room_id)
                    room_brain.sync_member(npp)
                except Exception as err:
                    logger.warning(f"[COLLAB] Error syncing brain for member {npp}: {err}")

                await collab_broadcast_manager.broadcast(room_id, {
                    "type": "members_updated",
                    "room_id": room_id,
                    "joined_npp": npp
                })
                return {"status": "success", "action": "accept", "message": "Undangan berhasil diterima."}

            else:  # reject
                await conn.execute(
                    """
                    UPDATE collab_room_members 
                    SET status = 'REJECTED', responded_at = NOW()
                    WHERE room_id = $1 AND npp = $2
                    """,
                    uuid.UUID(room_id), npp
                )
                return {"status": "success", "action": "reject", "message": "Undangan ditolak."}

    @staticmethod
    async def get_room_messages(room_id: str, npp: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Mengambil riwayat obrolan di ruang diskusi.
        """
        async with get_db() as conn:
            # Pastikan user adalah anggota aktif
            membership = await conn.fetchrow(
                "SELECT role_in_room FROM collab_room_members WHERE room_id = $1 AND npp = $2 AND COALESCE(status, 'ACCEPTED') = 'ACCEPTED'",
                uuid.UUID(room_id), npp
            )
            if not membership:
                raise PermissionError("Anda bukan anggota aktif ruang diskusi ini.")

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
        # Deteksi apakah ada mention @cakra atau panggil cakra / cak secara langsung
        is_mention = bool(re.search(r"\b@?(?:cakra|cak)\b", message_text, re.IGNORECASE))

        async with get_db() as conn:
            membership = await conn.fetchrow(
                "SELECT role_in_room FROM collab_room_members WHERE room_id = $1 AND npp = $2 AND COALESCE(status, 'ACCEPTED') = 'ACCEPTED'",
                uuid.UUID(room_id), sender_npp
            )
            if not membership:
                raise PermissionError("Anda bukan anggota aktif ruang diskusi ini.")

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

        # 3. Trigger evaluasi otomatis kurasi poin penting ke Catatan Tim (Auto-Notes)
        asyncio.create_task(
            CollabService._evaluate_auto_notes_background(
                room_id=room_id,
                trigger_message=msg_dict,
                sender_name=sender_name,
                sender_npp=sender_npp
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
    async def _evaluate_auto_notes_background(
        room_id: str,
        trigger_message: Dict[str, Any],
        sender_name: Optional[str] = None,
        sender_npp: Optional[str] = None
    ):
        """
        Background task: Mengevaluasi apakah pesan percakapan (baik dari anggota tim atau CAKRA)
        mengandung poin krusial/kesepakatan rapat/action items yang harus otomatis masuk ke Catatan Tim.
        """
        message_text = trigger_message.get("message_text", "")
        if not message_text or len(message_text.strip()) < 15:
            return

        try:
            async with get_db() as conn:
                room_row = await conn.fetchrow(
                    "SELECT topic, document_content FROM collab_rooms WHERE id = $1",
                    uuid.UUID(room_id)
                )
                if not room_row:
                    return

                existing_doc = room_row["document_content"] or ""

                # Ambil 6 pesan terakhir untuk konteks
                msg_rows = await conn.fetch(
                    """
                    SELECT sender_name, sender_npp, message_text
                    FROM collab_messages
                    WHERE room_id = $1
                    ORDER BY created_at DESC
                    LIMIT 6
                    """,
                    uuid.UUID(room_id)
                )
                recent_msgs = [dict(r) for r in reversed(msg_rows)]

            from backend.app.services.pipeline.modes.mode_collab import ModeCollab
            mode_collab_inst = ModeCollab()
            eval_result = await mode_collab_inst.evaluate_and_extract_key_note(
                message_text=message_text,
                sender_name=sender_name or trigger_message.get("sender_name") or "Anggota Tim",
                room_topic=room_row["topic"] or "",
                recent_messages=recent_msgs,
                existing_document=existing_doc
            )

            if eval_result and eval_result.get("is_noteworthy") and eval_result.get("bullet_note"):
                bullet_note = eval_result["bullet_note"]
                category = eval_result.get("category", "Poin Penting")
                logger.info(f"📌 [AUTO_NOTE] Terdeteksi poin penting ({category}) di room {room_id}: {bullet_note}")

                # Tambahkan ke document_content via append_to_document
                res_append = await CollabService.append_to_document(
                    room_id=room_id,
                    npp=sender_npp or trigger_message.get("sender_npp") or "SYSTEM",
                    text=bullet_note,
                    sender_name=sender_name or trigger_message.get("sender_name") or "Anggota Tim"
                )

                if res_append.get("status") == "success":
                    # Broadcast event auto_note_added agar frontend menampilkan badge visual
                    await collab_broadcast_manager.broadcast(room_id, {
                        "type": "auto_note_added",
                        "message_id": trigger_message.get("id"),
                        "note": bullet_note,
                        "category": category,
                        "sender_name": sender_name or trigger_message.get("sender_name")
                    })
        except Exception as e:
            logger.warning(f"[AUTO_NOTE] Gagal mengevaluasi auto-note di background: {e}")

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
            # LANGKAH 1: SSE sedang berpikir jalan DULU di bubble
            cakra_msg_id = str(uuid.uuid4())
            await collab_broadcast_manager.broadcast(room_id, {
                "type": "cakra_stream_start",
                "message_id": cakra_msg_id,
                "interjection_type": interjection_type or "EXPLICIT_MENTION",
                "thinking_phase": "Sedang berpikir"
            })

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
                is_last_mention = bool(re.search(r"\b@?(?:cakra|cak)\b", last_new_text, re.IGNORECASE))

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
                        await collab_broadcast_manager.broadcast(room_id, {
                            "type": "cakra_stream_end",
                            "message_id": cakra_msg_id,
                            "aborted": True
                        })
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
                        await collab_broadcast_manager.broadcast(room_id, {
                            "type": "cakra_thinking_phase",
                            "message_id": cakra_msg_id,
                            "thinking_phase": "Sedang mencari referensi"
                        })
                        rag_context, rag_sources = await rag_service.assemble_powerful_context(
                            query=clean_rag_query,
                            limit=3
                        )
                        logger.info(f"[COLLAB_RAG] ✨ RAG context berhasil disiapkan (chars={len(rag_context)}, docs={len(rag_sources)})")
                except Exception as rag_err:
                    logger.warning(f"[COLLAB_RAG] Gagal mengambil konteks RAG: {rag_err}")

            # 7. Transisi fase ke "Sedang mengetik" saat mulai masuk proses formulasi jawaban
            await collab_broadcast_manager.broadcast(room_id, {
                "type": "cakra_thinking_phase",
                "message_id": cakra_msg_id,
                "thinking_phase": "Sedang mengetik"
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

            # Evaluasi apakah kesimpulan / rekomendasi CAKRA layak dicatat ke Catatan Tim
            asyncio.create_task(
                CollabService._evaluate_auto_notes_background(
                    room_id=room_id,
                    trigger_message=cakra_dict,
                    sender_name="CAKRA AI Teammate",
                    sender_npp="CAKRA"
                )
            )

            logger.info(f"✅ [COLLAB_AI] Response streamed to room {room_id} ({interjection_type})")

        except Exception as e:
            logger.error(f"❌ [COLLAB_AI] Error in AI teammate background handler: {e}")
            if 'cakra_msg_id' in locals():
                await collab_broadcast_manager.broadcast(room_id, {
                    "type": "cakra_stream_end",
                    "message_id": cakra_msg_id,
                    "aborted": True
                })

    @staticmethod
    async def save_attachments(
        room_id: str,
        sender_npp: str,
        files: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Menyimpan berkas fisik lampiran obrolan tim ke Room Brain SSOT
        accounts/{master_npp}/collab/{room_id}/brain/images/
        dan mencatatnya ke manifest.json ruangan.
        """
        safe_room = "".join(c for c in str(room_id) if c.isalnum() or c == "-").strip("-")
        if not safe_room:
            raise ValueError("ID ruangan tidak valid.")

        async with get_db() as conn:
            membership = await conn.fetchrow(
                "SELECT role_in_room, status FROM collab_room_members WHERE room_id = $1 AND npp = $2",
                uuid.UUID(safe_room), sender_npp
            )
            if not membership or membership.get("status") != "ACCEPTED":
                raise PermissionError("Anda bukan anggota aktif ruangan ini.")

            room = await conn.fetchrow(
                "SELECT created_by FROM collab_rooms WHERE id = $1",
                uuid.UUID(safe_room)
            )
            if not room:
                raise ValueError("Ruang diskusi tidak ditemukan.")
            master_npp = room["created_by"]

        room_brain = RoomBrainService(master_npp, safe_room)
        room_brain.ensure_structure()
        if sender_npp != master_npp:
            room_brain.sync_member(sender_npp)

        target_dir = room_brain.images_dir

        results = []
        for file in files:
            await validate_attachment_security(file)
            file_bytes = await file.read()
            is_valid, validation_msg = validate_uploaded_file(
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream",
                file_bytes=file_bytes
            )
            if not is_valid:
                raise UploadValidationError(f"File '{file.filename}' tidak valid: {validation_msg}")

            # Sanitasi nama file
            safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)
            unique_filename = f"{int(time.time())}_{safe_filename}"
            target_path = target_dir / unique_filename

            with open(target_path, "wb") as f:
                f.write(file_bytes)

            file_size = len(file_bytes)
            relative_path = f"accounts/{master_npp}/collab/{safe_room}/brain/images/{unique_filename}"
            is_pdf = file.filename.lower().endswith(".pdf") or (file.content_type == "application/pdf")
            is_img = bool(
                (file.content_type or "").startswith("image/") or
                re.search(r"\.(png|jpe?g|webp|gif|bmp|svg)$", file.filename, re.I)
            )

            attachment_meta = {
                "name": file.filename,
                "filename": unique_filename,
                "file_path": relative_path,
                "file_url": f"/{relative_path}",
                "size": file_size,
                "type": file.content_type or ("application/pdf" if is_pdf else "application/octet-stream"),
                "is_pdf": is_pdf,
                "is_image": is_img,
                "uploaded_by": sender_npp
            }
            await room_brain.record_attachment(attachment_meta)
            results.append(attachment_meta)
            logger.info(f"📎 [COLLAB_UPLOAD] File '{file.filename}' ({file_size} bytes) tersimpan ke {relative_path}")

        return results

