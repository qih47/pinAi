import logging
import os
import shutil
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Body, Query
from typing import Optional
from pydantic import BaseModel
import bcrypt
import imaplib
import asyncio

from backend.app.core.database import get_db
from backend.app.api.endpoints.auth import verify_session
from backend.app.core.database import get_hris_db
from backend.app.utils.security_firewall import validate_attachment_security

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
        await validate_attachment_security(photo)
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

            # Sinkronisasi preferred_name ke user_settings JSONB jika ada perubahan
            if preferred_name is not None:
                existing_settings_row = await conn.fetchrow("SELECT settings FROM user_settings WHERE npp = $1", npp)
                curr_settings = {}
                if existing_settings_row and existing_settings_row["settings"]:
                    curr_settings = json.loads(existing_settings_row["settings"]) if isinstance(existing_settings_row["settings"], str) else existing_settings_row["settings"]
                curr_settings["preferred_name"] = preferred_name
                await conn.execute("""
                    INSERT INTO user_settings (npp, settings, updated_at)
                    VALUES ($1, $2::jsonb, now())
                    ON CONFLICT (npp) DO UPDATE 
                    SET settings = $2::jsonb, updated_at = now()
                """, npp, json.dumps(curr_settings))

        # Realtime refresh in-memory cache
        from backend.app.utils.employee_cache import invalidate_employee_cache
        invalidate_employee_cache(npp)
            
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

        # Sinkronisasi ke tabel users jika preferred_name dikirimkan
        if "preferred_name" in settings_data and settings_data["preferred_name"]:
            await conn.execute("UPDATE users SET preferred_name = $2 WHERE npp = $1", npp, settings_data["preferred_name"])

        # Realtime refresh in-memory cache
        from backend.app.utils.employee_cache import invalidate_employee_cache
        invalidate_employee_cache(npp)
        
    return {"status": "success", "message": "Settings updated"}

@router.get("/integrations")
async def get_integrations(token: str = Query(...)):
    """Ambil status koneksi Mail dan Cloud Pindad"""
    try:
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
        npp = user_data.data["npp"]
    except Exception as e:
        logger.error(f"Error verifikasi session integrations: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT mail_username, cloud_username FROM user_integrations WHERE npp = $1", npp)
        mail_connected = False
        cloud_connected = False
        
        if row:
            if row["mail_username"]: mail_connected = True
            if row["cloud_username"]: cloud_connected = True
            
    return {
        "status": "success", 
        "data": {
            "mail_connected": mail_connected,
            "cloud_connected": cloud_connected
        }
    }

@router.post("/integrations/mail")
async def connect_mail(payload: dict = Body(...)):
    """Simpan kredensial Mail Pindad (Smart Mail / Zimbra)"""
    token = payload.get("token")
    username = payload.get("username")
    password = payload.get("password")
    
    if not token or not username or not password:
        raise HTTPException(status_code=400, detail="Token, username, dan password wajib diisi")
        
    try:
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
        npp = user_data.data["npp"]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    # Verifikasi koneksi ke IMAP mail.pindad.com
    try:
        def verify_imap():
            mail = imaplib.IMAP4_SSL("mail.pindad.com", 993)
            mail.login(username, password)
            mail.logout()
        await asyncio.to_thread(verify_imap)
    except imaplib.IMAP4.error as e:
        logger.error(f"[ZIMBRA] Verifikasi Login IMAP Gagal untuk {username}: {e}")
        raise HTTPException(
            status_code=400,
            detail="Verifikasi Gagal: Username atau Password Zimbra salah. Mohon periksa kembali kredensial akun mail.pindad.com Anda."
        )
    except Exception as e:
        logger.error(f"[ZIMBRA] Verifikasi IMAP Gagal untuk {username}: {e}")
        raise HTTPException(
            status_code=400,
            detail="Gagal menghubungi server mail.pindad.com. Silakan periksa koneksi atau kredensial akun Anda."
        )
    
    async with get_db() as conn:
        await conn.execute("""
            INSERT INTO user_integrations (npp, mail_username, mail_password, updated_at)
            VALUES ($1, $2, $3, now())
            ON CONFLICT (npp) DO UPDATE 
            SET mail_username = $2, mail_password = $3, updated_at = now()
        """, npp, username, password)
        
    return {"status": "success", "message": "Mail Pindad berhasil disambungkan"}

@router.delete("/integrations/mail")
async def disconnect_mail(token: str = Query(...)):
    """Hapus kredensial Mail Pindad"""
    try:
        user_data = await verify_session(token=token)
        npp = user_data.data["npp"]
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    async with get_db() as conn:
        await conn.execute("UPDATE user_integrations SET mail_username = NULL, mail_password = NULL, updated_at = now() WHERE npp = $1", npp)
        
    return {"status": "success", "message": "Mail Pindad berhasil diputus"}

