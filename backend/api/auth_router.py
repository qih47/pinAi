from fastapi import APIRouter, HTTPException, Request
import hashlib
import uuid
import logging
from typing import Dict, Any
from backend.schemas.auth import LoginRequest, LoginResponse, LogoutRequest, LogoutResponse, VerifySessionResponse
from backend.database.connection import get_login_db_pool, get_local_db_pool
from backend.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """
    Login endpoint that authenticates users against HRIS database and syncs to local database
    """
    npp = request.username
    password_input = request.password

    if not npp or not password_input:
        raise HTTPException(
            status_code=400, 
            detail={"status": "error", "message": "NPP dan Password wajib diisi"}
        )

    password_md5 = hashlib.md5(password_input.encode()).hexdigest()
    
    try:
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
            logging.info("Login via Special Account: Learn Data AI")

        else:
            # --- LANGKAH 1: CEK KE DB HRIS (User Reguler) ---
            login_pool = await get_login_db_pool()
            
            async with login_pool.acquire() as conn:
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
                user_hris = await conn.fetchrow(query_hris, npp)

            if not user_hris:
                raise HTTPException(
                    status_code=404, 
                    detail={"status": "error", "message": "NPP tidak terdaftar"}
                )

            # Validasi Password Reguler (MD5)
            if user_hris["password"] != password_md5:
                raise HTTPException(
                    status_code=401, 
                    detail={"status": "error", "message": "Password salah"}
                )

        # --- LANGKAH 2: SIMPAN SESSION & SYNC KE DB LOKAL ---
        local_pool = await get_local_db_pool()
        session_token = str(uuid.uuid4())
        
        # Get client IP and user agent
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "") if request.headers else ""

        async with local_pool.acquire() as conn:
            async with conn.transaction():
                # Jika bukan akun spesial, ambil role dari DB lokal (siapa tahu sudah di-set TRAINER sebelumnya)
                if npp != "99999":
                    existing_user = await conn.fetchrow(
                        "SELECT role FROM users WHERE npp = $1", user_hris["npp"]
                    )
                    current_role = existing_user["role"] if existing_user else "USER"

                # Sinkronisasi Data ke Tabel Users Lokal
                await conn.execute("""
                    INSERT INTO users (npp, fullname, divisi, role) 
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (npp) DO UPDATE SET 
                        fullname = EXCLUDED.fullname, 
                        divisi = EXCLUDED.divisi,
                        role = EXCLUDED.role; 
                """, user_hris["npp"], user_hris["nama"], user_hris["divisi"], current_role)

                # Insert Session
                await conn.execute("""
                    INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity)
                    VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (npp) DO UPDATE SET 
                        session_token = EXCLUDED.session_token, 
                        is_login = TRUE, 
                        last_activity = CURRENT_TIMESTAMP;
                """, user_hris["npp"], session_token, client_host)

                # History
                await conn.execute(
                    "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                    user_hris["npp"], client_host, user_agent
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

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Login Error: {e}")
        raise HTTPException(
            status_code=500, 
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: LogoutRequest) -> LogoutResponse:
    """
    Logout endpoint that updates session status and records logout action
    """
    token = request.token

    try:
        local_pool = await get_local_db_pool()
        
        async with local_pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT npp FROM session_login WHERE session_token = $1", token
                )

                if row:
                    npp = row["npp"]
                    
                    # Update session to logged out status
                    await conn.execute(
                        "UPDATE session_login SET is_login = FALSE, session_token = '' WHERE npp = $1",
                        npp,
                    )

                    # Record logout history
                    client_host = request.client.host if request.client else "unknown"
                    await conn.execute(
                        """
                        INSERT INTO history_login (npp, action, ip_address)
                        VALUES ($1, 'LOGOUT', $2);
                        """,
                        npp, client_host
                    )

                    return LogoutResponse(status="success", message="Logged out")

                # Jika token tidak ditemukan, anggap saja sudah logout
                return LogoutResponse(status="success", message="Token already gone")

    except Exception as e:
        logger.error(f"❌ LOGOUT ERROR: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={"status": "error", "message": str(e)}
        )


@router.get("/verify-session", response_model=VerifySessionResponse)
async def verify_session(token: str) -> VerifySessionResponse:
    """
    Verify session endpoint to check if user session is still valid
    """
    if not token:
        raise HTTPException(
            status_code=401, 
            detail={"status": "error", "message": "Token missing"}
        )

    try:
        local_pool = await get_local_db_pool()
        
        async with local_pool.acquire() as conn:
            # Join ke tabel users untuk ambil data lengkap
            query = """
                SELECT u.npp, u.fullname, u.divisi 
                FROM session_login s
                JOIN users u ON s.npp = u.npp
                WHERE s.session_token = $1 AND s.is_login = TRUE
            """
            user = await conn.fetchrow(query, token)

            if user:
                # Update last_activity setiap kali user akses
                await conn.execute(
                    "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
                    token,
                )

                return VerifySessionResponse(
                    status="success",
                    data={
                        "username": user["npp"],
                        "fullname": user["fullname"],
                        "divisi": user["divisi"],
                    },
                )
            else:
                raise HTTPException(
                    status_code=401, 
                    detail={"status": "error", "message": "Session expired or invalid"}
                )
                
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={"status": "error", "message": str(e)}
        )


@router.get("/available-models")
async def get_available_models():
    """
    Return list of available models
    """
    models = [
        {"id": "qwen3:8b", "name": "Qwen 3 (8B)"},
        {"id": "qwen2.5:14b-instruct", "name": "Qwen 2.5-Instruct (14b)"},
        {"id": "qwen3-vl:8b", "name": "qwen 3 vl (8b)"},
        {"id": "llama3.1:8b", "name": "Llama 3.1 (8b)"},
    ]
    return {"status": "success", "data": models}