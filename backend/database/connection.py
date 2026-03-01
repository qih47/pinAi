import asyncpg
from typing import Optional
from ..core.config import DB_RAG_CONFIG, DB_LOGIN_CONFIG


class DatabaseManager:
    def __init__(self):
        self.rag_pool: Optional[asyncpg.Pool] = None
        self.login_pool: Optional[asyncpg.Pool] = None

    async def init_rag_pool(self):
        """Initialize connection pool for RAG database"""
        self.rag_pool = await asyncpg.create_pool(
            host=DB_RAG_CONFIG["host"],
            database=DB_RAG_CONFIG["database"],
            user=DB_RAG_CONFIG["user"],
            password=DB_RAG_CONFIG["password"],
            port=DB_RAG_CONFIG["port"],
            min_size=5,
            max_size=20,
            command_timeout=60
        )

    async def init_login_pool(self):
        """Initialize connection pool for login database"""
        self.login_pool = await asyncpg.create_pool(
            host=DB_LOGIN_CONFIG["host"],
            database=DB_LOGIN_CONFIG["database"],
            user=DB_LOGIN_CONFIG["user"],
            password=DB_LOGIN_CONFIG["password"],
            port=DB_LOGIN_CONFIG["port"],
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    
    async def close_pools(self):
        """Close both connection pools"""
        if self.rag_pool:
            await self.rag_pool.close()
        if self.login_pool:
            await self.login_pool.close()

    async def get_rag_connection(self) -> asyncpg.Pool:
        """Get the RAG pool"""
        if not self.rag_pool:
            await self.init_rag_pool()
        return self.rag_pool

    async def get_login_connection(self) -> asyncpg.Pool:
        """Get the login pool"""
        if not self.login_pool:
            await self.init_login_pool()
        return self.login_pool


# Global database manager instance
db_manager = DatabaseManager()