# utils/embeddings.py
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Initialize embedding model
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")
logger = logging.getLogger(__name__)

# Gunakan thread pool untuk CPU-bound task
_embedding_executor = ThreadPoolExecutor(max_workers=2)

def _sync_get_embedding(text):
    """Sync version for executor"""
    if not text:
        return None
    try:
        embedding = EMBEDDING_MODEL.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Embedding Error: {e}")
        return None

async def get_embedding(text):
    """Async wrapper for embedding generation"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_embedding_executor, _sync_get_embedding, text)

def embedding_to_pgvector_str(embedding):
    """Convert numpy embedding to PostgreSQL vector string format"""
    if isinstance(embedding, list):
        embedding = np.array(embedding)
    return f"[{','.join(f'{val:.8f}' for val in embedding)}]"