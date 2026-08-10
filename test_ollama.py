import asyncio
import json
import httpx

async def main():
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "gemma4:31b",
        "messages": [
            {"role": "user", "content": "cuy dolar ke idr sekarang berapa?"}
        ],
        "stream": False
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=60.0)
        print(resp.json())

asyncio.run(main())
