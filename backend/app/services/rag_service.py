import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_RAG_SERVICE")

class RagService:
    """
    Orkestrator Advanced RAG (Diet Ketat & High Performance).
    Menghubungkan Vector Search dengan taktik Parent-Child Expansion 
    dan filtrasi skor ketat sebelum disuntikkan ke Slot 2 (DeepSeek R1).
    """
    
    def __init__(self):
        print("🛡️  [RAG SERVICE] Orkestrator Advanced RAG Engine bertenaga Parent-Child siap tempur, bolo!")

    async def assemble_powerful_context(
        self, 
        query: str, 
        limit: int = 4, 
        min_score: float = 0.35
    ) -> str:
        """
        Inti Kekuatan: Mencari child chunks, mengekspansinya ke parent text,
        dan menyusunnya menjadi blok context yang terstruktur rapi untuk LLM.
        """
        print(f"🔍 [RAG CORE] Memulai ekstraksi dokumen taktis untuk kueri: \"{query}\"")
        
        # 🔥 FIX SAKTI SUNTIKAN LAZY IMPORT:
        # Kita panggil vector_service di dalam fungsi ini agar Python tidak crash saat bootstrap main.py
        try:
            from backend.app.services.vector_service import vector_service
        except ImportError:
            # Fallback jika ternyata nama instance di file lo menggunakan huruf besar / nama lain
            import backend.app.services.vector_service as vs
            # Cari tahu apakah ada objek VectorService atau sejenisnya
            if hasattr(vs, "vector_service"):
                vector_service = vs.vector_service
            elif hasattr(vs, "VectorService"):
                # Jika cuma ada Class, kita instansiasi darurat di sini
                vector_service = vs.VectorService()
            else:
                logger.error("💥 [RAG CRITICAL] Instansi 'vector_service' tidak ditemukan di berkas aslinya!")
                return ""

        # 1. Eksekusi Hybrid Search (Vector Cosine + BM25 Lexical) via vector_service
        raw_results = await vector_service.hybrid_search(query, limit=limit)
        
        if not raw_results:
            print("⚠️  [RAG CORE] Zero Match! Tidak ada dokumen yang relevan di RAGDB.")
            return ""

        parent_ids_to_fetch = []
        chunks_metadata: Dict[str, Dict[str, Any]] = {}

        # 2. Filter berdasarkan Score Threshold & Kumpulkan Parent ID
        for item in raw_results:
            score = item.get("score", 0.0)
            if score < min_score:
                print(f"🗑️  [RAG FILTER] Chunk dieliminasi (Skor {score:.4f} < Threshold {min_score})")
                continue
                
            parent_id = item.get("parent_id")
            if parent_id:
                parent_ids_to_fetch.append(parent_id)
                chunks_metadata[str(parent_id)] = {
                    "judul_dokumen": item.get("judul_dokumen", "Dokumen Pindad"),
                    "nomor_regulasi": item.get("nomor_regulasi", "N/A"),
                    "halaman": item.get("page_number", 1),
                    "score": score
                }

        if not parent_ids_to_fetch:
            return ""

        # 3. PARENT CONTEXT EXPANSION: Tarik teks utuh dari tabel induk (Parent)
        expanded_contexts = []
        
        async with get_db() as conn:
            try:
                query_parent = """
                    SELECT id, parent_text 
                    FROM document_parent_chunks 
                    WHERE id = ANY($1);
                """
                rows = await conn.fetch(query_parent, parent_ids_to_fetch)
                
                print(f"📦 [RAG CORE] Berhasil mengekspansi {len(rows)} Parent Context secara aman.")
                
                for idx, row in enumerate(rows):
                    p_id = str(row['id'])
                    meta = chunks_metadata.get(p_id, {})
                    
                    block = (
                        f"--- DOKUMEN RUJUKAN [{idx + 1}] ---\n"
                        f"• Judul: {meta.get('judul_dokumen')}\n"
                        f"• No. Regulasi: {meta.get('nomor_regulasi')}\n"
                        f"• Halaman: {meta.get('halaman')}\n"
                        f"• Validitas Relevansi: {meta.get('score'):.4f}\n"
                        f"• Isi Dokumen:\n{row['parent_text']}\n"
                    )
                    expanded_contexts.append(block)
                    
            except Exception as e:
                logger.error(f"💥 [RAG DB ERROR] Gagal mengekspansi parent context: {str(e)}")
                return ""

        full_context_str = "\n".join(expanded_contexts)
        return full_context_str

rag_service = RagService()