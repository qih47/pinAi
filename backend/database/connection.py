import asyncpg
import logging
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Connection pools
local_pool = None
login_pool = None

async def get_local_db_pool():
    global local_pool
    if local_pool is None:
        local_pool = await asyncpg.create_pool(
            host=settings.LOCAL_DB_HOST,
            database=settings.LOCAL_DB_NAME,
            user=settings.LOCAL_DB_USER,
            password=settings.LOCAL_DB_PASSWORD,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    return local_pool

async def get_login_db_pool():
    global login_pool
    if login_pool is None:
        login_pool = await asyncpg.create_pool(
            host=settings.LOGIN_DB_HOST,
            database=settings.LOGIN_DB_NAME,
            user=settings.LOGIN_DB_USER,
            password=settings.LOGIN_DB_PASSWORD,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    return login_pool

async def init_db():
    """Initialize database pools"""
    try:
        await get_local_db_pool()
        await get_login_db_pool()
        logger.info("Database pools initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database pools: {e}")
        raise

async def close_db_pools():
    """Close database pools"""
    global local_pool, login_pool
    if local_pool:
        await local_pool.close()
    if login_pool:
        await login_pool.close()
    logger.info("Database pools closed")