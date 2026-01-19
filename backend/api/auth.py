from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid
import asyncio
import hashlib
from typing import Dict, Any, Optional
import asyncpg
import logging

from ..schemas.auth import LoginRequest, LoginResponse, LogoutRequest, VerifySessionRequest, VerifySessionResponse
from ..database.connection import db_manager
from ..core.config import DB_LOGIN_CONFIG, DB_RAG_CONFIG
from ..utils.helpers import hash_password

router = APIRouter(prefix="/api", tags=["Authentication"])

logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Login endpoint with validation against HRIS database"""
    conn_login = None
    conn_local = None
    
    try:
        npp = request.username
        password_input = request.password

        if not npp or not password_input:
            return LoginResponse(
                status="error",
                message="NPP dan Password wajib diisi"
            )

        password_md5 = hash_password(password_input)
        
        user_hris = None
        current_role = "USER"

        # --- LANGKAH 0: HANDLE SPECIAL ACCOUNT (LEARN DATA AI) ---
        if str(npp) == "99999" and str(password_input) == "123456":
            user_hris = {
                "npp": "99999",
                "nama": "Learn Data AI",
                "username_alias": "LearnDataAI",
                "divisi": "PINDAD",
                "password": password_input,  # bypass check md5 nanti
            }
            current_role = "TRAINER"
            logger.info("Login via Special Account: Learn Data AI")

        else:
            # --- LANGKAH 1: CEK KE DB HRIS (User Reguler) ---
            login_pool = await db_manager.get_login_connection()
            async with login_pool.acquire() as conn_login:
                # Execute query to HRIS database
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
                
                user_hris = await conn_login.fetchrow(query_hris, npp)

                if not user_hris:
                    return LoginResponse(
                        status="error",
                        message="NPP tidak terdaftar"
                    )

                # Validasi Password Reguler (MD5)
                if user_hris["password"] != password_md5:
                    return LoginResponse(status="error", message="Password salah")

        # --- LANGKAH 2: SIMPAN SESSION & SYNC KE DB LOKAL ---
        rag_pool = await db_manager.get_rag_connection()
        session_token = str(uuid.uuid4())
        user_ip = request.client.host if request.client else "unknown"
        u_agent = request.headers.get("User-Agent", "")

        async with rag_pool.acquire() as conn_local:
            # Jika bukan akun spesial, ambil role dari DB lokal (siapa tahu sudah di-set TRAINER sebelumnya)
            if npp != "99999":
                existing = await conn_local.fetchrow(
                    "SELECT role FROM users WHERE npp = $1", user_hris["npp"]
                )
                current_role = existing["role"] if existing else "USER"

            # Sinkronisasi Data ke Tabel Users Lokal
            await conn_local.execute(
                """
                INSERT INTO users (npp, fullname, divisi, role) 
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (npp) DO UPDATE SET 
                    fullname = EXCLUDED.fullname, 
                    divisi = EXCLUDED.divisi,
                    role = EXCLUDED.role; 
                """,
                user_hris["npp"],
                user_hris["nama"],
                user_hris["divisi"],
                current_role,
            )

            # Insert Session
            await conn_local.execute(
                """
                INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity)
                VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT (npp) DO UPDATE SET 
                    session_token = EXCLUDED.session_token, 
                    is_login = TRUE, 
                    last_activity = CURRENT_TIMESTAMP;
                """,
                user_hris["npp"], session_token, user_ip
            )

            # History
            await conn_local.execute(
                "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                user_hris["npp"], user_ip, u_agent
            )

        return LoginResponse(
            status="success",
            data={
                "token": session_token,
                "username": user_hris.get("username_alias", user_hris["npp"]),
                "npp": user_hris["npp"],
                "fullname": user_hris["nama"],
                "divisi": user_hris["divisi"],
                "role": current_role,
            }
        )

    except Exception as e:
        logger.error(f"Login Error: {e}")
        return LoginResponse(status="error", message=f"System Error: {str(e)}")


@router.post("/logout")
async def logout(request: LogoutRequest) -> Dict[str, Any]:
    """Logout endpoint"""
    conn_local = None
    try:
        token = request.token

        rag_pool = await db_manager.get_rag_connection()
        async with rag_pool.acquire() as conn_local:
            row = await conn_local.fetchrow(
                "SELECT npp FROM session_login WHERE session_token = $1", token
            )

            if row:
                npp = row["npp"]
                # GANTI NULL MENJADI '' (String Kosong) agar tidak melanggar constraint
                await conn_local.execute(
                    "UPDATE session_login SET is_login = FALSE, session_token = '' WHERE npp = $1",
                    npp
                )

                await conn_local.execute(
                    """
                    INSERT INTO history_login (npp, action, ip_address)
                    VALUES ($1, 'LOGOUT', $2);
                    """,
                    npp, request.client.host if request.client else "unknown"
                )

                return {"status": "success", "message": "Logged out"}

            # Jika token tidak ditemukan, anggap saja sudah logout
            return {"status": "success", "message": "Token already gone"}

    except Exception as e:
        logger.error(f"❌ LOGOUT ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/verify-session", response_model=VerifySessionResponse)
async def verify_session(request: Request) -> VerifySessionResponse:
    """Verify session endpoint"""
    token = request.query_params.get("token")
    if not token:
        return VerifySessionResponse(status="error", message="Token missing")

    try:
        rag_pool = await db_manager.get_rag_connection()
        async with rag_pool.acquire() as conn_local:
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
                    token
                )

                return VerifySessionResponse(
                    status="success",
                    data={
                        "username": user["npp"],
                        "fullname": user["fullname"],
                        "divisi": user["divisi"],
                    }
                )
            else:
                return VerifySessionResponse(
                    status="error", message="Session expired or invalid"
                )
    except Exception as e:
        return VerifySessionResponse(status="error", message=str(e))


@router.get("/available-models")
async def get_available_models() -> Dict[str, Any]:
    """Get available models endpoint"""
    models = [
        {"id": "qwen3:8b", "name": "Qwen 3 (8B)"},
        {"id": "qwen2.5:14b-instruct", "name": "Qwen 2.5-Instruct (14b)"},
        {"id": "qwen3-vl:8b", "name": "qwen 3 vl (8b)"},
        {"id": "llama3.1:8b", "name": "Llama 3.1 (8b)"},
    ]
    return {"status": "success", "data": models}