import logging
from fastapi import Request, Header, HTTPException, status
from typing import Optional
# 🔥 PASTIKAN IMPORT get_hris_db SUDAH TERCANTUM DI ATAS
from backend.app.core.database import get_db, get_hris_db 

logger = logging.getLogger("CAKRA_AUTH_DEPENDENCY")

_GUEST_NPP_PLACEHOLDERS = frozenset({"NPP ------", "NPP -----", "NPP------", "GUEST"})


async def get_current_user_npp(
    request: Request, 
    x_npp_header: Optional[str] = Header(None, alias="X-NPP-Header")
) -> Optional[str]:
    """
    Dependency Validator untuk membedakan Pegawai Resmi vs Guest Mode.
    """
    
    # 1. Jika tidak ada header NPP atau placeholder UI guest, masuk GUEST MODE
    if not x_npp_header or x_npp_header.strip() == "":
        return None

    npp_clean = x_npp_header.strip()
    if npp_clean in _GUEST_NPP_PLACEHOLDERS:
        return None

    # 2. VALIDASI KE DATABASE HRIS REMOTE
    # 🔥 FIX SAKTI: Ganti get_db(pool_name="hris") dengan get_hris_db() bawaan asli lu bolo!
    async with get_hris_db() as conn:  
        try:
            query = "SELECT npp, nama_lengkap FROM master_personil WHERE npp = $1 AND kode_status_aktif = 1 LIMIT 1;"
            row = await conn.fetchrow(query, npp_clean)
            
            if not row:
                logger.warning(f"[AUTH] NPP '{npp_clean}' rejected - not registered/inactive in HRIS DB")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"NPP Pegawai {npp_clean} tidak terdaftar atau sudah tidak aktif di PT Pindad, bolo!"
                )
                
            logger.info(f"[AUTH] Access validated: {row['nama_lengkap']} (NPP: {row['npp']})")
            return row['npp']

        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"[AUTH] Failed to query HRIS DB: {str(e)}")
            logger.warning(f"[AUTH] HRIS DB issue - allowing emergency bypass for NPP: {npp_clean}")
            return npp_clean