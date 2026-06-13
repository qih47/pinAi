"""
B13 — HNSW Vector Index Optimization
Create HNSW index untuk pgvector queries pada dokumen_chunk table.
"""

import logging

logger = logging.getLogger("cakra.db")


async def setup_hnsw_index():
    """
    Create HNSW index pada dokumen_chunk.embedding untuk fast vector search.
    
    HNSW (Hierarchical Navigable Small World) adalah algoritma ANN yang lebih cepat
    dibanding sequential scan, terutama untuk dataset besar (>10k rows).
    
    Parameters:
    - m=16: Maximum connections per node (balance antara akurasi dan performa)
    - ef_construction=64: Size of dynamic list (higher = more accurate, slower to build)
    
    Run ini sekali saat startup atau migration.
    """
    from backend.app.core.database import get_db_pool
    
    migration_sql = """
    -- B13: HNSW Vector Index Optimization
    -- Create index pada embedding column untuk fast cosine similarity search
    
    CREATE INDEX IF NOT EXISTS idx_dokumen_chunk_embedding_hnsw
    ON dokumen_chunk 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
    
    -- Optional: Drop old sequential scan index jika ada
    -- DROP INDEX IF EXISTS idx_dokumen_chunk_embedding;
    
    -- Analyze table untuk update query planner statistics
    ANALYZE dokumen_chunk;
    """
    
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(migration_sql)
        
        logger.info(
            "✅ [INDEX] HNSW index created on dokumen_chunk.embedding"
        )
        
        # Verify index creation
        async with pool.acquire() as conn:
            indexes = await conn.fetch("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'dokumen_chunk'
                AND indexname LIKE '%hnsw%'
            """)
            
            if indexes:
                logger.info(f"✅ [INDEX] HNSW index verified: {len(indexes)} index(es)")
                for idx in indexes:
                    logger.debug(f"   - {idx['indexname']}")
    
    except Exception as e:
        logger.warning(f"⚠️ [INDEX] HNSW setup error (may already exist): {e}")


async def get_index_info():
    """Get information tentang existing indexes pada dokumen_chunk."""
    from backend.app.core.database import get_db_pool
    
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            # Get all indexes
            indexes = await conn.fetch("""
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
            """)
            
            return indexes
    
    except Exception as e:
        logger.error(f"❌ [INDEX] Failed to get index info: {e}")
        return []


async def optimize_vector_search():
    """
    Run optimization commands untuk vector search:
    1. CLUSTER table by HNSW index (optional, untuk contiguous storage)
    2. VACUUM ANALYZE
    3. Get statistics
    """
    from backend.app.core.database import get_db_pool
    
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            # VACUUM ANALYZE untuk update statistics
            await conn.execute("VACUUM ANALYZE dokumen_chunk")
            logger.info("✅ [OPTIMIZE] VACUUM ANALYZE completed")
            
            # Get statistics
            stats = await conn.fetchrow("""
                SELECT 
                    count(*) as total_chunks,
                    pg_size_pretty(pg_relation_size('dokumen_chunk'::regclass)) as table_size,
                    pg_size_pretty(pg_total_relation_size('dokumen_chunk'::regclass)) as total_with_indexes
                FROM dokumen_chunk
            """)
            
            if stats:
                logger.info(f"📊 [STATS] {stats['total_chunks']} chunks | "
                           f"Table: {stats['table_size']} | "
                           f"Total: {stats['total_with_indexes']}")
            
            return stats
    
    except Exception as e:
        logger.error(f"❌ [OPTIMIZE] Optimization failed: {e}")
        return None
