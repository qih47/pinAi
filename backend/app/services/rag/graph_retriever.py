"""
CAKRA AI — Knowledge Graph Context Retriever (Graph RAG)
=========================================================
Modul penelusuran relasi semantik entitas korporat dan regulasi (Graph RAG)
berdasarkan tabel `knowledge_graph_nodes` dan `knowledge_graph_edges` di PostgreSQL ragdb.

Fitur:
1. Multi-hop & Authority Traversal: Mengekstrak relasi organisasi (BERTANGGUNG_JAWAB,
   MENGATUR, SANKSI_UNTUK, MENETAPKAN, MENYETUJUI) dari dokumen-dokumen yang relevan.
2. Keyword-Guided Filtering: Memprioritaskan node entitas yang selaras dengan kata kunci substantif query.
3. Fail-Safe & Non-Destructive: Eksekusi berindeks super cepat (< 5ms), jika tidak ada relasi
   atau terjadi galat, mengembalikan string kosong tanpa mengganggu alur teks chunk utama.
"""

import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_GRAPH_RETRIEVER")

_NOISE_TOKENS = {
    "yang", "di", "ke", "dari", "dan", "atau", "untuk", "with", "dengan", "pada",
    "adalah", "ini", "itu", "dalam", "oleh", "juga", "sudah", "akan", "tidak",
    "ada", "saya", "anda", "bisa", "lebih", "seperti", "sebagai", "saat", "jika",
    "maka", "telah", "harus", "dapat", "agar", "bahwa", "karena", "namun",
    "pasal", "ayat", "huruf", "angka", "nomor", "no", "tentang", "aturan",
    "peraturan", "berapa", "bagaimana", "apakah", "terkait", "mengenai", "pindad"
}


class GraphRetriever:
    """Layanan ekstraksi relasi struktur dan kewenangan dari Knowledge Graph."""

    def _extract_keywords(self, query: str) -> List[str]:
        """Mengekstrak kata kunci substantif dari query pengguna."""
        if not query:
            return []
        cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in query.lower())
        tokens = [t for t in cleaned.split() if len(t) >= 3 and t not in _NOISE_TOKENS]
        return tokens[:5]

    async def retrieve_graph_context(
        self,
        doc_ids: List[int],
        query: str = "",
        max_relations: int = 6
    ) -> str:
        """
        Mengambil relasi Knowledge Graph yang terhubung dengan dokumen-dokumen aktif.
        Mengembalikan blok teks terformat untuk disuntikkan ke dalam prompt LLM.
        """
        if not doc_ids:
            return ""

        valid_doc_ids = list({int(d) for d in doc_ids if str(d).isdigit()})[:8]
        if not valid_doc_ids:
            return ""

        keywords = self._extract_keywords(query)
        collected_relations = []
        seen_pairs = set()

        async with get_db() as conn:
            try:
                # 1. Tahap Prioritas: Cari relasi yang entitasnya cocok dengan kata kunci kueri
                for kw in keywords:
                    if len(collected_relations) >= max_relations:
                        break
                    kw_pattern = f"%{kw}%"
                    kw_sql = """
                        SELECT 
                            n1.entity_name AS src_name,
                            n1.entity_type AS src_type,
                            e.relation_type AS rel,
                            n2.entity_name AS tgt_name,
                            n2.entity_type AS tgt_type,
                            COALESCE(d.nomor, d.judul) AS doc_ref
                        FROM knowledge_graph_edges e
                        JOIN knowledge_graph_nodes n1 ON e.source_node_id = n1.id
                        JOIN knowledge_graph_nodes n2 ON e.target_node_id = n2.id
                        JOIN dokumen d ON e.dokumen_id = d.id
                        WHERE e.dokumen_id = ANY($1)
                          AND (n1.entity_name ILIKE $2 OR n2.entity_name ILIKE $2)
                        ORDER BY e.weight DESC, e.id ASC
                        LIMIT $3;
                    """
                    kw_rows = await conn.fetch(kw_sql, valid_doc_ids, kw_pattern, max_relations)
                    for r in kw_rows:
                        pair_key = (r["src_name"], r["rel"], r["tgt_name"])
                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)
                            collected_relations.append(dict(r))

                # 2. Tahap Fallback/Struktural: Jika masih ada kuota, isi dengan relasi kunci otoritatif
                remaining_limit = max_relations - len(collected_relations)
                if remaining_limit > 0:
                    struct_sql = """
                        SELECT 
                            n1.entity_name AS src_name,
                            n1.entity_type AS src_type,
                            e.relation_type AS rel,
                            n2.entity_name AS tgt_name,
                            n2.entity_type AS tgt_type,
                            COALESCE(d.nomor, d.judul) AS doc_ref
                        FROM knowledge_graph_edges e
                        JOIN knowledge_graph_nodes n1 ON e.source_node_id = n1.id
                        JOIN knowledge_graph_nodes n2 ON e.target_node_id = n2.id
                        JOIN dokumen d ON e.dokumen_id = d.id
                        WHERE e.dokumen_id = ANY($1)
                        ORDER BY 
                            CASE 
                                WHEN e.relation_type = 'BERTANGGUNG_JAWAB' THEN 1
                                WHEN e.relation_type = 'MENGATUR' THEN 2
                                WHEN e.relation_type = 'SANKSI_UNTUK' THEN 3
                                WHEN e.relation_type = 'MENETAPKAN' THEN 4
                                WHEN e.relation_type = 'MENYETUJUI' THEN 5
                                ELSE 6
                            END ASC,
                            e.weight DESC, e.id ASC
                        LIMIT $2;
                    """
                    struct_rows = await conn.fetch(struct_sql, valid_doc_ids, remaining_limit * 2)
                    for r in struct_rows:
                        if len(collected_relations) >= max_relations:
                            break
                        pair_key = (r["src_name"], r["rel"], r["tgt_name"])
                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)
                            collected_relations.append(dict(r))

            except Exception as e:
                logger.warning(f"[GRAPH_RETRIEVER] ⚠️ Gagal mengekstrak relasi graph (abaikan non-destruktif): {e}")
                return ""

        if not collected_relations:
            return ""

        # Format relasi ke representasi teks terstruktur yang ramah bagi LLM CoT
        lines = ["[PETA RELASI STRUKTUR & KEWENANGAN (KNOWLEDGE GRAPH)]"]
        for r in collected_relations:
            st = r.get("src_type") or "ENTITAS"
            sn = r.get("src_name") or "-"
            rel = r.get("rel") or "TERKAIT"
            tt = r.get("tgt_type") or "OBJEK"
            tn = r.get("tgt_name") or "-"
            ref = r.get("doc_ref") or "Regulasi Pindad"
            lines.append(f"• [{st}: {sn}] ──({rel})──► [{tt}: {tn}] (Dasar: {ref})")

        graph_summary = "\n".join(lines) + "\n\n"
        logger.info(f"[GRAPH_RETRIEVER] 🕸️ Berhasil mengekstrak {len(collected_relations)} relasi semantik untuk dokumen {valid_doc_ids}")
        return graph_summary


graph_retriever = GraphRetriever()
