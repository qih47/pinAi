from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, Query, Response
from typing import Dict, Any, List
import asyncio
import urllib.parse
from backend.app.services.corporate.corporate_service import (
    generate_email_draft, generate_email_triage, generate_nota_dinas, 
    analyze_email_threat, compose_new_email_ai,
    save_user_draft, list_user_drafts, delete_user_draft
)
from backend.app.services.corporate.zimbra_service import fetch_unread_emails, send_email_reply, get_email_attachment_bytes
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

# 1. Email Triage Skeleton & Multi-Folder (Inbox / Sent)
@router.post("/emails/fetch")
async def fetch_real_emails(payload: Dict[str, Any] = Body(...)):
    """Mengembalikan daftar email dari Zimbra (mendukung folder 'inbox' dan 'sent')."""
    token = payload.get("token")
    folder = payload.get("folder", "inbox")
    limit = int(payload.get("limit", 30))
    auth = await get_mail_credentials(token)
    
    if not auth:
        return {
            "status": "error",
            "message": "NOT_CONNECTED"
        }
        
    email_address = auth["username"]
    password = auth["password"]
        
    try:
        emails = await asyncio.to_thread(fetch_unread_emails, email_address, password, limit, folder)
        
        # Jika folder inbox, cocokkan dengan database corporate_email_triage untuk isi cache
        if folder.lower() in ["inbox", "kotak masuk"] and emails:
            msg_ids = [e["message_id"] for e in emails if e.get("message_id")]
            if msg_ids:
                try:
                    async with get_db() as conn:
                        rows = await conn.fetch(
                            "SELECT message_id, priority, threat_reason FROM corporate_email_triage WHERE user_email = $1 AND message_id = ANY($2)",
                            email_address, msg_ids
                        )
                        triage_map = {r["message_id"]: r for r in rows}
                        for e in emails:
                            mid = e.get("message_id")
                            if mid in triage_map:
                                e["priority"] = triage_map[mid]["priority"]
                                e["has_triage"] = True
                                if triage_map[mid]["threat_reason"]:
                                    e["threat_reason"] = triage_map[mid]["threat_reason"]
                            else:
                                e["has_triage"] = False
                except Exception as db_err:
                    # Jangan gagalkan fetch jika query DB cache mengalami isu kecil
                    pass
        elif folder.lower() in ["sent", "terkirim"]:
            for e in emails:
                e["has_triage"] = True
                e["priority"] = "📤 Sent"

        return {
            "status": "success",
            "folder": folder,
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
    """Menentukan prioritas email menggunakan AI dan menyimpannya di DB cache."""
    token = payload.get("token")
    message_id = payload.get("message_id")
    email_uid = str(payload.get("email_uid") or payload.get("id") or "")
    email_content = payload.get("email_content", "")
    email_subject = payload.get("email_subject", "")
    sender = payload.get("sender", "")
    
    if not email_content:
        return {"status": "success", "data": {"priority": "🟢 INFO"}}
        
    priority = await generate_email_triage(email_content, email_subject)
    
    # Simpan hasil triage ke database PostgreSQL agar tidak di-triage berulang kali
    auth = await get_mail_credentials(token) if token else None
    if auth and message_id:
        try:
            async with get_db() as conn:
                await conn.execute("""
                    INSERT INTO corporate_email_triage (user_email, message_id, imap_uid, subject, sender, priority)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (user_email, message_id) 
                    DO UPDATE SET priority = EXCLUDED.priority, imap_uid = EXCLUDED.imap_uid, subject = EXCLUDED.subject
                """, auth["username"], message_id, email_uid, email_subject, sender, priority)
        except Exception as e:
            pass

    return {
        "status": "success",
        "data": {
            "priority": priority
        }
    }

@router.get("/emails/{email_uid}/attachments/{part_index}/download")
async def download_email_attachment(
    email_uid: str,
    part_index: int,
    token: str = Query(...),
    folder: str = Query("inbox")
):
    """Mengunduh lampiran dokumen email asli dari IMAP Zimbra secara streaming."""
    auth = await get_mail_credentials(token)
    if not auth:
        raise HTTPException(status_code=401, detail="Sesi autentikasi Zimbra tidak valid atau belum terhubung.")
        
    try:
        att = await asyncio.to_thread(
            get_email_attachment_bytes,
            auth["username"],
            auth["password"],
            email_uid,
            part_index,
            folder
        )
        safe_filename = urllib.parse.quote(att["filename"])
        return Response(
            content=att["data"],
            media_type=att["content_type"] or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{att["filename"]}"; filename*=UTF-8\'\'{safe_filename}'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Gagal mengunduh lampiran email: {str(e)}")

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
    """Send an email reply or new composed email with optional attachments via Zimbra."""
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
    is_reply = payload.get("is_reply", True)
    attachments = payload.get("attachments", [])
    draft_id = payload.get("draft_id")
    
    if not all([to_address, subject, body]):
        raise HTTPException(status_code=400, detail="Semua field (to, subject, body) wajib diisi.")
        
    try:
        success = await asyncio.to_thread(
            send_email_reply, 
            email_address, password, to_address, subject, body, cc_address, is_reply, attachments
        )
        
        # Jika berhasil terkirim dan berasal dari draft yang tersimpan, bersihkan draft tersebut
        if draft_id:
            try:
                await delete_user_draft(email_address, int(draft_id))
            except Exception as e_draft:
                pass
                
        return {"status": "success", "message": "Email berhasil dikirim."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/emails/drafts")
async def api_list_drafts(token: str = Query(None)):
    """Mendapatkan seluruh draf email yang tersimpan untuk user."""
    auth = await get_mail_credentials(token)
    if not auth:
        raise HTTPException(status_code=401, detail="NOT_CONNECTED")
    
    drafts = await list_user_drafts(auth["username"])
    return {
        "status": "success",
        "data": drafts
    }

@router.post("/emails/drafts/save")
async def api_save_draft(payload: Dict[str, Any] = Body(...)):
    """Menyimpan atau memperbarui draf email pengguna."""
    token = payload.get("token")
    auth = await get_mail_credentials(token)
    if not auth:
        raise HTTPException(status_code=401, detail="NOT_CONNECTED")
        
    user_email = auth["username"]
    draft_id = payload.get("draft_id")
    to_addr = payload.get("to", "")
    cc_addr = payload.get("cc", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    attachments = payload.get("attachments", [])
    
    saved = await save_user_draft(
        user_email=user_email,
        to_addr=to_addr,
        cc_addr=cc_addr,
        subject=subject,
        body=body,
        attachments=attachments,
        draft_id=int(draft_id) if draft_id else None
    )
    return {
        "status": "success",
        "message": "Draf email berhasil disimpan.",
        "data": saved
    }

@router.delete("/emails/drafts/{draft_id}")
async def api_delete_draft(draft_id: int, token: str = Query(None)):
    """Menghapus draf email pengguna."""
    auth = await get_mail_credentials(token)
    if not auth:
        raise HTTPException(status_code=401, detail="NOT_CONNECTED")
        
    success = await delete_user_draft(auth["username"], draft_id)
    return {
        "status": "success",
        "deleted": success
    }


@router.post("/emails/compose-ai")
async def api_compose_email_ai(payload: Dict[str, Any] = Body(...)):
    """Membuat Draf Email Baru & Subjek secara otomatis dari instruksi pengguna menggunakan Gemma4."""
    instruction = payload.get("instruction", "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="Instruksi tidak boleh kosong.")
        
    tone = payload.get("tone", "formal")
    user_name = payload.get("user_name", "Karyawan PT Pindad")
    user_role = payload.get("user_role", "")
    
    result = await compose_new_email_ai(instruction, tone, user_name, user_role)
    return {
        "status": "success",
        "data": result
    }

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
