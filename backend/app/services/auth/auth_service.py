import logging
import hashlib
import uuid
import bcrypt
from typing import Optional, Dict, Any, Tuple

from backend.app.core.database import get_db, get_hris_db
from backend.app.core.config import settings
from backend.app.services.security_service import log_security_event

logger = logging.getLogger("CAKRA_AUTH_SERVICE")

class AuthService:
    @staticmethod
    async def get_user_role(npp: str) -> Optional[str]:
        """Fetch the role of the user by NPP."""
        try:
            async with get_db() as conn:
                role = await conn.fetchval(
                    "SELECT role FROM users WHERE npp = $1",
                    npp
                )
                return role
        except Exception as e:
            logger.error(f"Failed to fetch user role: {e}")
            return None

    @staticmethod
    async def verify_session(token: str) -> Optional[Dict[str, Any]]:
        """Verify the session token and update last activity."""
        async with get_db() as conn:
            query = """
                SELECT u.npp, u.fullname, u.divisi, u.role, s.expires_at
                FROM session_login s
                JOIN users u ON s.npp = u.npp
                WHERE s.session_token = $1 AND s.is_login = TRUE AND s.expires_at > NOW()
            """
            user = await conn.fetchrow(query, token)

            if user:
                # Update aktivitas terakhir pegawai
                await conn.execute(
                    "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
                    token,
                )
                
                user_email = None
                try:
                    async with get_hris_db() as hris_conn:
                        hris_data = await hris_conn.fetchrow(
                            "SELECT email_internet, email_intranet FROM master_personil WHERE npp = $1", user["npp"]
                        )
                        if hris_data:
                            user_email = hris_data["email_internet"] or hris_data["email_intranet"]
                except Exception as e:
                    logger.error(f"Gagal mengambil email dari HRIS untuk NPP {user['npp']}: {e}")

                return {
                    "npp": user["npp"],
                    "username": user["npp"],
                    "fullname": user["fullname"],
                    "divisi": user["divisi"],
                    "role": user["role"],
                    "email": user_email,
                    "session_token": token,
                    "expires_at": user["expires_at"].isoformat() if user["expires_at"] else None
                }
            return None

    @staticmethod
    async def login(npp: str, password_input: str, user_ip: str, u_agent: str, guest_session_id: Optional[str]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Proses login: Cek bypass, HRIS, sinkronisasi RAGDB lokal.
        Mengembalikan tuple: (success, user_data_dict_or_none, error_message_string)
        """
        password_md5 = hashlib.md5(password_input.encode()).hexdigest()
        
        user_fullname = None
        user_divisi = None
        current_role = "USER"

        bypass_enabled = settings.BYPASS_ACCOUNT_ENABLED
        bypass_npp = settings.BYPASS_ACCOUNT_NPP or "99999"
        bypass_password_hash = settings.BYPASS_ACCOUNT_PASSWORD_HASH or ""
        
        user_hris = None

        if bypass_enabled and str(npp) == bypass_npp:
            if bypass_password_hash and bcrypt.checkpw(password_input.encode(), bypass_password_hash.encode()):
                user_fullname = "Admin CAKRA"
                user_divisi = "System Admin"
                current_role = "TRAINER"
            else:
                await log_security_event("LOGIN_FAILED", npp, user_ip, "Invalid admin bypass password", "HIGH")
                return False, None, "Password salah"
        else:
            async with get_db() as conn:
                local_user = await conn.fetchrow(
                    "SELECT fullname, divisi, role FROM users WHERE npp = $1", npp
                )
                if local_user:
                    current_role = local_user["role"]

            async with get_hris_db() as conn:
                user_hris = await conn.fetchrow(
                    """
                    SELECT 
                        mp.nama_lengkap as nama, tu.npp, tu.password, 
                        split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi,
                        mp.email_internet, mp.email_intranet
                    FROM master_unit unit
                    JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                    LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                    LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                    WHERE tu.npp = $1
                    """,
                    npp,
                )

            if not user_hris:
                await log_security_event("LOGIN_FAILED", npp, user_ip, "NPP not found in HRIS", "LOW")
                return False, None, "NPP tidak terdaftar di HRIS"

            if user_hris["password"] != password_md5:
                await log_security_event("LOGIN_FAILED", npp, user_ip, "Invalid password", "MEDIUM")
                return False, None, "Password salah"

            user_fullname = user_hris["nama"]
            user_divisi = user_hris["divisi"] or "Umum"

        session_token = str(uuid.uuid4())

        async with get_db() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO users (npp, fullname, divisi, role) 
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (npp) DO UPDATE SET 
                        fullname = EXCLUDED.fullname, 
                        divisi = EXCLUDED.divisi;
                    """,
                    npp, user_fullname, user_divisi, current_role,
                )

                await conn.execute(
                    "DELETE FROM session_login WHERE npp = $1 AND expires_at < NOW()",
                    npp
                )

                expires_at = await conn.fetchval(
                    """
                    INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity, expires_at)
                    VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP, NOW() + INTERVAL '1 month')
                    RETURNING expires_at;
                    """,
                    npp, session_token, user_ip,
                )

                await conn.execute(
                    "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                    npp, user_ip, u_agent,
                )

        if guest_session_id:
            try:
                async with get_db() as main_conn:
                    await main_conn.execute(
                        """
                        UPDATE chat_sessions 
                        SET npp = $1 
                        WHERE session_uuid = $2 AND (npp = 'GUEST' OR npp IS NULL)
                        """,
                        npp, guest_session_id
                    )
            except Exception as e:
                logger.error(f"Gagal migrasi sesi GUEST: {e}")

        user_email = user_hris.get("email_internet") or user_hris.get("email_intranet") if user_hris else None
        
        return True, {
            "token": session_token,
            "npp": npp,
            "fullname": user_fullname,
            "divisi": user_divisi,
            "role": current_role,
            "email": user_email,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }, None

    @staticmethod
    async def logout(token: str, user_ip: str) -> bool:
        """Logout user and record audit log."""
        async with get_db() as conn:
            row = await conn.fetchrow(
                "SELECT npp FROM session_login WHERE session_token = $1", token
            )

            if row:
                npp = row["npp"]
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE session_login SET is_login = FALSE WHERE session_token = $1",
                        token,
                    )
                    await conn.execute(
                        "INSERT INTO history_login (npp, action, ip_address) VALUES ($1, 'LOGOUT', $2)",
                        npp, user_ip,
                    )
                return True
            return False

auth_service = AuthService()
