from fastapi import APIRouter, HTTPException, Request, Query, Body, status
from pydantic import BaseModel
import logging
from typing import Optional

from backend.app.services.auth.auth_service import auth_service
from backend.app.api.schemas import LoginRequest, LoginResponse, ExtendSessionRequest

router = APIRouter()
logger = logging.getLogger("CAKRA_AUTH")

@router.get("/verify-session", response_model=LoginResponse)
async def verify_session(token: str = Query(None)):
    """
    Mengecek status validasi token di localStorage secara asinkronus.
    """
    if not token:
        logger.warning("👤 [GUARD] Verifikasi gagal: Request datang tanpa token.")
        raise HTTPException(status_code=401, detail="Token missing")

    logger.info(f"🔍 [AUTH] Memverifikasi session token: {token[:8]}...")
    try:
        user_data = await auth_service.verify_session(token)
        if user_data:
            logger.info(f"🟩 [AUTH] Session VALID untuk User: {user_data['fullname']} [{user_data['role']}]")
            return LoginResponse(
                status="success",
                data=user_data
            )
        else:
            logger.warning(f"⚠️ [AUTH] Session INVALID atau sudah kedaluwarsa untuk token: {token[:8]}...")
            raise HTTPException(status_code=401, detail="Session expired or invalid")

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ Verify Session Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/login", response_model=LoginResponse)
async def login(request_body: LoginRequest, request: Request):
    """
    Endpoint Login Optimal: Mengutamakan penarikan Role dari RAGDB Lokal, 
    Validasi kredensial ke HRIS, dan Auto-Registrasi User Baru ke Lokal.
    """
    npp = request_body.username.strip()
    password_input = request_body.password

    logger.info(f"\n🔐 [LOGIN] Menerima request login untuk NPP: {npp}")

    if not npp or not password_input:
        logger.warning("❌ [LOGIN] Gagal: Input NPP atau password kosong.")
        return LoginResponse(status="error", message="NPP dan Password wajib diisi")

    user_ip = request.client.host if request.client else "127.0.0.1"
    u_agent = request.headers.get("user-agent", "FastAPI Client")

    try:
        success, user_data, error_msg = await auth_service.login(
            npp=npp,
            password_input=password_input,
            user_ip=user_ip,
            u_agent=u_agent,
            guest_session_id=request_body.guest_session_id
        )

        if not success:
            status_code = 404 if error_msg == "NPP tidak terdaftar di HRIS" else 401
            raise HTTPException(status_code=status_code, detail=error_msg)
            
        logger.info(f"🟩 [SUCCESS] Login tuntas! {user_data['fullname']} [{user_data['role']}] masuk ke sistem CAKRA AI.")
        return LoginResponse(
            status="success",
            data=user_data,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ Login Critical Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(request: Request, payload: dict = Body(...)):
    """
    Logout Sektor: Mematikan token session dan mencatat audit trail history.
    """
    token = payload.get("token")
    if not token:
        return {"status": "success", "message": "No token provided"}

    user_ip = request.client.host if request.client else "127.0.0.1"
    logger.info(f"\n🛑 [LOGOUT] Memproses request keluar untuk token: {token[:8]}...")

    try:
        logged_out = await auth_service.logout(token, user_ip)
        if logged_out:
            logger.info(f"[AUTH_LOGOUT_SUCCESS] Clean shutdown session. Audit trail secured.")
            return {"status": "success", "message": "Logged out successfully"}
        else:
            logger.warning("⚠️  [LOGOUT] Sesi token sudah tidak aktif sebelumnya.")
            return {"status": "success", "message": "Session already inactive"}

    except Exception as e:
        logger.error(f"[AUTH_LOGOUT_ERROR] Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error during logout")

@router.post("/extend-session")
async def extend_session(request: Request, body: ExtendSessionRequest = Body(...)):
    """
    Memperpanjang masa aktif session token user yang sedang login.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("👤 [GUARD] Perpanjangan sesi gagal: Token tidak disertakan atau format salah.")
        raise HTTPException(status_code=401, detail="Token missing or invalid")
    
    token = auth_header.split(" ")[1]
    
    from backend.app.utils.token_expiry import extend_session_expiry_by_token
    new_expiry = await extend_session_expiry_by_token(token, body.hours_to_add)
    
    if not new_expiry:
        logger.warning("⚠️ [AUTH] Gagal memperpanjang sesi. Token tidak valid atau tidak aktif.")
        raise HTTPException(status_code=401, detail="Session invalid or expired")
        
    logger.info(f"🕒 [AUTH] Sesi diperpanjang. Expiry baru: {new_expiry.isoformat()}")
    return {
        "status": "success",
        "expires_at": new_expiry.isoformat(),
        "message": "Session extended successfully"
    }