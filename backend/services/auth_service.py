import hashlib
import uuid
from typing import Dict, Any, Optional
import asyncpg
from backend.database.connection import db_manager
from backend.config.settings import settings
import logging


class AuthService:
    @staticmethod
    async def login(username: str, password: str) -> Dict[str, Any]:
        """Handle user login with validation against both local and HRIS databases"""
        conn_hris = None
        conn_local = None
        
        try:
            user_hris = None
            current_role = "USER"

            # --- HANDLE SPECIAL ACCOUNT (LEARN DATA AI) ---
            if str(username) == "99999" and str(password) == "123456":
                user_hris = {
                    "npp": "99999",
                    "nama": "Learn Data AI",
                    "username_alias": "LearnDataAI",
                    "divisi": "PINDAD",
                    "password": password,  # bypass check md5 nanti
                }
                current_role = "TRAINER"
                logging.info("Login via Special Account: Learn Data AI")

            else:
                # --- CEK KE DB HRIS (User Reguler) ---
                conn_hris = await db_manager.get_login_connection()
                
                query_hris = """
                    SELECT 
                        mp.nama_lengkap as nama, tu.npp, tu.password, 
                        split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi
                    FROM master_unit unit
                    JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                    LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                    LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                    WHERE tu.npp = $1
                """
                user_hris = await conn_hris.fetchrow(query_hris, username)

                if not user_hris:
                    return {"status": "error", "message": "NPP tidak terdaftar"}

                # Validasi Password Reguler (MD5)
                password_md5 = hashlib.md5(password.encode()).hexdigest()
                if user_hris["password"] != password_md5:
                    return {"status": "error", "message": "Password salah"}

            # --- SIMPAN SESSION & SYNC KE DB LOKAL ---
            conn_local = await db_manager.get_rag_connection()
            session_token = str(uuid.uuid4())
            
            # Get client IP and user agent would require request object in actual implementation
            # For now we'll use placeholder values
            user_ip = "127.0.0.1"  # This would come from request object
            u_agent = "FastAPI Client"  # This would come from request object

            # Jika bukan akun spesial, ambil role dari DB lokal (siapa tahu sudah di-set TRAINER sebelumnya)
            if username != "99999":
                existing = await conn_local.fetchrow(
                    "SELECT role FROM users WHERE npp = $1", user_hris["npp"]
                )
                current_role = existing["role"] if existing else "USER"

            # Sinkronisasi Data ke Tabel Users Lokal
            await conn_local.execute("""
                INSERT INTO users (npp, fullname, divisi, role) 
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (npp) DO UPDATE SET 
                    fullname = EXCLUDED.fullname, 
                    divisi = EXCLUDED.divisi,
                    role = EXCLUDED.role; 
            """, user_hris["npp"], user_hris["nama"], user_hris["divisi"], current_role)

            # Insert Session
            await conn_local.execute("""
                INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity)
                VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT (npp) DO UPDATE SET 
                    session_token = EXCLUDED.session_token, 
                    is_login = TRUE, 
                    last_activity = CURRENT_TIMESTAMP;
            """, user_hris["npp"], session_token, user_ip)

            # History
            await conn_local.execute(
                "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                user_hris["npp"], user_ip, u_agent
            )
            
            await conn_local.execute("COMMIT")

            return {
                "status": "success",
                "data": {
                    "token": session_token,
                    "username": user_hris.get("username_alias", user_hris["npp"]),
                    "npp": user_hris["npp"],
                    "fullname": user_hris["nama"],
                    "divisi": user_hris["divisi"],
                    "role": current_role,
                },
            }

        except Exception as e:
            if conn_local:
                await conn_local.execute("ROLLBACK")
            logging.error(f"Login Error: {e}")
            return {"status": "error", "message": f"System Error: {str(e)}"}
        finally:
            if conn_hris:
                await db_manager.release_login_connection(conn_hris)
            if conn_local:
                await db_manager.release_rag_connection(conn_local)

    @staticmethod
    async def logout(token: str) -> Dict[str, Any]:
        """Handle user logout"""
        conn_local = None
        try:
            conn_local = await db_manager.get_rag_connection()
            
            row = await conn_local.fetchrow(
                "SELECT npp FROM session_login WHERE session_token = $1", token
            )

            if row:
                npp = row["npp"]
                # Update session to logged out status
                await conn_local.execute(
                    "UPDATE session_login SET is_login = FALSE, session_token = '' WHERE npp = $1",
                    npp,
                )

                await conn_local.execute("""
                    INSERT INTO history_login (npp, action, ip_address)
                    VALUES ($1, 'LOGOUT', $2);
                """, npp, "127.0.0.1")  # IP would come from request object

                await conn_local.execute("COMMIT")
                return {"status": "success", "message": "Logged out"}

            # Jika token tidak ditemukan, anggap saja sudah logout
            return {"status": "success", "message": "Token already gone"}

        except Exception as e:
            if conn_local:
                await conn_local.execute("ROLLBACK")
            print(f"❌ LOGOUT ERROR: {str(e)}")
            return {"status": "error", "message": str(e)}
        finally:
            if conn_local:
                await db_manager.release_rag_connection(conn_local)

    @staticmethod
    async def verify_session(token: str) -> Dict[str, Any]:
        """Verify if session is valid"""
        if not token:
            return {"status": "error", "message": "Token missing"}

        conn_local = None
        try:
            conn_local = await db_manager.get_rag_connection()
            
            # Join ke tabel users untuk ambil data lengkap
            query = """
                SELECT u.npp, u.fullname, u.divisi 
                FROM session_login s
                JOIN users u ON s.npp = u.npp
                WHERE s.session_token = $1 AND s.is_login = TRUE
            """
            user = await conn_local.fetchrow(query, token)

            if user:
                # Update last_activity setiap kali user akses
                await conn_local.execute(
                    "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
                    token,
                )
                await conn_local.execute("COMMIT")

                return {
                    "status": "success",
                    "data": {
                        "username": user["npp"],
                        "fullname": user["fullname"],
                        "divisi": user["divisi"],
                    },
                }
            else:
                return {"status": "error", "message": "Session expired or invalid"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            if conn_local:
                await db_manager.release_rag_connection(conn_local)