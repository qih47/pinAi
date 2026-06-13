"""
CAKRA AI — Admin Dashboard Endpoints
====================================
Endpoints untuk administratior: memory consolidation trigger, audit logs, system config, dll.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.background_tasks import trigger_manual_memory_consolidation

router = APIRouter()
logger = logging.getLogger("CAKRA_ADMIN")


@router.post("/run-memory-consolidation")
async def manual_memory_consolidation_trigger(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Manual trigger untuk konsolidasi memori pegawai (Nightly Job).
    Hanya bisa diakses oleh admin yang sudah login.
    
    Usage: POST /api/admin/run-memory-consolidation
    """
    if not current_user_npp:
        logger.warning("⚠️ [ADMIN] Akses admin memory consolidation tanpa login ditolak")
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    logger.info(f"🔧 [ADMIN] User {current_user_npp} memicu manual memory consolidation...")
    
    try:
        result = await trigger_manual_memory_consolidation()
        logger.info(f"✅ [ADMIN] Manual consolidation selesai: {result}")
        return {
            "status": "success",
            "message": "Konsolidasi memori berhasil dijalankan secara manual",
            "details": result
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Manual consolidation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Manual consolidation failed: {str(e)}"
        )


@router.get("/system-status")
async def get_system_status(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Endpoint untuk melihat status sistem CAKRA AI (GPU, memory, scheduler jobs, dll).
    Hanya bisa diakses oleh admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        import torch
        from backend.app.services.background_tasks import scheduler
        
        gpu_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else "N/A"
        vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3 if gpu_available else 0.0
        
        scheduler_status = "RUNNING" if (scheduler and scheduler.running) else "STOPPED"
        
        logger.info(f"📊 [ADMIN] {current_user_npp} mengakses system status")
        
        return {
            "status": "success",
            "system": {
                "gpu": {
                    "available": gpu_available,
                    "name": gpu_name,
                    "vram_gb": f"{vram_total:.2f}" if vram_total > 0 else "0.00"
                },
                "scheduler": {
                    "status": scheduler_status,
                    "jobs": [
                        {
                            "id": job.id,
                            "name": job.name,
                            "next_run": str(job.next_run_time) if job.next_run_time else "N/A"
                        }
                        for job in (scheduler.get_jobs() if scheduler and scheduler.running else [])
                    ]
                }
            }
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] System status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")


@router.get("/cache-stats")
async def get_embedding_cache_stats(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Get embedding cache statistics (W13).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.embedding_cache import get_embedding_cache
        cache = get_embedding_cache()
        return {
            "status": "success",
            "stats": cache.stats()
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Cache stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.post("/clear-embedding-cache")
async def clear_embedding_cache_endpoint(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Clear all embedding cache entries (W13).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.embedding_cache import get_embedding_cache
        cache = get_embedding_cache()
        cache.clear()
        logger.info(f"🧹 [ADMIN] Embedding cache cleared by user {current_user_npp}")
        return {
            "status": "success",
            "message": "Embedding cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Clear cache error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/vector-index-status")
async def get_vector_index_status_endpoint(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Get HNSW index status and DB size information (W15).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.vector_index import get_index_info
        from backend.app.core.database import get_db_pool
        
        indexes = await get_index_info()
        
        # Check if HNSW index is active
        hnsw_active = False
        parsed_indexes = []
        for idx in indexes:
            is_hnsw = "hnsw" in idx["indexdef"].lower()
            if is_hnsw:
                hnsw_active = True
            parsed_indexes.append({
                "name": idx["indexname"],
                "definition": idx["indexdef"],
                "scans": idx["scans"] or 0,
                "tuples_read": idx["tuples_read"] or 0,
                "tuples_fetched": idx["tuples_fetched"] or 0,
                "size": idx["size"] or "N/A"
            })
            
        # Get chunk stats
        pool = get_db_pool()
        total_chunks = 0
        table_size = "N/A"
        total_with_indexes = "N/A"
        
        try:
            async with pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        count(*) as total_chunks,
                        pg_size_pretty(pg_relation_size('dokumen_chunk'::regclass)) as table_size,
                        pg_size_pretty(pg_total_relation_size('dokumen_chunk'::regclass)) as total_with_indexes
                    FROM dokumen_chunk
                """)
                if stats:
                    total_chunks = stats["total_chunks"]
                    table_size = stats["table_size"]
                    total_with_indexes = stats["total_with_indexes"]
        except Exception as db_err:
            logger.warning(f"⚠️ Failed to query DB stats: {db_err}")
            
        return {
            "status": "success",
            "hnsw_active": hnsw_active,
            "indexes": parsed_indexes,
            "stats": {
                "total_chunks": total_chunks,
                "table_size": table_size,
                "total_with_indexes": total_with_indexes
            }
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Vector index status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get vector index status: {str(e)}")


@router.post("/optimize-vector-index")
async def optimize_vector_index_endpoint(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Run VACUUM ANALYZE to optimize vector search performance (W15).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.vector_index import optimize_vector_search
        
        logger.info(f"🔧 [ADMIN] User {current_user_npp} triggering vector index optimization...")
        stats = await optimize_vector_search()
        
        return {
            "status": "success",
            "message": "Vector index optimized and VACUUM ANALYZE completed successfully",
            "stats": {
                "total_chunks": stats["total_chunks"] if stats else 0,
                "table_size": stats["table_size"] if stats else "N/A",
                "total_with_indexes": stats["total_with_indexes"] if stats else "N/A"
            }
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Optimize index error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to optimize vector index: {str(e)}")
