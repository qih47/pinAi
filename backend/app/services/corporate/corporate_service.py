import logging
import httpx
import re
from typing import Dict, Any, Optional, List
from backend.app.core.config import settings
from backend.app.services.pipeline.prompts.core_prompts import (
    build_smart_mail_draft_prompt,
    build_smart_mail_triage_prompt,
    build_nota_dinas_prompt,
    build_threat_analysis_prompt,
    build_vendor_analyzer_prompt
)

logger = logging.getLogger("CAKRA_CORPORATE_SERVICE")

async def generate_text_response(model_name: str, prompt: str, temperature: float = 0.3) -> str:
    """Helper to generate non-streaming text response from Ollama."""
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "keep_alive": -1,
        "options": {
            "temperature": temperature,
            "num_ctx": 16384 if ("31b" in model_name or "persona" in model_name.lower()) else 4096,
            "num_batch": 512,
        },
    }
    
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                result = response.json()
                content = result.get("message", {}).get("content", "")
                
                # Cleanup potential markdown json/code blocks if any
                return content.strip()
            else:
                logger.error(f"[CORPORATE] Ollama error: {response.text}")
                return "Mohon maaf, terjadi kesalahan pada AI engine saat memproses permintaan."
    except Exception as e:
        logger.error(f"[CORPORATE] Request failed: {e}")
        return "Mohon maaf, AI engine sedang tidak dapat diakses."

async def generate_email_draft(email_content: str, instruction: Optional[str] = None, user_name: str = "CAKRA", user_role: str = "Asisten AI PT Pindad (Persero)") -> str:
    """Generate professional email draft using Gemma4."""
    # Truncate email content to prevent context overflow (max 4000 chars)
    if len(email_content) > 4000:
        email_content = email_content[:4000] + "\n...[DIPOTONG KARENA TERLALU PANJANG]..."
        
    prompt = build_smart_mail_draft_prompt(email_content, instruction)
    draft = await generate_text_response(settings.MODEL_PERSONA, prompt, temperature=0.3)
    
    # Force strip markdown since LLMs are sometimes stubborn
    draft = re.sub(r'\*\*(.*?)\*\*', r'\1', draft) # Remove **bold**
    draft = re.sub(r'\*(.*?)\*', r'\1', draft)     # Remove *italic*
    draft = re.sub(r'#+\s*', '', draft)            # Remove headers
    
    draft = draft.strip()
    
    # Append signature automatically
    signature = f"\n\nDemikian kami sampaikan, terima kasih.\n\nHormat kami,\n\n{user_name}\n{user_role}\nPT Pindad (Persero)"
    
    if "Hormat kami," not in draft and "Demikian kami sampaikan" not in draft:
        draft += signature
        
    return draft

async def compose_new_email_ai(
    instruction: str, 
    tone: str = "formal", 
    user_name: str = "Karyawan PT Pindad", 
    user_role: str = ""
) -> Dict[str, str]:
    """Menghasilkan Subjek dan Draf Body Email Baru dari instruksi pengguna menggunakan Gemma4."""
    tone_guidelines = {
        "formal": "Bahasa Indonesia baku yang sangat sopan, formal, profesional, berwibawa, dan santun korporat PT Pindad.",
        "concise": "Langsung ke inti pokok bahasan (to the point), efisien, padat dan jelas, tanpa basa-basi berlebih namun tetap sopan.",
        "friendly": "Hangat, bersahabat, kolaboratif, luwes, namun tetap menghormati tata krama kerja profesional.",
        "announcement": "Gaya pengumuman / sosialisasi resmi terstruktur, memuat poin-poin penting, waktu, dan instruksi tindakan yang jelas."
    }
    selected_tone = tone_guidelines.get(tone, tone_guidelines["formal"])
    
    prompt = f"""Kamu adalah CAKRA, asisten AI resmi PT Pindad (Persero).
Tugasmu adalah membuatkan Subjek dan Draf Email Baru yang sangat rapi dan profesional berdasarkan instruksi pengguna.

Pedoman Gaya Bahasa / Nada:
{selected_tone}

Identitas Pengirim:
Nama: {user_name}
Jabatan/Unit: {user_role or 'PT Pindad (Persero)'}

Instruksi Pengguna:
{instruction}

Format Output Wajib (hanya berikan format ini tanpa kata pengantar lain):
SUBJEK: [Tuliskan subjek email yang padat, jelas, dan profesional di sini]
BODY:
[Tuliskan draf lengkap isi email mulai dari salam pembuka yang santun, uraian pesan, hingga penutup dan tanda tangan identitas pengirim]
"""
    raw_response = await generate_text_response(settings.MODEL_PERSONA, prompt, temperature=0.3)
    
    subject = ""
    body = ""
    if "SUBJEK:" in raw_response and "BODY:" in raw_response:
        parts = raw_response.split("BODY:", 1)
        sub_part = parts[0].replace("SUBJEK:", "").strip()
        subject = sub_part.split("\n")[0].strip()
        body = parts[1].strip()
    elif "BODY:" in raw_response:
        body = raw_response.split("BODY:", 1)[1].strip()
        subject = instruction[:60].strip()
    else:
        body = raw_response.strip()
        subject = instruction[:60].strip()
        
    # Pastikan tanda tangan identitas ada jika belum
    signature = f"\n\nDemikian kami sampaikan, terima kasih.\n\nHormat kami,\n\n{user_name}\n{user_role or 'PT Pindad (Persero)'}"
    if "Hormat kami" not in body and "Demikian" not in body:
        body += signature

    return {
        "subject": subject,
        "body": body
    }

