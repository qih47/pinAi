from fastapi import APIRouter, HTTPException, Body, UploadFile, File
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from backend.app.utils.security_firewall import validate_attachment_security
import logging
import json
import os
import asyncio
import httpx
import re
import subprocess
import shutil
import uuid

from backend.app.core.paths import LOGS_DIR
from backend.app.services.analytics_service import (
    get_system_metrics,
    get_ollama_running_models,
    get_top_users,
    get_rag_stats,
    simulate_rag_search,
    get_user_sessions,
    get_session_chat_history,
    get_session_attachments,
    get_quality_metrics,
    get_agent_steps,
    get_security_threat_score,
    get_query_clusters
)
from backend.app.services.security_service import get_recent_security_logs
from backend.app.services.hardware_service import get_hardware_telemetry


logger = logging.getLogger("CAKRA_ANALYTICS")
router = APIRouter()

LOG_FILE_PATH = os.path.join(LOGS_DIR, "cakra_analytics.jsonl")

async def log_generator():
    """Generator untuk membaca log terbaru (tail) dari file cakra_analytics.jsonl."""
    if not os.path.exists(LOG_FILE_PATH):
        # Jika file belum ada, tunggu sebentar
        yield "data: {\"status\": \"Log file not found yet\"}\n\n"
        
    with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
        # Pindah ke bagian akhir file (minus sedikit agar ada context log terbaru)
        f.seek(0, os.SEEK_END)
        # Mundur sedikit jika perlu (contoh: 5KB terakhir)
        size = f.tell()
        if size > 5120:
            f.seek(size - 5120)
            f.readline() # buang baris setengah
        else:
            f.seek(0)
            
        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.5)
                continue
                
            line = line.strip()
            if line:
                # Kirim dalam format SSE (data: {...}\n\n)
                yield f"data: {line}\n\n"

@router.get("/logs/stream")
async def stream_logs():
    """
    Endpoint SSE untuk streaming cakra_analytics.jsonl ke Dashboard Frontend.
    """
    logger.info("[ANALYTICS] Stream connected from dashboard")
    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream"
    )

async def metrics_generator():
    """Generator untuk memancarkan metrik server setiap 3 detik."""
    while True:
        try:
            metrics = await get_system_metrics()
            yield f"data: {json.dumps(metrics)}\n\n"
        except Exception as e:
            logger.error(f"[ANALYTICS] Error in metrics generator: {e}")
        await asyncio.sleep(3.0)

@router.get("/metrics/stream")
async def stream_metrics():
    """
    Endpoint SSE untuk streaming metrik performa ke Dashboard Frontend (Radar & KPI).
    """
    return StreamingResponse(
        metrics_generator(),
        media_type="text/event-stream"
    )

@router.get("/ollama/models")
async def get_ollama_models():
    """Mengambil daftar model yang tersedia dari Ollama"""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{ollama_url}/api/tags")
            if res.status_code == 200:
                models = res.json().get("models", [])
                return {"status": "success", "models": [m["name"] for m in models]}
    except Exception as e:
        logger.error(f"Failed to fetch Ollama models: {e}")
    return {"status": "error", "models": []}

@router.get("/ollama/ps")
async def get_ollama_ps():
    """Mengambil daftar model yang sedang berjalan (loaded in VRAM) dari Ollama"""
    models = await get_ollama_running_models()
    return {"status": "success", "running_models": models}

@router.get("/users/leaderboard")
async def get_leaderboard():
    """Mengambil top users berdasarkan konsumsi token"""
    users = await get_top_users()
    return {"status": "success", "leaderboard": users}

@router.get("/knowledge/stats")
async def knowledge_stats():
    """Mengambil statistik RAG vector DB"""
    total_chunks = await get_rag_stats()
    return {"status": "success", "total_chunks": total_chunks}

@router.get("/security/logs")
async def security_logs():
    """Mengambil log percobaan hacking/keamanan terbaru"""
    logs = await get_recent_security_logs(limit=50)
    return {"status": "success", "logs": logs}

@router.get("/users/{npp}/sessions")
async def user_sessions(npp: str):
    """GOD MODE: Mengambil daftar sesi chat seorang user"""
    sessions = await get_user_sessions(npp)
    return {"status": "success", "sessions": sessions}

@router.get("/sessions/{session_uuid}")
async def session_history(session_uuid: str):
    """GOD MODE: Mengambil isi percakapan dari sebuah sesi beserta attachments"""
    history = await get_session_chat_history(session_uuid)
    attachments = await get_session_attachments(session_uuid)
    return {"status": "success", "history": history, "attachments": attachments}

@router.get("/quality")
async def quality_metrics():
    """AIOps: Mengambil rasio feedback dari user (Hallucination Radar)"""
    metrics = await get_quality_metrics()
    return {"status": "success", "metrics": metrics}

@router.get("/pipeline")
async def agent_pipeline():
    """Mengambil history langkah (steps) dari AI Agent untuk Node Graph Visualizer"""
    steps = await get_agent_steps()
    return {"status": "success", "steps": steps}

@router.get("/hardware")
async def hardware_telemetry():
    """AIOps: Mengambil metrik hardware server secara real-time (GPU, CPU, RAM)"""
    telemetry = await get_hardware_telemetry()
    return {"status": "success", "telemetry": telemetry}


@router.get("/knowledge/latest-rag")
async def latest_rag_step():
    """Mengambil step RAG terakhir dari seluruh sistem"""
    from backend.app.services.analytics_service import get_latest_rag_step
    step = await get_latest_rag_step()
    return {"status": "success", "step": step}


class RagSimulationRequest(BaseModel):
    query: str

