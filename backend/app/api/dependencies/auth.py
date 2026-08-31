import logging
from fastapi import Request, Header, HTTPException, status
from typing import Optional
from backend.app.core.config import settings
from backend.app.core.database import get_db, get_hris_db 

logger = logging.getLogger("CAKRA_AUTH_DEPENDENCY")

_GUEST_NPP_PLACEHOLDERS = frozenset({"NPP ------", "NPP -----", "NPP------", "GUEST"})


async def get_current_user_npp(
    request: Request, 
    x_npp_header: Optional[str] = Header(None, alias="X-NPP-Header"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> Optional[str]:
    """
    Dependency Validator untuk membedakan Pegawai Resmi vs Guest Mode,
    serta mendukung Server-to-Server Auth via X-API-Key dan Bearer Token Session.
    """
    
    # 0. CEK API KEY (SERVER-TO-SERVER)
    if x_api_key:
        import hashlib
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        async with get_db() as conn:
            row = await conn.fetchrow(
                "SELECT owner_npp, is_active FROM api_keys WHERE key_hash = $1", 
                key_hash
            )
            if not row or not row['is_active']:
                logger.warning(f"[AUTH] Tolak akses API Key tidak valid. Hash: {key_hash[:10]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API Key tidak valid atau sudah dicabut."
                )
            
            # Update tracker secara asinkron
            await conn.execute("UPDATE api_keys SET total_requests = total_requests + 1, last_used_at = now() WHERE key_hash = $1", key_hash)
            logger.info(f"[AUTH] Akses via API Key valid. Owner: {row['owner_npp']}")
            return row['owner_npp']

    # 1. Cek Header NPP, Query Param, atau Bearer Token
    npp_clean = None
    if x_npp_header and x_npp_header.strip():
        npp_clean = x_npp_header.strip()
    else:
        query_npp = request.query_params.get("npp")
        if query_npp and query_npp.strip():
            npp_clean = query_npp.strip()

    # 1b. Fallback: Cek Bearer Session Token jika NPP belum ada di header
    if not npp_clean and authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        if token:
            try:
                async with get_db() as conn:
                    session_row = await conn.fetchrow(
                        "SELECT npp FROM session_login WHERE session_token = $1 AND is_login = TRUE AND expires_at > NOW()",
                        token
                    )
                    if session_row and session_row["npp"]:
                        npp_clean = session_row["npp"]
                        logger.info(f"[AUTH] Resolved NPP '{npp_clean}' from Bearer session token.")
            except Exception as e:
                logger.error(f"[AUTH] Failed to resolve session token: {e}")

    if not npp_clean or npp_clean in _GUEST_NPP_PLACEHOLDERS:
        return None

    # 2. VALIDASI KE DATABASE LOKAL / BYPASS / HRIS
    # 2a. Cek Bypass Account
    if settings.BYPASS_ACCOUNT_ENABLED and str(npp_clean) == str(settings.BYPASS_ACCOUNT_NPP or "99999"):
        return npp_clean

    # 2b. Cek Local RAG DB users table (User yang sudah terdaftar di sistem CAKRA)
    try:
        async with get_db() as conn:
            user_row = await conn.fetchrow("SELECT npp, role FROM users WHERE npp = $1", npp_clean)
            if user_row and user_row["npp"]:
                return user_row["npp"]
    except Exception as e:
        logger.error(f"[AUTH] Error checking local users: {e}")

    # 2c. Validasi ke HRIS Remote jika user belum tercatat di database lokal
    try:
        async with get_hris_db() as conn:  
            query = "SELECT npp, nama_lengkap FROM master_personil WHERE npp = $1 LIMIT 1;"
            row = await conn.fetchrow(query, npp_clean)
            
            if not row:
                logger.warning(f"[AUTH] NPP '{npp_clean}' rejected - not found in HRIS DB")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"NPP Pegawai {npp_clean} tidak terdaftar di HRIS."
                )
                
            return row['npp']

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"[AUTH] Failed to query HRIS DB: {str(e)}")
        logger.warning(f"[AUTH] HRIS DB issue - allowing emergency bypass for NPP: {npp_clean}")
        return npp_clean