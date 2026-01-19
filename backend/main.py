from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import auth_router, chat_router, file_router, search_router
from backend.core.config import settings
from backend.database.connection import init_db
from backend.logging.logger_config import app_logger as logger
import logging

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.11.80:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(file_router, prefix="/api", tags=["files"])
app.include_router(search_router, prefix="/api", tags=["search"])

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")

@app.get("/")
async def root():
    return {"message": "Welcome to Pindad AI Chat API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)