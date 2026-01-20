import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from ..config import settings

# Initialize embedding model
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")

def get_embedding(text):
    """Generate embedding using SentenceTransformer"""
    if not text:
        return None
    try:
        embedding = EMBEDDING_MODEL.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logging.error(f"Embedding Error: {e}")
        return None

def embedding_to_pgvector_str(embedding):
    """Convert numpy embedding to PostgreSQL vector string format"""
    if isinstance(embedding, list):
        embedding = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in embedding)}]"