async def generate_email_triage(email_content: str, email_subject: str = "") -> str:
    """Klasifikasi prioritas email menggunakan AI."""
    if len(email_content) > 3000:
        email_content = email_content[:3000] + "..."
    prompt = build_smart_mail_triage_prompt(email_content, email_subject)
    # Triage returns only one word, keep temp low to be deterministic
    triage_result = await generate_text_response(settings.MODEL_PERSONA, prompt, temperature=0.1)
    
    # Normalisasi hasil AI (bisa jadi kepanjangan karena AI membangkang)
    triage_upper = triage_result.upper()
    if "URGENT" in triage_upper:
        return "🔴 URGENT"
    elif "APPROVAL" in triage_upper:
        return "🟡 APPROVAL"
    elif "SPAM" in triage_upper or "SCAM" in triage_upper:
        return "🚫 SPAM"
    else:
        return "🟢 INFO"


async def analyze_email_threat(email_content: str) -> str:
    """Menganalisis alasan mengapa email diklasifikasikan sebagai SPAM/SCAM."""
    if len(email_content) > 3000:
        email_content = email_content[:3000] + "..."
    prompt = build_threat_analysis_prompt(email_content)
    analysis = await generate_text_response(settings.MODEL_PERSONA, prompt, temperature=0.2)
    return analysis.strip()


async def generate_nota_dinas(instruction: str) -> str:
    """Generate Nota Dinas text body using Gemma4 terintegrasi tool Persuratan."""
    from backend.app.services.tools.persuratan import _today_indonesian, _generate_draft_number
    prompt = build_nota_dinas_prompt(instruction)
    body = await generate_text_response(settings.MODEL_PERSONA, prompt, temperature=0.2)
    
    tgl = _today_indonesian()
    no_draft = _generate_draft_number("nota_dinas")

    dummy_nota = f"""
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; background: white; padding: 40px; color: black; border: 1px solid #ccc; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <div style="text-align: center; border-bottom: 2px solid black; padding-bottom: 10px; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 18px;">PT PINDAD (PERSERO)</h2>
        <p style="margin: 5px 0 0 0; font-size: 14px; font-weight: bold;">NOTA DINAS</p>
    </div>
    
    <table style="width: 100%; font-size: 14px; margin-bottom: 20px;">
        <tr><td style="width: 15%;">Nomor</td><td>: {no_draft}</td></tr>
        <tr><td>Kepada</td><td>: Yth. Pejabat / Manager Terkait</td></tr>
        <tr><td>Dari</td><td>: Pemohon / Unit Kerja Pengusul</td></tr>
        <tr><td>Tanggal</td><td>: {tgl}</td></tr>
        <tr><td>Sifat</td><td>: Biasa</td></tr>
        <tr><td>Perihal</td><td>: {instruction[:60]}...</td></tr>
    </table>
    
    <div style="font-size: 14px; line-height: 1.6; text-align: justify; white-space: pre-wrap;">
{body}
    </div>
    
    <div style="margin-top: 50px; text-align: right; font-size: 14px;">
        <p>Hormat kami,</p>
        <br><br><br>
        <p><strong>( ______________________ )</strong></p>
        <p>Pejabat Berwenang</p>
    </div>
</div>
"""
    return dummy_nota