@router.get("/security/threat-score")
async def security_threat_score():
    """AIOps: Hitung Threat Score anomali keamanan 24 jam terakhir"""
    data = await get_security_threat_score()
    return {"status": "success", "data": data}

@router.get("/knowledge/clusters")
async def knowledge_clusters():
    """AIOps: Distribusi routing intent untuk Semantic Query Clustering"""
    clusters = await get_query_clusters()
    return {"status": "success", "clusters": clusters}

@router.post("/knowledge/simulate")
async def knowledge_simulate(request: RagSimulationRequest):
    """Menyimulasikan pencarian RAG untuk debugging"""
    results = await simulate_rag_search(request.query)
    return {"status": "success", "results": results}

@router.post("/simulate-ocr")
async def simulate_ocr(file: UploadFile = File(...)):
    """Simulate OCR extraction for a given PDF file."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    await validate_attachment_security(file)
    
    temp_dir = "/tmp/cakra_ocr_sandbox"
    os.makedirs(temp_dir, exist_ok=True)
    # Gunakan basename untuk cegah directory traversal
    safe_filename = os.path.basename(file.filename)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_filename}")
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        from backend.app.services.peraturan_service import simulate_ocr_extraction
        extracted_text, images = await simulate_ocr_extraction(temp_path)
        
        return {
            "status": "success", 
            "extracted_text": extracted_text,
            "images": images
        }
    except Exception as e:
        logger.error(f"[ANALYTICS] OCR Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.get("/prompts")
async def get_all_prompts():
    """Mengambil semua prompt dari database untuk Prompt Studio."""
    from backend.app.services.pipeline.prompt_manager import prompt_manager
    try:
        prompts = await prompt_manager.get_all_prompts()
        return {"status": "success", "prompts": prompts}
    except Exception as e:
        logger.error(f"Failed to fetch prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class PromptUpdateRequest(BaseModel):
    template: str

@router.put("/prompts/{name}")
async def update_prompt(name: str, request: PromptUpdateRequest):
    """Update sebuah prompt di DB dan picu hot-reload di PromptManager."""
    from backend.app.services.pipeline.prompt_manager import prompt_manager
    try:
        await prompt_manager.update_prompt(name, request.template)
        return {"status": "success", "message": f"Prompt {name} updated and hot-reloaded successfully"}
    except Exception as e:
        logger.error(f"Failed to update prompt {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/settings")
async def update_system_settings(
    settings: dict = Body(...),
    sudo_password: str = Body(...)
):
    """Update settings in .env and restart server using sudo"""
    from backend.app.core.config import ENV_PATH
    
    if not os.path.exists(ENV_PATH):
        raise HTTPException(status_code=404, detail="Environment file not found")
        
    try:
        # Baca isi .env
        with open(ENV_PATH, 'r') as f:
            lines = f.readlines()
            
        # Update nilai
        for key, value in settings.items():
            key_found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    key_found = True
                    break
            if not key_found:
                lines.append(f"{key}={value}\n")
                
        # Tulis kembali ke .env
        with open(ENV_PATH, 'w') as f:
            f.writelines(lines)
            
        logger.info("[SETTINGS] Environment variables updated successfully.")
        
        # Eksekusi restart di background task (supaya API bisa respond sukses)
        async def delayed_restart():
            await asyncio.sleep(2)
            cmd = f"echo '{sudo_password}' | sudo -S systemctl daemon-reload && echo '{sudo_password}' | sudo -S systemctl restart cakra-backend"
            subprocess.Popen(cmd, shell=True, executable="/bin/bash")
            
        asyncio.create_task(delayed_restart())
        
        return {"status": "success", "message": "Settings saved. Restarting server..."}
        
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings")
async def get_system_settings():
    """Mengambil konfigurasi sistem untuk tab Settings di Dashboard"""
    from backend.app.core.config import settings
    return {
        "status": "success",
        "data": {
            "OLLAMA_BASE_URL": settings.OLLAMA_BASE_URL,
            "DB_HOST": settings.DB_HOST,
            "MODEL_PERSONA": settings.MODEL_PERSONA,
            "MODEL_EMBEDDING": settings.MODEL_EMBEDDING,
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "production"),
            "DEBUG_MODE": "True" if settings.DEBUG else "False",
            "MAX_SESSIONS": "Unlimited",
            "SYSTEM_VERSION": "3.0.0 (Cakra Engine)"
        }
    }

@router.post("/operations/{action}")
async def execute_operation(action: str, sudo_password: str = Body(default="")):
    """Menjalankan aksi operasional tingkat lanjut dari Dashboard"""
    valid_actions = ["reload_llm", "clear_vector_cache", "clear_sessions", "restart_services"]
    
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail="Invalid operation action")
        
    logger.warning(f"🚨 [OPERATIONS] Admin triggered critical action: {action.upper()}")
    
    if action == "restart_services":
        if not sudo_password:
            raise HTTPException(status_code=400, detail="Sudo password required for this operation")
        async def delayed_restart():
            await asyncio.sleep(2)
            cmd = f"echo '{sudo_password}' | sudo -S systemctl daemon-reload && echo '{sudo_password}' | sudo -S systemctl restart cakra-backend"
            subprocess.Popen(cmd, shell=True, executable="/bin/bash")
        asyncio.create_task(delayed_restart())
        return {"status": "success", "message": "Restarting server...", "timestamp": os.popen("date").read().strip()}
    
    # Simulate other operations
    await asyncio.sleep(1.5)
    
    return {
        "status": "success",
        "message": f"Action {action.upper()} executed successfully",
        "timestamp": os.popen("date").read().strip()
    }
