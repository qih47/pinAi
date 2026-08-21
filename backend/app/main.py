import sys
import os

# ==============================================================================
# DOUBLE-PATH RESOLUTION FOR SYSTEMD DAEMON
# ==============================================================================
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))  # backend/app
BACKEND_DIR = os.path.dirname(CURRENT_FILE_DIR)                # backend
ROOT_DIR = os.path.dirname(BACKEND_DIR)                        # pinAi

for path in [ROOT_DIR, BACKEND_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)
# ==============================================================================

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.database import init_db_pool, close_db_pool
from backend.app.services.rag.reranker_service import _load_reranker
from backend.app.core.logging_setup import setup_root_logger
from backend.app.api.router import api_router
from backend.app.core.llm_client import warm_up_model
from backend.app.core.hardware import check_gpu_status
from backend.app.core.paths import DOCUMENTS_DIR, UPLOAD_DIR, ACCOUNTS_DIR, FILE_PERATURAN_DIR
from backend.app.services.system.background_tasks import start_background_scheduler, stop_background_scheduler
from backend.app.utils.request_logging import RequestIDLoggingMiddleware, setup_request_id_logging
from backend.app.utils.token_expiry import setup_token_expiry_migration
from backend.app.utils.vector_index import setup_hnsw_index, optimize_vector_search

setup_root_logger()
setup_request_id_logging()
logger = logging.getLogger("CAKRA_MAIN")

DB_DOC_DIR = os.path.join(ROOT_DIR, "db_doc")
if not os.path.exists(DB_DOC_DIR):
    os.makedirs(DB_DOC_DIR)
    logger.info(f"[STORAGE_DIR_CREATED] '{DB_DOC_DIR}' created.")


async def _unload_deprecated_models():
    """
    Unload deprecated models (Qwen 0.6B/1.7B) from VRAM to optimize memory.
    """
    # Deprecated models feature removed, preserving function signature for safe lifespan
    pass


