import sys
import os

# ==============================================================================
# 🔥 [SUPER-HOTFIX] DOUBLE-PATH RESOLUTION FOR SYSTEMD DEAMON
# ==============================================================================
# Menarik path absolut dari direktori proyek utama (/home/qisthi/pinAi)
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))  # backend/app
BACKEND_DIR = os.path.dirname(CURRENT_FILE_DIR)                # backend
ROOT_DIR = os.path.dirname(BACKEND_DIR)                        # pinAi

# Daftarin kedua folder ke dalam system path Python agar import tidak bingung
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

# Import komponen core dengan jalur modul yang sudah tervalidasi aman
from backend.app.core.config import settings
from backend.app.core.database import init_db_pool, close_db_pool
from backend.app.core.logging_setup import setup_root_logger
from backend.app.api.router import api_router
from backend.app.core.llm_client import warm_up_model
from backend.app.core.hardware import check_gpu_status
from backend.app.core.paths import DOCUMENTS_DIR, UPLOAD_DIR
from backend.app.services.background_tasks import start_background_scheduler, stop_background_scheduler

# 1. Mengaktifkan konfigurasi log seragam kita
setup_root_logger()
logger = logging.getLogger("CAKRA_MAIN")

DB_DOC_DIR = os.path.join(ROOT_DIR, "db_doc")

# Pembuatan folder dilakukan langsung di level compile/load time sebelum dimount
if not os.path.exists(DB_DOC_DIR):
    os.makedirs(DB_DOC_DIR)
    logger.info(f"📁 [STORAGE] Folder statis absolut '{DB_DOC_DIR}' berhasil dibuat otomatis, bolo!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manajemen siklus hidup aplikasi (Pengganti on_event modern)"""
    logger.info("\n" + "═"*60)
    logger.info("⏳ [LIFESPAN] Memulai proses bootstrap sistem CAKRA AI...")
    logger.info("═"*60)
    # Cek Hardware
    check_gpu_status()
    # Pastikan Path Aman
    logger.info(f"📂 [PATHS] Dokumen beroperasi di: {DOCUMENTS_DIR}")
    # Kunci 1: Inisialisasi pool database ganda (ragdb & hris)
    try:
        await init_db_pool()
        logger.info("⚡ [BOOTSTRAP] Koneksi dual-pool database aman terkendali, bolo!")
        
        # 🔥 New Sequential Pipeline Warmup Strategy:
        # - Layer 3 (Gemma4 Persona) ALWAYS LOADED: Must be ready for instant response
        # - Layer 1 (Qwen2.5 Router): ON-DEMAND lazy load in Layer 1 (saves VRAM)
        # - Layer 2 (DeepSeek-R1): ON-DEMAND lazy load only when need_rag=true
        # This reduces VRAM footprint and allows more concurrent requests
        
        # Ganti bagian warmup di lifespan:
        asyncio.create_task(warm_up_model(settings.MODEL_PERSONA, "Warmup Gemma4 [Layer 2 Executor]"))
        asyncio.create_task(warm_up_model(settings.MODEL_ROUTER, "Warmup Qwen3B [Layer 1 Analyzer]"))
        asyncio.create_task(warm_up_model(settings.MODEL_GATEWAY, "Warmup Qwen Gateway [Layer 0]"))
        
        # 🔥 Kunci 2: Inisialisasi Background Task Scheduler (Memory Consolidation dll)
        await start_background_scheduler(app)
        
    except Exception as e:
        logger.error(f"❌ [CRITICAL] Gagal booting database pool: {e}")
        raise e
        
    yield  # ──────────────── ATAS: STARTUP | BAWAH: SHUTDOWN ────────────────
    
    logger.info("\n" + "═"*60)
    logger.info("🛑 [LIFESPAN] Memulai proses shutdown sistem CAKRA AI...")
    logger.info("═"*60)
    await stop_background_scheduler()  # Hentikan scheduler sebelum close DB
    await close_db_pool()
    logger.info("✨ [SHUTDOWN] Semua resource pool dibersihkan dengan aman, bolo!")


# 2. Inisialisasi FastAPI Instance
app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Agentic RAG System (Three-Engine Architecture) - PT Pindad",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 3. GLOBAL CONCURRENCY SEMAPHORE (Mengamankan VRAM GPU dari limitasi hardware)
app.state.gpu_limit = asyncio.Semaphore(2)
logger.info("🔒 [HARDWARE] GPU Concurrency Semaphore dikunci pada limit maks: 2 Antrean.")

# 🔥 FIX STORAGE 2: Menggunakan path absolut UPLOAD_DIR yang tervalidasi aman dari systemd daemon
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
logger.info(f"🌐 [MOUNT] Direktori absolut '{UPLOAD_DIR}' resmi dibuka untuk serving lampiran user (MiniCPM-V Ready).")

# 4. Mount Folder Statis Dokumen menggunakan PATH ABSOLUT agar tidak terjebak WorkingDirectory
app.mount("/db_doc", StaticFiles(directory=DB_DOC_DIR), name="db_doc")
logger.info(f"🌐 [MOUNT] Direktori absolut '{DB_DOC_DIR}' resmi dibuka untuk serving dokumen statis.")

# 5. Konfigurasi CORS (Menggunakan IP server lokal lo 192.168.11.80)
origins = [
    "http://192.168.11.80:5173",  # IP MobaXterm/Server lo
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
logger.info(f"🛡️  [SECURITY] CORS dikonfigurasi aman untuk origin Frontend: {origins}")

# 6. Menghubungkan Hub Router API Utama kita
app.include_router(api_router, prefix="/api")
logger.info("🔌 [ROUTING] Jalur lintas /api berhasil ditancapkan ke hub router.")


@app.get("/", tags=["Root Route"])
async def root_endpoint():
    """Endpoint dasar check status via browser"""
    logger.info("🎯 [ROOT] Ada yang ngintip root API lewat browser/client!")
    return {
        "app_name": settings.APP_NAME,
        "version": "2.0.0",
        "status": "Online, Bolo!",
        # Ganti root endpoint roster:
        "roster": {
            "layer_0_gateway": settings.MODEL_GATEWAY,
            "layer_1_analyzer": settings.MODEL_ROUTER,
            "layer_2_executor": settings.MODEL_PERSONA,
            "embedding": settings.MODEL_EMBEDDING
        }
    }


# Perintah buat running via terminal jika file dieksekusi langsung
if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 [LAUNCHER] Memulai server Uvicorn di port 5000...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)