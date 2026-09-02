"""
CAKRA AI - Auth Service
Runs on port 8003.
Handles: /auth endpoints (login, JWT, HRIS integration)
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
logger = logging.getLogger("CAKRA_AUTH_SERVICE")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("⏳ [AUTH_SERVICE] Starting Auth Service on port 8003...")
    logger.info("=" * 60)
    try:
        await init_db_pool()
        logger.info("✅ [AUTH_SERVICE] Database pool ready.")
    except Exception as e:
        logger.error(f"❌ [AUTH_SERVICE] Startup failed: {e}")
        raise
    yield
    logger.info("🛑 [AUTH_SERVICE] Shutting down...")
    await close_db_pool()
    logger.info("✅ [AUTH_SERVICE] Shutdown complete.")


app = FastAPI(
    title="CAKRA AI - Auth Service",
    description="Authentication & Authorization microservice",
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

auth_service_router = APIRouter()
from backend.app.api.endpoints import auth
auth_service_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

app.include_router(auth_service_router, prefix="/api")
logger.info("🔌 [AUTH_SERVICE] /api/auth router mounted.")


@app.get("/", tags=["Health"])
async def root():
    return {"service": "auth", "status": "online", "port": 8003}


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 [AUTH_SERVICE] Starting on port 8003...")
    uvicorn.run("run_auth_service:app", host="0.0.0.0", port=8003, reload=False)
