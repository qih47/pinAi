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
from backend.app.core.paths import DOCUMENTS_DIR, UPLOAD_DIR, ACCOUNTS_DIR
from backend.app.services.background_tasks import start_background_scheduler, stop_background_scheduler
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
      - Gemma4 (MODEL_PERSONA): satu-satunya LLM — handles semua chat intent
      - Embedding (MODEL_EMBEDDING): untuk RAG vector search

    Vision (MiniCPM) tidak dipin di startup — di-load on-demand saat ada attachment.
    """
    import httpx

    models_to_pin = [
        (settings.MODEL_PERSONA, "Gemma4 Agentic Engine"),
        (settings.MODEL_EMBEDDING, "Embedding"),
    ]

    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    for model_name, label in models_to_pin:
        logger.info(f"⏳ [WARMUP] Pinning {label} ({model_name}) ke VRAM...")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": -1,   # permanent — tidak di-evict sampai service restart
                    "options": {"temperature": 0.1, "num_predict": 1},
                }
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ [WARMUP] {label} ({model_name}) pinned successfully.")
                else:
                    logger.warning(f"⚠️ [WARMUP] {label} ({model_name}) warmup returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ [WARMUP] {label} ({model_name}) warmup failed: {e}")

    # Khusus embedding — pakai endpoint /api/embeddings bukan /api/chat
    try:
        embed_url = f"{settings.OLLAMA_BASE_URL}/api/embeddings"
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            resp = await client.post(embed_url, json={
                "model": settings.MODEL_EMBEDDING,
                "prompt": "warmup",
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

# GPU semaphore — 1 slot: Strict Queue untuk antrean GPU
app.state.gpu_limit = asyncio.Semaphore(1)
logger.info("🔒 [HARDWARE] GPU Concurrency Semaphore: 1 slot (Strict Queue).")

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
logger.info(f"🌐 [MOUNT] uploads → {UPLOAD_DIR}")

# ✅ FIX: bug lama StaticFiles(directory=StaticFiles(...).directory) — nested tidak perlu
app.mount("/db_doc", StaticFiles(directory=DB_DOC_DIR), name="db_doc")
logger.info(f"🌐 [MOUNT] db_doc → {DB_DOC_DIR}")

app.mount("/accounts", StaticFiles(directory=ACCOUNTS_DIR), name="accounts")
logger.info(f"🌐 [MOUNT] accounts → {ACCOUNTS_DIR}")

FILE_PERATURAN_DIR = os.path.join(ROOT_DIR, "file_peraturan")
app.mount("/file_peraturan", StaticFiles(directory=FILE_PERATURAN_DIR), name="file_peraturan")
logger.info(f"🌐 [MOUNT] file_peraturan → {FILE_PERATURAN_DIR}")

origins = [
    "http://192.168.11.80:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
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