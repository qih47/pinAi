"""
Employee Cache Module — Reduce N+1 queries for employee fullname lookups
=========================================================================
Caches employee fullname in memory with TTL to avoid DB hits on every request.
Invalidates on user logout or manual refresh.
"""

import logging
import time
from typing import Optional, Dict
from functools import lru_cache

logger = logging.getLogger("CAKRA_EMPLOYEE_CACHE")

# In-memory cache: {npp: (fullname, timestamp)}
_employee_cache: Dict[str, tuple[str, float]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour TTL


async def get_cached_employee_data(
    npp: str,
    db_fetch_func=None,  # async function(npp) -> Optional[dict]
) -> Optional[dict]:
    """
    Get employee fullname from cache or fetch from DB if not cached/expired.
    
    Args:
        npp: Employee NPP (Nomor Pokok Pegawai)
        db_fetch_func: Async function that fetches fullname from DB
    
    Returns:
        Employee data dict or None if not found
    """
    
    current_time = time.time()
    
    # Check if in cache and not expired
    if npp in _employee_cache:
        cached_name, cached_time = _employee_cache[npp]
        if (current_time - cached_time) < _CACHE_TTL_SECONDS:
            logger.debug(f"✅ [CACHE HIT] NPP {npp} → {cached_name}")
            return cached_name
        else:
            # Expired, remove from cache
            logger.info(f"⏰ [CACHE EXPIRED] NPP {npp} (age: {current_time - cached_time:.0f}s)")
            del _employee_cache[npp]
    
    # Not in cache or expired — fetch from DB if function provided
    if db_fetch_func is None:
        return None
    
    try:
        employee_data = await db_fetch_func(npp)
        if employee_data:
            _employee_cache[npp] = (employee_data, current_time)
            logger.info(f"📝 [CACHE SET] NPP {npp} → {employee_data}")
            return employee_data
        else:
            # Store negative result to avoid repeated DB hits
            _employee_cache[npp] = (None, current_time)
            return None
    except Exception as e:
        logger.warning(f"⚠️ [CACHE FETCH] Error fetching {npp}: {e}")
        return None


def invalidate_employee_cache(npp: Optional[str] = None):
    """
    Invalidate employee cache entry.
    
    Args:
        npp: Specific NPP to invalidate, or None to clear entire cache
    """
    global _employee_cache
    
    if npp is None:
        _employee_cache.clear()
        logger.info("🧹 [CACHE] Entire employee cache cleared")
    else:
        if npp in _employee_cache:
            del _employee_cache[npp]
            logger.info(f"🧹 [CACHE] Invalidated NPP {npp}")


def get_cache_stats() -> Dict:
    """Get cache statistics for monitoring"""
    return {
        "total_entries": len(_employee_cache),
        "entries": list(_employee_cache.keys()),
    }
