import asyncpg
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_DATABASE")

# Global connection pools
db_pool = None
hris_pool = None

async def init_db_pool():
    """Inisialisasi dual-database connection pools saat startup"""
    global db_pool, hris_pool
    try:
        # 1. Main Database Pool (ragdb)
        db_pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            database=settings.DB_DATABASE,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            min_size=5,
            max_size=20,
            command_timeout=60.0,
        )

        # 2. HRIS Database Pool (Login DB)
        hris_pool = await asyncpg.create_pool(
            host=settings.DB_LOGIN_HOST,
            database=settings.DB_LOGIN_DATABASE,
            user=settings.DB_LOGIN_USER,
            password=settings.DB_LOGIN_PASSWORD,
            min_size=3,
            max_size=10,
            command_timeout=60.0,
        )

        logger.info("[DB_CONNECTION_POOL_INIT] Dual-database pools (ragdb & hris) initialized successfully.")
    except Exception as e:
        logger.error(f"[DB_CONNECTION_POOL_ERROR] Failed to initialize database pools: {e}")
        raise e

async def close_db_pool():
    """Menutup pool koneksi saat aplikasi shutdown"""
    global db_pool, hris_pool
    if db_pool:
        await db_pool.close()
    if hris_pool:
        await hris_pool.close()
    logger.info("🛑 [DATABASE] All database connection pools closed clean.")

@asynccontextmanager
async def get_db():
    """Get main database (ragdb) connection context manager"""
    global db_pool
    if db_pool is None:
        logging.error("Database pool (db_pool) is None. Pastikan init_db_pool() sudah jalan.")
        raise RuntimeError("Main database pool not initialized")
    
    async with db_pool.acquire() as connection:
        yield connection

@asynccontextmanager
async def get_hris_db():
    """Get HRIS database connection context manager"""
    global hris_pool
    if hris_pool is None:
        logging.error("HRIS pool (hris_pool) is None. Pastikan init_db_pool() sudah jalan.")
        raise RuntimeError("HRIS database pool not initialized")
    
    async with hris_pool.acquire() as connection:
        yield connection

def embedding_to_pgvector_str(embedding) -> str:
    """Convert embedding list/numpy array to PostgreSQL vector format string"""
    import numpy as np
    if isinstance(embedding, list):
        embedding = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in embedding)}]"