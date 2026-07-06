import asyncio
import asyncpg
from backend.app.core.config import settings

async def run():
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        database=settings.DB_DATABASE,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    rows = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'history_login';")
    print("COLUMNS:", [r['column_name'] for r in rows])
    await conn.close()

asyncio.run(run())
