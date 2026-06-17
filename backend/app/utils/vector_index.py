import logging

logger = logging.getLogger("cakra.db")


async def setup_hnsw_index():
    from backend.app.core.database import db_pool

    migration_sql = """
    CREATE INDEX IF NOT EXISTS idx_dokumen_chunk_embedding_hnsw
    ON dokumen_chunk 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
    
    ANALYZE dokumen_chunk;
    """

    if db_pool is None:
        logger.error("❌ [INDEX] Database pool belum diinisialisasi!")
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(migration_sql)

        logger.info("✅ [INDEX] HNSW index created on dokumen_chunk.embedding")

        async with db_pool.acquire() as conn:
            indexes = await conn.fetch(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'dokumen_chunk'
                AND indexname LIKE '%hnsw%'
            """
            )

            if indexes:
                logger.info(f"✅ [INDEX] HNSW index verified: {len(indexes)} index(es)")
                for idx in indexes:
                    logger.debug(f"   - {idx['indexname']}")

    except Exception as e:
        logger.warning(f"⚠️ [INDEX] HNSW setup error (may already exist): {e}")


async def get_index_info():
    from backend.app.core.database import db_pool

    if db_pool is None:
        return []

    try:
        async with db_pool.acquire() as conn:
            indexes = await conn.fetch(
                """
                SELECT 
                    indexname,
                    indexdef,
                    idx_scan as scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched,
                    pg_size_pretty(pg_relation_size(indexrelid)) as size
                FROM pg_stat_user_indexes
                WHERE relname = 'dokumen_chunk'
                ORDER BY idx_scan DESC
            """
            )
            return indexes

    except Exception as e:
        logger.error(f"❌ [INDEX] Failed to get index info: {e}")
        return []


async def optimize_vector_search():
    from backend.app.core.database import db_pool

    if db_pool is None:
        return None

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("VACUUM ANALYZE dokumen_chunk")
            logger.info("✅ [OPTIMIZE] VACUUM ANALYZE completed")

            stats = await conn.fetchrow(
                """
                SELECT 
                    count(*) as total_chunks,
                    pg_size_pretty(pg_relation_size('dokumen_chunk'::regclass)) as table_size,
                    pg_size_pretty(pg_total_relation_size('dokumen_chunk'::regclass)) as total_with_indexes
                FROM dokumen_chunk
            """
            )

            if stats:
                logger.info(
                    f"📊 [STATS] {stats['total_chunks']} chunks | "
                    f"Table: {stats['table_size']} | "
                    f"Total: {stats['total_with_indexes']}"
                )

            return stats

    except Exception as e:
        logger.error(f"❌ [OPTIMIZE] Optimization failed: {e}")
        return None
