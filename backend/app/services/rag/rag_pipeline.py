"""
RAG Pipeline — Sprint 2 Enhanced
=================================

Perubahan:
  1. Semantic Cache Interceptor (cosine similarity > 0.90)
  2. Auto-save ke cache setelah RAG DB pipeline selesai
  3. Score Exposure sudah ditangani di rag_service.py
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, List, Dict, Any, Tuple, Optional  # ✅ FIXED: Tambah Optional

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
    npp: Optional[str] = None,
    use_cache: bool = False,
) -> AsyncGenerator[str, None]:
    if not rewritten_queries:
        logger.info("[RAG_PIPELINE] No queries → skip RAG")
        yield format_sse_pipeline_data({"context": "", "sources": []})
        return

    yield format_sse(status="🔎 Mencari dokumen internal...", event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)

    start_time = time.time()

    # ── SPRINT 2: SEMANTIC CACHE CHECK ───────────────────────────────────────
    cache_result = None
    if use_cache:
        cache_result = await _check_cache_for_queries(rewritten_queries, npp)

    if cache_result:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"[RAG_PIPELINE] ⚡ Cache HIT | topic={cache_result['topic_key']} | "
            f"similarity={cache_result['similarity']:.4f} | {duration_ms}ms"
        )

        combined_sources = cache_result["sources"]
        for src in combined_sources:
            src["search_time_ms"] = duration_ms
            src["cache_hit"] = True

        yield format_sse(status="⚡ Menggunakan cache dokumen terkait", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        yield format_sse(status=f"✨ Menemukan {len(combined_sources)} dokumen relevan!", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

        yield format_sse("", "", False, sources=combined_sources, event_type=SSEEventType.SOURCES)
        await asyncio.sleep(0.01)

        yield format_sse_pipeline_data({
            "context": cache_result["context"],
            "sources": combined_sources,
        })
        return

    # ── CACHE MISS: Jalankan RAG DB Pipeline Normal ──────────────────────────
    rag_task = asyncio.create_task(
        _run_parallel_rag(rewritten_queries, limit_per_query)
    )

    slow_warned = False
    while not rag_task.done():
        await asyncio.sleep(0.5)
        elapsed = time.time() - start_time
        if elapsed > _SLOW_SEARCH_THRESHOLD_S and not slow_warned:
            yield format_sse(status="⏳ Memeriksa arsip rujukan...", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)
            slow_warned = True

    try:
        combined_context, combined_sources, total_candidates = await rag_task
    except Exception as e:
        logger.error(f"[RAG_PIPELINE] Parallel RAG error: {e}")
        yield format_sse(status="⚠️ Gagal mengakses dokumen rujukan", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)
        yield format_sse_pipeline_data({"context": "", "sources": []})
        return

    duration_ms = int((time.time() - start_time) * 1000)

    for src in combined_sources:
        src["search_time_ms"] = duration_ms

    yield format_sse(status="📊 Memilih rujukan paling sesuai...", event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)

    if combined_sources:
        doc_count = len(combined_sources)
        yield format_sse(
            status=f"✅ Menemukan {doc_count} rujukan dokumen terkait",
            event_type=SSEEventType.STATUS,
        )
        await asyncio.sleep(0.01)

        yield format_sse(
            "", "", False,
            sources=combined_sources,
            event_type=SSEEventType.SOURCES,
        )
        await asyncio.sleep(0.01)
    else:
        yield format_sse(status="⚠️ Tidak menemukan dokumen terkait yang valid. Akan menggunakan pengetahuan internal.", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)

    logger.info(
        f"[RAG_PIPELINE] Done | {len(combined_context)} chars | "
        f"{len(combined_sources)} sources | {total_candidates} candidates | "
        f"{duration_ms}ms"
    )

    # ── SPRINT 2: SAVE TO SEMANTIC CACHE ─────────────────────────────────────
    if combined_context and combined_sources and use_cache:
        await _save_cache_for_queries(
            rewritten_queries, combined_context, combined_sources, npp
        )

    yield format_sse_pipeline_data({"context": combined_context, "sources": combined_sources})


async def _check_cache_for_queries(
    queries: List[str],
    npp: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Cek semantic cache untuk query pertama yang punya embedding."""
    try:
        from backend.app.services.rag.rag_cache_service import check_semantic_cache
        from backend.app.services.rag.vector_service import vector_service

        for query in queries:
            embedding = await vector_service.get_query_embedding(query)
            if embedding:
                result = await check_semantic_cache(embedding, query, npp)
                if result:
                    return result
    except Exception as e:
        logger.warning(f"[RAG_PIPELINE] Cache check failed (non-fatal): {e}")

    return None


async def _save_cache_for_queries(
    queries: List[str],
    context: str,
    sources: List[Dict[str, Any]],
    npp: Optional[str] = None,
) -> None:
    """Simpan hasil RAG ke semantic cache (fire-and-forget)."""
    try:
        from backend.app.services.rag.rag_cache_service import save_to_semantic_cache
        from backend.app.services.rag.vector_service import vector_service

        # Gunakan query pertama sebagai representative
        query = queries[0] if queries else ""
        if not query:
            return

        embedding = await vector_service.get_query_embedding(query)
        if embedding:
            await save_to_semantic_cache(query, embedding, context, sources, npp)
    except Exception as e:
        logger.warning(f"[RAG_PIPELINE] Cache save failed (non-fatal): {e}")


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

    results = await asyncio.gather(*[_fetch(q, limit_per_query) for q in rewritten_queries])

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