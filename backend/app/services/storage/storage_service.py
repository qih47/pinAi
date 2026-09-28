import os
import shutil
import time
import logging
import re
from typing import Dict, Any, Optional
from backend.app.core.database import get_db
from backend.app.core.paths import ACCOUNTS_DIR

logger = logging.getLogger("CAKRA_STORAGE_SERVICE")

# Default Quota: 5.0 GB per employee (Nextcloud Pindad standard)
DEFAULT_STORAGE_QUOTA_BYTES = 5 * 1024 * 1024 * 1024  # 5,368,709,120 bytes

# In-memory fast cache for storage stats (TTL: 30 seconds)
_stats_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 30


def _sanitize_npp(npp: str) -> str:
    """Sanitasi NPP untuk keamanan path filesystem (mencegah path traversal)."""
    if not npp:
        raise ValueError("NPP tidak boleh kosong.")
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "", str(npp).strip())
    if not clean:
        raise ValueError("NPP tidak valid.")
    return clean


def _get_user_account_dir(npp: str) -> str:
    """Mendapatkan path direktori akun user yang aman."""
    clean_npp = _sanitize_npp(npp)
    user_dir = os.path.abspath(os.path.join(ACCOUNTS_DIR, clean_npp))
    # Validasi path traversal
    abs_accounts = os.path.abspath(ACCOUNTS_DIR)
    if not user_dir.startswith(abs_accounts):
        raise ValueError("Akses direktori ditolak: Path traversal detected.")
    return user_dir


