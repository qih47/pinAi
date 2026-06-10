import httpx
import logging
from typing import List
from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_VECTOR")


class VectorService:
    """
    Service Layer untuk komputasi vektor mxbai-embed-large via Ollama.
    Native 1024 dimensi, dioptimalkan untuk retrieval dokumen formal Indonesia.
    """

    def __init__(self):
        logger.info("📡 [VECTOR SERVICE] mxbai-embed-large Engine aktif.")

    async def _call_ollama_embedding(self, prompt: str) -> List[float]:
        """
        Panggil Ollama embedding API. mxbai-embed-large tidak butuh options tambahan
        karena 1024 dimensi sudah native dari model-nya.
        """
        url = f"{settings.OLLAMA_BASE_URL}/api/embeddings"

        payload = {
            "model": settings.MODEL_EMBEDDING,
            "prompt": prompt,
            # Tidak ada 'options' — mxbai sudah fix 1024 dim, tidak perlu dipaksa
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload)

                if response.status_code != 200:
                    logger.error(
                        f"💥 [VECTOR] Ollama error {response.status_code}: {response.text}"
                    )
                    return []

                response_json = response.json()
                embedding = response_json.get("embedding")

                if not embedding:
                    logger.warning("⚠️  [VECTOR] Embedding kosong dari Ollama!")
                    return []

                # Validasi dimensi — mxbai harus 1024
                if len(embedding) != 1024:
                    logger.error(
                        f"💥 [VECTOR] Dimensi salah! Expected 1024, got {len(embedding)}. "
                        f"Pastikan MODEL_EMBEDDING=mxbai-embed-large di .env"
                    )
                    return []

                return embedding

            except httpx.TimeoutException:
                logger.error("🚨 [VECTOR] Timeout generate embedding mxbai.")
                return []
            except Exception as e:
                logger.error(f"💥 [VECTOR CRITICAL] Error: {str(e)}")
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
                "⚠️  [VECTOR] Teks dipotong ke 2000 char untuk ingestion embedding."
            )
        return await self._call_ollama_embedding(text)

    async def get_query_embedding(self, query: str) -> List[float]:
        """
        Untuk runtime RAG — query user saat pencarian.
        mxbai-embed-large direkomendasikan menggunakan prefix 'Represent this sentence for searching relevant passages:'
        untuk query (bukan untuk dokumen saat ingestion).
        """
        prefixed_query = (
            f"Represent this sentence for searching relevant passages: {query}"
        )
        if len(prefixed_query) > 800:
            prefixed_query = prefixed_query[:800]
        return await self._call_ollama_embedding(prefixed_query)


vector_service = VectorService()
