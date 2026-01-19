import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Optional


# Initialize embedding model
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")


def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for text using SentenceTransformer"""
    if not text:
        return None
    try:
        # Generate embedding using SentenceTransformer
        embedding = EMBEDDING_MODEL.encode(text, normalize_embeddings=True)
        # Convert from numpy array to list for JSON serialization
        return embedding.tolist()
    except Exception as e:
        print(f"Embedding Error: {e}")
        return None


def embedding_to_pgvector_str(embedding: List[float]) -> str:
    """Convert embedding numpy array to string format vector PostgreSQL."""
    emb_array = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in emb_array)}]"