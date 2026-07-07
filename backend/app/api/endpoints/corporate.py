from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from typing import Dict, Any, List
import asyncio
from backend.app.services.corporate.corporate_service import generate_email_draft, generate_email_triage, generate_nota_dinas, analyze_email_threat
from backend.app.services.corporate.zimbra_service import fetch_unread_emails, send_email_reply
from backend.app.core.config import settings

router = APIRouter()

# 1. Email Triage Skeleton
@router.post("/emails/fetch")
async def fetch_real_emails(payload: Dict[str, Any] = Body(...)):
    """Returns a list of real emails from Zimbra."""
    email_address = payload.get("email")
    password = payload.get("password")
    
    if not email_address or not password:
        return {
            "status": "error",
            "message": "Email dan Password Zimbra wajib diisi."
        }
        
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
    email_address = payload.get("email")
    password = payload.get("password")
    to_address = payload.get("to")
    cc_address = payload.get("cc")
    subject = payload.get("subject")
    body = payload.get("body")
    
    if not all([email_address, password, to_address, subject, body]):
        raise HTTPException(status_code=400, detail="Semua field (email, password, to, subject, body) wajib diisi.")
        
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

# 3. Vendor Analyzer Skeleton
@router.post("/vendor/analyze")
async def analyze_vendors(payload: Dict[str, Any]):
    """Simulates analyzing multiple vendor documents."""
    await asyncio.sleep(3) # Simulate heavy AI processing
    
    return {
        "status": "success",
        "data": {
            "summary": "Vendor A menawarkan harga terendah, namun Vendor B memiliki SLA yang lebih sesuai dengan standar Pindad.",
            "matrix": [
                {"kriteria": "Harga", "vendor_a": "Rp 500.000.000", "vendor_b": "Rp 550.000.000", "pemenang": "Vendor A"},
                {"kriteria": "Garansi", "vendor_a": "1 Tahun", "vendor_b": "3 Tahun", "pemenang": "Vendor B"},
                {"kriteria": "Waktu Pengerjaan", "vendor_a": "45 Hari", "vendor_b": "30 Hari", "pemenang": "Vendor B"},
                {"kriteria": "SLA Support", "vendor_a": "8x5", "vendor_b": "24x7", "pemenang": "Vendor B"}
            ]
        }
    }
