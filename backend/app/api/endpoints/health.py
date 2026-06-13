import time
import logging
from fastapi import APIRouter, status
# Import database context managers
from backend.app.core.database import get_db, get_hris_db

router = APIRouter()
logger = logging.getLogger("CAKRA_HEALTH")

@router.get("", summary="自由 Cek Kesehatan Aliansi Sistem CAKRA AI")
async def health_check():
    """
    Endpoint monitoring taktis untuk memeriksa vitalitas backend FastAPI 
    serta status koneksi dual-pool database secara independen.
    """
    start_time = time.time()
    
    status_db_rag = "DOWN"
    status_db_hris = "DOWN"
    system_healthy = True

    # 1. Tes Vitalitas RAGDB (Lokal PostgreSQL via get_db)
    try:
        async with get_db() as conn:
            await conn.execute("SELECT 1;")
            status_db_rag = "UP"
    except Exception as e:
        logger.error(f"[HEALTH_CHECK_RAGDB_ERROR] Pool 'ragdb' error: {str(e)}")
        system_healthy = False

    # 2. Tes Vitalitas HRIS DB (Remote DB Pegawai via get_hris_db)
    try:
        async with get_hris_db() as conn:
            await conn.execute("SELECT 1;")
            status_db_hris = "UP"
    except Exception as e:
        logger.error(f"[HEALTH_CHECK_HRISDB_ERROR] Pool 'hris' remote unreachable: {str(e)}")
        # HRIS down tidak bikin system_healthy = False total agar Chat Sektor & Guest Mode tetap hidup
        status_db_hris = "DEGRADED (Remote DB Unreachable)"

    # Hitung Latensi Komputasi Total
    latency_ms = (time.time() - start_time) * 1000

    logger.info(f"[HEALTH_CHECK_COMPLETE] Completed in {latency_ms:.2f}ms | RAGDB: {status_db_rag} | HRIS: {status_db_hris}")

    return {
        "status": "Healthy" if system_healthy else "Unhealthy / Degraded",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "latency_ms": f"{latency_ms:.2f}ms",
        "dependencies": {
            "rag_vector_database": status_db_rag,
            "hris_remote_database": status_db_hris
        }
    }