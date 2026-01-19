from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import logging
from backend.models.auth import LoginRequest, LogoutRequest, VerifySessionResponse
from backend.services.auth_service import AuthService


router = APIRouter(prefix="/api", tags=["Authentication"])


@router.post("/login")
async def login(request: LoginRequest):
    """Login endpoint"""
    try:
        result = await AuthService.login(request.username, request.password)
        if result["status"] == "error":
            raise HTTPException(status_code=401 if "Password salah" in result["message"] or "NPP tidak terdaftar" in result["message"] else 400, 
                              detail=result["message"])
        return result
    except Exception as e:
        logging.error(f"Login API Error: {e}")
        raise HTTPException(status_code=500, detail=f"System Error: {str(e)}")


@router.post("/logout")
async def logout(request: LogoutRequest):
    """Logout endpoint"""
    try:
        result = await AuthService.logout(request.token)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except Exception as e:
        logging.error(f"Logout API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verify-session")
async def verify_session(token: Optional[str] = None):
    """Verify session endpoint"""
    try:
        result = await AuthService.verify_session(token)
        if result["status"] == "error":
            status_code = 401 if "Session expired" in result["message"] or "Token missing" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except Exception as e:
        logging.error(f"Verify Session API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))