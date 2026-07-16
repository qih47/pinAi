import asyncio
import os
import sys

# Add parent directory to path to allow importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db, init_db_pool, close_db_pool

async def migrate():
    await init_db_pool()
    async with get_db() as conn:
        print("Migrating users table...")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo_url VARCHAR(500);")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);")
        print("Migration complete.")
    await close_db_pool()

if __name__ == "__main__":
    asyncio.run(migrate())
