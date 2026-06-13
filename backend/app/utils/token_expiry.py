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
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(migration_sql)
        print("✅ [MIGRATION] Token expiry schema setup completed")
    except Exception as e:
        print(f"⚠️ [MIGRATION] Token expiry schema already exists or error: {e}")


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
            SET is_active = FALSE
            WHERE expires_at < NOW() AND is_active = TRUE
        """)
        
        print("✅ [CLEANUP] Expired sessions marked inactive")


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
                SET expires_at = NOW() + INTERVAL '{extension_hours} hours'
                WHERE npp = $1 AND is_active = TRUE
                RETURNING id
            """, npp)
            
            return result is not None
    except Exception as e:
        print(f"❌ [TOKEN] Extend session failed for {npp}: {e}")
        return False


def get_token_expiry_time(hours: int = 8) -> datetime:
    """
    Helper function untuk get expiry timestamp.
    
    Args:
        hours: Token validity duration (default: 8)
    
    Returns:
        datetime: Expiry timestamp
    """
    return datetime.utcnow() + timedelta(hours=hours)


async def validate_token_expiry(npp: str, token: str) -> bool:
    """
    Validate apakah token user sudah expired.
    Call ini di middleware atau verify-session endpoint.
    
    Args:
        npp: User NPP
        token: Session token
    
    Returns:
        bool: True jika token masih valid, False jika expired
    """
    from backend.app.core.database import get_db_pool
    
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT id FROM session_login
                WHERE npp = $1 
                  AND token = $2
                  AND is_active = TRUE
                  AND expires_at > NOW()
            """, npp, token)
            
            return result is not None
    except Exception as e:
        print(f"❌ [TOKEN] Validate expiry failed: {e}")
        return False
