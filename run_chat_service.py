#!/home/qisthi/pinAi/rag_env/bin/python
"""
CAKRA AI - Chat Service
Runs on port 8001.
Handles: /chat, /documents, /synthetic, /training, /notifications, /corporate, /nextcloud, /voice, /user, /keys, /health
"""
import sys
import os
import glob
import asyncio

CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = CURRENT_FILE_DIR

# Auto-configure LD_LIBRARY_PATH for NVIDIA CUDA libraries if running directly
_nvidia_dir = os.path.join(ROOT_DIR, "rag_env/lib/python3.10/site-packages/nvidia")
if os.path.isdir(_nvidia_dir):
    _lib_dirs = [d for d in glob.glob(f"{_nvidia_dir}/*/lib") if os.path.isdir(d)]
    _current_ld = os.environ.get("LD_LIBRARY_PATH", "")
    _missing = [d for d in _lib_dirs if d not in _current_ld]
    if _missing:
        os.environ["LD_LIBRARY_PATH"] = ":".join(_missing) + (f":{_current_ld}" if _current_ld else "")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    # Secondary safeguard: preload shared objects
    import ctypes
    for _so in sorted(glob.glob(f"{_nvidia_dir}/*/lib/*.so*")):
        try:
            ctypes.CDLL(_so, mode=ctypes.RTLD_GLOBAL)
        except Exception:
            pass

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

setup_root_logger(service_name="chat_service")
setup_request_id_logging()
logger = logging.getLogger("CAKRA_CHAT_SERVICE")


