import logging
import asyncio
from typing import List
from functools import lru_cache

logger = logging.getLogger("CAKRA_RERANKER")


@lru_cache(maxsize=1)
def _load_reranker():
    """
    Lazy load BAAI/bge-reranker-v2-m3 sekali saat pertama dipanggil.
    lru_cache(maxsize=1) memastikan model tidak di-reload ulang antar request.
    Model sudah tersedia lokal di cache HuggingFace.
    """
    from sentence_transformers import CrossEncoder
    logger.info("[RERANKER_MODEL_LOAD_START] Loading BAAI/bge-reranker-v2-m3 CrossEncoder model.")
    model = CrossEncoder(
        "BAAI/bge-reranker-v2-m3",
        max_length=512,       # cukup untuk chunk dokumen Pindad
        device="cuda",        # GPU — model kecil ~570MB, tidak signifikan ngaruhi VRAM gemma4:e4b
        local_files_only=True
    )
    logger.info("[RERANKER_MODEL_LOAD_SUCCESS] BAAI/bge-reranker-v2-m3 model loaded successfully.")
    return model


class RerankerService:
    """
    Cross-Encoder Re-ranker menggunakan BAAI/bge-reranker-v2-m3.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        logger.info("[RERANKER_SERVICE_INIT] BGE Cross-Encoder Engine ready.")

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================

    async def compute_scores(
        self, query: str, corpus_texts: List[str]
    ) -> List[float]:
        """
        Hitung cross-encoder relevance score tiap teks terhadap query.

        Inference dijalankan di thread pool (run_in_executor) agar tidak
        memblokir event loop FastAPI saat model berjalan di CPU.
        """
        if not corpus_texts:
            return []

        logger.info(
            f"[RERANKER_SCORING_START] BGE scoring {len(corpus_texts)} candidates for query: \"{query[:60]}\""
        )

        try:
            # Gunakan lock agar PyTorch model.predict tidak dijalankan concurrent oleh multi-thread
            async with self._lock:
                # Jalankan inference sinkron di thread pool — tidak blokir event loop
                scores = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._run_inference,
                    query,
                    corpus_texts,
                )

            logger.info(
                f"[RERANKER_SCORING_COMPLETE] Completed. Max score: {max(scores):.4f}, Min score: {min(scores):.4f}"
            )
            return scores

        except Exception as e:
            logger.error(
                f"[RERANKER_SCORING_ERROR] BGE inference failed: {str(e)}. Fallback to uniform scores."
            )
            # Fallback aman: skor merata
            n = len(corpus_texts)
            return [1.0 / n] * n

    # ==========================================================================
    # INFERENCE (SYNC — dijalankan via run_in_executor)
    # ==========================================================================

    def _run_inference(self, query: str, corpus_texts: List[str]) -> List[float]:
        """
        Jalankan cross-encoder inference secara sinkron.
        """
        model = _load_reranker()

        # Format input: list of (query, doc) pairs — standar CrossEncoder
        pairs = [(query, doc[:1000]) for doc in corpus_texts]

        # CrossEncoder.predict() mengembalikan numpy array of float
        raw_scores = model.predict(pairs, show_progress_bar=False)

        # Konversi numpy float → Python float + Sigmoid (mengubah raw logit menjadi 0.0 - 1.0 probabilitas)
        import math
        scores = []
        for s in raw_scores:
            val = float(s)
            # Sigmoid function: 1 / (1 + exp(-val))
            prob = 1.0 / (1.0 + math.exp(-val))
            scores.append(prob)

        for idx, p in enumerate(scores):
            logger.debug(f"   [RERANKER] Kandidat #{idx} → BGE score (prob): {p:.4f}")

        return scores


# Singleton
reranker_service = RerankerService()
