import httpx
import json
import logging
from typing import List
# Import settings mundur satu tingkat karena sekarang kita ada di folder services/
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_VECTOR")

async def get_text_embedding(text: str) -> List[float]:
    """
    Menembak API Ollama secara asinkronus untuk mengubah teks mentah dokumen
    menjadi array embedding vektor 1024 dimensi menggunakan model nomic-embed-text.
    Diarsitekturkan di dalam layer backend/app/services/vector_service.py
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/embeddings"
    
    payload = {
        "model": settings.MODEL_EMBEDDING,
        "prompt": text,
        "options": {
            "embedding_dim": 1024  # Memaksa model memuntahkan matriks 1024 dimensi sesuai ERD DB lo
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                print(f"💥 [VECTOR] Ollama return error {response.status_code}: {response.text}")
                return []
                
            response_json = response.json()
            embedding = response_json.get("embedding")
            
            if not embedding:
                print("⚠️  [VECTOR] Response Ollama sukses tapi array embedding kosong, bolo!")
                return []
                
            # Validasi dimensi pengaman sebelum dilempar ke pgvector
            if len(embedding) != 1024:
                print(f"🚨 [VECTOR WARNING] Dimensi tidak sinkron! Terbaca: {len(embedding)}, Spek DB lo: 1024")
                
            return embedding
            
        except httpx.TimeoutException:
            print("🚨 [VECTOR] Timeout saat mencoba generate embedding ke Ollama.")
            return []
        except Exception as e:
            print(f"💥 [VECTOR CRITICAL] Error pada vector service: {str(e)}")
            return []