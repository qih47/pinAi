"""
CAKRA AI — User Management Service
===================================
Service logika bisnis untuk mengelola pengguna di RAGDB dan sinkronisasi
dengan HRIS DB (MURNI SELECT / Read-Only).

Aturan Arsitektur:
- hris_db: HANYA BOLEH SELECT (Read-Only). Tidak boleh ada INSERT/UPDATE/DELETE.
- ragdb: Penyimpanan lokal pengguna CAKRA (tabel users & user_account_types).
  Semua modifikasi role, password hash (bcrypt), dan penambahan user manual
  non-resmi dilakukan di sini tanpa membutuhkan ALTER TABLE pada tabel users.
"""

import logging
import bcrypt
from typing import Optional, Dict, Any, List, Tuple
from backend.app.core.database import get_db, get_hris_db
from backend.app.utils.employee_cache import invalidate_employee_cache

logger = logging.getLogger("CAKRA_USER_MANAGEMENT_SERVICE")

VALID_ROLES = {"USER", "TRAINER", "ADMIN", "SUPERADMIN"}


class UserManagementService:
    @staticmethod
    async def ensure_schema() -> None:
        """Memastikan tabel user_account_types tersedia di RAGDB."""
        try:
            async with get_db() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_account_types (
                        npp VARCHAR(50) PRIMARY KEY,
                        account_type VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    CREATE INDEX IF NOT EXISTS idx_user_account_type ON user_account_types(account_type);
                """)
        except Exception as e:
            logger.warning(f"⚠️ [USER_MGMT] Gagal memastikan schema user_account_types: {e}")

    @staticmethod
    async def get_users_list(
        page: int = 1,
        page_size: int = 15,
        search: str = "",
        role_filter: str = "",
        type_filter: str = ""
    ) -> Dict[str, Any]:
        """
        Mengambil daftar pengguna dari ragdb.users dengan filter, pencarian,
        dan informasi statistik pengguna.
        """
        await UserManagementService.ensure_schema()
        offset = (page - 1) * page_size

        where_clauses = ["1=1"]
        params: List[Any] = []
        p_idx = 1

        if search:
            search_pattern = f"%{search.strip()}%"
            where_clauses.append(f"(u.npp ILIKE ${p_idx} OR u.fullname ILIKE ${p_idx} OR u.divisi ILIKE ${p_idx} OR u.email ILIKE ${p_idx})")
            params.append(search_pattern)
            p_idx += 1

        if role_filter and role_filter.upper() != "ALL":
            where_clauses.append(f"u.role = ${p_idx}")
            params.append(role_filter.upper())
            p_idx += 1

        if type_filter and type_filter.upper() != "ALL":
            if type_filter.upper() == "MANUAL":
                where_clauses.append(f"COALESCE(uat.account_type, 'HRIS') = 'MANUAL'")
            elif type_filter.upper() == "HRIS":
                where_clauses.append(f"COALESCE(uat.account_type, 'HRIS') = 'HRIS'")

        where_sql = " AND ".join(where_clauses)

        async with get_db() as conn:
            # 1. Hitung total data sesuai filter
            count_query = f"""
                SELECT COUNT(*) 
                FROM users u
                LEFT JOIN user_account_types uat ON uat.npp = u.npp
                WHERE {where_sql}
            """
            total_count = await conn.fetchval(count_query, *params)

            # 2. Ambil data users dengan pagination
            data_query = f"""
                SELECT 
                    u.npp, 
                    u.fullname, 
                    u.preferred_name, 
                    u.divisi, 
                    u.role, 
                    u.email, 
                    COALESCE(uat.account_type, 'HRIS') as account_type,
                    u.profile_photo_url,
                    u.created_at,
                    (u.password_hash IS NOT NULL) as has_password
                FROM users u
                LEFT JOIN user_account_types uat ON uat.npp = u.npp
                WHERE {where_sql}
                ORDER BY u.created_at DESC NULLS LAST, u.npp ASC
                LIMIT ${p_idx} OFFSET ${p_idx + 1}
            """
            rows = await conn.fetch(data_query, *params, page_size, offset)

            # 3. Hitung ringkasan statistik
            stats_query = """
                SELECT 
                    COUNT(*) as total_all,
                    COUNT(*) FILTER (WHERE COALESCE(uat.account_type, 'HRIS') = 'MANUAL') as total_manual,
                    COUNT(*) FILTER (WHERE COALESCE(uat.account_type, 'HRIS') = 'HRIS') as total_hris,
                    COUNT(*) FILTER (WHERE u.role = 'ADMIN' OR u.role = 'SUPERADMIN') as total_admin,
                    COUNT(*) FILTER (WHERE u.role = 'TRAINER') as total_trainer,
                    COUNT(*) FILTER (WHERE u.role = 'USER') as total_user
                FROM users u
                LEFT JOIN user_account_types uat ON uat.npp = u.npp
            """
            stats_row = await conn.fetchrow(stats_query)

        users_list = []
        for r in rows:
            users_list.append({
                "npp": r["npp"],
                "fullname": r["fullname"] or "-",
                "preferred_name": r["preferred_name"],
                "divisi": r["divisi"] or "Umum",
                "role": r["role"] or "USER",
                "email": r["email"] or "-",
                "account_type": r["account_type"],
                "profile_photo_url": r["profile_photo_url"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "has_password": r["has_password"]
            })

        return {
            "users": users_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_count or 0,
                "total_pages": (total_count + page_size - 1) // page_size if total_count else 0
            },
            "statistics": {
                "total_all": stats_row["total_all"] if stats_row else 0,
                "total_manual": stats_row["total_manual"] if stats_row else 0,
                "total_hris": stats_row["total_hris"] if stats_row else 0,
                "roles": {
                    "ADMIN": stats_row["total_admin"] if stats_row else 0,
                    "TRAINER": stats_row["total_trainer"] if stats_row else 0,
                    "USER": stats_row["total_user"] if stats_row else 0
                }
            }
        }

    @staticmethod
    async def create_manual_user(
        npp: str,
        fullname: str,
        divisi: str,
        role: str,
        password: str,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Menambahkan pengguna manual / non-tetap langsung ke ragdb.users.
        Password di-hash dengan bcrypt sehingga langsung dapat digunakan login.
        """
        await UserManagementService.ensure_schema()
        clean_npp = npp.strip()
        clean_name = fullname.strip()
        clean_role = role.strip().upper()

        if not clean_npp:
            raise ValueError("ID Pengguna / NPP tidak boleh kosong")
        if not clean_name:
            raise ValueError("Nama lengkap tidak boleh kosong")
        if clean_role not in VALID_ROLES:
            raise ValueError(f"Role tidak valid. Pilihan: {', '.join(VALID_ROLES)}")
        if not password or len(password.strip()) < 6:
            raise ValueError("Password minimal 6 karakter")

        hashed_pw = bcrypt.hashpw(password.strip().encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        async with get_db() as conn:
            # Cek duplikasi
            existing = await conn.fetchrow("SELECT npp FROM users WHERE npp = $1", clean_npp)
            if existing:
                raise ValueError(f"User dengan ID / NPP '{clean_npp}' sudah terdaftar di CAKRA.")

            async with conn.transaction():
                query = """
                    INSERT INTO users (
                        npp, fullname, divisi, role, password_hash, email, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    RETURNING npp, fullname, divisi, role, email, created_at
                """
                new_user = await conn.fetchrow(
                    query,
                    clean_npp,
                    clean_name,
                    divisi.strip() if divisi else "Mitra / Non-Tetap",
                    clean_role,
                    hashed_pw,
                    email.strip() if email else None
                )

                # Catat metadata account_type = 'MANUAL'
                await conn.execute("""
                    INSERT INTO user_account_types (npp, account_type, created_at)
                    VALUES ($1, 'MANUAL', NOW())
                    ON CONFLICT (npp) DO UPDATE SET account_type = 'MANUAL';
                """, clean_npp)

        logger.info(f"✅ [USER_MGMT] Berhasil mendaftarkan user manual baru: {clean_npp} ({clean_name}) role={clean_role}")
        return {
            "npp": new_user["npp"],
            "fullname": new_user["fullname"],
            "divisi": new_user["divisi"],
            "role": new_user["role"],
            "email": new_user["email"],
            "account_type": "MANUAL",
            "created_at": new_user["created_at"].isoformat() if new_user["created_at"] else None
        }

    @staticmethod
    async def search_hris_employees(search_query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Pencarian data karyawan resmi di hris_db (MURNI SELECT / Read-Only).
        Juga memeriksa status apakah karyawan tersebut sudah terdaftar di ragdb.users.
        """
        clean_q = search_query.strip()
        if not clean_q or len(clean_q) < 2:
            return []

        pattern = f"%{clean_q}%"

        # 1. SELECT MURNI dari HRIS DB
        async with get_hris_db() as hris_conn:
            hris_query = """
                SELECT 
                    mp.npp, 
                    mp.nama_lengkap AS nama, 
                    split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi,
                    mp.email_internet, 
                    mp.email_intranet
                FROM master_unit unit
                JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                WHERE (
                    mp.npp ILIKE $1 OR 
                    mp.nama_lengkap ILIKE $1
                ) AND mp.npp IS NOT NULL
                ORDER BY mp.nama_lengkap ASC
                LIMIT $2
            """
            hris_rows = await hris_conn.fetch(hris_query, pattern, limit)

        if not hris_rows:
            return []

        # 2. Cek status di ragdb.users untuk mengetahui siapa yang sudah di-impor
        npps = [r["npp"] for r in hris_rows if r["npp"]]
        imported_map: Dict[str, Dict[str, Any]] = {}

        if npps:
            async with get_db() as rag_conn:
                rag_users = await rag_conn.fetch(
                    "SELECT npp, role, created_at FROM users WHERE npp = ANY($1)",
                    npps
                )
                for u in rag_users:
                    imported_map[u["npp"]] = {
                        "role": u["role"],
                        "created_at": u["created_at"].isoformat() if u["created_at"] else None
                    }

        results = []
        for r in hris_rows:
            npp_val = r["npp"]
            is_in_rag = npp_val in imported_map
            email_val = r["email_internet"] or r["email_intranet"] or "-"

            results.append({
                "npp": npp_val,
                "nama": r["nama"] or "-",
                "divisi": r["divisi"] or "Umum",
                "email": email_val,
                "is_imported": is_in_rag,
                "current_role": imported_map[npp_val]["role"] if is_in_rag else None
            })

        return results

    @staticmethod
    async def import_hris_employee(npp: str, initial_role: str = "USER") -> Dict[str, Any]:
        """
        Menyalin personil dari hris_db (MURNI SELECT) ke ragdb.users.
        Jika sudah ada, akan memperbarui role dan informasinya.
        """
        await UserManagementService.ensure_schema()
        clean_npp = npp.strip()
        clean_role = initial_role.strip().upper()

        if clean_role not in VALID_ROLES:
            clean_role = "USER"

        # 1. SELECT data personil dari HRIS DB
        async with get_hris_db() as hris_conn:
            hris_query = """
                SELECT 
                    mp.npp, 
                    mp.nama_lengkap AS nama, 
                    split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi,
                    mp.email_internet, 
                    mp.email_intranet
                FROM master_unit unit
                JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                WHERE (tu.npp = $1 OR mp.npp = $1)
                LIMIT 1
            """
            personil = await hris_conn.fetchrow(hris_query, clean_npp)

        if not personil:
            raise ValueError(f"Karyawan dengan NPP '{clean_npp}' tidak ditemukan di HRIS DB.")

        user_fullname = personil["nama"] or "Karyawan Pindad"
        user_divisi = personil["divisi"] or "Umum"
        user_email = personil["email_internet"] or personil["email_intranet"]

        # 2. INSERT / SINKRONKAN ke RAGDB
        async with get_db() as rag_conn:
            async with rag_conn.transaction():
                upsert_query = """
                    INSERT INTO users (npp, fullname, divisi, role, email, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (npp) DO UPDATE SET
                        fullname = EXCLUDED.fullname,
                        divisi = EXCLUDED.divisi,
                        role = EXCLUDED.role,
                        email = COALESCE(EXCLUDED.email, users.email)
                    RETURNING npp, fullname, divisi, role, email;
                """
                result = await rag_conn.fetchrow(
                    upsert_query,
                    clean_npp,
                    user_fullname,
                    user_divisi,
                    clean_role,
                    user_email
                )

                # Catat metadata account_type = 'HRIS'
                await rag_conn.execute("""
                    INSERT INTO user_account_types (npp, account_type, created_at)
                    VALUES ($1, 'HRIS', NOW())
                    ON CONFLICT (npp) DO UPDATE SET account_type = 'HRIS';
                """, clean_npp)

        invalidate_employee_cache(clean_npp)
        logger.info(f"✅ [USER_MGMT] Berhasil mengimpor/menyinkronkan karyawan HRIS: {clean_npp} ({user_fullname}) role={clean_role}")

        return {
            "npp": result["npp"],
            "fullname": result["fullname"],
            "divisi": result["divisi"],
            "role": result["role"],
            "email": result["email"],
            "account_type": "HRIS"
        }

    @staticmethod
    async def update_user_role(npp: str, new_role: str, current_admin_npp: Optional[str] = None) -> Dict[str, Any]:
        """Memperbarui role pengguna di ragdb.users dengan proteksi hierarki SUPERADMIN."""
        clean_npp = npp.strip()
        clean_role = new_role.strip().upper()

        if clean_role not in VALID_ROLES:
            raise ValueError(f"Role tidak valid. Pilihan role: {', '.join(VALID_ROLES)}")

        async with get_db() as conn:
            # 1. Cek role admin pemanggil
            caller_role = "ADMIN"
            if current_admin_npp:
                caller = await conn.fetchrow("SELECT role FROM users WHERE npp = $1", current_admin_npp.strip())
                if caller and caller["role"]:
                    caller_role = caller["role"].upper()

            user = await conn.fetchrow("SELECT npp, fullname, role FROM users WHERE npp = $1", clean_npp)
            if not user:
                raise ValueError(f"User dengan NPP/ID '{clean_npp}' tidak ditemukan di CAKRA.")

            target_current_role = (user["role"] or "USER").upper()

            # 2. Proteksi SUPERADMIN:
            # - Admin biasa tidak boleh mengubah akun SUPERADMIN
            if target_current_role == "SUPERADMIN" and caller_role != "SUPERADMIN":
                raise ValueError("Akses ditolak: Hanya Superadmin yang berhak mengubah hak akses akun Superadmin.")

            # - Admin biasa tidak boleh mengangkat user menjadi SUPERADMIN
            if clean_role == "SUPERADMIN" and caller_role != "SUPERADMIN":
                raise ValueError("Akses ditolak: Hanya Superadmin yang berhak mengangkat pengguna menjadi Superadmin.")

            await conn.execute(
                "UPDATE users SET role = $2 WHERE npp = $1",
                clean_npp, clean_role
            )

        invalidate_employee_cache(clean_npp)
        logger.info(f"✅ [USER_MGMT] Role user {clean_npp} diubah dari {user['role']} -> {clean_role} oleh {current_admin_npp}")
        return {
            "npp": clean_npp,
            "fullname": user["fullname"],
            "old_role": user["role"],
            "new_role": clean_role
        }

    @staticmethod
    async def reset_user_password(npp: str, new_password: str) -> Dict[str, Any]:
        """
        Mereset password pengguna di ragdb.users menggunakan bcrypt.
        Juga menghapus session login aktif agar user harus login ulang.
        """
        clean_npp = npp.strip()
        if not new_password or len(new_password.strip()) < 6:
            raise ValueError("Password baru minimal 6 karakter")

        hashed_pw = bcrypt.hashpw(new_password.strip().encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        async with get_db() as conn:
            user = await conn.fetchrow("SELECT npp, fullname FROM users WHERE npp = $1", clean_npp)
            if not user:
                raise ValueError(f"User dengan NPP/ID '{clean_npp}' tidak ditemukan di CAKRA.")

            async with conn.transaction():
                await conn.execute(
                    "UPDATE users SET password_hash = $2 WHERE npp = $1",
                    clean_npp, hashed_pw
                )
                # Invalidate sesi aktif
                await conn.execute("DELETE FROM session_login WHERE npp = $1", clean_npp)

        logger.info(f"✅ [USER_MGMT] Password user {clean_npp} berhasil di-reset dan sesi aktif dicabut")
        return {
            "npp": clean_npp,
            "fullname": user["fullname"],
            "status": "success",
            "message": "Password berhasil di-reset"
        }

    @staticmethod
    async def delete_user(npp: str, current_admin_npp: Optional[str] = None) -> Dict[str, Any]:
        """
        Menghapus akun pengguna dari ragdb.users beserta sesi aktifnya.
        TIDAK MENYENTUH HRIS DB sama sekali.
        """
        clean_npp = npp.strip()

        if current_admin_npp and clean_npp == current_admin_npp:
            raise ValueError("Anda tidak dapat menghapus akun Anda sendiri yang sedang aktif.")

        async with get_db() as conn:
            # 1. Cek role admin pemanggil
            caller_role = "ADMIN"
            if current_admin_npp:
                caller = await conn.fetchrow("SELECT role FROM users WHERE npp = $1", current_admin_npp.strip())
                if caller and caller["role"]:
                    caller_role = caller["role"].upper()

            user = await conn.fetchrow("SELECT npp, fullname, role FROM users WHERE npp = $1", clean_npp)
            if not user:
                raise ValueError(f"User dengan NPP/ID '{clean_npp}' tidak ditemukan di CAKRA.")

            # 2. Proteksi SUPERADMIN: Akun Superadmin tidak bisa dihapus oleh Admin biasa
            target_role = (user["role"] or "USER").upper()
            if target_role == "SUPERADMIN" and caller_role != "SUPERADMIN":
                raise ValueError("Akses ditolak: Akun Superadmin dilindungi dan tidak dapat dihapus oleh Admin biasa.")

            async with conn.transaction():
                # Hapus session login aktif
                await conn.execute("DELETE FROM session_login WHERE npp = $1", clean_npp)
                # Hapus metadata tipe akun
                await conn.execute("DELETE FROM user_account_types WHERE npp = $1", clean_npp)
                # Hapus setting khusus jika ada
                await conn.execute("DELETE FROM user_settings WHERE npp = $1", clean_npp)
                await conn.execute("DELETE FROM user_integrations WHERE npp = $1", clean_npp)
                # Hapus user dari ragdb.users
                await conn.execute("DELETE FROM users WHERE npp = $1", clean_npp)

        invalidate_employee_cache(clean_npp)
        logger.info(f"🗑️ [USER_MGMT] User {clean_npp} ({user['fullname']}) berhasil dihapus dari CAKRA oleh admin {current_admin_npp}")
        return {
            "npp": clean_npp,
            "fullname": user["fullname"],
            "status": "success",
            "message": "Pengguna berhasil dihapus dari CAKRA"
        }
