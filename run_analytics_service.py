"""
CAKRA AI - Analytics Service
Runs on port 8002.
Handles: /analytics, /audit-logs, /admin endpoints
"""
import sys
import os

CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = CURRENT_FILE_DIR

for path in [ROOT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter

from backend.app.core.config import settings
from backend.app.core.database import init_db_pool, close_db_pool
from backend.app.core.logging_setup import setup_root_logger
from backend.app.utils.request_logging import RequestIDLoggingMiddleware, setup_request_id_logging
from backend.app.utils.security_firewall import security_firewall_dependency

setup_root_logger()
setup_request_id_logging()
logger = logging.getLogger("CAKRA_ANALYTICS_SERVICE")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("⏳ [ANALYTICS_SERVICE] Starting Analytics Service on port 8002...")
    logger.info("=" * 60)
    try:
        await init_db_pool()
        logger.info("✅ [ANALYTICS_SERVICE] Database pool ready.")
    except Exception as e:
        logger.error(f"❌ [ANALYTICS_SERVICE] Startup failed: {e}")
        raise
    yield
    logger.info("🛑 [ANALYTICS_SERVICE] Shutting down...")
    await close_db_pool()


app = FastAPI(
    title="CAKRA AI - Analytics Service",
    description="Analytics & Monitoring microservice",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(security_firewall_dependency)]
)

app.add_middleware(RequestIDLoggingMiddleware)

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

analytics_service_router = APIRouter()

from backend.app.api.endpoints import analytics, notifications, admin
analytics_service_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
analytics_service_router.include_router(notifications.audit_router, tags=["Audit Logs"])
analytics_service_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

app.include_router(analytics_service_router, prefix="/api")
logger.info("🔌 [ANALYTICS_SERVICE] /api/analytics, /api/admin, /audit-logs routers mounted.")


# ── Secure Static Files ───────────────────────────────────────────────────────
from fastapi import Request, HTTPException
from fastapi.responses import FileResponse
from backend.app.core.paths import DOCUMENTS_DIR, UPLOAD_DIR, ACCOUNTS_DIR, FILE_PERATURAN_DIR
from backend.app.api.dependencies.auth import get_current_user_npp
from typing import Optional

DB_DOC_DIR = os.path.join(CURRENT_FILE_DIR, "db_doc")

@app.get("/db_doc/{file_path:path}", tags=["Static Files"])
async def serve_db_doc(file_path: str, request: Request, current_user_npp: Optional[str] = Depends(get_current_user_npp)):
    if not current_user_npp or current_user_npp == "GUEST":
        raise HTTPException(status_code=403, detail="Akses ditolak.")
    abs_path = os.path.join(DB_DOC_DIR, file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(abs_path)


@app.get("/", tags=["Health"])
async def root():
    return {"service": "analytics", "status": "online", "port": 8002}


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 [ANALYTICS_SERVICE] Starting on port 8002...")
    uvicorn.run("run_analytics_service:app", host="0.0.0.0", port=8002, reload=False)
