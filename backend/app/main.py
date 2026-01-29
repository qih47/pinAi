import logging
import os
import asyncio # Tambahkan ini untuk Semaphore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings

# 1. Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CAKRA AI API",
    description="AI Assistant for PT Pindad",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- GLOBAL SEMAPHORE ---
app.state.gpu_limit = asyncio.Semaphore(2)
# -------------------------

if not os.path.exists("db_doc"):
    os.makedirs("db_doc")

app.mount("/db_doc", StaticFiles(directory="db_doc"), name="db_doc")

# 2. CORS Setup
origins = getattr(
    settings,
    "cors_origins",
    [
        "http://192.168.11.80:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Import & Include Routers
from .routers import auth, chat, documents, health, scrapers

app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(scrapers.router, prefix="/api", tags=["Web Scraping"])
app.include_router(health.router, tags=["Health"])

# 4. Lifecycle Management
@app.on_event("startup")
async def startup_event():
    from .database import init_db
    try:
        await init_db()
        logger.info("🚀 CAKRA AI database pool initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize DB on startup: {e}")

    # Set parallel settings untuk Ollama via Environment jika memungkinkan
    # atau informasikan spek load di log
    print(f"\n" + "=" * 50)
    print(f"🤖 Primary Model: {settings.primary_model}")
    print(f"⚡ GPU Concurrency Limit: 1 Requests")
    print(f"🌐 API running on: http://192.168.11.80:5000")
    print(f"=" * 50 + "\n")

@app.get("/")
async def root():
    return {"message": "CAKRA AI API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=5000, reload=True, log_level="info"
    )