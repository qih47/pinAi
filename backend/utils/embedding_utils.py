import numpy as np
from sentence_transformers import SentenceTransformer
from backend.core.config import settings

# Initialize embedding model
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")

def embedding_to_pgvector_str(embedding):
    """Konversi embedding numpy ke string format vector PostgreSQL secara efisien."""
    emb_array = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in emb_array)}]"

def get_embedding(text: str):
    """Generate embedding for a single text using bge-m3 model."""
    # Normalize embeddings for cosine similarity with pgvector
    embedding = EMBEDDING_MODEL.encode([text], normalize_embeddings=True)[0].tolist()
    return embedding

def get_embeddings(texts: list):
    """Generate embeddings for multiple texts using bge-m3 model."""
    # Normalize embeddings for cosine similarity with pgvector
    embeddings = EMBEDDING_MODEL.encode(texts, normalize_embeddings=True).tolist()
    return embeddings