class StorageService:
    @staticmethod
    def invalidate_user_cache(npp: str):
        """Invalidasi cache kalkulasi storage user setelah ada mutasi file/data."""
        clean_npp = _sanitize_npp(npp)
        _stats_cache.pop(clean_npp, None)

    @classmethod
    async def get_user_storage_stats(cls, npp: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Menghitung penggunaan storage user secara komprehensif:
        1. Lampiran & Dokumen (images/ + documents/ di semua sesi)
        2. Artefak AI & Draf (artifacts/ + docwriter/)
        3. Ruang Collab (collab/ folder)
        4. Teks DB Chat (chat_messages & chat_sessions)
        5. Teks DB Collab
        """
        clean_npp = _sanitize_npp(npp)
        now = time.time()

        if not force_refresh and clean_npp in _stats_cache:
            cached = _stats_cache[clean_npp]
            if now - cached.get("_cached_at", 0) < _CACHE_TTL_SECONDS:
                return cached["data"]

        user_dir = _get_user_account_dir(clean_npp)

        attachments_bytes = 0
        attachments_count = 0
        artifacts_bytes = 0
        artifacts_count = 0
        collabs_files_bytes = 0
        collabs_files_count = 0
        other_files_bytes = 0

        if os.path.exists(user_dir):
            for root, dirs, files in os.walk(user_dir):
                rel_path = os.path.relpath(root, user_dir).replace("\\", "/").lower()
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        f_size = os.path.getsize(file_path)
                    except OSError:
                        f_size = 0

                    if "image" in rel_path or "document" in rel_path:
                        attachments_bytes += f_size
                        attachments_count += 1
                    elif "artifact" in rel_path or "docwriter" in rel_path:
                        artifacts_bytes += f_size
                        artifacts_count += 1
                    elif "collab" in rel_path:
                        collabs_files_bytes += f_size
                        collabs_files_count += 1
                    else:
                        other_files_bytes += f_size

        # Query Database untuk ukuran chat text dan collab text
        chats_db_bytes = 0
        chat_sessions_count = 0
        chat_messages_count = 0
        collab_rooms_created = 0
        collab_db_bytes = 0

        try:
            async with get_db() as conn:
                chat_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(DISTINCT cs.id) as session_count,
                        COUNT(cm.id) as message_count,
                        COALESCE(SUM(pg_column_size(cm.content)), 0) + 
                        COALESCE(SUM(pg_column_size(cs.title)), 0) as chat_size_bytes
                    FROM chat_sessions cs
                    LEFT JOIN chat_messages cm ON cs.session_uuid = cm.session_uuid
                    WHERE cs.npp = $1 AND cs.is_deleted = FALSE
                """, clean_npp)

                if chat_stats:
                    chat_sessions_count = chat_stats["session_count"] or 0
                    chat_messages_count = chat_stats["message_count"] or 0
                    chats_db_bytes = chat_stats["chat_size_bytes"] or 0

                collab_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(DISTINCT cr.id) as created_rooms_count,
                        COALESCE(SUM(pg_column_size(cr.document_content)), 0) +
                        COALESCE(SUM(pg_column_size(cm.content)), 0) as collab_size_bytes
                    FROM collab_rooms cr
                    LEFT JOIN collab_messages cm ON cr.id = cm.room_id
                    WHERE cr.created_by = $1
                """, clean_npp)

                if collab_stats:
                    collab_rooms_created = collab_stats["created_rooms_count"] or 0
                    collab_db_bytes = collab_stats["collab_size_bytes"] or 0
        except Exception as e:
            logger.error(f"⚠️ [STORAGE_SERVICE] Gagal mengambil stats DB untuk NPP {clean_npp}: {e}")

        total_chats_bytes = chats_db_bytes
        total_collabs_bytes = collabs_files_bytes + collab_db_bytes
        total_used = (
            attachments_bytes +
            artifacts_bytes +
            total_chats_bytes +
            total_collabs_bytes +
            other_files_bytes
        )

        quota_bytes = DEFAULT_STORAGE_QUOTA_BYTES
        free_bytes = max(0, quota_bytes - total_used)
        used_percentage = round((total_used / quota_bytes) * 100, 1) if quota_bytes > 0 else 0.0

        result = {
            "quota_bytes": quota_bytes,
            "quota_gb": round(quota_bytes / (1024 ** 3), 1),
            "used_bytes": total_used,
            "free_bytes": free_bytes,
            "used_percentage": min(100.0, used_percentage),
            "is_near_quota": used_percentage >= 80.0,
            "is_critical_quota": used_percentage >= 90.0,
            "is_exceeded": used_percentage >= 98.0,
            "breakdown": {
                "attachments": {
                    "bytes": attachments_bytes,
                    "count": attachments_count,
                    "label": "Foto & Lampiran Berkas",
                },
                "artifacts": {
                    "bytes": artifacts_bytes,
                    "count": artifacts_count,
                    "label": "Artefak AI & Dokumen Draf",
                },
                "chats": {
                    "bytes": total_chats_bytes,
                    "count": chat_sessions_count,
                    "message_count": chat_messages_count,
                    "label": "Riwayat Percakapan Pribadi",
                },
                "collabs": {
                    "bytes": total_collabs_bytes,
                    "count": collab_rooms_created,
                    "label": "Ruang & Diskusi Tim Collab",
                },
                "system_cache": {
                    "bytes": other_files_bytes,
                    "label": "Cache Sistem & Metadata",
                }
            }
        }

        # Cache results
        _stats_cache[clean_npp] = {
            "_cached_at": now,
            "data": result
        }

        return result

    @classmethod
    async def check_upload_quota(cls, npp: str, incoming_bytes: int) -> bool:
        """
        Memeriksa apakah upload baru akan melebihi kuota 5.0 GB (98% threshold).
        Mengembalikan True jika aman, False jika melebihi kuota.
        """
        stats = await cls.get_user_storage_stats(npp)
        projected_used = stats["used_bytes"] + incoming_bytes
        if projected_used >= (DEFAULT_STORAGE_QUOTA_BYTES * 0.98):
            return False
        return True

    @classmethod
    async def purge_attachments_and_cache(cls, npp: str) -> Dict[str, Any]:
        """
        Membersihkan semua file lampiran dan dokumen fisik di direktori akun user.
        PENTING: Tidak menghapus pesan chat di DB, sehingga riwayat chat tetap terbaca utuh.
        """
        clean_npp = _sanitize_npp(npp)
        user_dir = _get_user_account_dir(clean_npp)
        deleted_bytes = 0
        deleted_files_count = 0

        if os.path.exists(user_dir):
            for root, dirs, files in os.walk(user_dir, topdown=False):
                rel_path = os.path.relpath(root, user_dir).replace("\\", "/").lower()
                # Cek apakah folder ini adalah folder lampiran/gambar/dokumen
                if "image" in rel_path or "document" in rel_path:
                    for f in files:
                        file_path = os.path.join(root, f)
                        try:
                            f_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_bytes += f_size
                            deleted_files_count += 1
                        except Exception as e:
                            logger.warning(f"⚠️ Gagal menghapus file lampiran {file_path}: {e}")

        cls.invalidate_user_cache(clean_npp)
        logger.info(f"🧹 [PURGE] Berhasil membersihkan {deleted_files_count} lampiran ({deleted_bytes} bytes) untuk NPP {clean_npp}")

        new_stats = await cls.get_user_storage_stats(clean_npp, force_refresh=True)
        return {
            "status": "success",
            "freed_bytes": deleted_bytes,
            "freed_files_count": deleted_files_count,
            "current_stats": new_stats,
        }

    @classmethod
    async def purge_artifacts(cls, npp: str) -> Dict[str, Any]:
        """
        Membersihkan file draf dokumen dan artefak AI di direktori akun user.
        """
        clean_npp = _sanitize_npp(npp)
        user_dir = _get_user_account_dir(clean_npp)
        deleted_bytes = 0
        deleted_files_count = 0

        if os.path.exists(user_dir):
            for root, dirs, files in os.walk(user_dir, topdown=False):
                rel_path = os.path.relpath(root, user_dir).replace("\\", "/").lower()
                if "artifact" in rel_path or "docwriter" in rel_path:
                    for f in files:
                        file_path = os.path.join(root, f)
                        try:
                            f_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_bytes += f_size
                            deleted_files_count += 1
                        except Exception as e:
                            logger.warning(f"⚠️ Gagal menghapus file artefak {file_path}: {e}")

        cls.invalidate_user_cache(clean_npp)
        logger.info(f"🧹 [PURGE_ARTIFACTS] Berhasil menghapus {deleted_files_count} artefak ({deleted_bytes} bytes) untuk NPP {clean_npp}")

        new_stats = await cls.get_user_storage_stats(clean_npp, force_refresh=True)
        return {
            "status": "success",
            "freed_bytes": deleted_bytes,
            "freed_files_count": deleted_files_count,
            "current_stats": new_stats,
        }

    @classmethod
    async def clear_private_chats(cls, npp: str) -> Dict[str, Any]:
        """
        Menghapus seluruh riwayat percakapan pribadi user (Soft Delete di DB dan hapus folder sesi).
        """
        clean_npp = _sanitize_npp(npp)
        deleted_sessions_count = 0

        try:
            async with get_db() as conn:
                # 1. Soft delete all active sessions
                res = await conn.execute("""
                    UPDATE chat_sessions 
                    SET is_deleted = TRUE, is_active = FALSE 
                    WHERE npp = $1 AND is_deleted = FALSE
                """, clean_npp)
                # Format response res: e.g. "UPDATE 15"
                if res and "UPDATE" in res:
                    deleted_sessions_count = int(res.split(" ")[-1])
        except Exception as e:
            logger.error(f"❌ [CLEAR_CHATS] Gagal mengupdate DB chat_sessions: {e}")
            raise

        cls.invalidate_user_cache(clean_npp)
        logger.info(f"🗑️ [CLEAR_CHATS] NPP {clean_npp} berhasil menghapus {deleted_sessions_count} sesi percakapan.")

        new_stats = await cls.get_user_storage_stats(clean_npp, force_refresh=True)
        return {
            "status": "success",
            "deleted_sessions_count": deleted_sessions_count,
            "current_stats": new_stats,
        }

    @classmethod
    async def clear_collab_data(cls, npp: str) -> Dict[str, Any]:
        """
        Menghapus semua ruang kolaborasi yang dibuat oleh user (dan keluar dari ruang lain).
        """
        clean_npp = _sanitize_npp(npp)
        deleted_rooms_count = 0

        try:
            async with get_db() as conn:
                # Hapus ruang yang dibuat oleh user
                res = await conn.execute("""
                    DELETE FROM collab_rooms 
                    WHERE created_by = $1
                """, clean_npp)
                if res and "DELETE" in res:
                    deleted_rooms_count = int(res.split(" ")[-1])

                # Keluar dari keanggotaan ruang lain
                await conn.execute("""
                    DELETE FROM collab_room_members 
                    WHERE npp = $1
                """, clean_npp)
        except Exception as e:
            logger.error(f"❌ [CLEAR_COLLABS] Gagal membersihkan data collab: {e}")
            raise

        # Hapus folder collab lokal akun user
        user_dir = _get_user_account_dir(clean_npp)
        collab_dir = os.path.join(user_dir, "collab")
        if os.path.exists(collab_dir):
            try:
                shutil.rmtree(collab_dir)
            except Exception as e:
                logger.warning(f"⚠️ Gagal menghapus folder collab user: {e}")

        cls.invalidate_user_cache(clean_npp)
        logger.info(f"👥 [CLEAR_COLLABS] NPP {clean_npp} berhasil menghapus {deleted_rooms_count} ruang collab.")

        new_stats = await cls.get_user_storage_stats(clean_npp, force_refresh=True)
        return {
            "status": "success",
            "deleted_rooms_count": deleted_rooms_count,
            "current_stats": new_stats,
        }

    @classmethod
    async def wipe_all_user_data(cls, npp: str) -> Dict[str, Any]:
        """
        Tindakan drastis: Menghapus seluruh percakapan, berkas fisik, artefak, dan ruang collab.
        Profil akun tetap ada, namun storage kembali ke 0.
        """
        clean_npp = _sanitize_npp(npp)
        await cls.clear_private_chats(clean_npp)
        await cls.clear_collab_data(clean_npp)
        await cls.purge_artifacts(clean_npp)
        await cls.purge_attachments_and_cache(clean_npp)

        # Bersihkan direktori akun sepenuhnya
        user_dir = _get_user_account_dir(clean_npp)
        if os.path.exists(user_dir):
            for item in os.listdir(user_dir):
                item_path = os.path.join(user_dir, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except Exception as e:
                    logger.warning(f"⚠️ Gagal membersihkan item {item_path}: {e}")

        cls.invalidate_user_cache(clean_npp)
        logger.info(f"💣 [WIPE_ALL] NPP {clean_npp} telah melakukan pembersihan total data.")

        new_stats = await cls.get_user_storage_stats(clean_npp, force_refresh=True)
        return {
            "status": "success",
            "message": "Semua data percakapan dan berkas berhasil dibersihkan sepenuhnya.",
            "current_stats": new_stats,
        }
