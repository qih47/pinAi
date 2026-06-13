"""
Database Connection Manager — Ensure proper cleanup on client disconnect
========================================================================
Manages DB connections in streaming contexts and ensures cleanup on CancelledError.
"""

import logging
import asyncio
from typing import Optional, List, Any, Callable
from contextlib import asynccontextmanager

logger = logging.getLogger("CAKRA_CONNMGR")


class StreamConnectionManager:
    """
    Tracks active DB connections dalam SSE streaming context.
    Cleanup otomatis ketika client disconnect (CancelledError).
    """

    def __init__(self):
        self.active_connections: List[Any] = []
        self._lock = asyncio.Lock()

    async def register_connection(self, conn: Any):
        """Register DB connection untuk tracking"""
        async with self._lock:
            self.active_connections.append(conn)
            logger.debug(f"📌 [CONNMGR] Registered connection (total: {len(self.active_connections)})")

    async def unregister_connection(self, conn: Any):
        """Unregister DB connection setelah selesai"""
        async with self._lock:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
                logger.debug(f"📌 [CONNMGR] Unregistered connection (total: {len(self.active_connections)})")

    async def cleanup_all(self):
        """Force cleanup semua connections saat client disconnect"""
        async with self._lock:
            count = len(self.active_connections)
            if count > 0:
                logger.warning(f"🧹 [CONNMGR] Force cleanup {count} open connections")
                # Connections akan auto-returned ke pool ketika context manager selesai
                self.active_connections.clear()

    async def get_stats(self) -> dict:
        """Get connection stats untuk monitoring"""
        async with self._lock:
            return {
                "active_connections": len(self.active_connections),
            }


class SafeStreamingContext:
    """
    Async context manager untuk SSE streaming dengan proper error handling.
    Ensures database connections di-return ke pool bahkan jika terjadi error.
    """

    def __init__(self, get_db_func: Callable):
        self.get_db_func = get_db_func
        self.connections: List[Any] = []
        self.conn_manager = StreamConnectionManager()

    async def get_connection(self):
        """
        Get database connection dengan auto-tracking.
        Akan di-cleanup otomatis saat streaming berakhir.
        """
        async with self.get_db_func() as conn:
            await self.conn_manager.register_connection(conn)
            self.connections.append(conn)
            try:
                yield conn
            finally:
                await self.conn_manager.unregister_connection(conn)

    async def cleanup(self):
        """Force cleanup semua connections"""
        await self.conn_manager.cleanup_all()
        self.connections.clear()

    async def get_stats(self) -> dict:
        """Get statistics"""
        return await self.conn_manager.get_stats()


@asynccontextmanager
async def safe_stream_context(get_db_func: Callable):
    """
    Factory untuk menciptakan SafeStreamingContext.
    Usage:
        async with safe_stream_context(get_db) as ctx:
            conn = await ctx.get_connection()
    """
    ctx = SafeStreamingContext(get_db_func)
    try:
        yield ctx
    except asyncio.CancelledError:
        logger.info("⚠️ [STREAM CTX] Client disconnect detected, cleaning up connections")
        await ctx.cleanup()
        raise
    except Exception as e:
        logger.error(f"❌ [STREAM CTX] Error in streaming context: {e}")
        await ctx.cleanup()
        raise
    finally:
        await ctx.cleanup()
