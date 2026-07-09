"""
CAKRA AI — Real-time Notifications & Audit Logs
===============================================
B15: Notifications endpoint (SSE stream)
B16: Audit log admin dashboard
"""

import logging
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import StreamingResponse

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.database import get_db
from backend.app.services.notifications.notification_service import (
    get_notification_broker,
    Notification,
    NotificationType,
)
from backend.app.services.auth.auth_service import auth_service
from backend.app.services.system.audit_service import audit_service

logger = logging.getLogger("CAKRA_NOTIFICATIONS_API")

router = APIRouter(prefix="", tags=["notifications"])

# ══════════════════════════════════════════════════════════════════════════════
# B15 — GET /api/notifications/subscribe — SSE Real-time Notifications
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/subscribe")
async def subscribe_notifications(
    request: Request,
    npp: Optional[str] = Query(None, description="Fallback NPP dari query string URL"),
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Subscribe to real-time SSE notifications untuk user (Safe Fallback + Fast Reload Support).
    """
    auth_str = str(current_user_npp).strip() if current_user_npp is not None else ""
    query_str = str(npp).strip() if npp is not None else ""

    if auth_str and auth_str != "None" and auth_str != "GUEST":
        resolved_npp = auth_str
    elif query_str and query_str != "None" and query_str != "GUEST":
        resolved_npp = query_str
    else:
        resolved_npp = "NPP_UNKNOWN"

    if resolved_npp == "NPP_UNKNOWN":
        raise HTTPException(
            status_code=403, detail="Akses ditolak: Identitas pegawai tidak terautentikasi"
        )

    async def notification_generator():
        broker = get_notification_broker()
        queue = await broker.subscribe(resolved_npp)
        
        logger.info(f"📡 [SUBSCRIBE] NPP {resolved_npp} connected to notifications")
        
        try:
            yield 'data: {"id": 0, "event_type": "DEFAULT", "title": "Connected", "message": "Sukses terhubung ke broker"}\n\n'
            
            while True:
                if getattr(request.app.state, "shutdown_requested", False):
                    logger.info(
                        f"📡 [LIFESPAN_SHUTDOWN] Memutus antrean SSE NPP {resolved_npp} untuk reload kilat."
                    )
                    break

                try:
                    notification_json = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {notification_json}\n\n"
                except asyncio.TimeoutError:
                    continue
                
        except asyncio.CancelledError:
            logger.info(f"📡 [UNSUBSCRIBE] NPP {resolved_npp} disconnected from notifications (Cancelled)")
            raise
        except Exception as e:
            logger.error(f"❌ [SUBSCRIBE] Error: {e}")
            raise
        finally:
            await broker.unsubscribe(resolved_npp, queue)
    
    return StreamingResponse(
        notification_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/stats")
async def get_notification_stats(
    current_user_npp: str = Depends(get_current_user_npp),
):
    """
    Get notification broker statistics (admin only).
    """
    user_role = await auth_service.get_user_role(current_user_npp)
    
    if user_role not in ("ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    broker = get_notification_broker()
    stats = await broker.get_stats()
    
    logger.info(f"📊 [STATS] Retrieved notification broker stats")
    
    return {
        "status": "ok",
        "broker_stats": stats,
        "timestamp": datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# B16 — Audit Log Endpoints — Admin Dashboard
# ══════════════════════════════════════════════════════════════════════════════

audit_router = APIRouter(prefix="/admin/audit-logs", tags=["audit-logs"])


@audit_router.get("")
async def get_audit_logs(
    current_user_npp: str = Depends(get_current_user_npp),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    npp: Optional[str] = Query(None, description="Filter by employee NPP"),
    days: int = Query(7, ge=1, le=90, description="Last N days"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Get audit logs dengan filtering dan pagination.
    """
    user_role = await auth_service.get_user_role(current_user_npp)
    
    # if user_role not in ("ADMIN", "SUPERADMIN", "TRAINER"):
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = await audit_service.get_audit_logs(event_type, npp, days, limit, offset)
        logger.info(f"📋 [AUDIT] Retrieved logs (total: {result['total']})")
        return result
    except Exception as e:
        logger.error(f"❌ [AUDIT] Error fetching logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@audit_router.get("/stats")
async def get_audit_stats(
    current_user_npp: str = Depends(get_current_user_npp),
    days: int = Query(7, ge=1, le=90),
):
    """
    Get audit statistics dashboard untuk admin.
    """
    user_role = await auth_service.get_user_role(current_user_npp)
    
    # if user_role not in ("ADMIN", "SUPERADMIN", "TRAINER"):
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = await audit_service.get_audit_stats(days)
        logger.info(f"📊 [AUDIT STATS] Generated statistics for {days} days")
        return result
    except Exception as e:
        logger.error(f"❌ [AUDIT STATS] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@audit_router.post("/export")
async def export_audit_logs(
    current_user_npp: str = Depends(get_current_user_npp),
    event_type: Optional[str] = Query(None),
    npp: Optional[str] = Query(None),
    days: int = Query(7),
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """
    Export audit logs dalam format JSON atau CSV untuk compliance.
    """
    user_role = await auth_service.get_user_role(current_user_npp)
    
    # if user_role not in ("ADMIN", "SUPERADMIN", "TRAINER"):
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    logger.info(f"📤 [EXPORT] Exporting audit logs (format: {format}, days: {days})")
    
    return {
        "message": "Export functionality coming soon",
        "status": "not_implemented",
    }