"""
CAKRA AI - Chat Service
Runs on port 8001.
Handles: /chat, /documents, /synthetic, /training, /notifications, /corporate, /nextcloud, /voice, /user, /keys, /health
"""
import sys
import os
import asyncio

CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = CURRENT_FILE_DIR

for path in [ROOT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
from fastapi.responses import FileResponse
from typing import Optional

from backend.app.core.config import settings
from backend.app.core.database import init_db_pool, close_db_pool
from backend.app.core.logging_setup import setup_root_logger
from backend.app.services.rag.reranker_service import _load_reranker
from backend.app.core.hardware import check_gpu_status
from backend.app.core.paths import DOCUMENTS_DIR, UPLOAD_DIR, ACCOUNTS_DIR, FILE_PERATURAN_DIR
from backend.app.services.system.background_tasks import start_background_scheduler, stop_background_scheduler
from backend.app.utils.request_logging import RequestIDLoggingMiddleware, setup_request_id_logging
from backend.app.utils.token_expiry import setup_token_expiry_migration
from backend.app.utils.vector_index import setup_hnsw_index, optimize_vector_search
from backend.app.utils.security_firewall import security_firewall_dependency

setup_root_logger()
setup_request_id_logging()
logger = logging.getLogger("CAKRA_CHAT_SERVICE")


async def _warmup_and_pin_models():
    """Warmup dan pin model LLM dan Embedding ke VRAM saat startup."""
    import httpx
    # 1. Pin LLM Models via /api/chat
    llm_models = [
        (settings.MODEL_ROUTER, "Gemma4 Router Engine", 4096),
        (settings.MODEL_PERSONA, "Gemma4 Agentic Engine", 16384),
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
                    "keep_alive": -1,
                    "options": {"temperature": 0.1, "num_predict": 1, "num_ctx": ctx_len},
                }
                resp = await client.post(chat_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ [WARMUP] {label} pinned successfully.")
                else:
                    logger.warning(f"⚠️ [WARMUP] {label} warmup returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ [WARMUP] {label} warmup failed: {e}")

    # 2. Pin Embedding Model via /api/embed
    if getattr(settings, "MODEL_EMBEDDING", None):
        embed_model = settings.MODEL_EMBEDDING
        logger.info(f"⏳ [WARMUP] Pinning Embedding Model ({embed_model}) ke VRAM...")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                embed_url = f"{settings.OLLAMA_BASE_URL}/api/embed"
                payload = {
                    "model": embed_model,
                    "input": "pindad",
                    "keep_alive": -1
                }
                resp = await client.post(embed_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ [WARMUP] Embedding Model ({embed_model}) pinned successfully.")
                else:
                    logger.warning(f"⚠️ [WARMUP] Embedding warmup returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ [WARMUP] Embedding warmup failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("⏳ [CHAT_SERVICE] Starting Chat Service on port 8001...")
    logger.info("=" * 60)

    check_gpu_status()
    try:
        await init_db_pool()
        logger.info("✅ [CHAT_SERVICE] Database pool ready.")

        from backend.app.services.pipeline.prompt_manager import prompt_manager
        await prompt_manager.initialize()

        await setup_token_expiry_migration()
        await setup_hnsw_index()
        await optimize_vector_search()

        # Background Warmup: Model pinning, BGE reranker, dan F5-TTS di-load secara asinkron
        # agar Chat Service langsung membuka port 8001 dalam <1 detik tanpa blocking gateway
        async def background_warmup():
            try:
                await _warmup_and_pin_models()
                logger.info("⏳ [WARMUP] Loading BAAI/bge-reranker...")
                await asyncio.get_event_loop().run_in_executor(None, _load_reranker)
                logger.info("⏳ [WARMUP] Preloading F5-TTS...")
                from backend.app.api.endpoints.voice import get_f5_tts
                ema_model, vocoder = await asyncio.get_event_loop().run_in_executor(None, get_f5_tts)
                if ema_model is not None:
                    logger.info("✅ [WARMUP] F5-TTS ready.")
                else:
                    logger.warning("⚠️ [WARMUP] F5-TTS will lazy-load on first request.")
                logger.info("✅ [WARMUP] All background models pinned and ready.")
            except Exception as e:
                logger.warning(f"⚠️ [WARMUP] Background warmup encountered: {e}")

        asyncio.create_task(background_warmup())

        await start_background_scheduler(app)
        logger.info("✅ [CHAT_SERVICE] All systems nominal. Service ready on port 8001.")
    except Exception as e:
        logger.error(f"❌ [CHAT_SERVICE] Startup failed: {e}")
        raise

    yield

    logger.info("�� [CHAT_SERVICE] Shutting down...")
    app.state.shutdown_requested = True
    await stop_background_scheduler()
    await close_db_pool()
    try:
        from backend.app.core.llm_client import _shared_client
        if _shared_client:
            await _shared_client.aclose()
    except Exception as e:
        logger.warning(f"⚠️ Failed to close LLM client: {e}")
    logger.info("✅ [CHAT_SERVICE] Shutdown complete.")


from backend.app.core.llm_client import get_gpu_semaphore

app = FastAPI(
    title="CAKRA AI - Chat Service",
    description="Core chat & document processing microservice",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(security_firewall_dependency)]
)

app.add_middleware(RequestIDLoggingMiddleware)
app.state.gpu_limit = get_gpu_semaphore(4)

origins = [
    "http://localhost:8000",
    "http://192.168.11.80:8000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://192.168.11.80:5173",
    "http://192.168.11.80:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Secure Static Files ───────────────────────────────────────────────────────
from backend.app.api.dependencies.auth import get_current_user_npp

DB_DOC_DIR = os.path.join(CURRENT_FILE_DIR, "db_doc")

@app.get("/db_doc/{file_path:path}", tags=["Static Files"])
async def serve_db_doc(file_path: str, request: Request, current_user_npp: Optional[str] = Depends(get_current_user_npp)):
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Akses ditolak.")
    abs_path = os.path.join(DB_DOC_DIR, file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)

@app.get("/api/system/models-status", tags=["System"])
async def get_system_models_status():
    from backend.app.services.rag.reranker_service import _load_reranker
    from backend.app.api.endpoints import voice
    
    reranker_loaded = _load_reranker.cache_info().currsize > 0
    f5_loaded = getattr(voice, "_f5_ema_model", None) is not None
    return {
        "status": "success",
        "reranker": {
            "loaded": reranker_loaded,
            "name": "bge-reranker-v2-m3",
            "size": 570 * 1024 * 1024,
            "size_vram": 570 * 1024 * 1024 if reranker_loaded else 0
        },
        "f5_tts": {
            "loaded": f5_loaded,
            "name": "f5-tts-indo",
            "size": 1500 * 1024 * 1024,
            "size_vram": 1500 * 1024 * 1024 if f5_loaded else 0
        }
    }


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

# ── Load Chat routers ─────────────────────────────────────────────────────────
chat_service_router = APIRouter()

from backend.app.api.endpoints import (
    chat, health, documents, notifications, api_keys,
    training, corporate, synthetic, nextcloud, voice, user
)

chat_service_router.include_router(chat.router,           prefix="/chat",          tags=["Chat"])
chat_service_router.include_router(health.router,         prefix="/health",        tags=["Health"])
chat_service_router.include_router(api_keys.router,       prefix="/keys",          tags=["API Keys"])
chat_service_router.include_router(training.router,       prefix="/training",      tags=["Training"])
chat_service_router.include_router(synthetic.router,      prefix="/synthetic",     tags=["Synthetic Training"])
chat_service_router.include_router(corporate.router,      prefix="/corporate",     tags=["Corporate Tools"])
chat_service_router.include_router(documents.router,      prefix="/documents",     tags=["Documents"])
chat_service_router.include_router(notifications.router,  prefix="/notifications", tags=["Notifications"])
chat_service_router.include_router(nextcloud.router,      prefix="/nextcloud",     tags=["Nextcloud"])
chat_service_router.include_router(voice.router,          prefix="/voice",         tags=["Voice"])
chat_service_router.include_router(user.router,           prefix="/user",          tags=["User Profile"])

app.include_router(chat_service_router, prefix="/api")
logger.info("🔌 [CHAT_SERVICE] All chat routers mounted.")


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "chat",
        "status": "online",
        "port": 8001,
        "active_models": {
            "agentic_engine": settings.MODEL_PERSONA,
            "vision": settings.MODEL_VISION,
            "embedding": settings.MODEL_EMBEDDING,
        }
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 [CHAT_SERVICE] Starting on port 8001...")
    uvicorn.run("run_chat_service:app", host="0.0.0.0", port=8001, reload=False)
