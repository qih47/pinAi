"""
CAKRA AI — Peraturan Catalog & Lineage Sync Service (MySQL -> ragdb)
===================================================================
100% Read-Only terhadap MySQL (peraturan_db).
Menarik katalog 2.234 dokumen regulasi resmi PT Pindad dan memetakan silsilah hukum:
- Nomor regulasi (noper)
- Status keaktifan (stataktif -> is_berlaku & priority_tier)
- Silsilah dua arah: mencabut (forward) & dicabut oleh (reverse)
- Rantai regulasi aktif penerus (latest_active)
- Mendaftarkan dokumen fisik yang valid ke PostgreSQL ragdb
"""

import os
import logging
from typing import Dict, Any, List, Optional
import aiomysql
import fitz  # PyMuPDF

from backend.app.core.config import settings
from .db_setup import get_ragdb_conn

logger = logging.getLogger("CAKRA_PERATURAN_SYNC")
PERATURAN_STORAGE_DIR = "/home/qisthi/pinAi/file_peraturan"

class PeraturanLineageSyncService:
    @staticmethod
    async def get_mysql_connection():
        """Koneksi Read-Only ke MySQL peraturan_db"""
        return await aiomysql.connect(
            host=settings.DB_PERATURAN_HOST or "192.168.220.61",
            user=settings.DB_PERATURAN_USER or "qisthi",
            password=settings.DB_PERATURAN_PASSWORD or "q1sthi",
            db=settings.DB_PERATURAN_DATABASE or "peraturan_db",
            cursorclass=aiomysql.DictCursor,
            connect_timeout=10
        )

    @classmethod
    async def sync_catalog_and_lineage(cls) -> Dict[str, Any]:
        """
        Sinkronisasi katalog dokumen dari MySQL ke PostgreSQL ragdb:
        1. SELECT semua dokumen dari tabel berita (MySQL)
        2. Bangun peta silsilah dua arah (mencabut & dicabut oleh)
        3. Verifikasi ketersediaan file fisik di file_peraturan/
        4. Masukkan ke tabel dokumen & nightly_training_checkpoints di ragdb
        """
        logger.info("🔄 [SYNC_START] Memulai sinkronisasi katalog dan silsilah regulasi dari MySQL ke ragdb...")

        # 1. Ambil data dari MySQL
        raw_berita: List[Dict[str, Any]] = []
        try:
            conn_mysql = await cls.get_mysql_connection()
            async with conn_mysql.cursor() as cur:
                await cur.execute("""
                    SELECT 
                        b.id_berita, 
                        b.judul, 
                        b.noper, 
                        b.tgl_tetap, 
                        b.tanggal, 
                        COALESCE(NULLIF(b.gambar, ''), NULLIF(b.gambar2, ''), NULLIF(b.gambar3, '')) AS filename, 
                        k.nama_kategori AS jenis_dokumen,
                        b.stataktif,
                        b.mencabut,
                        b.linkper
                    FROM berita b
                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                    WHERE COALESCE(NULLIF(b.gambar, ''), NULLIF(b.gambar2, ''), NULLIF(b.gambar3, '')) IS NOT NULL
                    ORDER BY b.id_berita ASC
                """)
                raw_berita = await cur.fetchall()
            conn_mysql.close()
            logger.info(f"📥 [MYSQL_FETCH] Berhasil mengambil {len(raw_berita)} record dari MySQL peraturan_db.")
        except Exception as e:
            logger.error(f"❌ [MYSQL_ERROR] Gagal membaca dari MySQL peraturan_db: {e}")
            raise e

        # 2. Bangun Peta Silsilah (Bidirectional Lineage Map)
        mencabut_map: Dict[int, List[int]] = {}
        revoked_by_map: Dict[int, List[int]] = {}
        status_map: Dict[int, bool] = {} # id -> is_berlaku

        for r in raw_berita:
            doc_id = r["id_berita"]
            stat = str(r.get("stataktif", "")).strip().lower()
            is_active = stat not in ["obsolete", "batal", "0", "2"]
            status_map[doc_id] = is_active

            # Parse mencabut string ("123|456|789")
            m_str = r.get("mencabut") or ""
            revoked_ids = []
            if m_str:
                parts = [p.strip() for p in m_str.split("|") if p.strip().isdigit()]
                revoked_ids = [int(p) for p in parts]
            mencabut_map[doc_id] = revoked_ids

            # Forward map to reverse map
            for rev_id in revoked_ids:
                if rev_id not in revoked_by_map:
                    revoked_by_map[rev_id] = []
                revoked_by_map[rev_id].append(doc_id)

        # 3. Cari Terminal Active Document (latest_active) untuk dokumen yang obsolete
        latest_active_map: Dict[int, Optional[int]] = {}
        for doc_id, is_active in status_map.items():
            if is_active:
                latest_active_map[doc_id] = doc_id
            else:
                # Traverse reverse lineage sampai ketemu yang aktif
                visited = {doc_id}
                queue = list(revoked_by_map.get(doc_id, []))
                found_active = None
                while queue:
                    curr_id = queue.pop(0)
                    if curr_id in visited:
                        continue
                    visited.add(curr_id)
                    if status_map.get(curr_id, False):
                        found_active = curr_id
                        break
                    queue.extend(revoked_by_map.get(curr_id, []))
                latest_active_map[doc_id] = found_active

        # 4. Sinkronisasikan ke PostgreSQL ragdb
        total_matched_pdf = 0
        tier1_active_count = 0
        tier2_obsolete_count = 0
        skipped_no_file = 0

        async with get_ragdb_conn() as conn:
            # Ambil dokumen yang saat ini sudah COMPLETED agar tidak tertimpa
            completed_rows = await conn.fetch("SELECT dokumen_id FROM nightly_training_checkpoints WHERE status = 'COMPLETED'")
            completed_ids = {r["dokumen_id"] for r in completed_rows}

            for r in raw_berita:
                doc_id = r["id_berita"]
                filename = r["filename"]
                if not filename:
                    skipped_no_file += 1
                    continue

                pdf_path = os.path.join(PERATURAN_STORAGE_DIR, filename)
                if not os.path.exists(pdf_path):
                    skipped_no_file += 1
                    continue

                total_matched_pdf += 1
                is_berlaku = status_map.get(doc_id, True)
                priority_tier = 1 if is_berlaku else 2

                if is_berlaku:
                    tier1_active_count += 1
                else:
                    tier2_obsolete_count += 1

                judul = r["judul"] or f"Dokumen #{doc_id}"
                nomor = r["noper"] or ""
                mencabut_str = "|".join(map(str, mencabut_map.get(doc_id, [])))
                revoked_by_str = "|".join(map(str, revoked_by_map.get(doc_id, [])))
                latest_act_id = latest_active_map.get(doc_id)
                linkper_str = r.get("linkper") or ""

                # Hitung jumlah halaman fisik jika belum selesai
                total_pages = 0
                try:
                    doc = fitz.open(pdf_path)
                    total_pages = len(doc)
                    doc.close()
                except Exception:
                    total_pages = 0

                # 4a. Update / Insert tabel dokumen
                await conn.execute("""
                    INSERT INTO dokumen (id, judul, nomor, filename, status)
                    VALUES ($1, $2, $3, $4, 'draft')
                    ON CONFLICT (id) DO UPDATE 
                    SET judul = EXCLUDED.judul,
                        nomor = EXCLUDED.nomor,
                        filename = EXCLUDED.filename
                """, doc_id, judul, nomor, filename)

                # 4b. Update / Insert tabel nightly_training_checkpoints
                if doc_id in completed_ids:
                    # Jangan reset status COMPLETED
                    await conn.execute("""
                        UPDATE nightly_training_checkpoints
                        SET judul = $2,
                            nomor_dokumen = $3,
                            file_path = $4,
                            total_pages = CASE WHEN total_pages = 0 THEN $5 ELSE total_pages END,
                            priority_tier = $6,
                            is_berlaku = $7,
                            mencabut_ids = $8,
                            revoked_by_ids = $9,
                            latest_active_id = $10,
                            linkper = $11
                        WHERE dokumen_id = $1
                    """, doc_id, judul, nomor, pdf_path, total_pages, priority_tier, is_berlaku,
                        mencabut_str, revoked_by_str, latest_act_id, linkper_str)
                else:
                    await conn.execute("""
                        INSERT INTO nightly_training_checkpoints (
                            dokumen_id, judul, nomor_dokumen, file_path, total_pages,
                            priority_tier, is_berlaku, mencabut_ids, revoked_by_ids,
                            latest_active_id, linkper, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'PENDING')
                        ON CONFLICT (dokumen_id) DO UPDATE 
                        SET judul = EXCLUDED.judul,
                            nomor_dokumen = EXCLUDED.nomor_dokumen,
                            file_path = EXCLUDED.file_path,
                            total_pages = CASE WHEN nightly_training_checkpoints.total_pages = 0 THEN EXCLUDED.total_pages ELSE nightly_training_checkpoints.total_pages END,
                            priority_tier = EXCLUDED.priority_tier,
                            is_berlaku = EXCLUDED.is_berlaku,
                            mencabut_ids = EXCLUDED.mencabut_ids,
                            revoked_by_ids = EXCLUDED.revoked_by_ids,
                            latest_active_id = EXCLUDED.latest_active_id,
                            linkper = EXCLUDED.linkper
                    """, doc_id, judul, nomor, pdf_path, total_pages, priority_tier, is_berlaku,
                        mencabut_str, revoked_by_str, latest_act_id, linkper_str)

        summary = {
            "total_mysql_records": len(raw_berita),
            "matched_pdf_files": total_matched_pdf,
            "tier1_active_regulations": tier1_active_count,
            "tier2_obsolete_regulations": tier2_obsolete_count,
            "skipped_no_physical_file": skipped_no_file,
            "completed_preserved": len(completed_ids)
        }
        logger.info(f"✅ [SYNC_COMPLETE] Selesai sinkronisasi! Hasil: {summary}")
        return summary
