from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from typing import Dict, Any, List
import asyncio
from backend.app.services.corporate.corporate_service import generate_email_draft, generate_email_triage, generate_nota_dinas, analyze_email_threat
from backend.app.services.corporate.zimbra_service import fetch_unread_emails, send_email_reply
from backend.app.core.config import settings
from backend.app.api.endpoints.auth import verify_session
from backend.app.core.database import get_db

router = APIRouter()

async def get_mail_credentials(token: str):
    """Ambil kredensial Mail Pindad dari database berdasarkan token sesi."""
    if not token:
        return None
        
    try:
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            return None
        npp = user_data.data["npp"]
    except Exception:
        return None
        
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT mail_username, mail_password FROM user_integrations WHERE npp = $1", npp)
        if not row or not row["mail_username"] or not row["mail_password"]:
            return None
        
        return {"username": row["mail_username"], "password": row["mail_password"]}

# 1. Email Triage Skeleton
@router.post("/emails/fetch")
async def fetch_real_emails(payload: Dict[str, Any] = Body(...)):
    """Returns a list of real emails from Zimbra."""
    token = payload.get("token")
    auth = await get_mail_credentials(token)
    
    if not auth:
        return {
            "status": "error",
            "message": "NOT_CONNECTED"
        }
        
    email_address = auth["username"]
    password = auth["password"]
        
    try:
        emails = await asyncio.to_thread(fetch_unread_emails, email_address, password, 30)
        return {
            "status": "success",
            "data": emails
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Autentikasi IMAP Zimbra Gagal: {str(e)}"
        }

@router.post("/emails/{email_id}/draft")
async def api_generate_email_draft(email_id: str, payload: Dict[str, Any] = Body(default={})):
    """Generates AI email draft using Gemma4."""
    instruction = payload.get("instruction")
    
    # Ambil konten asli (untuk sekarang, jika user mengklik, text dikirim dari UI saja agar gampang)
    email_content = payload.get("email_content", "Tolong balas email ini.")
    user_name = payload.get("user_name", "CAKRA")
    user_role = payload.get("user_role", "Asisten AI PT Pindad (Persero)")
        
    draft = await generate_email_draft(email_content, instruction, user_name, user_role)
        
    return {
        "status": "success",
        "data": {
            "draft_content": draft
        }
    }


@router.post("/emails/triage")
async def api_generate_email_triage(payload: Dict[str, Any] = Body(...)):
    """Menentukan prioritas email menggunakan AI."""
    email_content = payload.get("email_content", "")
    email_subject = payload.get("email_subject", "")
    
    if not email_content:
        return {"status": "success", "data": {"priority": "🟢 INFO"}}
        
    priority = await generate_email_triage(email_content, email_subject)
    return {
        "status": "success",
        "data": {
            "priority": priority
        }
    }

@router.post("/emails/threat-analysis")
async def api_analyze_threat(payload: Dict[str, Any] = Body(...)):
    """Menghasilkan analisis ancaman dari email SPAM."""
    email_content = payload.get("email_content", "")
    if not email_content:
        raise HTTPException(status_code=400, detail="email_content wajib diisi.")
        
    analysis = await analyze_email_threat(email_content)
    return {
        "status": "success",
        "data": {
            "threat_reason": analysis
        }
    }

@router.post("/emails/reply")
async def send_zimbra_reply(payload: Dict[str, Any] = Body(...)):
    """Send an email reply via Zimbra."""
    token = payload.get("token")
    auth = await get_mail_credentials(token)
    
    if not auth:
        raise HTTPException(status_code=401, detail="NOT_CONNECTED")
        
    email_address = auth["username"]
    password = auth["password"]
    
    to_address = payload.get("to")
    cc_address = payload.get("cc")
    subject = payload.get("subject")
    body = payload.get("body")
    
    if not all([to_address, subject, body]):
        raise HTTPException(status_code=400, detail="Semua field (to, subject, body) wajib diisi.")
        
    try:
        success = await asyncio.to_thread(send_email_reply, email_address, password, to_address, subject, body, cc_address)
        return {"status": "success", "message": "Email berhasil dikirim."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. Surat Dinas Generator
@router.post("/document/generate")
async def api_generate_surat_dinas(payload: Dict[str, Any]):
    """Generates a Nota Dinas document using Gemma4."""
    instruction = payload.get("instruction", "")
    if not instruction:
        raise HTTPException(status_code=400, detail="Instruksi tidak boleh kosong")
        
    nota_html = await generate_nota_dinas(instruction)
    
    return {
        "status": "success",
        "data": {
            "document_html": nota_html
        }
    }

# 3. Vendor Analyzer
@router.post("/vendor/analyze")
async def api_analyze_vendors(payload: Dict[str, Any]):
    """Analyzes vendor documents using AI."""
    vendors_data = payload.get("vendors_data")
    if not vendors_data:
        raise HTTPException(status_code=400, detail="Data vendor tidak boleh kosong.")
        
    result = await analyze_vendors(vendors_data)
    return result
