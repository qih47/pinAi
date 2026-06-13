from fastapi import APIRouter
import logging
from backend.app.api.endpoints import auth, chat, health, documents, admin, notifications  # 🔥 Added notifications

logger = logging.getLogger("CAKRA_ROUTER")

# Inisialisasi APIRouter utama
api_router = APIRouter()

# Tancapkan semua sub-router ke hub utama /api
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication Sektor"])
api_router.include_router(chat.router, prefix="/chat", tags=["Engine Obrolan Sektor"])
api_router.include_router(health.router, prefix="/health", tags=["System Health Sektor"]) # 🔥 RAPI DI SINI!
api_router.include_router(documents.router, prefix="/documents", tags=["Manajemen Dokumen Sektor"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])  # 🔥 Admin endpoints
api_router.include_router(notifications.router, prefix="/notifications", tags=["Real-time Notifications"])  # 🔥 B15
api_router.include_router(notifications.audit_router, tags=["Audit Logs"])  # 🔥 B16

logger.info("🔀 [ROUTER] Hub utama api_router sukses memuat sub-router /auth, /chat, /health, /documents, /admin, /notifications, dan /audit-logs, bolo!")