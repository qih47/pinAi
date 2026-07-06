import logging
from typing import List, Dict, Any, Optional
from backend.app.core import database

logger = logging.getLogger("CAKRA_SECURITY")

async def log_security_event(
    event_type: str, 
    npp: Optional[str] = "UNKNOWN", 
    ip_address: Optional[str] = "UNKNOWN", 
    description: str = "", 
    severity: str = "MEDIUM"
) -> bool:
    """
    Log an anomaly to the security_logs table.
    Designed to not block the main execution flow if it fails.
    """
    if database.db_pool is None:
        logger.warning(f"[SOC] Event missed (DB not ready): {event_type} - {description}")
        return False

    try:
        async with database.db_pool.acquire() as conn:
            query = """
                INSERT INTO security_logs (event_type, npp, ip_address, description, severity)
                VALUES ($1, $2, $3, $4, $5)
            """
            await conn.execute(query, event_type, str(npp), str(ip_address), description, severity)
            logger.info(f"[SOC] Logged {severity} severity event: {event_type} from {npp} ({ip_address})")
            return True
    except Exception as e:
        logger.error(f"[SOC_ERROR] Failed to save security log: {e}")
        return False


async def get_recent_security_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch recent security anomalies for the Analytics Dashboard SOC.
    """
    if database.db_pool is None:
        return []

    try:
        async with database.db_pool.acquire() as conn:
            query = """
                SELECT id, timestamp, event_type, npp, ip_address, description, severity
                FROM security_logs
                ORDER BY timestamp DESC
                LIMIT $1
            """
            rows = await conn.fetch(query, limit)
            
            logs = []
            for r in rows:
                logs.append({
                    "id": str(r["id"]),
                    "timestamp": r["timestamp"].isoformat(),
                    "event_type": r["event_type"],
                    "npp": r["npp"],
                    "ip_address": r["ip_address"],
                    "description": r["description"],
                    "severity": r["severity"]
                })
            return logs
    except Exception as e:
        logger.error(f"[SOC_ERROR] Failed to fetch security logs: {e}")
        return []
