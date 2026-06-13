"""
B10 — Session Token Expiry Management
Auto-expire session tokens setelah 8 jam (satu shift kerja).
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional


async def setup_token_expiry_migration():
    """
    Migration SQL untuk menambahkan expires_at column ke session_login table.
    
    Run this once saat startup untuk ensure schema is correct.
    """
    from backend.app.core.database import get_db_pool
    
    migration_sql = """
    -- B10: Token Expiry Management
    ALTER TABLE session_login
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '8 hours');
    
    -- Index untuk efficient cleanup query
    CREATE INDEX IF NOT EXISTS idx_session_login_expires_at 
    ON session_login(expires_at);
    
    -- Update kolom untuk existing rows (set expiry 8 jam dari sekarang)
    UPDATE session_login 
    SET expires_at = NOW() + INTERVAL '8 hours'
    WHERE expires_at IS NULL OR expires_at < NOW();
    """
    
    try:
        import logging
        logger = logging.getLogger("CAKRA_TOKEN_EXPIRY")
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(migration_sql)
        logger.info("[TOKEN_EXPIRY] Schema setup completed")
    except Exception as e:
        import logging
        logger = logging.getLogger("CAKRA_TOKEN_EXPIRY")
        logger.warning(f"[TOKEN_EXPIRY] Schema already exists or error: {e}")


async def cleanup_expired_sessions():
    """
    Background task untuk delete expired sessions (soft delete).
    Run ini periodik (misalnya setiap 30 menit).
    """
    from backend.app.core.database import get_db_pool
    
    pool = get_db_pool()
    async with pool.acquire() as conn:
        # Hapus token yang sudah expired
        await conn.execute("""
            UPDATE session_login
            SET is_login = FALSE, session_token = ''
            WHERE expires_at < NOW() AND is_login = TRUE
        """)
        
        logger.info("[TOKEN_EXPIRY] Expired sessions marked inactive")


async def extend_session_expiry(npp: str, extension_hours: int = 8) -> bool:
    """
    Extend session expiry untuk user yang masih aktif.
    Call ini setiap kali ada request dari authenticated user.
    
    Args:
        npp: User NPP
        extension_hours: Jam extension (default: 8)
    
    Returns:
        bool: Success flag
    """
    from backend.app.core.database import get_db_pool
    
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(f"""
                UPDATE session_login
                SET expires_at = NOW() + INTERVAL '{extension_hours} hours',
                    last_activity = CURRENT_TIMESTAMP
                WHERE npp = $1 AND is_login = TRUE
            """, npp)
            
            return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"[TOKEN_EXPIRY] Extend session failed for {npp}: {e}")
        return False


async def extend_session_expiry_by_token(token: str, extension_hours: int = 8):
    """
    Extend session expiry menggunakan token.
    
    Args:
        token: Session token
        extension_hours: Jam extension (default: 8)
        
    Returns:
        datetime: Expiry timestamp baru jika sukses, else None
    """
    from backend.app.core.database import get_db_pool
    
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                UPDATE session_login
                SET expires_at = NOW() + INTERVAL '{extension_hours} hours',
                    last_activity = CURRENT_TIMESTAMP
                WHERE session_token = $1 AND is_login = TRUE
                RETURNING expires_at
            """, token)
            
            if row:
                return row['expires_at']
            return None
    except Exception as e:
        logger.error(f"[TOKEN_EXPIRY] Extend session by token failed: {e}")
        return None


def get_token_expiry_time(hours: int = 8) -> datetime:
    """
    Helper function untuk get expiry timestamp.
    
    Args:
        hours: Token validity duration (default: 8)
    
    Returns:
        datetime: Expiry timestamp
    """
    from datetime import datetime, timedelta
    return datetime.utcnow() + timedelta(hours=hours)


async def validate_token_expiry(token: str) -> bool:
    """
    Validate apakah token user sudah expired.
    Call ini di middleware atau verify-session endpoint.
    
    Args:
        token: Session token
    
    Returns:
        bool: True jika token masih valid, False jika expired
    """
    from backend.app.core.database import get_db_pool
    
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT npp FROM session_login
                WHERE session_token = $1 
                  AND is_login = TRUE
                  AND expires_at > NOW()
            """, token)
            
            return result is not None
    except Exception as e:
        logger.error(f"[TOKEN_EXPIRY] Validate expiry failed: {e}")
        return False
