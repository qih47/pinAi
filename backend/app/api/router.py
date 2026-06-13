from fastapi import APIRouter
import logging
from backend.app.api.endpoints import auth, chat, health, documents, admin, notifications

logger = logging.getLogger("CAKRA_ROUTER")

# Main API router
api_router = APIRouter()

# Register all sub-routers under /api prefix
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(notifications.audit_router, tags=["Audit Logs"])

logger.info("[ROUTER_INIT] Main api_router loaded: /auth, /chat, /health, /documents, /admin, /notifications, /audit-logs")