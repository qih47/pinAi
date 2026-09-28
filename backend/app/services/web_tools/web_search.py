import logging
import httpx
import asyncio
import time
import re
from typing import List, Dict, Any, Optional, Union, AsyncGenerator

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

def normalize_temporal_web_query(query: str, user_message: str = "") -> str:
    """
    Menyelaraskan jangkar tahun pada query pencarian web dengan tahun aktual (saat ini).
    Mencegah halusinasi model LLM yang menyematkan tahun-tahun lampau training data
    (seperti 2023, 2024, atau rentang 2024-2025) pada pencarian hal 'terbaru' / 'viral',
    KECUALI jika pengguna secara eksplisit menyebutkan tahun tersebut di pesan aslinya.
    """
    if not query:
        return ""
    
    from datetime import datetime
    now_year = datetime.now().year  # 2026
    
    # Ambil tahun yang secara sadar diminta user
    user_years = set(re.findall(r"\b(19\d{2}|20\d{2})\b", user_message or ""))
    
    q = query
    
    # 1. Deteksi pola rentang tahun lampau beruntun seperti "2024 2025", "2024-2025", atau "2024/2025"
    range_pattern = r"\b(20\d{2})\s*[-/ ]\s*(20\d{2})\b"
    for m in re.finditer(range_pattern, q):
        y1, y2 = int(m.group(1)), int(m.group(2))
        full_match = m.group(0)
        # Jika kedua tahun adalah tahun lampau (< now_year), dan user tidak memintanya secara eksplisit
        if y2 < now_year and (m.group(1) not in user_years and m.group(2) not in user_years):
            # Sesuaikan rentang tahun ke tahun aktual (misal: 2025 2026)
            new_range = f"{now_year - 1} {now_year}"
            q = q.replace(full_match, new_range)
            logger.info(f"[Web Search] 🕒 Normalized outdated year range '{full_match}' -> '{new_range}'")
            
    # 2. Deteksi single year lampau (misal 2023, 2024) yang muncul jika user tidak memintanya
    for y_str in re.findall(r"\b(20\d{2})\b", q):
        y_int = int(y_str)
        if y_int < (now_year - 1) and y_str not in user_years:
            q = re.sub(rf"\b{y_str}\b", str(now_year), q)
            logger.info(f"[Web Search] 🕒 Normalized outdated single year '{y_str}' -> '{now_year}'")

    q = re.sub(r"\s+", " ", q).strip()
    return q


def sanitize_web_query(query: str, user_message: str = "") -> str:
    """Membersihkan sanitasi teknis murni dan menyelaraskan jangkar tahun aktual."""
    if not query:
        return ""
    q = query.strip()
    # Hapus tanda kutip luar pembungkus string
    q = re.sub(r'^["\']+|["\']+$', '', q).strip()
    # Hapus karakter newline / tab
    q = re.sub(r'[\r\n\t]+', ' ', q)
    # Bersihkan multiple spaces
    q = re.sub(r'\s+', ' ', q).strip()
    # Normalisasi tahun lampau halusinasi
    q = normalize_temporal_web_query(q, user_message=user_message)
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


# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 UNIFIED WEB SEARCH PIPELINE (SINGLE SOURCE OF TRUTH)
# ═══════════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field
from typing import AsyncGenerator

@dataclass
class WebSearchResult:
    """Hasil akhir komprehensif dari eksekusi Web Search Pipeline."""
    display_query: str
    results: List[Dict[str, Any]]
    llm_context: str
    top_urls: List[str] = field(default_factory=list)
    raw_count: int = 0


@dataclass
class WebSearchPipelineEvent:
    """Event progresif untuk streaming status dan preview UI."""
    event_type: str  # "SEARCHING" | "RERANKING" | "RANKED" | "SCRAPING" | "FILTERING_FACTS" | "RESULT"
    data: Any = None


