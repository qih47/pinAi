from fastapi import APIRouter
import aiohttp
from ..config import settings

router = APIRouter()

@router.get("/health")
async def health():
    """Health check endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.ollama_url,
                json={
                    "model": settings.primary_model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
                timeout=5
            ) as resp:
                ollama_status = resp.status == 200

        return {
            "status": "healthy",
            "service": "CAKRA AI Pro",
            "model": settings.primary_model,
            "ollama_connected": ollama_status,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }