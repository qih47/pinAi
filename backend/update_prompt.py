import asyncio
from app.core.database import init_db_pool, close_db_pool, get_db
from app.services.pipeline.prompts.email_prompts import EMAIL_SYSTEM_PROMPT

async def main():
    await init_db_pool()
    async with get_db() as conn:
        await conn.execute(
            "UPDATE system_prompts SET template = $1 WHERE name = 'RESPONSE_PROMPT_EMAIL'",
            EMAIL_SYSTEM_PROMPT
        )
        print("Prompt updated successfully in PostgreSQL")
    await close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
