from fastapi import FastAPI

from app.api.endpoints import auth, chat, documents, health, learning, scrapers


def register_routers(app: FastAPI) -> None:
    app.include_router(auth.router, prefix="/api", tags=["Authentication"])
    app.include_router(chat.router, prefix="/api", tags=["Chat"])
    app.include_router(documents.router, prefix="/api", tags=["Documents"])
    app.include_router(learning.router, prefix="/api", tags=["Learning & OCR"])
    app.include_router(scrapers.router, prefix="/api", tags=["Web Scraping"])
    app.include_router(health.router, tags=["Health"])