async def _warmup_and_pin_models():
    """
    Warmup dan pin model ke VRAM saat startup.
    Dijalankan sekuensial agar tidak berebut slot semaphore.

    Model yang dipin:
      - Router (MODEL_ROUTER, ctx=4096): Call 1 JSON routing
      - Gemma4 (MODEL_PERSONA, ctx=16384): Call 2 Persona & Generator
      - Embedding (MODEL_EMBEDDING, ctx=512): RAG vector search
    """
    import httpx

    llm_models = [
        (getattr(settings, "MODEL_ROUTER", "gemma4:e4b"), "Router (Call 1)", 4096),
        (settings.MODEL_PERSONA, "Gemma4 Agentic Engine (Call 2)", 16384),
    ]

    chat_url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    for model_name, label, ctx_len in llm_models:
        logger.info(f"⏳ [WARMUP] Pinning {label} ({model_name}, ctx={ctx_len}) ke VRAM...")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": -1,   # permanent — tidak di-evict sampai service restart
                    "options": {"temperature": 0.1, "num_predict": 1, "num_ctx": ctx_len},
                }
                resp = await client.post(chat_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ [WARMUP] {label} ({model_name}) pinned successfully.")
                else:
                    logger.warning(f"⚠️ [WARMUP] {label} ({model_name}) warmup returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ [WARMUP] {label} ({model_name}) warmup failed: {e}")

    # Khusus embedding — pakai endpoint /api/embed bukan /api/chat
    if getattr(settings, "MODEL_EMBEDDING", None):
        try:
            embed_url = f"{settings.OLLAMA_BASE_URL}/api/embed"
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                resp = await client.post(embed_url, json={
                    "model": settings.MODEL_EMBEDDING,
                    "input": "pindad",
                    "keep_alive": -1,
                })
                if resp.status_code == 200:
                    logger.info(f"✅ [WARMUP] Embedding ({settings.MODEL_EMBEDDING}) endpoint pinned.")
        except Exception as e:
            logger.warning(f"⚠️ [WARMUP] Embedding endpoint warmup failed: {e}")

    logger.info("🔒 [WARMUP] Semua model aktif sudah dipinned ke VRAM.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.shutdown_requested = False

    logger.info("\n" + "═"*60)
    logger.info("⏳ [LIFESPAN] Memulai proses bootstrap sistem CAKRA AI...")
    logger.info("═"*60)

    check_gpu_status()
    logger.info(f"📂 [PATHS] Dokumen beroperasi di: {DOCUMENTS_DIR}")

    try:
        await init_db_pool()
        logger.info("[DB_POOL] Dual-pool database connection initialized.")

        from backend.app.services.pipeline.prompt_manager import prompt_manager
        await prompt_manager.initialize()

        await setup_token_expiry_migration()
        await setup_hnsw_index()
        await optimize_vector_search()

        # Warmup sekuensial — bukan fire-and-forget
        # Startup memang sedikit lebih lama, tapi request pertama tidak cold-start
        await _unload_deprecated_models()
        await _warmup_and_pin_models()

        # Warmup BGE Reranker Model
        logger.info("⏳ [WARMUP] Memulai pinning BAAI/bge-reranker-v2-m3 ke memori...")
        await asyncio.get_event_loop().run_in_executor(None, _load_reranker)

        # Warmup F5-TTS Model ke GPU (background thread, non-blocking)
        logger.info("⏳ [WARMUP] Memulai preload F5-TTS Indo model ke GPU...")
        from backend.app.api.endpoints.voice import get_f5_tts
        ema_model, vocoder = await asyncio.get_event_loop().run_in_executor(None, get_f5_tts)
        if ema_model is not None:
            logger.info("✅ [WARMUP] F5-TTS model & vocoder siap di GPU.")
        else:
            logger.warning("⚠️ [WARMUP] F5-TTS model gagal preload (akan lazy-load saat request pertama).")

        await start_background_scheduler(app)

    except Exception as e:
        logger.error(f"❌ [CRITICAL] Gagal booting: {e}")
        raise e

    yield  # ──── STARTUP selesai | SHUTDOWN di bawah ────

    logger.info("\n" + "═"*60)
    logger.info("🛑 [LIFESPAN] Memulai proses shutdown sistem CAKRA AI...")
    logger.info("═"*60)

    app.state.shutdown_requested = True
    await stop_background_scheduler()
    await close_db_pool()
    
    # Close shared LLM client connections
    try:
        from backend.app.core.llm_client import _shared_client
        if _shared_client:
            await _shared_client.aclose()
            logger.info("🔌 [LLM CLIENT] Persistent HTTP connection pool closed.")
    except Exception as e:
        logger.warning(f"⚠️ Failed to close LLM client: {e}")

    logger.info("[DB_POOL] All database connection pools closed.")


from fastapi import FastAPI, Depends
from backend.app.utils.security_firewall import security_firewall_dependency

app = FastAPI(
    title=settings.APP_NAME if hasattr(settings, "APP_NAME") else "Intelligent Agentic RAG System",
    description="Intelligent Agentic RAG System - PT Pindad",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(security_firewall_dependency)]
)

# Request ID logging
app.add_middleware(RequestIDLoggingMiddleware)

# GPU semaphore — 4 slots: Concurrent Processing via Singleton
from backend.app.core.llm_client import get_gpu_semaphore
app.state.gpu_limit = get_gpu_semaphore(4)
logger.info("🔒 [HARDWARE] GPU Concurrency Semaphore: 4 slots (Concurrent Processing via Singleton).")

# ==============================================================================
# SECURE STATIC FILES ROUTES (Replaces app.mount to enforce security firewall)
# ==============================================================================
from fastapi.responses import FileResponse
from backend.app.api.dependencies.auth import get_current_user_npp
from typing import Optional
from fastapi import Request, HTTPException

@app.get("/db_doc/{file_path:path}", tags=["Static Files"])
async def serve_db_doc(file_path: str, request: Request, current_user_npp: Optional[str] = Depends(get_current_user_npp)):
    if not current_user_npp or current_user_npp == "GUEST":
        # allow if token is in query param for file downloads (already handled by get_current_user_npp if we add it, but currently auth.py doesn't check query param). 
        # Actually, if guest is trying to access db_doc, block it.
        raise HTTPException(status_code=403, detail="Akses ditolak. Guest tidak dapat mengakses dokumen RAG.")
    
    abs_path = os.path.join(DB_DOC_DIR, file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)


@app.get("/uploads/{file_path:path}", tags=["Static Files"])
async def serve_uploads(file_path: str, request: Request):
    abs_path = os.path.join(UPLOAD_DIR, file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)


@app.get("/accounts/{file_path:path}", tags=["Static Files"])
async def serve_accounts(file_path: str, request: Request, current_user_npp: Optional[str] = Depends(get_current_user_npp)):
    abs_path = os.path.join(ACCOUNTS_DIR, file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)


@app.get("/file_peraturan/{file_path:path}", tags=["Static Files"])
async def serve_file_peraturan(file_path: str, request: Request):
    abs_path = os.path.join(FILE_PERATURAN_DIR, file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)
# ==============================================================================

origins = [
    "http://192.168.11.80:5173",
    "http://192.168.11.80:5174",
    "http://192.168.11.80:8000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"🛡️ [SECURITY] CORS origins: {origins}")

app.include_router(api_router, prefix="/api")
logger.info("🔌 [ROUTING] /api router mounted.")


@app.get("/", tags=["Root Route"])
async def root_endpoint():
    return {
        "app_name": settings.APP_NAME,
        "version": "3.0.0",
        "status": "Online",
        "active_models": {
            "agentic_engine": settings.MODEL_PERSONA,
            "vision": settings.MODEL_VISION,
            "embedding": settings.MODEL_EMBEDDING,
        },
        "architecture": "Single-model Gemma4 Agentic — Layer 0/1/2 deprecated",
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 [LAUNCHER] Starting Uvicorn on port 5000...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)