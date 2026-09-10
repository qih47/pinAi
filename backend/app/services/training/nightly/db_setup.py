"""
CAKRA AI — Nightly Training DB Setup & Dedicated Connection Pool (RAGDB ONLY)
=============================================================================
Menyediakan koneksi khusus yang 100% eksklusif ke PostgreSQL (ragdb) di localhost.
TIDAK PERNAH menyentuh database lain (MySQL, HRIS, Payroll, dll).
"""

import logging
import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_NIGHTLY_DB")

# Dedicated pool khusus ragdb
_ragdb_pool: asyncpg.Pool = None

async def init_ragdb_pool() -> asyncpg.Pool:
    global _ragdb_pool
    if _ragdb_pool is None:
        logger.info(f"🔌 [NIGHTLY_DB] Menginisialisasi connection pool eksklusif ke ragdb ({settings.DB_HOST}:{settings.DB_DATABASE})...")
        _ragdb_pool = await asyncpg.create_pool(
            host=settings.DB_HOST or "localhost",
            database=settings.DB_DATABASE or "ragdb",
            user=settings.DB_USER or "pindadai",
            password=settings.DB_PASSWORD or "Pindad123!",
            min_size=2,
            max_size=25,
            command_timeout=15.0,
        )
    return _ragdb_pool

@asynccontextmanager
async def get_ragdb_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Context manager untuk acquire connection ke ragdb saja"""
    pool = await init_ragdb_pool()
    async with pool.acquire() as conn:
        yield conn

async def close_ragdb_pool():
    global _ragdb_pool
    if _ragdb_pool is not None:
        await _ragdb_pool.close()
        _ragdb_pool = None
        logger.info("🔌 [NIGHTLY_DB] Connection pool ragdb ditutup.")