async def analyze_vendors(vendors_data: str) -> Dict[str, Any]:
    """Analyze vendors and return structured JSON using AI."""
    import json
    prompt = build_vendor_analyzer_prompt(vendors_data)
    
    # Use low temperature for structured factual extraction
    response_text = await generate_text_response(settings.MODEL_PERSONA, prompt, temperature=0.1)
    
    # Try to parse the JSON
    try:
        data = json.loads(response_text)
        return {
            "status": "success",
            "data": data
        }
    except json.JSONDecodeError:
        logger.error(f"[CORPORATE] Failed to parse vendor analysis JSON. Raw output: {response_text}")
        # Fallback if AI didn't return valid JSON
        return {
            "status": "success",
            "data": {
                "summary": "Analisis gagal diformat ke dalam bentuk JSON oleh AI. Berikut adalah output mentah:\n" + response_text,
                "matrix": []
            }
        }

async def save_user_draft(
    user_email: str, 
    to_addr: str = "", 
    cc_addr: str = "", 
    subject: str = "", 
    body: str = "", 
    attachments: list = None, 
    draft_id: Optional[int] = None
) -> Dict[str, Any]:
    """Menyimpan atau memperbarui draf email pengguna di database."""
    import json
    from backend.app.core.database import get_db
    attachments_json = json.dumps(attachments or [])
    
    async with get_db() as conn:
        if draft_id:
            row = await conn.fetchrow("""
                UPDATE corporate_email_drafts
                SET to_recipients = $1, cc_recipients = $2, subject = $3, body = $4, attachments = $5::jsonb, updated_at = now()
                WHERE id = $6 AND user_email = $7
                RETURNING id, user_email, to_recipients, cc_recipients, subject, body, attachments, updated_at;
            """, to_addr, cc_addr, subject, body, attachments_json, draft_id, user_email)
            if row:
                return {
                    "id": row["id"],
                    "to": row["to_recipients"],
                    "cc": row["cc_recipients"],
                    "subject": row["subject"],
                    "body": row["body"],
                    "attachments": json.loads(row["attachments"]) if isinstance(row["attachments"], str) else (row["attachments"] or []),
                    "updated_at": row["updated_at"].isoformat()
                }
        
        row = await conn.fetchrow("""
            INSERT INTO corporate_email_drafts (user_email, to_recipients, cc_recipients, subject, body, attachments)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING id, user_email, to_recipients, cc_recipients, subject, body, attachments, updated_at;
        """, user_email, to_addr, cc_addr, subject, body, attachments_json)
        
        return {
            "id": row["id"],
            "to": row["to_recipients"],
            "cc": row["cc_recipients"],
            "subject": row["subject"],
            "body": row["body"],
            "attachments": json.loads(row["attachments"]) if isinstance(row["attachments"], str) else (row["attachments"] or []),
            "updated_at": row["updated_at"].isoformat()
        }

async def list_user_drafts(user_email: str) -> List[Dict[str, Any]]:
    """Mengambil daftar seluruh draf email yang tersimpan untuk pengguna tertentu."""
    import json
    from backend.app.core.database import get_db
    
    async with get_db() as conn:
        rows = await conn.fetch("""
            SELECT id, user_email, to_recipients, cc_recipients, subject, body, attachments, updated_at
            FROM corporate_email_drafts
            WHERE user_email = $1
            ORDER BY updated_at DESC;
        """, user_email)
        
        results = []
        for r in rows:
            atts = r["attachments"]
            if isinstance(atts, str):
                try:
                    atts = json.loads(atts)
                except Exception:
                    atts = []
            results.append({
                "id": r["id"],
                "to": r["to_recipients"] or "",
                "cc": r["cc_recipients"] or "",
                "subject": r["subject"] or "(Tanpa Subjek)",
                "body": r["body"] or "",
                "attachments": atts or [],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else ""
            })
        return results

async def delete_user_draft(user_email: str, draft_id: int) -> bool:
    """Menghapus draf email pengguna."""
    from backend.app.core.database import get_db
    async with get_db() as conn:
        res = await conn.execute("""
            DELETE FROM corporate_email_drafts
            WHERE id = $1 AND user_email = $2;
        """, draft_id, user_email)
        return "DELETE 1" in res
