import logging
import httpx
import asyncio
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("cakra.web_tools.search")

SEARXNG_URL = "http://localhost:8080/search"

# ── ⚡ In-memory TTL Cache untuk SearXNG ─────────────────────────────────────
# Key: query string (lowercase stripped) | Value: (timestamp, results)
_search_cache: Dict[str, tuple] = {}
_CACHE_TTL_SECONDS = 300  # 5 menit

def _get_cached_results(query: str) -> Optional[List[Dict[str, Any]]]:
    """Return cached results jika masih dalam TTL, None jika expired/miss."""
    key = query.strip().lower()
    if key in _search_cache:
        ts, results = _search_cache[key]
        if time.time() - ts < _CACHE_TTL_SECONDS:
            logger.info(f"[Web Search] ⚡ CACHE HIT for: '{query}' ({len(results)} results)")
            return results
        else:
            del _search_cache[key]  # expired
    return None

def _set_cache(query: str, results: List[Dict[str, Any]]) -> None:
    """Simpan hasil ke cache. Batas max 50 entry untuk cegah memory leak."""
    key = query.strip().lower()
    if len(_search_cache) >= 50:
        # Hapus entry terlama
        oldest_key = min(_search_cache, key=lambda k: _search_cache[k][0])
        del _search_cache[oldest_key]
    _search_cache[key] = (time.time(), results)

import re

def sanitize_web_query(query: str) -> str:
    """Membersihkan kata-kata filler percakapan dari query pencarian web."""
    if not query:
        return ""
    q = query.strip()
    fillers = [
        r"^mencari referensi terkait\s*",
        r"^referensi terkait\s*",
        r"^carikan info(rmasi)? terkait\s*",
        r"^cari di web\s*",
        r"^cari web\s*",
        r"^tolong cari(kan)?\s*",
        r"^info(rmasi)? tentang\s*",
    ]
    for pattern in fillers:
        q = re.sub(pattern, "", q, flags=re.IGNORECASE).strip()
    return q or query.strip()

async def perform_web_search(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Melakukan pencarian ke SearXNG dan mengembalikan daftar hasil.
    Hasil di-cache selama 5 menit untuk menghindari duplikat request.
    """
    clean_q = sanitize_web_query(query)
    if not clean_q:
        clean_q = query.strip()

    # Cek cache dulu
    cached = _get_cached_results(clean_q)
    if cached is not None:
        return cached[:num_results]

    logger.info(f"[Web Search] Searching for: '{clean_q}' (raw: '{query}')")
    
    params = {
        "q": clean_q,
        "format": "json",
        "language": "id",
        "categories": "general",
        "safesearch": "0"
    }
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(SEARXNG_URL, params=params)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            
            # Format results
            formatted_results = []
            for r in results[:num_results]:
                formatted_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "engine": r.get("engine", "")
                })
            
            # Simpan ke cache
            _set_cache(clean_q, formatted_results)
            return formatted_results
            
    except Exception as e:
        logger.error(f"[Web Search] Failed to search SearXNG: {str(e)}")
        return []


def format_search_results_for_llm(results: List[Dict[str, Any]]) -> str:
    """
    Mengubah list JSON hasil search menjadi string konteks yang siap dibaca LLM.
    """
    if not results:
        return "Tidak ada hasil pencarian yang ditemukan."
        
    context = "BERIKUT ADALAH HASIL PENCARIAN WEB TERBARU:\n\n"
    for idx, r in enumerate(results, 1):
        context += f"[{idx}] Judul Sumber: {r.get('title', 'Sumber Web')}\n"
        context += f"URL: {r.get('url', '')}\n"
        context += f"Format Sitasi Markdown Wajib: [{r.get('title', 'Sumber Web')}]({r.get('url', '')})\n"
        context += f"Isi Ringkasan: {r.get('content', '')}\n\n"
        
    context += "PANDUAN SITASI: Setiap menyebutkan fakta dari sumber di atas, WAJIB sertakan format markdown link `[Nama Sumber](URL)` yang sesuai agar pengguna dapat mengkliknya.\n"
    return context
