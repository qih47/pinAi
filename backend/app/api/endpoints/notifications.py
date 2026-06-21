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
from backend.app.services.notification_service import (
    get_notification_broker,
    Notification,
    NotificationType,
)

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
    async with get_db() as conn:
        user_role = await conn.fetchval(
            "SELECT role FROM users WHERE npp = $1",
            current_user_npp,
        )
    
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

audit_router = APIRouter(prefix="/api/admin/audit-logs", tags=["audit-logs"])


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
    async with get_db() as conn:
        user_role = await conn.fetchval(
            "SELECT role FROM users WHERE npp = $1",
            current_user_npp,
        )
    
    if user_role not in ("ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        async with get_db() as conn:
            where_parts = ["login_time >= NOW() - INTERVAL '1 day' * $1"]
            params = [days]
            param_count = 1
            
            if event_type:
                param_count += 1
                where_parts.append(f"event_type = ${param_count}")
                params.append(event_type)
            
            if npp:
                param_count += 1
                where_parts.append(f"npp = ${param_count}")
                params.append(npp)
            
            where_clause = " AND ".join(where_parts)
            
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM history_login WHERE {where_clause}",
                *params,
            )
            
            param_count += 1
            limit_idx = param_count
            params.append(limit)
            
            param_count += 1
            offset_idx = param_count
            params.append(offset)
            
            rows = await conn.fetch(
                f"""
                SELECT 
                    id, npp, event_type, ip_address, 
                    device_info, login_time as created_at, status,
                    description
                FROM history_login
                WHERE {where_clause}
                ORDER BY login_time DESC
                LIMIT ${limit_idx} OFFSET ${offset_idx}
                """,
                *params,
            )
            
            audit_logs = [
                {
                    "id": row["id"],
                    "npp": row["npp"],
                    "event_type": row["event_type"],
                    "ip_address": row["ip_address"],
                    "device_info": row["device_info"],
                    "timestamp": row["created_at"].isoformat() if row["created_at"] else None,
                    "status": row["status"],
                    "description": row["description"],
                }
                for row in rows
            ]
            
            logger.info(f"📋 [AUDIT] Retrieved {len(audit_logs)} logs (total: {total})")
            
            return {
                "items": audit_logs,
                "total": total or 0,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "event_type": event_type,
                    "npp": npp,
                    "days": days,
                },
            }
    
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
    async with get_db() as conn:
        user_role = await conn.fetchval(
            "SELECT role FROM users WHERE npp = $1",
            current_user_npp,
        )
    
    if user_role not in ("ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        async with get_db() as conn:
            total_logins = await conn.fetchval(
                "SELECT COUNT(*) FROM history_login WHERE login_time >= NOW() - INTERVAL '1 day' * $1",
                days,
            )
            
            unique_users = await conn.fetchval(
                "SELECT COUNT(DISTINCT npp) FROM history_login WHERE login_time >= NOW() - INTERVAL '1 day' * $1",
                days,
            )
            
            failed_logins = await conn.fetchval(
                "SELECT COUNT(*) FROM history_login WHERE status = $1 AND login_time >= NOW() - INTERVAL '1 day' * $2",
                "FAILED",
                days,
            )
            
            top_users = await conn.fetch(
                """
                SELECT npp, COUNT(*) as login_count
                FROM history_login
                WHERE login_time >= NOW() - INTERVAL '1 day' * $1
                GROUP BY npp
                ORDER BY login_count DESC
                LIMIT 10
                """,
                days,
            )
            
            top_ips = await conn.fetch(
                """
                SELECT ip_address, COUNT(*) as count
                FROM history_login
                WHERE login_time >= NOW() - INTERVAL '1 day' * $1
                GROUP BY ip_address
                ORDER BY count DESC
                LIMIT 5
                """,
                days,
            )
            
            logger.info(f"📊 [AUDIT STATS] Generated statistics for {days} days")
            
            return {
                "period_days": days,
                "summary": {
                    "total_logins": total_logins or 0,
                    "unique_users": unique_users or 0,
                    "failed_logins": failed_logins or 0,
                    "success_rate": f"{((total_logins - (failed_logins or 0)) / total_logins * 100):.1f}%" if total_logins else "N/A",
                },
                "top_users": [
                    {"npp": row["npp"], "login_count": row["login_count"]}
                    for row in top_users
                ],
                "top_ips": [
                    {"ip_address": row["ip_address"], "count": row["count"]}
                    for row in top_ips
                ],
            }
    
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
    async with get_db() as conn:
        user_role = await conn.fetchval(
            "SELECT role FROM users WHERE npp = $1",
            current_user_npp,
        )
    
    if user_role not in ("ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logger.info(f"📤 [EXPORT] Exporting audit logs (format: {format}, days: {days})")
    
    return {
        "message": "Export functionality coming soon",
        "status": "not_implemented",
    }