def _chunk_scraped_text(text: str, source: str, chunk_size: int = 1500, overlap: int = 200) -> List[Dict[str, str]]:
    """Membagi teks panjang hasil web scraping menjadi potongan terukur untuk BGE reranker."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append({
            "text": text[start:end],
            "source": source
        })
        start += chunk_size - overlap
    return chunks


async def execute_web_search_pipeline_stream(
    queries: Union[str, List[str]],
    user_message: str = "",
    pre_fetched_urls: Optional[List[Dict[str, Any]]] = None,
    pre_fetched_content: str = "",
    num_raw_results: int = 12,
    scrape_top_k: int = 2,
) -> AsyncGenerator[WebSearchPipelineEvent, None]:
    """
    Eksekusi terpusat (Single Source of Truth) untuk penelusuran web di CAKRA AI:
    1. Multi-query sanitization & dynamic temporal normalization.
    2. SearXNG multi-target retrieval dengan deduplikasi tautan.
    3. Fallback simplifikasi query otomatis jika hasil kosong.
    4. BGE Cross-Encoder Reranking dengan Dynamic Thresholding (dinamis 3 - 10 hasil).
    5. Parallel deep scraping untuk URL teratas + chunk-level fact reranking.
    6. Pemancaran event progresif untuk update UI realtime.
    """
    from backend.app.services.web_tools.url_reader import fetch_webpage_content
    from backend.app.services.rag.reranker_service import reranker_service

    # 1. Normalisasi dan sanitasi daftar query
    raw_query_list = [queries] if isinstance(queries, str) else list(queries or [])
    clean_target_queries: List[str] = []
    seen_q = set()

    for q in raw_query_list:
        if not isinstance(q, str) or not q.strip():
            continue
        cleaned = sanitize_web_query(q.strip(), user_message=user_message) or q.strip()
        if cleaned.lower() not in seen_q:
            seen_q.add(cleaned.lower())
            clean_target_queries.append(cleaned)

    if not clean_target_queries:
        fallback_q = sanitize_web_query(user_message.strip(), user_message=user_message) if user_message.strip() else ""
        if fallback_q:
            clean_target_queries.append(fallback_q)

    display_query = " & ".join(clean_target_queries) if clean_target_queries else (user_message.strip() or "Penelusuran Web")

    # Event 1: Memulai pencarian
    yield WebSearchPipelineEvent("SEARCHING", {
        "query": display_query,
        "queries": clean_target_queries
    })

    if not clean_target_queries:
        yield WebSearchPipelineEvent("RESULT", WebSearchResult(
            display_query=display_query,
            results=[],
            llm_context="Tidak ada kata kunci pencarian yang valid."
        ))
        return

    # 2. Penelusuran SearXNG paralel untuk semua query
    search_tasks = [perform_web_search(q, num_results=num_raw_results) for q in clean_target_queries]
    results_lists = await asyncio.gather(*search_tasks)

    seen_urls = set()
    raw_search_results: List[Dict[str, Any]] = []
    for r_list in results_lists:
        for r in r_list:
            u = r.get("url")
            if u and u not in seen_urls:
                seen_urls.add(u)
                raw_search_results.append(r)

    # 2.1 Fallback otomatis jika hasil kosong
    if not raw_search_results:
        fallback_queries = []
        for q in clean_target_queries:
            sq = simplify_search_query(q)
            if sq and sq.lower() != q.lower() and sq.lower() not in seen_q:
                fallback_queries.append(sq)
        if fallback_queries:
            logger.info(f"[Web Search Pipeline] 🔄 Retrying search with simplified queries: {fallback_queries}")
            fb_tasks = [perform_web_search(q, num_results=num_raw_results) for q in fallback_queries]
            fb_results_lists = await asyncio.gather(*fb_tasks)
            for r_list in fb_results_lists:
                for r in r_list:
                    u = r.get("url")
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        raw_search_results.append(r)

    if not raw_search_results:
        logger.warning(f"[Web Search Pipeline] Zero search results for: '{display_query}'")
        yield WebSearchPipelineEvent("RESULT", WebSearchResult(
            display_query=display_query,
            results=list(pre_fetched_urls or []),
            llm_context=f"Tidak ditemukan hasil pencarian web yang valid untuk query: '{display_query}'.",
            raw_count=0
        ))
        return

    # Event 2: Reranking dimulai
    yield WebSearchPipelineEvent("RERANKING", {"raw_count": len(raw_search_results)})

    # 3. BGE Cross-Encoder Reranking
    search_results = raw_search_results
    try:
        corpus_texts = [
            f"{r.get('title', '')} {r.get('content', '')}".strip()
            for r in raw_search_results
        ]
        rerank_query = " ".join(clean_target_queries)
        scores = await reranker_service.compute_scores(rerank_query, corpus_texts)

        ranked = sorted(zip(scores, raw_search_results), key=lambda x: x[0], reverse=True)

        # Dynamic Relevance Filter (Ambil relevan score >= 0.38, rentang dinamis 3 - 10)
        relevant_results = [r for s, r in ranked if s >= 0.38]
        if len(relevant_results) < 3:
            search_results = [r for _, r in ranked[:3]]
        else:
            max_res = 10 if len(clean_target_queries) > 1 else 8
            search_results = relevant_results[:max_res]

        logger.info(
            f"[Web Search Pipeline] 🎯 Dynamically filtered {len(search_results)} relevant results "
            f"(from {len(ranked)} raw). Top: '{search_results[0].get('title', '')[:50]}'"
        )
    except Exception as e:
        logger.warning(f"[Web Search Pipeline] Reranker error fallback (top 6): {e}")
        search_results = raw_search_results[:6]

    # Gabungkan dengan pre_fetched_urls jika ada
    combined_results = list(pre_fetched_urls or []) + search_results

    # Event 3: Ranked results siap (dapat langsung dipreview di UI)
    yield WebSearchPipelineEvent("RANKED", {
        "search_results": combined_results,
        "display_query": display_query
    })

    # 4. Format konteks awal LLM
    web_context = format_search_results_for_llm(search_results)

    # 4.1 Injeksi pre_fetched_content jika ada
    if pre_fetched_content and "[KONTEN WEB DARI URL DI CHAT]" in pre_fetched_content:
        url_section = pre_fetched_content.split("[KONTEN WEB DARI URL DI CHAT]")[-1].strip()
        if url_section:
            web_context += f"\n\n=== KONTEN LANGSUNG DARI URL YANG DISEBUTKAN USER ===\n{url_section[:20000]}"

    # 5. Deep scraping URL teratas secara paralel
    top_urls = [r["url"] for r in search_results[:scrape_top_k] if r.get("engine") != "url_reader" and r.get("url")]
    if top_urls:
        yield WebSearchPipelineEvent("SCRAPING", {"top_urls": top_urls})

        async def _scrape_one(u: str) -> str:
            try:
                c = await asyncio.wait_for(fetch_webpage_content(u), timeout=4.0)
                return c or ""
            except Exception as e:
                logger.warning(f"[Web Search Pipeline] Scrape timeout/failed for {u}: {e}")
                return ""

        scrape_results = await asyncio.gather(*[_scrape_one(u) for u in top_urls])

        all_chunks = []
        for u, content in zip(top_urls, scrape_results):
            if content and content.strip():
                all_chunks.extend(_chunk_scraped_text(content.strip(), u))

        if all_chunks:
            yield WebSearchPipelineEvent("FILTERING_FACTS", {"chunk_count": len(all_chunks)})

            try:
                chunk_texts = [c["text"] for c in all_chunks]
                c_scores = await reranker_service.compute_scores(display_query, chunk_texts)

                scored_chunks = []
                for i, s in enumerate(c_scores):
                    scored_chunks.append({
                        "text": chunk_texts[i],
                        "source": all_chunks[i]["source"],
                        "score": s
                    })

                scored_chunks.sort(key=lambda x: x["score"], reverse=True)

                seen_texts = set()
                unique_scored = []
                for c in scored_chunks:
                    snip = c["text"][:100].strip()
                    if snip not in seen_texts:
                        seen_texts.add(snip)
                        unique_scored.append(c)

                rel_chunks = [c for c in unique_scored if c["score"] >= 0.55]
                top_chunks = rel_chunks[:7] if len(rel_chunks) >= 3 else unique_scored[:4]

                combined_deep = "\n\n---\n\n".join(
                    f"[Sumber: {c['source']}]\n{c['text']}" for c in top_chunks
                )
                web_context += f"\n\n=== DETAIL KONTEN WEB TERBARU (FILTERED & RERANKED) ===\n{combined_deep}"
                logger.info(f"[Web Search Pipeline] Deep rerank selected {len(top_chunks)} chunks from {len(all_chunks)}.")
            except Exception as e:
                logger.warning(f"[Web Search Pipeline] Fact rerank fallback: {e}")

    # Batasi context budget agar aman
    safe_web_context = (web_context[:10000] + "\n(konten web dipotong sesuai batas context)") if len(web_context) > 10000 else web_context

    yield WebSearchPipelineEvent("RESULT", WebSearchResult(
        display_query=display_query,
        results=combined_results,
        llm_context=safe_web_context,
        top_urls=top_urls,
        raw_count=len(raw_search_results)
    ))


async def execute_web_search_pipeline(
    queries: Union[str, List[str]],
    user_message: str = "",
    pre_fetched_urls: Optional[List[Dict[str, Any]]] = None,
    pre_fetched_content: str = "",
    num_raw_results: int = 12,
    scrape_top_k: int = 2,
) -> WebSearchResult:
    """Wrapper non-streaming untuk eksekusi langsung Web Search Pipeline."""
    final_result: Optional[WebSearchResult] = None
    async for event in execute_web_search_pipeline_stream(
        queries=queries,
        user_message=user_message,
        pre_fetched_urls=pre_fetched_urls,
        pre_fetched_content=pre_fetched_content,
        num_raw_results=num_raw_results,
        scrape_top_k=scrape_top_k,
    ):
        if event.event_type == "RESULT" and isinstance(event.data, WebSearchResult):
            final_result = event.data

    return final_result or WebSearchResult(
        display_query=str(queries),
        results=[],
        llm_context="Pencarian web tidak mengembalikan hasil."
    )

