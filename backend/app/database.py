import asyncpg
import logging
from contextlib import asynccontextmanager  # Wajib untuk handle yield dalam async with
from .config import settings

# Connection pools
db_pool = None
hris_pool = None


async def init_db():
    """Initialize database connection pools"""
    global db_pool, hris_pool

    try:
        # Main database pool
        db_pool = await asyncpg.create_pool(
            host=settings.db_host,
            database=settings.db_database,
            user=settings.db_user,
            password=settings.db_password,
            min_size=5,
            max_size=20,
            command_timeout=60,
        )

        # HRIS database pool
        hris_pool = await asyncpg.create_pool(
            host=settings.db_login_host,
            database=settings.db_login_database,
            user=settings.db_login_user,
            password=settings.db_login_password,
            min_size=3,
            max_size=10,
            command_timeout=60,
        )

        print(f"✅ Database pools initialized")
    except Exception as e:
        print(f"❌ Failed to initialize database pools: {e}")
        raise e


@asynccontextmanager
async def get_db():
    """
    Get main database connection.
    Menggunakan @asynccontextmanager agar bisa dipanggil dengan:
    async with get_db() as conn:
    """
    if db_pool is None:
        logging.error(
            "Database pool (db_pool) is None. Pastikan init_db() sudah dipanggil."
        )
        raise RuntimeError("Database pool not initialized")

    async with db_pool.acquire() as connection:
        yield connection


@asynccontextmanager
async def get_hris_db():
    """
    Get HRIS database connection.
    """
    if hris_pool is None:
        logging.error("HRIS pool is None. Pastikan init_db() sudah dipanggil.")
        raise RuntimeError("HRIS pool not initialized")

    async with hris_pool.acquire() as connection:
        yield connection


def embedding_to_pgvector_str(embedding):
    """Convert numpy embedding to PostgreSQL vector string format"""
    import numpy as np

    if isinstance(embedding, list):
        embedding = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in embedding)}]"
