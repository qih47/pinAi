import logging
import os
import shutil
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Body, Query
from typing import Optional
from pydantic import BaseModel
import bcrypt

from backend.app.core.database import get_db
from backend.app.api.endpoints.auth import verify_session
from backend.app.core.database import get_hris_db

router = APIRouter()
logger = logging.getLogger("CAKRA_USER")

UPLOAD_DIR = "uploads/profiles"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.put("/profile")
async def update_profile(
    fullname: Optional[str] = Form(None),
    preferred_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    token: str = Form(...),
):
    """
    Endpoint untuk mengupdate profil pengguna di tabel users.
    """
    logger.info("Menerima request update profil...")
    
    try:
        # Verifikasi session token untuk mendapatkan NPP
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        npp = user_data.data["npp"]
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error verifying session for profile update: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    profile_photo_url = None
    if photo:
        file_ext = photo.filename.split('.')[-1]
        filename = f"{npp}.{file_ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)
            
        # Simpan relative path / API path untuk diakses frontend
        profile_photo_url = f"/api/user/photo/{filename}"

    async with get_db() as conn:
        updates = []
        values = []
        idx = 1
        
        if fullname is not None:
            updates.append(f"fullname = ${idx}")
            values.append(fullname)
            idx += 1

        if preferred_name is not None:
            updates.append(f"preferred_name = ${idx}")
            values.append(preferred_name)
            idx += 1

        if email is not None:
            updates.append(f"email = ${idx}")
            values.append(email)
            idx += 1
            
        if profile_photo_url is not None:
            updates.append(f"profile_photo_url = ${idx}")
            values.append(profile_photo_url)
            idx += 1
            
        if updates:
            values.append(npp)
            query = f"UPDATE users SET {', '.join(updates)} WHERE npp = ${idx}"
            await conn.execute(query, *values)
            
    return {"status": "success", "message": "Profil berhasil diperbarui", "profile_photo_url": profile_photo_url}


from fastapi.responses import FileResponse

@router.get("/photo/{filename}")
async def get_profile_photo(filename: str):
    """
    Endpoint untuk mengambil foto profil lokal.
    """
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(filepath)

class PasswordUpdateRequest(BaseModel):
    token: str
    old_password: str
    new_password: str

@router.put("/password")
async def update_password(req: PasswordUpdateRequest):
    logger.info("Menerima request update password...")
    try:
        user_data = await verify_session(token=req.token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
        npp = user_data.data["npp"]
    except Exception as e:
        logger.error(f"Error verifying session for password update: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    async with get_db() as conn:
        user_row = await conn.fetchrow("SELECT password_hash FROM users WHERE npp = $1", npp)
        if not user_row:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")
            
        current_hash = user_row["password_hash"]
        
        # Verify old password
        if current_hash:
            if not bcrypt.checkpw(req.old_password.encode(), current_hash.encode()):
                raise HTTPException(status_code=400, detail="Password lama salah")
        else:
            # If no local hash exists, try verifying with HRIS
            try:
                async with get_hris_db() as hris_conn:
                    hris_user = await hris_conn.fetchrow(
                        "SELECT password FROM master_personil WHERE npp = $1 AND st = 1 LIMIT 1", npp
                    )
                    if hris_user:
                        is_valid = bcrypt.checkpw(req.old_password.encode('utf-8'), hris_user['password'].encode('utf-8'))
                        if not is_valid:
                            raise HTTPException(status_code=400, detail="Password lama salah (HRIS)")
                    else:
                        raise HTTPException(status_code=400, detail="User tidak aktif atau tidak ditemukan di HRIS")
            except HTTPException as he:
                raise he
            except Exception as e:
                logger.error(f"Error validating HRIS password: {e}")
                raise HTTPException(status_code=500, detail="Gagal memvalidasi password lama")
                
        # Save new password hash
        new_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
        await conn.execute("UPDATE users SET password_hash = $2 WHERE npp = $1", npp, new_hash)
        
    return {"status": "success", "message": "Password berhasil diperbarui"}


import json

@router.get("/settings")
async def get_user_settings(token: str = Query(...)):
    """Ambil pengaturan user dari database"""
    try:
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
        npp = user_data.data["npp"]
    except Exception as e:
        logger.error(f"Error verifikasi session settings: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT settings FROM user_settings WHERE npp = $1", npp)
        settings_data = {}
        if row and row["settings"]:
            settings_data = json.loads(row["settings"])
            
    return {"status": "success", "settings": settings_data}

@router.put("/settings")
async def update_user_settings(payload: dict = Body(...)):
    """Simpan pengaturan user ke database"""
    token = payload.get("token")
    settings_data = payload.get("settings", {})
    
    if not token:
        raise HTTPException(status_code=401, detail="Token missing")
        
    try:
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
        npp = user_data.data["npp"]
    except Exception as e:
        logger.error(f"Error verifikasi session settings: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    async with get_db() as conn:
        settings_json = json.dumps(settings_data)
        await conn.execute("""
            INSERT INTO user_settings (npp, settings, updated_at)
            VALUES ($1, $2::jsonb, now())
            ON CONFLICT (npp) DO UPDATE 
            SET settings = $2::jsonb, updated_at = now()
        """, npp, settings_json)
        
    return {"status": "success", "message": "Settings updated"}

