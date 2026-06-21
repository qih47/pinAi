import asyncio
import logging
import time
from typing import AsyncGenerator, List, Dict, Any, Tuple

from backend.app.services.rag_service import rag_service
from backend.app.services.pipeline.sse_validation import (
    SSEEventType,
    format_sse,
    format_sse_pipeline_data,
)

logger = logging.getLogger("CAKRA_RAG_PIPELINE")

_SLOW_SEARCH_THRESHOLD_S = 3.0


async def run_rag_pipeline(
    rewritten_queries: List[str],
    limit_per_query: int = 3,
) -> AsyncGenerator[str, None]:
    if not rewritten_queries:
        logger.info("[RAG_PIPELINE] No queries → skip RAG")
        yield format_sse_pipeline_data({"context": "", "sources": []})
        return

    yield format_sse("", "🔎 Mencari dokumen internal...", False, event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)

    start_time = time.time()

    rag_task = asyncio.create_task(
        _run_parallel_rag(rewritten_queries, limit_per_query)
    )

    slow_warned = False
    while not rag_task.done():
        await asyncio.sleep(0.5)
        elapsed = time.time() - start_time
        if elapsed > _SLOW_SEARCH_THRESHOLD_S and not slow_warned:
            yield format_sse(
                "", "⏳ Memeriksa arsip rujukan...", False,
                event_type=SSEEventType.STATUS,
            )
            await asyncio.sleep(0.01)
            slow_warned = True

    try:
        combined_context, combined_sources, total_candidates = await rag_task
    except Exception as e:
        logger.error(f"[RAG_PIPELINE] Parallel RAG error: {e}")
        yield format_sse("", "⚠️ Gagal mengakses dokumen rujukan", False, event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)
        yield format_sse_pipeline_data({"context": "", "sources": []})
        return

    # 🔥 HITUNG DURASI TOTAL PENCARIAN
    duration_ms = int((time.time() - start_time) * 1000)

    # 🔥 SUNTIK DURASI KE SETIAP UTAS SUMBER DOKUMEN AGAR RAGMETRICS FE TIDAK UNDEFINED
    for src in combined_sources:
        src["search_time_ms"] = duration_ms

    yield format_sse("", "📊 Memilih rujukan paling sesuai...", False, event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)

    if combined_sources:
        doc_count = len(combined_sources)
        yield format_sse(
            "",
            f"✅ Menemukan {doc_count} rujukan dokumen terkait",
            False,
            event_type=SSEEventType.STATUS,
        )
        await asyncio.sleep(0.01)
        
        # 🔥 FIX CRITICAL: Emit event SOURCES secara mandiri dari dalam pipeline RAG 
        # agar ditangkap oleh generator router utama, jangan cuma dikemas di format_sse_pipeline_data!
        yield format_sse(
            "", "", False,
            sources=combined_sources,
            event_type=SSEEventType.SOURCES,
        )
        await asyncio.sleep(0.01)
    else:
        yield format_sse(
            "", "⚠️ Dokumen rujukan tidak ditemukan", False,
            event_type=SSEEventType.STATUS,
        )
        await asyncio.sleep(0.01)

    logger.info(
        f"[RAG_PIPELINE] Done | {len(combined_context)} chars | "
        f"{len(combined_sources)} sources | {total_candidates} candidates | "
        f"{duration_ms}ms"
    )

    # Tetap kirimkan payload data internal untuk kebutuhan injeksi konteks prompt LLM
    yield format_sse_pipeline_data({"context": combined_context, "sources": combined_sources})


async def _run_parallel_rag(
    rewritten_queries: List[str],
    limit_per_query: int,
) -> Tuple[str, List[Dict[str, Any]], int]:
    from backend.app.utils.embedding_cache import get_embedding_cache
    cache = get_embedding_cache()
    hits_before = cache.hits

    async def _fetch(q: str, limit: int):
        try:
            ctx, sources = await rag_service.assemble_powerful_context(
                query=q, limit=limit
            )
            return ctx, sources
        except Exception as e:
            logger.warning(f"[RAG_PIPELINE] Query '{q[:50]}' error: {e}")
            return "", []

    # Batasi agar total dokumen yang dirender tidak lebih dari ~3-4
    dynamic_limit = max(1, 4 // len(rewritten_queries)) if rewritten_queries else limit_per_query

    results = await asyncio.gather(*[_fetch(q, dynamic_limit) for q in rewritten_queries])

    hits_after = cache.hits
    is_cache_hit = hits_after > hits_before

    combined_context_parts = []
    seen_ids = set()
    combined_sources = []
    total_candidates = 0

    for ctx, sources in results:
        if ctx:
            combined_context_parts.append(ctx)
        total_candidates += len(sources)
        for src in sources:
            src_id = src.get("id") or src.get("chunk_id") or str(src)
            if src_id not in seen_ids:
                seen_ids.add(src_id)
                src["cache_hit"] = is_cache_hit
                combined_sources.append(src)

    combined_context = "\n\n---\n\n".join(combined_context_parts)

    logger.info(
        f"[RAG_PIPELINE] {len(rewritten_queries)} queries | "
        f"{len(combined_context)} chars | {len(combined_sources)} unique sources | "
        f"cache_hit={is_cache_hit}"
    )

    return combined_context, combined_sources, total_candidates