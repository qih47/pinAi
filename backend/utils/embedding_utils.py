import numpy as np
from sentence_transformers import SentenceTransformer
from backend.config.settings import settings


class EmbeddingManager:
    def __init__(self):
        self.model = SentenceTransformer("BAAI/bge-m3")

    def get_embedding(self, text: str) -> list:
        """Generate embedding for text using SentenceTransformer"""
        if not text:
            return None
        try:
            # Generate embedding using SentenceTransformer
            embedding = self.model.encode(text, normalize_embeddings=True)
            # Convert from numpy array to list for asyncpg compatibility
            return embedding.tolist()
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None

    def embedding_to_pgvector_str(self, embedding: list) -> str:
        """Convert embedding numpy to string format vector PostgreSQL"""
        emb_array = np.array(embedding)
        return f"[{','.join(f'{val:.8f}' for val in emb_array)}]"


# Global instance
embedding_manager = EmbeddingManager()