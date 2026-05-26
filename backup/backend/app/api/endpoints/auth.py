from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends
from app.api.schemas.auth import LoginRequest, LoginResponse
from pydantic import BaseModel
import hashlib
import uuid
import logging
from typing import Optional

# Import context manager dari database.py
from app.core.database import get_db, get_hris_db

router = APIRouter()
logger = logging.getLogger(__name__)

# --- ENDPOINTS ---


@router.get("/verify-session")
async def verify_session(token: str = Query(None)):
    """
    Mengecek apakah token di localStorage masih valid.
    Frontend: fetch('/api/verify-session?token=...')
    """
    if not token:
        raise HTTPException(status_code=401, detail="Token missing")

    try:
        async with get_db() as conn:
            query = """
                SELECT u.npp, u.fullname, u.divisi, u.role
                FROM session_login s
                JOIN users u ON s.npp = u.npp
                WHERE s.session_token = $1 AND s.is_login = TRUE
            """
            user = await conn.fetchrow(query, token)

            if user:
                # Update aktivitas terakhir
                await conn.execute(
                    "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
                    token,
                )

                return {
                    "status": "success",
                    "data": {
                        "npp": user["npp"],
                        "username": user["npp"],
                        "fullname": user["fullname"],
                        "divisi": user["divisi"],
                        "role": user["role"],
                    },
                }
            else:
                raise HTTPException(
                    status_code=401, detail="Session expired or invalid"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Verify Session Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/login", response_model=LoginResponse)
async def login(request_body: LoginRequest, request: Request):
    """
    Endpoint Login: Autentikasi via HRIS dan sinkronisasi ke DB Lokal.
    """
    npp = request_body.username
    password_input = request_body.password

    if not npp or not password_input:
        return LoginResponse(status="error", message="NPP dan Password wajib diisi")

    password_md5 = hashlib.md5(password_input.encode()).hexdigest()
    user_hris = None
    current_role = "USER"

    try:
        # 1. Logic Akun Spesial
        if str(npp) == "99999" and str(password_input) == "123456":
            user_hris = {
                "npp": "99999",
                "nama": "Learn Data AI",
                "divisi": "PINDAD",
                "password": password_input,
            }
            current_role = "TRAINER"

        else:
            # 2. Query HRIS database
            async with get_hris_db() as conn:
                user_hris = await conn.fetchrow(
                    """
                    SELECT 
                        mp.nama_lengkap as nama, tu.npp, tu.password, 
                        split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi
                    FROM master_unit unit
                    JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                    LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                    LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                    WHERE tu.npp = $1
                """,
                    npp,
                )

            if not user_hris:
                raise HTTPException(
                    status_code=404, detail="NPP tidak terdaftar di HRIS"
                )

            if user_hris["password"] != password_md5:
                raise HTTPException(status_code=401, detail="Password salah")

            # 3. Ambil Role dari DB lokal
            async with get_db() as conn:
                existing = await conn.fetchrow(
                    "SELECT role FROM users WHERE npp = $1", user_hris["npp"]
                )
                if existing:
                    current_role = existing["role"]

        # 4. Buat Session & Simpan Data
        session_token = str(uuid.uuid4())
        user_ip = request.client.host if request.client else "127.0.0.1"
        u_agent = request.headers.get("user-agent", "FastAPI Client")

        async with get_db() as conn:
            # Gunakan transaksi agar atomic
            async with conn.transaction():
                # Sync user ke DB lokal
                await conn.execute(
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

                # Insert/Update session_login
                await conn.execute(
                    """
                    INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity)
                    VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (npp) DO UPDATE SET 
                        session_token = EXCLUDED.session_token, 
                        is_login = TRUE, 
                        last_activity = CURRENT_TIMESTAMP;
                """,
                    user_hris["npp"],
                    session_token,
                    user_ip,
                )

                # Log history LOGIN
                await conn.execute(
                    "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                    user_hris["npp"],
                    user_ip,
                    u_agent,
                )

        return LoginResponse(
            status="success",
            data={
                "token": session_token,
                "npp": user_hris["npp"],
                "fullname": user_hris["nama"],
                "divisi": user_hris["divisi"],
                "role": current_role,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login Critical Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(request: Request, payload: dict = Body(...)):
    """
    Logout:
    1. Matikan session.
    2. Catat history LOGOUT.
    """
    token = payload.get("token")
    if not token:
        return {"status": "success", "message": "No token provided"}

    user_ip = request.client.host if request.client else "127.0.0.1"

    try:
        async with get_db() as conn:
            # Ambil NPP dulu untuk kebutuhan history
            row = await conn.fetchrow(
                "SELECT npp FROM session_login WHERE session_token = $1", token
            )

            if row:
                npp = row["npp"]
                async with conn.transaction():
                    # Update status login
                    await conn.execute(
                        "UPDATE session_login SET is_login = FALSE, session_token = '' WHERE npp = $1",
                        npp,
                    )
                    # Log history LOGOUT
                    await conn.execute(
                        "INSERT INTO history_login (npp, action, ip_address) VALUES ($1, 'LOGOUT', $2)",
                        npp,
                        user_ip,
                    )

                return {"status": "success", "message": "Logged out successfully"}

            return {"status": "success", "message": "Session already inactive"}

    except Exception as e:
        logger.error(f"❌ Logout Error: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal Server Error during logout"
        )
