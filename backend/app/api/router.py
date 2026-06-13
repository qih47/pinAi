from fastapi import APIRouter
from backend.app.api.endpoints import auth, chat, health, documents  # 🔥 SEKARANG HEALTH SUDAH PUNYA SEKTOR SENDIRI

# Inisialisasi APIRouter utama
api_router = APIRouter()

# Tancapkan semua sub-router ke hub utama /api
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication Sektor"])
api_router.include_router(chat.router, prefix="/chat", tags=["Engine Obrolan Sektor"])
api_router.include_router(health.router, prefix="/health", tags=["System Health Sektor"]) # 🔥 RAPI DI SINI!
api_router.include_router(documents.router, prefix="/documents", tags=["Manajemen Dokumen Sektor"])

print("🔀 [ROUTER] Hub utama api_router sukses memuat sub-router /auth, /chat, /health, dan /documents, bolo!")