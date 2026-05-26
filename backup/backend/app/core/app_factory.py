import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import register_routers
from app.core.config import settings
from app.core.database import init_db

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="CAKRA AI API",
        description="AI Assistant for PT Pindad",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.gpu_limit = asyncio.Semaphore(2)

    if not os.path.exists("db_doc"):
        os.makedirs("db_doc")
    app.mount("/db_doc", StaticFiles(directory="db_doc"), name="db_doc")

    origins = getattr(settings, "cors_origins", ["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routers(app)

    @app.on_event("startup")
    async def startup_event():
        try:
            await init_db()
            logger.info("CAKRA AI database pool initialized.")
        except Exception as e:
            logger.error("Failed to initialize DB on startup: %s", e)

    @app.get("/")
    async def root():
        return {"message": "CAKRA AI API", "status": "running"}

    return app
