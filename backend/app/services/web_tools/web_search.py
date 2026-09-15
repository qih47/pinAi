import logging
import httpx
import asyncio
import time
import re
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
    """Simpan hasil ke cache jika tidak kosong. Batas max 50 entry untuk cegah memory leak."""
    if not results:
        return
    key = query.strip().lower()
    if len(_search_cache) >= 50:
        # Hapus entry terlama
        oldest_key = min(_search_cache, key=lambda k: _search_cache[k][0])
        del _search_cache[oldest_key]
    _search_cache[key] = (time.time(), results)

def sanitize_web_query(query: str) -> str:
    """Membersihkan sanitasi teknis murni (tanda kutip luar, spasi berlebih, baris baru) tanpa memotong kata semantik."""
    if not query:
        return ""
    q = query.strip()
    # Hapus tanda kutip luar pembungkus string
    q = re.sub(r'^["\']+|["\']+$', '', q).strip()
    # Hapus karakter newline / tab
    q = re.sub(r'[\r\n\t]+', ' ', q)
    # Bersihkan multiple spaces
    q = re.sub(r'\s+', ' ', q).strip()
    return q or query.strip()


def simplify_search_query(query: str) -> str:
    """Mengekstrak kata kunci inti entitas dari query jika pencarian utama memerlukan penyederhanaan."""
    if not query:
        return ""
    q = sanitize_web_query(query)
    modifiers = [
        r"\b(berita|kabar|info|informasi|update|terbaru|terkini|hari ini|saat ini|sekarang|teranyar)\b",
        r"\b(tentang|mengenai|soal|terkait|pada|di|ke|dari|dan|atau|yang|adalah)\b"
    ]
    simplified = q
    for mod in modifiers:
        simplified = re.sub(mod, " ", simplified, flags=re.IGNORECASE)
    simplified = re.sub(r"\s+", " ", simplified).strip()
    return simplified if len(simplified.split()) >= 2 else q


async def perform_web_search(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Melakukan pencarian ke SearXNG dan mengembalikan daftar hasil.
    Dilengkapi multi-tier query retry & language fallback agar tidak menghasilkan kosongan.
    """
    clean_q = sanitize_web_query(query)
    if not clean_q:
        clean_q = query.strip()

    # Cek cache dulu
    cached = _get_cached_results(clean_q)
    if cached is not None and len(cached) > 0:
        return cached[:num_results]

    logger.info(f"[Web Search] Searching for: '{clean_q}' (raw: '{query}')")
    
    candidate_queries = [clean_q]
    simplified_q = simplify_search_query(clean_q)
    if simplified_q and simplified_q.lower() != clean_q.lower():
        candidate_queries.append(simplified_q)

    # Coba candidate queries secara berurutan jika hasil kosong
    for cand_idx, target_q in enumerate(candidate_queries):
        # Percobaan 1: dengan language=id
        # Percobaan 2 (jika kosong): tanpa language restriction (all languages)
        for lang_opt in ["id", None]:
            params = {
                "q": target_q,
                "format": "json",
                "categories": "general",
                "safesearch": "0"
            }
            if lang_opt:
                params["language"] = lang_opt

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(SEARXNG_URL, params=params)
                    response.raise_for_status()

                    data = response.json()
                    results = data.get("results", [])
                    
                    if results:
                        formatted_results = []
                        for r in results[:num_results]:
                            formatted_results.append({
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "content": r.get("content", ""),
                                "engine": r.get("engine", "")
                            })
                        
                        logger.info(f"[Web Search] ✅ Found {len(formatted_results)} results for '{target_q}' (lang={lang_opt})")
                        _set_cache(clean_q, formatted_results)
                        return formatted_results

            except Exception as e:
                logger.warning(f"[Web Search] Attempt failed for '{target_q}' (lang={lang_opt}): {e}")

    logger.warning(f"[Web Search] ⚠️ Zero results returned across all candidates for: '{clean_q}'")
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
