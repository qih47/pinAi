from app.core.database import get_db


async def get_db_conn():
    async with get_db() as conn:
        yield conn
