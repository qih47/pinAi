"""
B9 — Query Embedding Caching (LRU Cache)
Caching embedding query untuk menghindari redundant Ollama calls.
"""

import hashlib
import time
from typing import List, Optional, Dict
from functools import lru_cache


class EmbeddingCache:
    """LRU cache for query embeddings dengan TTL support."""
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        """
        Args:
            max_size: Maximum cache entries (default: 500)
            ttl_seconds: Time-to-live untuk cached entries (default: 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple] = {}  # {hash: (embedding, timestamp)}
        self.hits = 0
        self.misses = 0
    
    @staticmethod
    def _hash_query(query: str) -> str:
        """Generate hash dari query untuk cache key."""
        return hashlib.sha256(query.encode()).hexdigest()
    
    def get(self, query: str) -> Optional[List[float]]:
        """
        Ambil embedding dari cache jika ada dan belum expired.
        
        Args:
            query: Query string
            
        Returns:
            List[float] embedding atau None jika tidak ada / expired
        """
        query_hash = self._hash_query(query)
        
        if query_hash not in self.cache:
            self.misses += 1
            return None
        
        embedding, timestamp = self.cache[query_hash]
        
        # Cek TTL
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[query_hash]
            self.misses += 1
            return None
        
        self.hits += 1
        return embedding
    
    def put(self, query: str, embedding: List[float]) -> None:
        """
        Simpan embedding ke cache dengan TTL.
        
        Args:
            query: Query string
            embedding: Embedding vector [float, float, ...]
        """
        # Jika cache sudah penuh, clear oldest entry (simple FIFO)
        if len(self.cache) >= self.max_size:
            # Hapus entry tertua (minimal timestamp)
            oldest_key = min(self.cache.keys(), 
                            key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        query_hash = self._hash_query(query)
        self.cache[query_hash] = (embedding, time.time())
    
    def clear(self) -> None:
        """Clear seluruh cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def cleanup_expired(self) -> int:
        """
        Hapus semua expired entries.
        
        Returns:
            Jumlah entries yang di-cleanup
        """
        current_time = time.time()
        expired_keys = [
            k for k, (_, ts) in self.cache.items()
            if current_time - ts > self.ttl_seconds
        ]
        for k in expired_keys:
            del self.cache[k]
        return len(expired_keys)
    
    def stats(self) -> dict:
        """Return cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0
        return {
            "total_entries": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "utilization_percent": (len(self.cache) / self.max_size) * 100,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2)
        }


# Singleton instance
_embedding_cache_instance = None


def get_embedding_cache() -> EmbeddingCache:
    """Get singleton embedding cache instance."""
    global _embedding_cache_instance
    if _embedding_cache_instance is None:
        _embedding_cache_instance = EmbeddingCache(max_size=500, ttl_seconds=3600)
    return _embedding_cache_instance


def invalidate_embedding_cache(query: str) -> None:
    """Manually invalidate cache entry untuk query tertentu."""
    cache = get_embedding_cache()
    query_hash = cache._hash_query(query)
    if query_hash in cache.cache:
        del cache.cache[query_hash]
