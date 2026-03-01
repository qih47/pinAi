from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .database.connection import db_manager
from .logging.setup import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting CAKRA AI Pro Application...")
    try:
        await db_manager.init_rag_pool()
        await db_manager.init_login_pool()
        logger.info("✅ Database connections established")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down CAKRA AI Pro Application...")
    await db_manager.close_pools()
    logger.info("✅ Database connections closed")


app = FastAPI(
    title="CAKRA AI Pro API",
    description="Advanced AI-powered chat system with RAG capabilities for PT Pindad",
    version="1.0.0",
    lifespan=lifespan
)


# Include routers
app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    return {"message": "CAKRA AI Pro API - Advanced RAG System for PT Pindad"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        import aiohttp
        import asyncio
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "qwen3:8b",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                ollama_status = resp.status == 200

        return {
            "status": "healthy",
            "service": "CAKRA AI Pro",
            "model": "qwen3:8b",
            "ollama_connected": ollama_status,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )