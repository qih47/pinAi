import asyncio
import asyncpg
import json

async def main():
    conn = await asyncpg.connect("postgresql://cakra_user:cakra_pass_999@localhost/cakradb")
    rows = await conn.fetch("SELECT role, text, thought, sources FROM chat_messages ORDER BY id DESC LIMIT 5")
    for row in rows:
        print(f"ROLE: {row['role']}")
        print(f"TEXT: {row['text'][:200]}...")
        print(f"SOURCES: {row['sources'][:50] if row['sources'] else 'None'}...")
        print("-" * 50)
    await conn.close()

asyncio.run(main())
