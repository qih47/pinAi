import httpx
import logging
from typing import List
from backend.app.core.config import settings
from backend.app.core.llm_client import get_shared_client

logger = logging.getLogger("CAKRA_VECTOR")


class VectorService:
    """
    Service Layer untuk komputasi vektor mxbai-embed-large via Ollama.
    Native 1024 dimensi, dioptimalkan untuk retrieval dokumen formal Indonesia.
    """

    def __init__(self):
        logger.info("[VECTOR_SERVICE_INIT] mxbai-embed-large engine initialized.")

    async def _call_ollama_embedding(self, prompt: str) -> List[float]:
        """
        Panggil Ollama embedding API. mxbai-embed-large tidak butuh options tambahan
        karena 1024 dimensi sudah native dari model-nya.
        """
        url = f"{settings.OLLAMA_BASE_URL}/api/embeddings"

        payload = {
            "model": settings.MODEL_EMBEDDING,
            "prompt": prompt,
        }

        client = get_shared_client()
        try:
            response = await client.post(url, json=payload, timeout=90.0)

            if response.status_code != 200:
                logger.error(
                    f"[VECTOR_OLLAMA_ERROR] Ollama error {response.status_code}: {response.text}"
                )
                return []

            response_json = response.json()
            embedding = response_json.get("embedding")

            if not embedding:
                logger.warning("[VECTOR_OLLAMA_EMPTY] Empty embedding returned from Ollama")
                return []

            # Validasi dimensi — mxbai harus 1024
            if len(embedding) != 1024:
                logger.error(
                    f"[VECTOR_DIMENSION_ERROR] Dimension error! Expected 1024, got {len(embedding)}. "
                    f"Pastikan MODEL_EMBEDDING=mxbai-embed-large di .env"
                )
                return []

            return embedding

        except httpx.TimeoutException:
            logger.error("[VECTOR_TIMEOUT] Timeout generating embedding mxbai.")
            return []
        except Exception as e:
            logger.error(f"[VECTOR_CRITICAL_ERROR] Error: {str(e)}")
            return []

    async def get_text_embedding(self, text: str) -> List[float]:
        """
        Untuk INGESTION dokumen ke database.
        mxbai tidak butuh prefix khusus saat ingestion.
        """
        # Truncate jika terlalu panjang — mxbai optimal di bawah 512 token (~2000 karakter)
        if len(text) > 800:  # ~512 token untuk teks Indonesia
            text = text[:800]
            logger.warning(
                "[VECTOR_TRUNCATION_WARNING] Text truncated to 800 chars for ingestion embedding."
            )
        return await self._call_ollama_embedding(text)

    async def get_query_embedding(self, query: str) -> List[float]:
        """
        Untuk runtime RAG — query user saat pencarian.
        mxbai-embed-large direkomendasikan menggunakan prefix 'Represent this sentence for searching relevant passages:'
        untuk query (bukan untuk dokumen saat ingestion).
        """
        from backend.app.utils.embedding_cache import get_embedding_cache
        cache = get_embedding_cache()
        cached_embedding = cache.get(query)
        if cached_embedding:
            logger.info(f"[VECTOR_CACHE_HIT] Embedding hit from cache for query: {query[:50]}")
            return cached_embedding

        prefixed_query = (
            f"Represent this sentence for searching relevant passages: {query}"
        )
        if len(prefixed_query) > 800:
            prefixed_query = prefixed_query[:800]
        
        embedding = await self._call_ollama_embedding(prefixed_query)
        if embedding:
            cache.put(query, embedding)
            logger.info(f"[VECTOR_CACHE_MISS] Embedding generated and cached for query: {query[:50]}")
        return embedding


vector_service = VectorService()
