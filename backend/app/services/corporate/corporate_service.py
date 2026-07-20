import logging
import httpx
import re
from typing import Dict, Any, Optional
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
        "options": {"temperature": temperature},
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
    """Generate Nota Dinas text body using Gemma4."""
    prompt = build_nota_dinas_prompt(instruction)
    body = await generate_text_response(settings.MODEL_PERSONA, prompt, temperature=0.2)
    
    dummy_nota = f"""
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; background: white; padding: 40px; color: black; border: 1px solid #ccc; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <div style="text-align: center; border-bottom: 2px solid black; padding-bottom: 10px; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 18px;">PT PINDAD (PERSERO)</h2>
        <p style="margin: 5px 0 0 0; font-size: 14px;">NOTA DINAS</p>
    </div>
    
    <table style="width: 100%; font-size: 14px; margin-bottom: 20px;">
        <tr><td style="width: 15%;">Nomor</td><td>: ND-___/CAKRA/2026</td></tr>
        <tr><td>Kepada</td><td>: Yth. Manager Terkait</td></tr>
        <tr><td>Dari</td><td>: Divisi Pemohon</td></tr>
        <tr><td>Tanggal</td><td>: 06 Juli 2026</td></tr>
        <tr><td>Sifat</td><td>: Biasa</td></tr>
        <tr><td>Perihal</td><td>: Permohonan Resmi</td></tr>
    </table>
    
    <div style="font-size: 14px; line-height: 1.6; text-align: justify; white-space: pre-wrap;">
{body}
    </div>
    
    <div style="margin-top: 50px; text-align: right; font-size: 14px;">
        <p>Hormat kami,</p>
        <br><br><br>
        <p><strong>( ______________________ )</strong></p>
        <p>Manager Divisi</p>
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
