"""
CAKRA AI — Checkpoint Manager & Zero-Loss Rollback (RAGDB ONLY)
==============================================================
Menjamin keutuhan data training per halaman.
Jika sistem dihentikan paksa (cutoff pagi 07:30/08:00) atau error:
1. Posisi halaman terakhir dan buffer potongan pasal tersimpan aman di nightly_training_checkpoints.
2. Transaksi halaman yang belum tuntas di-rollback bersih tanpa menyisakan data korup.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from .db_setup import get_ragdb_conn

logger = logging.getLogger("CAKRA_CHECKPOINT_MGR")

class CheckpointManager:
    @staticmethod
    async def get_or_create_checkpoint(
        dokumen_id: int,
        judul: str,
        nomor_dokumen: str,
        file_path: str,
        total_pages: int,
        is_berlaku: bool = True
    ) -> Dict[str, Any]:
        """Mengambil checkpoint existing atau membuat checkpoint baru di ragdb"""
        async with get_ragdb_conn() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM nightly_training_checkpoints WHERE dokumen_id = $1",
                dokumen_id
            )
            if row:
                return dict(row)

            # Buat baru
            await conn.execute("""
                INSERT INTO nightly_training_checkpoints (
                    dokumen_id, judul, nomor_dokumen, file_path, total_pages,
                    last_completed_page, pending_buffer, status, is_berlaku
                ) VALUES ($1, $2, $3, $4, $5, 0, '{}'::jsonb, 'PENDING', $6)
                ON CONFLICT (dokumen_id) DO NOTHING
            """, dokumen_id, judul, nomor_dokumen, file_path, total_pages, is_berlaku)

            new_row = await conn.fetchrow(
                "SELECT * FROM nightly_training_checkpoints WHERE dokumen_id = $1",
                dokumen_id
            )
            return dict(new_row) if new_row else {}

    @staticmethod
    async def commit_page_checkpoint(
        dokumen_id: int,
        page_num: int,
        total_pages: int,
        pending_buffer: Dict[str, Any],
        qa_count_delta: int = 0,
        graph_count_delta: int = 0
    ) -> bool:
        """
        Meng-commit progres bahwa halaman `page_num` telah selesai diproses oleh ke-5 worker.
        """
        is_finished = (page_num >= total_pages)
        status = "COMPLETED" if is_finished else "IN_PROGRESS"

        buffer_json = json.dumps(pending_buffer)

        async with get_ragdb_conn() as conn:
            await conn.execute("""
                UPDATE nightly_training_checkpoints
                SET last_completed_page = $1,
                    pending_buffer = $2::jsonb,
                    status = $3,
                    w1_text_status = 'DONE',
                    w2_qa_status = 'DONE',
                    w3_graph_status = 'DONE',
                    w4_vision_status = 'DONE',
                    w5_lora_status = 'DONE',
                    qa_count = qa_count + $4,
                    graph_nodes_count = graph_nodes_count + $5,
                    last_synced_at = NOW(),
                    error_message = NULL
                WHERE dokumen_id = $6
            """, page_num, buffer_json, status, qa_count_delta, graph_count_delta, dokumen_id)

            # Update juga status di tabel dokumen (ragdb) jika dokumen tuntas
            if is_finished:
                await conn.execute(
                    "UPDATE dokumen SET status = 'COMPLETED', last_processed = NOW() WHERE id = $1",
                    dokumen_id
                )

        logger.info(f"💾 [CHECKPOINT] Dokumen {dokumen_id}: Halaman {page_num}/{total_pages} berhasil di-commit (Status: {status}).")
        return True

    @staticmethod
    async def rollback_dirty_page(dokumen_id: int, failed_page_num: int, last_good_page: int) -> bool:
        """
        Rollback bersih jika halaman yang sedang berjalan gagal di tengah jalan.
        Menghapus chunk atau node graf yang belum tuntas untuk halaman tersebut.
        """
        logger.warning(f"⚠️ [ROLLBACK] Dokumen {dokumen_id}: Melakukan rollback untuk Halaman {failed_page_num}. Kembali ke checkpoint aman Halaman {last_good_page}.")
        page_str = str(failed_page_num)

        async with get_ragdb_conn() as conn:
            # Hapus chunk parsial
            await conn.execute(
                "DELETE FROM dokumen_chunk WHERE dokumen_id = $1 AND page_number = $2",
                dokumen_id, page_str
            )
            # Hapus node graf parsial
            await conn.execute(
                "DELETE FROM knowledge_graph_nodes WHERE dokumen_id = $1 AND page_number = $2",
                dokumen_id, failed_page_num
            )
            # Update status checkpoint menjadi PAUSED
            await conn.execute("""
                UPDATE nightly_training_checkpoints
                SET status = 'PAUSED',
                    last_synced_at = NOW(),
                    error_message = 'Rolled back dirty page ' || $2::text
                WHERE dokumen_id = $1
            """, dokumen_id, failed_page_num)

        return True

    @staticmethod
    async def rollback_dirty_pages(dokumen_id: int, failed_pages: List[int], last_good_page: int) -> bool:
        """
        Rollback bersih untuk bentangan halaman (two-page spread) jika gagal di tengah jalan.
        """
        logger.warning(f"⚠️ [ROLLBACK] Dokumen {dokumen_id}: Melakukan rollback bentangan Halaman {failed_pages}. Kembali ke checkpoint Halaman {last_good_page}.")
        async with get_ragdb_conn() as conn:
            for p in failed_pages:
                page_str = str(p)
                await conn.execute(
                    "DELETE FROM dokumen_chunk WHERE dokumen_id = $1 AND page_number = $2",
                    dokumen_id, page_str
                )
                await conn.execute(
                    "DELETE FROM knowledge_graph_nodes WHERE dokumen_id = $1 AND page_number = $2",
                    dokumen_id, p
                )
            await conn.execute("""
                UPDATE nightly_training_checkpoints
                SET status = 'PAUSED',
                    last_synced_at = NOW(),
                    error_message = 'Rolled back dirty spread ' || $2::text
                WHERE dokumen_id = $1
            """, dokumen_id, str(failed_pages))
        return True

    @staticmethod
    async def get_next_documents_queue(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Mengambil antrean dokumen prioritas:
        1. Tier 1: Peraturan Berlaku Aktif (priority_tier = 1, is_berlaku = TRUE)
        2. Status In-Progress / Paused dilanjutkan terlebih dahulu
        3. Tier 2: Peraturan Dicabut/Usang (priority_tier = 2) baru setelah Tier 1 selesai
        HANYA dari ragdb!
        """
        async with get_ragdb_conn() as conn:
            rows = await conn.fetch("""
                SELECT 
                    c.dokumen_id,
                    c.judul,
                    c.nomor_dokumen,
                    c.file_path,
                    c.total_pages,
                    c.last_completed_page,
                    c.pending_buffer,
                    c.status,
                    c.is_berlaku,
                    c.priority_tier,
                    c.mencabut_ids,
                    c.revoked_by_ids,
                    c.latest_active_id,
                    c.linkper
                FROM nightly_training_checkpoints c
                WHERE c.status IN ('PAUSED', 'IN_PROGRESS', 'PENDING')
                  AND c.file_path IS NOT NULL AND c.file_path != ''
                ORDER BY 
                    c.priority_tier ASC,
                    c.is_berlaku DESC,
                    CASE WHEN c.status = 'IN_PROGRESS' THEN 1
                         WHEN c.status = 'PAUSED' THEN 2
                         ELSE 3 END ASC,
                    c.dokumen_id ASC
                LIMIT $1
            """, limit)

            return [dict(r) for r in rows]

    @staticmethod
    async def get_training_statistics() -> Dict[str, Any]:
        """
        Mengambil statistik komprehensif Tier 1 vs Tier 2 untuk dashboard frontend & monitoring.
        """
        async with get_ragdb_conn() as conn:
            tier1_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed,
                    COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') as in_progress,
                    COUNT(*) FILTER (WHERE status = 'PAUSED') as paused,
                    COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
                    COALESCE(SUM(total_pages), 0) as total_pages,
                    COALESCE(SUM(last_completed_page), 0) as processed_pages,
                    COALESCE(SUM(qa_count), 0) as total_qa,
                    COALESCE(SUM(graph_nodes_count), 0) as total_graph_nodes
                FROM nightly_training_checkpoints
                WHERE priority_tier = 1
            """)

            tier2_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed,
                    COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') as in_progress,
                    COUNT(*) FILTER (WHERE status = 'PAUSED') as paused,
                    COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
                    COALESCE(SUM(total_pages), 0) as total_pages,
                    COALESCE(SUM(last_completed_page), 0) as processed_pages,
                    COALESCE(SUM(qa_count), 0) as total_qa,
                    COALESCE(SUM(graph_nodes_count), 0) as total_graph_nodes
                FROM nightly_training_checkpoints
                WHERE priority_tier = 2
            """)

            return {
                "tier1": dict(tier1_stats) if tier1_stats else {},
                "tier2": dict(tier2_stats) if tier2_stats else {}
            }

    @staticmethod
    async def reset_all_training_checkpoints(clean_artifacts: bool = True) -> Dict[str, Any]:
        """
        Mereset seluruh progres training malam kembali ke Titik 0 (Dokumen #1, Halaman 1):
        - Mengembalikan status seluruh 2.245 dokumen di nightly_training_checkpoints ke PENDING
        - Mengosongkan page checkpoint & pending buffer
        - Mengarsipkan dan mengosongkan dataset JSONL latih (Core & Router)
        - Menghapus artefak testing lama di ragdb (chunks, questions, graph nodes)
        CATATAN: HANYA beroperasi pada PostgreSQL (ragdb) & file lokal. MySQL peraturan_db TETAP 100% READ ONLY!
        """
        import os
        import shutil
        from datetime import datetime

        logger.warning("🚨 [CHECKPOINT_RESET] Memulai proses Reset Training ke Titik Awal (0)!")

        async with get_ragdb_conn() as conn:
            # 1. Reset seluruh checkpoint dokumen ke 0 dan PENDING
            await conn.execute("""
                UPDATE nightly_training_checkpoints
                SET last_completed_page = 0,
                    pending_buffer = '{}'::jsonb,
                    status = 'PENDING',
                    w1_text_status = 'PENDING',
                    w2_qa_status = 'PENDING',
                    w3_graph_status = 'PENDING',
                    w4_vision_status = 'PENDING',
                    w5_lora_status = 'PENDING',
                    qa_count = 0,
                    graph_nodes_count = 0,
                    error_message = NULL,
                    last_synced_at = NOW()
            """)

            # Update tabel dokumen jika ada
            try:
                await conn.execute("UPDATE dokumen SET status = 'PENDING', last_processed = NULL")
            except Exception as doc_err:
                logger.debug(f"[RESET] Update dokumen table skipped: {doc_err}")

            deleted_counts = {}
            if clean_artifacts:
                try:
                    res_chunk = await conn.execute("DELETE FROM dokumen_chunk")
                    deleted_counts["chunks"] = res_chunk
                except Exception as e:
                    logger.warning(f"[RESET] Clear dokumen_chunk error: {e}")

                try:
                    res_qa = await conn.execute("DELETE FROM rag_document_questions")
                    deleted_counts["qa_questions"] = res_qa
                except Exception as e:
                    logger.warning(f"[RESET] Clear rag_document_questions error: {e}")

                try:
                    res_nodes = await conn.execute("DELETE FROM knowledge_graph_nodes")
                    deleted_counts["graph_nodes"] = res_nodes
                except Exception as e:
                    logger.warning(f"[RESET] Clear knowledge_graph_nodes error: {e}")

                try:
                    res_edges = await conn.execute("DELETE FROM knowledge_graph_edges")
                    deleted_counts["graph_edges"] = res_edges
                except Exception as e:
                    pass

        # 2. Backup & Kosongkan File Dataset Fine-Tuning
        finetune_dir = "/home/qisthi/pinAi/data/finetune"
        os.makedirs(finetune_dir, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        backed_up_files = []
        for fname in ["nightly_cakra_core.jsonl", "nightly_call1_router.jsonl"]:
            fpath = os.path.join(finetune_dir, fname)
            if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
                bak_path = os.path.join(finetune_dir, f"{fname}.bak_{timestamp_str}")
                try:
                    shutil.copy2(fpath, bak_path)
                    backed_up_files.append(bak_path)
                except Exception as cp_err:
                    logger.error(f"[RESET] Gagal backup {fpath}: {cp_err}")
            # Buat file kosong baru
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("")

        logger.info(f"✅ [CHECKPOINT_RESET] Sukses mereset seluruh training ke titik 0. Backup datasets: {backed_up_files}")
        return {
            "status": "success",
            "message": "Seluruh checkpoint dan dataset training berhasil di-reset ke titik awal (Dokumen 1, Halaman 1).",
            "backed_up_files": backed_up_files,
            "deleted_artifacts": deleted_counts
        }

