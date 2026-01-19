from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio
from backend.database.connection import db_manager
from backend.routers import auth, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events"""
    # Startup
    print("🚀 Starting CAKRA AI Pro with FastAPI...")
    await db_manager.create_pools()
    print("✅ Database connections established")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    await db_manager.close_pools()
    print("✅ Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="CAKRA AI Pro API",
    description="AI-powered chat system for PT Pindad with RAG capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.11.80:5173", "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {"message": "CAKRA AI Pro API is running!"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # In a real implementation, you'd check actual services here
        return {
            "status": "healthy",
            "service": "CAKRA AI Pro",
            "version": "1.0.0"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    
    print(f"🚀 CAKRA AI Pro starting with FastAPI...")
    print(f"🌐 API running on http://0.0.0.0:8000")
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )