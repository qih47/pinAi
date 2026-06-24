import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("CAKRA_TOKEN_EXPIRY")


async def setup_token_expiry_migration():
    from backend.app.core.database import db_pool

    migration_sql = """
    ALTER TABLE session_login
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '1 month');
    
    CREATE INDEX IF NOT EXISTS idx_session_login_expires_at 
    ON session_login(expires_at);
    
    UPDATE session_login 
    SET expires_at = NOW() + INTERVAL '1 month'
    WHERE expires_at IS NULL OR expires_at < NOW();
    """

    if db_pool is None:
        logger.error("[TOKEN_EXPIRY] Database pool belum diinisialisasi!")
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(migration_sql)
        logger.info("[TOKEN_EXPIRY] Schema setup completed")
    except Exception as e:
        logger.warning(f"[TOKEN_EXPIRY] Schema already exists or error: {e}")


async def cleanup_expired_sessions():
    from backend.app.core.database import db_pool

    if db_pool is None:
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE session_login
                SET is_login = FALSE, session_token = ''
                WHERE expires_at < NOW() AND is_login = TRUE
            """
            )
        logger.info("[TOKEN_EXPIRY] Expired sessions marked inactive")
    except Exception as e:
        logger.error(f"[TOKEN_EXPIRY] Cleanup expired sessions failed: {e}")


async def extend_session_expiry(npp: str, extension_days: int = 30) -> bool:
    from backend.app.core.database import db_pool

    if db_pool is None:
        return False

    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE session_login
                SET expires_at = NOW() + ($2 || ' days')::INTERVAL,
                    last_activity = CURRENT_TIMESTAMP
                WHERE npp = $1 AND is_login = TRUE
            """,
                npp,
                str(extension_days),
            )
            return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"[TOKEN_EXPIRY] Extend session failed for {npp}: {e}")
        return False


async def extend_session_expiry_by_token(
    token: str, extension_days: int = 30
) -> Optional[datetime]:
    from backend.app.core.database import db_pool

    if db_pool is None:
        return None

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE session_login
                SET expires_at = NOW() + ($2 || ' days')::INTERVAL,
                    last_activity = CURRENT_TIMESTAMP
                WHERE session_token = $1 AND is_login = TRUE
                RETURNING expires_at
            """,
                token,
                str(extension_days),
            )
            if row:
                return row["expires_at"]
            return None
    except Exception as e:
        logger.error(f"[TOKEN_EXPIRY] Extend session by token failed: {e}")
        return None


def get_token_expiry_time(days: int = 30) -> datetime:
    return datetime.utcnow() + timedelta(days=days)


async def validate_token_expiry(token: str) -> bool:
    from backend.app.core.database import db_pool

    if db_pool is None:
        return False

    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT npp FROM session_login
                WHERE session_token = $1 
                  AND is_login = TRUE
                  AND expires_at > NOW()
            """,
                token,
            )
            return result is not None
    except Exception as e:
        logger.error(f"[TOKEN_EXPIRY] Validate expiry failed: {e}")
        return False