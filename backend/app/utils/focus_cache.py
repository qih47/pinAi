"""
Focus Mode Cache Module
Caches extracted text and rendered images of PDFs by session UUID to avoid re-rendering/re-extracting.
"""

import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CAKRA_FOCUS_CACHE")

# In-memory cache: {session_uuid: {"text_map": [...], "images": [...], "timestamp": float}}
_focus_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 7200  # 2 hours TTL

def get_focus_cache(session_uuid: str) -> Optional[Dict[str, Any]]:
    """Get focus cache for a session if exists and not expired."""
    if not session_uuid:
        return None
        
    current_time = time.time()
    if session_uuid in _focus_cache:
        cached_data = _focus_cache[session_uuid]
        if (current_time - cached_data["timestamp"]) < _CACHE_TTL_SECONDS:
            logger.info(f"[FOCUS_CACHE] Hit for session {session_uuid}")
            return cached_data
        else:
            logger.info(f"[FOCUS_CACHE] Expired for session {session_uuid}")
            del _focus_cache[session_uuid]
    return None

def set_focus_cache(session_uuid: str, text_map: List[Dict[str, Any]], images: List[str]):
    """Set focus cache for a session."""
    if not session_uuid:
        return
        
    _focus_cache[session_uuid] = {
        "text_map": text_map,
        "images": images,
        "timestamp": time.time()
    }
    logger.info(f"[FOCUS_CACHE] Saved for session {session_uuid} ({len(text_map)} text pages, {len(images)} images)")
