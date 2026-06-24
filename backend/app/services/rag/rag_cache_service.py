"""
RAG Semantic Cache Service — Sprint 2
======================================

Interceptor cosine similarity > 0.90 sebelum RAG DB pipeline.
Invalidasi berbasis trigger dokumen baru (bukan TTL).

Embedding: mxbai-embed-large (1024 dim) via vector_service
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_RAG_CACHE")

SIMILARITY_THRESHOLD = 0.90


async def check_semantic_cache(
    query_embedding: List[float],
    query_text: str,
    npp: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Cek cache via cosine similarity. Return context+sources jika HIT, None jika MISS.
    """
    if not query_embedding or len(query_embedding) != 1024:
        logger.debug("[RAG_CACHE] Invalid embedding, skip cache check")
        return None

    try:
        async with get_db() as conn:
            vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            row = await conn.fetchrow(
                """
                SELECT topic_key, context, sources,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM public.rag_topic_cache
                ORDER BY embedding <=> $1::vector
                LIMIT 1
                """,
                vec_str,
            )

            if not row:
                logger.debug("[RAG_CACHE] No cache entries found")
                return None

            similarity = float(row["similarity"])

            if similarity >= SIMILARITY_THRESHOLD:
                # Update hit stats
                await conn.execute(
                    """
                    UPDATE public.rag_topic_cache
                    SET hit_count = hit_count + 1,
                        last_hit_at = NOW(),
                        query_samples = (
                            SELECT jsonb_agg(elem)
                            FROM (
                                SELECT elem
                                FROM jsonb_array_elements(COALESCE(query_samples, '[]'::jsonb)) AS elem
                                UNION ALL
                                SELECT to_jsonb($2::text)
                                LIMIT 20
                            ) sub
                        )
                    WHERE topic_key = $1
                    """,
                    row["topic_key"],
                    query_text,
                )

                sources = row["sources"]
                if isinstance(sources, str):
                    sources = json.loads(sources)

                logger.info(
                    f"[RAG_CACHE] ✅ HIT | similarity={similarity:.4f} | "
                    f"topic={row['topic_key']} | query='{query_text[:60]}'"
                )

                return {
                    "context": row["context"],
                    "sources": sources,
                    "topic_key": row["topic_key"],
                    "similarity": similarity,
                }
            else:
                logger.debug(
                    f"[RAG_CACHE] ❌ MISS | best_similarity={similarity:.4f} < {SIMILARITY_THRESHOLD}"
                )
                return None

    except Exception as e:
        # Cache failure harus silent — jangan block RAG pipeline utama
        logger.warning(f"[RAG_CACHE] Error checking cache: {e}")
        return None


async def save_to_semantic_cache(
    query_text: str,
    query_embedding: List[float],
    context: str,
    sources: List[Dict[str, Any]],
    npp: Optional[str] = None,
) -> bool:
    """
    Simpan hasil RAG baru ke cache setelah pipeline selesai.
    topic_key = query_text asli (normalized).
    """
    if not query_embedding or len(query_embedding) != 1024:
        logger.warning("[RAG_CACHE] Cannot save: invalid embedding")
        return False

    if not context or not sources:
        logger.debug("[RAG_CACHE] Skip save: empty context or sources")
        return False

    topic_key = query_text.strip().lower()[:200]

    try:
        async with get_db() as conn:
            vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            # Cek apakah sudah ada (race condition guard)
            existing = await conn.fetchval(
                "SELECT 1 FROM public.rag_topic_cache WHERE topic_key = $1",
                topic_key,
            )

            if existing:
                # Update saja
                await conn.execute(
                    """
                    UPDATE public.rag_topic_cache
                    SET context = $2, sources = $3, embedding = $4::vector,
                        hit_count = hit_count + 1, last_hit_at = NOW()
                    WHERE topic_key = $1
                    """,
                    topic_key, context, json.dumps(sources), vec_str,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO public.rag_topic_cache
                        (topic_key, context, sources, embedding, created_by, query_samples)
                    VALUES ($1, $2, $3, $4::vector, $5, $6)
                    ON CONFLICT (topic_key) DO UPDATE SET
                        context = EXCLUDED.context,
                        sources = EXCLUDED.sources,
                        embedding = EXCLUDED.embedding,
                        hit_count = rag_topic_cache.hit_count + 1,
                        last_hit_at = NOW()
                    """,
                    topic_key,
                    context,
                    json.dumps(sources),
                    vec_str,
                    npp,
                    json.dumps([query_text]),
                )

            logger.info(
                f"[RAG_CACHE] 💾 Saved | topic='{topic_key[:60]}' | "
                f"{len(sources)} sources | {len(context)} chars"
            )
            return True

    except Exception as e:
        logger.warning(f"[RAG_CACHE] Error saving cache: {e}")
        return False


async def invalidate_cache_for_document(doc_nomor: str) -> int:
    """
    Invalidasi cache saat dokumen baru diupload dengan parameter 'menggantikan_nomor'.
    Hapus semua cache yang sources-nya mengandung nomor dokumen lama.
    """
    try:
        async with get_db() as conn:
            result = await conn.execute(
                """
                DELETE FROM public.rag_topic_cache
                WHERE sources @> $1::jsonb
                """,
                json.dumps([{"nomor": doc_nomor}]),
            )

            deleted = int(result.split()[-1]) if result else 0
            logger.info(
                f"[RAG_CACHE] 🗑️ Invalidated {deleted} cache entries for doc: {doc_nomor}"
            )
            return deleted

    except Exception as e:
        logger.error(f"[RAG_CACHE] Error invalidating cache: {e}")
        return 0