@router.post("/integrations/cloud")
async def connect_cloud(payload: dict = Body(...)):
    """Simpan kredensial Cloud Pindad (Nextcloud)"""
    token = payload.get("token")
    username = payload.get("username")
    password = payload.get("password")
    
    if not token or not username or not password:
        raise HTTPException(status_code=400, detail="Token, username, dan password wajib diisi")
        
    try:
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
        npp = user_data.data["npp"]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    # Verifikasi koneksi ke Nextcloud WebDAV
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                "PROPFIND",
                "https://cloud.pindad.com/remote.php/webdav/",
                auth=(username, password),
                headers={"Depth": "0"}
            )
            if response.status_code == 401 or response.status_code == 403:
                raise HTTPException(status_code=400, detail="Verifikasi Gagal: Username atau Password Cloud salah. Mohon periksa kembali kredensial akun cloud.pindad.com Anda.")
            if response.status_code >= 400 and response.status_code != 404:
                raise HTTPException(status_code=400, detail=f"Server cloud.pindad.com mengembalikan error HTTP {response.status_code}.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[NEXTCLOUD] Verifikasi Gagal untuk {username}: {e}")
        raise HTTPException(status_code=400, detail="Gagal menghubungi cloud.pindad.com. Silakan periksa kembali Username dan Password Anda.")
    
    async with get_db() as conn:
        await conn.execute("""
            INSERT INTO user_integrations (npp, cloud_username, cloud_password, updated_at)
            VALUES ($1, $2, $3, now())
            ON CONFLICT (npp) DO UPDATE 
            SET cloud_username = $2, cloud_password = $3, updated_at = now()
        """, npp, username, password)
        
    return {"status": "success", "message": "Cloud Pindad berhasil disambungkan"}

@router.delete("/integrations/cloud")
async def disconnect_cloud(token: str = Query(...)):
    """Hapus kredensial Cloud Pindad"""
    try:
        user_data = await verify_session(token=token)
        npp = user_data.data["npp"]
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    async with get_db() as conn:
        await conn.execute("UPDATE user_integrations SET cloud_username = NULL, cloud_password = NULL, updated_at = now() WHERE npp = $1", npp)
        
    return {"status": "success", "message": "Cloud Pindad berhasil diputus"}


class OnboardingRequest(BaseModel):
    token: str
    preferred_language: Optional[str] = "id"
    theme_preference: Optional[str] = "dark"
    communication_style: Optional[str] = "formal_saya_anda"
    preferred_name: Optional[str] = None
    mail_username: Optional[str] = None
    mail_password: Optional[str] = None
    cloud_username: Optional[str] = None
    cloud_password: Optional[str] = None


@router.post("/onboarding")
async def complete_onboarding(req: OnboardingRequest):
    """
    Menyimpan preferensi setup pertama kali (OOBE) dan mengaktifkan is_onboarded = TRUE.
    """
    logger.info(f"✨ [ONBOARDING] Menerima request onboarding setup...")
    try:
        user_data = await verify_session(token=req.token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Unauthorized")
        npp = user_data.data["npp"]
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with get_db() as conn:
        async with conn.transaction():
            # 1. Update preferred_name di users table
            if req.preferred_name:
                await conn.execute("UPDATE users SET preferred_name = $2 WHERE npp = $1", npp, req.preferred_name)

            # 2. Update user_settings JSONB dengan is_onboarded = TRUE
            import json
            existing_settings_row = await conn.fetchrow("SELECT settings FROM user_settings WHERE npp = $1", npp)
            curr_settings = {}
            if existing_settings_row and existing_settings_row["settings"]:
                curr_settings = json.loads(existing_settings_row["settings"]) if isinstance(existing_settings_row["settings"], str) else existing_settings_row["settings"]
            
            curr_settings["is_onboarded"] = True
            curr_settings["preferred_language"] = req.preferred_language or curr_settings.get("preferred_language", "id")
            curr_settings["theme_preference"] = req.theme_preference or curr_settings.get("theme_preference", "dark")
            curr_settings["communication_style"] = req.communication_style or curr_settings.get("communication_style", "formal_saya_anda")
            curr_settings["preferred_name"] = req.preferred_name or curr_settings.get("preferred_name")

            await conn.execute("""
                INSERT INTO user_settings (npp, settings, updated_at)
                VALUES ($1, $2::jsonb, now())
                ON CONFLICT (npp) DO UPDATE 
                SET settings = $2::jsonb, updated_at = now()
            """, npp, json.dumps(curr_settings))

            # 3. Update integrasi email / cloud jika diisi
            if req.mail_username and req.mail_password:
                await conn.execute("""
                    INSERT INTO user_integrations (npp, mail_username, mail_password, updated_at)
                    VALUES ($1, $2, $3, now())
                    ON CONFLICT (npp) DO UPDATE 
                    SET mail_username = $2, mail_password = $3, updated_at = now()
                """, npp, req.mail_username, req.mail_password)

            if req.cloud_username and req.cloud_password:
                await conn.execute("""
                    INSERT INTO user_integrations (npp, cloud_username, cloud_password, updated_at)
                    VALUES ($1, $2, $3, now())
                    ON CONFLICT (npp) DO UPDATE 
                    SET cloud_username = $2, cloud_password = $3, updated_at = now()
                """, npp, req.cloud_username, req.cloud_password)

        # Ambil user updated profile
        updated_user = await conn.fetchrow("""
            SELECT npp, fullname, preferred_name, divisi, role, email, profile_photo_url
            FROM users WHERE npp = $1
        """, npp)

        # Realtime refresh in-memory cache
        from backend.app.utils.employee_cache import invalidate_employee_cache
        invalidate_employee_cache(npp)

    return {
        "status": "success",
        "message": "Onboarding berhasil diselesaikan",
        "data": {
            "npp": updated_user["npp"],
            "fullname": updated_user["fullname"],
            "preferred_name": updated_user["preferred_name"] or curr_settings.get("preferred_name"),
            "divisi": updated_user["divisi"],
            "role": updated_user["role"],
            "email": updated_user["email"],
            "profile_photo_url": updated_user["profile_photo_url"],
            "is_onboarded": True,
            "preferred_language": curr_settings.get("preferred_language", "id"),
            "theme_preference": curr_settings.get("theme_preference", "dark"),
            "communication_style": curr_settings.get("communication_style", "formal_saya_anda"),
        }
    }