async def _warmup_and_pin_models():
    """Warmup dan pin model LLM dan Embedding ke VRAM saat startup."""
    import httpx
    is_vllm = getattr(settings, "LLM_ENGINE", "ollama") == "vllm"

    # 1. Warmup Router Model (Ollama)
    router_model = getattr(settings, "MODEL_ROUTER", "gemma4:e4b")
    logger.info(f"⏳ [WARMUP] Pinning Gemma4 Router Engine ({router_model}, ctx=4096) ke Ollama VRAM...")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            ollama_chat_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
            payload = {
                "model": router_model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "keep_alive": -1,
                "options": {"temperature": 0.1, "num_predict": 1, "num_ctx": 4096, "num_batch": 512},
            }
            resp = await client.post(ollama_chat_url, json=payload)
            if resp.status_code == 200:
                logger.info(f"✅ [WARMUP] Router Engine ({router_model}) pinned successfully.")
            else:
                logger.warning(f"⚠️ [WARMUP] Router Engine warmup returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ [WARMUP] Router Engine warmup failed: {e}")

    # 2. Warmup Persona Model (vLLM atau Ollama)
    persona_model = settings.MODEL_PERSONA
    if is_vllm:
        logger.info(f"⏳ [WARMUP] Verifying vLLM Engine readiness for Persona Model ({persona_model})...")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
                vllm_chat_url = f"{settings.VLLM_BASE_URL.rstrip('/')}/chat/completions"
                payload = {
                    "model": persona_model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                    "temperature": 0.1,
                }
                resp = await client.post(vllm_chat_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ [WARMUP] vLLM Engine ({persona_model}) is active & warm.")
                else:
                    logger.warning(f"⚠️ [WARMUP] vLLM warmup returned {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"⚠️ [WARMUP] vLLM warmup encountered: {e}")
    else:
        logger.info(f"⏳ [WARMUP] Pinning Gemma4 Agentic Engine ({persona_model}) ke Ollama VRAM...")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                ollama_chat_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
                payload = {
                    "model": persona_model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"temperature": 0.1, "num_predict": 1, "num_ctx": 16384, "num_batch": 512},
                }
                resp = await client.post(ollama_chat_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ [WARMUP] Persona Engine pinned successfully.")
        except Exception as e:
            logger.warning(f"⚠️ [WARMUP] Persona Engine warmup failed: {e}")

    # 3. Pin Embedding Model via /api/embed
    if getattr(settings, "MODEL_EMBEDDING", None):
        embed_model = settings.MODEL_EMBEDDING
        logger.info(f"⏳ [WARMUP] Pinning Embedding Model ({embed_model}) ke VRAM...")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
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
            err_msg = str(e) or "Operation timed out"
            logger.warning(f"⚠️ [WARMUP] Embedding warmup encountered ({type(e).__name__}): {err_msg}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("⏳ [CHAT_SERVICE] Starting Chat Service on port 8001...")
    logger.info("=" * 60)

    check_gpu_status()
    try:
        await init_db_pool()
        logger.info("✅ [CHAT_SERVICE] Database pool ready.")

        # Import semua modul prompt agar mendaftarkan default template terbaru ke prompt_manager
        import backend.app.services.pipeline.prompts.core_prompts
        import backend.app.services.pipeline.prompts.rag_prompts
        import backend.app.services.pipeline.prompts.coding_prompts
        import backend.app.services.pipeline.prompts.file_prompts
        import backend.app.services.pipeline.prompts.email_prompts
        import backend.app.services.pipeline.prompts.compliance_prompts
        import backend.app.services.pipeline.prompts.redteam_prompts

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
                logger.info("⏳ [WARMUP] Preloading F5-TTS via tts_service...")
                from backend.app.services.voice.tts_service import tts_service
                await tts_service.warmup()
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
    "http://cakra.ai",
    "http://cakra.ai:5173",
    "http://cakra.ai:8000",
    "http://www.cakra.ai",
    "http://www.cakra.ai:5173",
    "http://www.cakra.ai:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|192\.168\.11\.80|cakra\.ai|www\.cakra\.ai)(:\d+)?$",
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
    from backend.app.services.voice.tts_service import tts_service
    
    reranker_loaded = _load_reranker.cache_info().currsize > 0
    f5_loaded = getattr(tts_service, "_ema_model", None) is not None
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
        from pathlib import Path
        parts = Path(file_path).parts
        # Fallback untuk collab uploads yang tersimpan di Room Brain SSOT
        if len(parts) >= 3 and parts[0] == "collab":
            room_id = parts[1]
            filename = parts[2]
            for match in Path(ACCOUNTS_DIR).glob(f"*/collab/{room_id}/brain/images/{filename}"):
                if match.exists():
                    return FileResponse(str(match))
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)

@app.get("/accounts/{file_path:path}", tags=["Static Files"])
async def serve_accounts(file_path: str, request: Request, current_user_npp: Optional[str] = Depends(get_current_user_npp)):
    abs_path = os.path.join(ACCOUNTS_DIR, file_path)
    if not os.path.exists(abs_path):
        from pathlib import Path
        parts = Path(file_path).parts
        # Kasus 1: Request lama tanpa "brain" (accounts/npp/session/images/... -> accounts/npp/session/brain/images/...)
        if len(parts) >= 3 and parts[2] != "brain":
            alt_parts = list(parts[:2]) + ["brain"] + list(parts[2:])
            alt_path = os.path.join(ACCOUNTS_DIR, *alt_parts)
            if os.path.exists(alt_path):
                return FileResponse(alt_path)
        # Kasus 2: Request baru dengan "brain" tapi file fisik masih di lokasi lama (accounts/npp/session/brain/images/... -> accounts/npp/session/images/...)
        elif len(parts) >= 4 and parts[2] == "brain":
            alt_parts = list(parts[:2]) + list(parts[3:])
            alt_path = os.path.join(ACCOUNTS_DIR, *alt_parts)
            if os.path.exists(alt_path):
                return FileResponse(alt_path)
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)

@app.get("/file_peraturan/{file_path:path}", tags=["Static Files"])
@app.head("/file_peraturan/{file_path:path}", tags=["Static Files"])
async def serve_file_peraturan(file_path: str, request: Request):
    # 1. Direct match di FILE_PERATURAN_DIR
    abs_path = os.path.join(FILE_PERATURAN_DIR, file_path)
    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        return FileResponse(abs_path)

    # 2. Cek candidate dirs via find_valid_pdf_file
    from backend.app.services.tools.document_resolver import find_valid_pdf_file
    alt_file = find_valid_pdf_file(file_path)
    if alt_file and os.path.exists(alt_file) and os.path.isfile(alt_file):
        return FileResponse(alt_file)

    # 3. Dynamic lookup ke DB untuk placeholder/alias (misal SKEP_18_P_BD_I_2018.pdf -> 5da9dbaca28ea42d1cd66c0aa9abd4b8.pdf)
    try:
        clean_name = os.path.basename(file_path)
        from backend.app.core.database import get_db, get_peraturan_db

        # A. Cek di PG dokumen: cari row dengan filename ini, lalu cari row lain dengan nomor yang sama (case-insensitive) yang punya file fisik
        async with get_db() as pg_conn:
            doc_row = await pg_conn.fetchrow(
                "SELECT id, nomor, filename FROM dokumen WHERE filename = $1 LIMIT 1",
                clean_name
            )
            if doc_row and doc_row["nomor"]:
                nomor = doc_row["nomor"]
                alt_rows = await pg_conn.fetch(
                    "SELECT filename FROM dokumen WHERE nomor ILIKE $1 AND filename != $2 AND filename IS NOT NULL",
                    nomor, clean_name
                )
                for ar in alt_rows:
                    cand = find_valid_pdf_file(ar["filename"])
                    if cand and os.path.exists(cand) and os.path.isfile(cand):
                        return FileResponse(cand)

        # B. Cek di MySQL berita: cari berdasarkan gambar/gambar2/gambar3, ambil noper
        async with get_peraturan_db() as my_conn:
            async with my_conn.cursor() as cur:
                await cur.execute(
                    "SELECT noper, judul FROM berita WHERE gambar = %s OR gambar2 = %s OR gambar3 = %s LIMIT 1",
                    (clean_name, clean_name, clean_name)
                )
                b_row = await cur.fetchone()
                if b_row and b_row[0]:
                    noper = b_row[0].strip()
                    async with get_db() as pg_conn:
                        alt_rows = await pg_conn.fetch(
                            "SELECT filename FROM dokumen WHERE nomor ILIKE $1 AND filename IS NOT NULL",
                            f"%{noper}%"
                        )
                        for ar in alt_rows:
                            cand = find_valid_pdf_file(ar["filename"])
                            if cand and os.path.exists(cand) and os.path.isfile(cand):
                                return FileResponse(cand)

        # C. Pattern match dari nama file: misal SKEP_18_P_BD_I_2018.pdf -> %18%BD%I%2018%
        name_no_ext = os.path.splitext(clean_name)[0]
        parts = [p for p in name_no_ext.replace("-", "_").split("_") if p]
        if len(parts) >= 3:
            pattern = "%" + "%".join(parts[1:]) + "%"
            async with get_db() as pg_conn:
                alt_rows = await pg_conn.fetch(
                    "SELECT filename FROM dokumen WHERE nomor ILIKE $1 AND filename IS NOT NULL LIMIT 5",
                    pattern
                )
                for ar in alt_rows:
                    cand = find_valid_pdf_file(ar["filename"])
                    if cand and os.path.exists(cand) and os.path.isfile(cand):
                        return FileResponse(cand)
    except Exception as e:
        logger.warning(f"⚠️ [SERVE_FILE_PERATURAN] Error resolving alias {file_path}: {e}")

    raise HTTPException(status_code=404, detail="File tidak ditemukan")

DOC_PAGES_DIR = "/home/qisthi/pinAi/backend/storage/doc_pages"
os.makedirs(DOC_PAGES_DIR, exist_ok=True)

@app.get("/doc_pages/{file_path:path}", tags=["Static Files"])
async def serve_doc_pages(file_path: str):
    abs_path = os.path.join(DOC_PAGES_DIR, file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(abs_path)

# ── Load Chat routers ─────────────────────────────────────────────────────────
chat_service_router = APIRouter()

from backend.app.api.endpoints import (
    chat, health, documents, notifications, api_keys,
    training, corporate, synthetic, nextcloud, voice, user, collab, document_writer
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
chat_service_router.include_router(collab.router,         prefix="/collab",        tags=["Collab Space"])
chat_service_router.include_router(document_writer.router, tags=["Document Writer"])

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
            "router_engine": getattr(settings, "MODEL_ROUTER", "gemma4:e4b"),
            "embedding": getattr(settings, "MODEL_EMBEDDING", "mxbai-embed-large:latest"),
        }
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 [CHAT_SERVICE] Starting on port 8001...")
    uvicorn.run("run_chat_service:app", host="0.0.0.0", port=8001, reload=False)
