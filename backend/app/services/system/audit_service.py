import logging
from typing import Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_AUDIT_SERVICE")

class AuditService:
    @staticmethod
    async def get_audit_logs(
        event_type: Optional[str],
        npp: Optional[str],
        days: int,
        limit: int,
        offset: int
    ) -> Dict[str, Any]:
        """Fetch audit logs (history_login) with filtering and pagination."""
        try:
            async with get_db() as conn:
                where_parts = ["created_at >= NOW() - INTERVAL '1 day' * $1"]
                params = [days]
                param_count = 1
                
                if event_type:
                    param_count += 1
                    where_parts.append(f"action = ${param_count}")
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
                        id, npp, action as event_type, ip_address, 
                        user_agent as device_info, created_at, 'SUCCESS' as status,
                        '' as description
                    FROM history_login
                    WHERE {where_clause}
                    ORDER BY created_at DESC
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
            logger.error(f"Failed to fetch audit logs: {e}")
            raise RuntimeError(f"Database error when fetching audit logs: {e}")

    @staticmethod
    async def get_audit_stats(days: int) -> Dict[str, Any]:
        """Fetch audit statistics for the admin dashboard."""
        try:
            async with get_db() as conn:
                total_logins = await conn.fetchval(
                    "SELECT COUNT(*) FROM history_login WHERE created_at >= NOW() - INTERVAL '1 day' * $1",
                    days,
                )
                
                unique_users = await conn.fetchval(
                    "SELECT COUNT(DISTINCT npp) FROM history_login WHERE created_at >= NOW() - INTERVAL '1 day' * $1",
                    days,
                )
                
                failed_logins = await conn.fetchval(
                    "SELECT COUNT(*) FROM history_login WHERE action = $1 AND created_at >= NOW() - INTERVAL '1 day' * $2",
                    "FAILED",
                    days,
                )
                
                top_users = await conn.fetch(
                    """
                    SELECT npp, COUNT(*) as login_count
                    FROM history_login
                    WHERE created_at >= NOW() - INTERVAL '1 day' * $1
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
                    WHERE created_at >= NOW() - INTERVAL '1 day' * $1
                    GROUP BY ip_address
                    ORDER BY count DESC
                    LIMIT 5
                    """,
                    days,
                )
                
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
            logger.error(f"Failed to fetch audit stats: {e}")
            raise RuntimeError(f"Database error when fetching audit stats: {e}")

audit_service = AuditService()
