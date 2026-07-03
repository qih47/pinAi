import asyncio
from backend.app.core.database import get_peraturan_db, init_db_pool
import aiomysql

async def main():
    await init_db_pool()
    async with get_peraturan_db() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            # test offset 60
            await cursor.execute("SELECT b.id_berita FROM berita b ORDER BY b.id_berita DESC LIMIT %s OFFSET %s", [20, 60])
            rows = await cursor.fetchall()
            print(f"Offset 60 returned {len(rows)} rows.")
            
            # test total
            await cursor.execute("SELECT COUNT(*) AS total FROM berita b")
            total = await cursor.fetchone()
            print(f"Total: {total['total']}")

asyncio.run(main())
