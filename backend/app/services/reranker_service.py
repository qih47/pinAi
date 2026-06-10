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
    logger.info("📦 [RERANKER] Loading BAAI/bge-reranker-v2-m3... (sekali saja)")
    model = CrossEncoder(
        "BAAI/bge-reranker-v2-m3",
        max_length=512,       # cukup untuk chunk dokumen Pindad
        device="cuda",        # GPU — model kecil ~570MB, tidak signifikan ngaruhi VRAM gemma4:e4b
    )
    logger.info("✅ [RERANKER] BAAI/bge-reranker-v2-m3 siap.")
    return model


class RerankerService:
    """
    Cross-Encoder Re-ranker menggunakan BAAI/bge-reranker-v2-m3.

    Kelebihan vs BM25:
    - Paham semantik Bahasa Indonesia (multilingual model, termasuk ID)
    - "pakaian dinas" dan "seragam kerja" dianggap relevan meski token berbeda
    - Model dedicated reranking, bukan LLM yang dipaksa jadi scorer
    - Model kecil ~570MB di GPU — inference cepat, tidak signifikan ganggu gemma4:e4b

    Dipanggil dari rag_service.py:
        rerank_scores = await reranker_service.compute_scores(query, corpus_texts)

    Return: List[float] panjang == len(corpus_texts), nilai lebih tinggi = lebih relevan.
    """

    def __init__(self):
        logger.info("⚖️  [RERANKER SERVICE] BGE Cross-Encoder Engine siap (lazy load aktif).")

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

        Args:
            query        : Kueri asli dari user.
            corpus_texts : List teks kandidat hasil Fase 2 parent expansion.

        Returns:
            List[float] sepanjang corpus_texts. Sudah dinormalisasi ke [0, 1].
        """
        if not corpus_texts:
            return []

        logger.info(
            f"⚖️  [RERANKER] BGE scoring {len(corpus_texts)} kandidat "
            f'untuk kueri: "{query[:60]}"'
        )

        try:
            # Jalankan inference sinkron di thread pool — tidak blokir event loop
            scores = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_inference,
                query,
                corpus_texts,
            )

            logger.info(
                f"✅ [RERANKER] Selesai. "
                f"Skor tertinggi: {max(scores):.4f}, terendah: {min(scores):.4f}"
            )
            return scores

        except Exception as e:
            logger.error(
                f"💥 [RERANKER] BGE inference gagal: {str(e)}. "
                f"Fallback ke skor merata."
            )
            # Fallback aman: skor merata — urutan tetap dari RRF Fase 1
            n = len(corpus_texts)
            return [1.0 / n] * n

    # ==========================================================================
    # INFERENCE (SYNC — dijalankan via run_in_executor)
    # ==========================================================================

    def _run_inference(self, query: str, corpus_texts: List[str]) -> List[float]:
        """
        Jalankan cross-encoder inference secara sinkron.

        Pasang query dengan setiap dokumen → model nilai relevansinya.
        Output raw logit di-sigmoid → range [0, 1] otomatis oleh sentence-transformers.
        """
        model = _load_reranker()

        # Format input: list of (query, doc) pairs — standar CrossEncoder
        pairs = [(query, doc[:1000]) for doc in corpus_texts]
        # Truncate doc ke 1000 char — di atas max_length=512 token akan di-trim model

        # CrossEncoder.predict() mengembalikan numpy array of float
        # activate_function=sigmoid sudah default di bge-reranker
        raw_scores = model.predict(pairs, show_progress_bar=False)

        # Konversi numpy float → Python float
        scores = [float(s) for s in raw_scores]

        for idx, s in enumerate(scores):
            logger.debug(f"   [RERANKER] Kandidat #{idx} → BGE score: {s:.4f}")

        return scores


# Singleton — konsisten dengan vector_service dan rag_service
reranker_service = RerankerService()