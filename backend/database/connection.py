import asyncpg
from typing import Optional
from backend.config.settings import settings


class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.login_pool: Optional[asyncpg.Pool] = None

    async def create_pools(self):
        """Create connection pools for both databases"""
        self.pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        self.login_pool = await asyncpg.create_pool(
            host=settings.DB_LOGIN_HOST,
            port=settings.DB_LOGIN_PORT,
            database=settings.DB_LOGIN_NAME,
            user=settings.DB_LOGIN_USER,
            password=settings.DB_LOGIN_PASSWORD,
            min_size=2,
            max_size=10,
            command_timeout=60
        )

    async def close_pools(self):
        """Close both connection pools"""
        if self.pool:
            await self.pool.close()
        if self.login_pool:
            await self.login_pool.close()

    async def get_rag_connection(self):
        """Get connection from RAG database pool"""
        return await self.pool.acquire()

    async def release_rag_connection(self, conn):
        """Release RAG database connection back to pool"""
        await self.pool.release(conn)

    async def get_login_connection(self):
        """Get connection from login database pool"""
        return await self.login_pool.acquire()

    async def release_login_connection(self, conn):
        """Release login database connection back to pool"""
        await self.login_pool.release(conn)


# Global instance
db_manager = DatabaseManager()