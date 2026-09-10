"""
CAKRA AI — Master Nightly Training & Fine-Tuning Orchestrator
============================================================
Orchestrator utama yang mengatur eksekusi malam hari:
- Membaca dokumen dari ragdb secara berurutan layaknya membaca buku.
- 5 worker berjalan bersamaan per halaman (Text, Q&A Unlimited, Graph, Vision, LoRA).
- Menyambungkan pembahasan/pasal yang terpotong lintas halaman (hal 4 -> 5 -> 6).
- Mematuhi jendela waktu 18:00 - 07:30 WIB (hard stop 08:00 WIB).
- Checkpoint aman dan zero-corrupt rollback.
- Mendukung trigger manual dari Dashboard UI & otomatis via cron.
- 100% menggunakan ragdb (TIDAK menyentuh database lain).
"""

import os
import time
import logging
import asyncio
from datetime import datetime, time as dtime
from typing import Optional, Dict, Any, List

from .db_setup import get_ragdb_conn
from .page_parser import BookPageReader
from .worker_coordinator import WorkerCoordinator
from .checkpoint_manager import CheckpointManager

logger = logging.getLogger("CAKRA_NIGHTLY_ORCHESTRATOR")

PERATURAN_STORAGE_DIR = "/home/qisthi/pinAi/file_peraturan"

class NightlyTrainingOrchestrator:
    def __init__(
        self,
        start_hour: int = 18,
        start_minute: int = 0,
        soft_stop_hour: int = 7,
        soft_stop_minute: int = 30,
        hard_stop_hour: int = 8,
        hard_stop_minute: int = 0,
        model_name: str = "gemma4:31b"
    ):
        self.start_time = dtime(start_hour, start_minute)
        self.soft_stop_time = dtime(soft_stop_hour, soft_stop_minute)
        self.hard_stop_time = dtime(hard_stop_hour, hard_stop_minute)
        self.model_name = model_name
        self.coordinator = WorkerCoordinator(model_name=model_name)
        self.is_running = False
        self.stop_requested = False

        # Live State Tracking untuk Dashboard UI
        self.current_doc_id: Optional[int] = None
        self.current_doc_title: str = ""
        self.current_nomor_dokumen: str = ""
        self.current_page: int = 0
        self.current_total_pages: int = 0
        self.current_spread_left: Optional[int] = None
        self.current_spread_right: Optional[int] = None
        self.worker_states: Dict[str, str] = {
            "w1_text": "IDLE",
            "w2_qa": "IDLE",
            "w3_graph": "IDLE",
            "w4_vision": "IDLE",
            "w5_lora": "IDLE"
        }
        self.started_at: Optional[str] = None
        self.latest_log: str = "Menunggu trigger..."

        # Live Terminal Stream & Training Artifacts Inspector Buffer
        self.terminal_stream: List[Dict[str, Any]] = []
        self.last_spread_artifacts: Dict[str, Any] = {
            "doc_id": None,
            "doc_title": "",
            "nomor_dokumen": "",
            "spread_label": "",
            "chunks": [],
            "qa_pairs": [],
            "graph_triplets": [],
            "lora_samples": []
        }

    @property
    def workers(self) -> Dict[str, str]:
        return self.worker_states

    @property
    def current_doc(self) -> Optional[Dict[str, Any]]:
        if not self.current_doc_id:
            return None
        return {
            "id": self.current_doc_id,
            "title": self.current_doc_title,
            "nomor_dokumen": self.current_nomor_dokumen,
            "current_page": self.current_page,
            "total_pages": self.current_total_pages,
            "page_left": self.current_spread_left,
            "page_right": self.current_spread_right
        }

    def add_terminal_log(self, worker: str, level: str, message: str, details: Optional[Any] = None):
        """Menambahkan entri log realtime ke terminal stream buffer (maksimal 200 baris)"""
        entry = {
            "id": f"{int(time.time() * 1000)}_{len(self.terminal_stream)}",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "worker": worker,
            "level": level,
            "message": message,
            "details": details
        }
        self.terminal_stream.append(entry)
        if len(self.terminal_stream) > 200:
            self.terminal_stream = self.terminal_stream[-200:]

    def get_live_monitor_payload(self) -> Dict[str, Any]:
        """Mengambil data live bentangan 2 halaman, status worker, terminal stream, dan artifacts"""
        page_left_url = f"/doc_pages/{self.current_doc_id}/page_{self.current_spread_left:03d}.png" if self.current_doc_id and self.current_spread_left else None
        page_right_url = f"/doc_pages/{self.current_doc_id}/page_{self.current_spread_right:03d}.png" if self.current_doc_id and self.current_spread_right else None

        return {
            "is_running": self.is_running,
            "started_at": self.started_at,
            "current_doc": {
                "id": self.current_doc_id,
                "title": self.current_doc_title,
                "nomor_dokumen": self.current_nomor_dokumen,
                "current_page": self.current_page,
                "total_pages": self.current_total_pages,
                "page_left": self.current_spread_left,
                "page_right": self.current_spread_right,
                "page_left_url": page_left_url,
                "page_right_url": page_right_url
            } if self.current_doc_id else None,
            "workers": self.worker_states,
            "latest_log": self.latest_log,
            "terminal_stream": self.terminal_stream,
            "artifacts": self.last_spread_artifacts
        }

    def is_within_training_window(self, force_run: bool = False) -> bool:
        """
        Mengecek apakah saat ini berada dalam rentang waktu training malam:
        18:00 sore s/d 07:30 pagi.
        """
        if force_run:
            return True

        now = datetime.now().time()
        # Kasus lewat tengah malam: 18:00 -> 23:59 atau 00:00 -> 07:30
        if self.start_time <= now or now < self.soft_stop_time:
            return True
        return False

    def is_approaching_hard_stop(self) -> bool:
        """Mengecek apakah sudah lewat 07:50 mendekati 08:00"""
        now = datetime.now().time()
        cutoff_margin = dtime(7, 50)
        if cutoff_margin <= now < self.hard_stop_time:
            return True
        return False

    async def sync_ragdb_documents_to_checkpoints(self) -> int:
        """
        Mendaftarkan dokumen dari tabel `dokumen` (ragdb) ke `nightly_training_checkpoints`.
        HANYA menggunakan ragdb!
        """
        enrolled = 0
        async with get_ragdb_conn() as conn:
            rows = await conn.fetch("""
                SELECT id, judul, nomor, filename 
                FROM dokumen 
                ORDER BY id ASC
            """)

            for r in rows:
                doc_id = r["id"]
                judul = r["judul"] or f"Dokumen #{doc_id}"
                nomor = r["nomor"] or ""
                filename = r["filename"] or ""

                file_path = ""
                if filename:
                    candidate = os.path.join(PERATURAN_STORAGE_DIR, filename)
                    if os.path.exists(candidate):
                        file_path = candidate

                # Hitung total halaman jika PDF ditemukan
                total_pages = 0
                if file_path and os.path.exists(file_path):
                    try:
                        import fitz
                        doc = fitz.open(file_path)
                        total_pages = len(doc)
                        doc.close()
                    except Exception:
                        total_pages = 0

                await CheckpointManager.get_or_create_checkpoint(
                    dokumen_id=doc_id,
                    judul=judul,
                    nomor_dokumen=nomor,
                    file_path=file_path,
                    total_pages=total_pages,
                    is_berlaku=True
                )
                enrolled += 1

        logger.info(f"📋 [NIGHTLY_ORCHESTRATOR] {enrolled} dokumen dari ragdb terdaftar di antrean checkpoint.")
        return enrolled

    def check_disk_space_safety(self) -> bool:
        """Mengecek apakah sisa ruang disk >= 5 GB untuk keamanan sistem"""
        try:
            stat = os.statvfs("/home/qisthi/pinAi")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            if free_gb < 5.0:
                logger.warning(f"⚠️ [DISK_WARNING] Sisa ruang disk tinggal {free_gb:.2f} GB (< 5 GB). Menghentikan sementara proses untuk keselamatan sistem!")
                return False
            return True
        except Exception as e:
            logger.error(f"[DISK_CHECK_ERROR] Gagal cek disk: {e}")
            return True

    async def process_single_document(
        self,
        doc_info: Dict[str, Any],
        force_run: bool = False,
        page_limit: Optional[int] = None
    ) -> bool:
        """
        Memproses 1 dokumen secara bentangan 2 halaman (two-page spread) dengan 5 worker tersinkronisasi.
        Menggunakan input visual multimodal murni (PNG) yang diproses langsung oleh mata Gemma 31B.
        """
        dokumen_id = doc_info["dokumen_id"]
        judul = doc_info.get("judul", "")
        file_path = doc_info.get("file_path", "")
        last_page = doc_info.get("last_completed_page", 0)
        pending_buffer = doc_info.get("pending_buffer") or {}
        if isinstance(pending_buffer, str):
            try:
                import json
                pending_buffer = json.loads(pending_buffer)
            except Exception:
                pending_buffer = {}

        self.current_doc_id = dokumen_id
        self.current_doc_title = judul

        if not file_path or not os.path.exists(file_path):
            self.latest_log = f"PDF tidak ditemukan: {file_path}"
            logger.warning(f"⚠️ [ORCHESTRATOR] Dokumen {dokumen_id} ({judul}): File PDF tidak ditemukan di path '{file_path}'. Melewati...")
            return False

        reader = BookPageReader(file_path, dokumen_id, initial_buffer=pending_buffer)
        total_pages = reader.get_total_pages()
        self.current_total_pages = total_pages

        if total_pages == 0:
            self.latest_log = f"Dokumen {dokumen_id}: Total halaman 0"
            logger.warning(f"⚠️ [ORCHESTRATOR] Dokumen {dokumen_id}: Total halaman 0. Melewati...")
            reader.close()
            return False

        logger.info(f"📖 [ORCHESTRATOR] Membaca Dokumen {dokumen_id}: '{judul}' ({total_pages} Halaman). Melanjutkan dari Halaman {last_page + 1} (Bentangan 2 Halaman)...")

        start_page = last_page + 1
        end_page = total_pages
        if page_limit:
            end_page = min(total_pages, start_page + page_limit - 1)

        # Loop per bentangan 2 halaman (step = 2)
        for page_left in range(start_page, end_page + 1, 2):
            page_right = page_left + 1 if page_left + 1 <= total_pages else None
            spread_pages = [page_left] if page_right is None else [page_left, page_right]
            spread_label = f"{page_left}" if page_right is None else f"{page_left}-{page_right}"

            if self.stop_requested:
                self.latest_log = f"Dihentikan manual pada Halaman {last_page}"
                logger.info("🛑 [STOP_REQUESTED] Permintaan stop manual diterima. Berhenti dengan aman...")
                reader.close()
                return False

            # 1. Cek Safety Disk Space (< 5 GB)
            if not self.check_disk_space_safety():
                self.latest_log = "Ruang disk kritis (< 5 GB). Jeda pengamanan aktif."
                reader.close()
                return False

            # 2. Cek Jendela Waktu (Soft Stop 07:30 WIB)
            # Aturan: Jika sebelum mulai batch baru sudah >= 07:30 WIB, STOP.
            # Jika batch sudah berjalan saat 07:30 WIB tercapai, selesaikan batch tersebut toleransi s.d. 08:00 WIB.
            if not self.is_within_training_window(force_run):
                self.latest_log = f"Cutoff 07:30 WIB tercapai. Standby di checkpoint Halaman {last_page}."
                logger.info(f"⏰ [CUTOFF_0730] Waktu 07:30 WIB tercapai. Berhenti sebelum memulai bentangan baru Halaman {spread_label}. Checkpoint aman di Halaman {last_page}.")
                reader.close()
                return False

            # Cek Hard Stop 08:00 WIB
            if self.is_approaching_hard_stop():
                self.latest_log = "Hard stop 08:00 WIB tercapai. VRAM dibebaskan untuk jam operasional."
                logger.warning(f"🚨 [HARD_STOP_0800] Batas mutlak 08:00 WIB tercapai. Memastikan VRAM bersih!")
                reader.close()
                return False

            self.current_page = spread_pages[-1]
            self.current_spread_left = page_left
            self.current_spread_right = page_right
            self.current_nomor_dokumen = doc_info.get("nomor_dokumen", "")

            self.latest_log = f"Memproses Dokumen #{dokumen_id} Bentangan Halaman {spread_label}/{total_pages}..."
            logger.info(f"📄 [SPREAD {spread_label}/{total_pages}] Dokumen {dokumen_id}: Menjalankan 5 Worker Multimodal...")

            self.add_terminal_log("SYSTEM", "INFO", f"Memulai Bentangan Halaman {spread_label} dari {total_pages} (Dokumen #{dokumen_id}: {judul[:40]})")

            try:
                # 3. Ekstraksi visual bentangan 2 halaman (Two-Page Spread Multimodal)
                spread_data = reader.process_multimodal_spread(page_left, page_right)
                completed_sections = spread_data.get("completed_sections", [])
                spread_images_b64 = spread_data.get("images_b64") or spread_data.get("spread_images_b64", [])
                raw_text = spread_data.get("raw_text", "")

                # 4. Jalankan 5 Worker secara paralel memanfaatkan 4 slot Ollama (-np 4)
                self.worker_states = {
                    "w1_text": "RUNNING",
                    "w2_qa": "RUNNING",
                    "w3_graph": "RUNNING",
                    "w4_vision": "RUNNING",
                    "w5_lora": "PENDING"
                }

                log_cb = self.add_terminal_log

                # Task 1: Text RAG (Embeddings via mxbai-embed-large + Multimodal OCR via Gemma-4 31B jika scan)
                t1 = self.coordinator.run_worker1_text_rag(
                    dokumen_id, completed_sections,
                    spread_images_b64=spread_images_b64,
                    raw_text=raw_text,
                    spread_label=spread_label,
                    log_cb=log_cb
                )
                # Task 2: Synthetic QA Visual (gemma4:31b multimodal - UNLIMITED & NO 10 CAP)
                t2 = self.coordinator.run_worker2_synthetic_qa(
                    dokumen_id, completed_sections,
                    spread_images_b64=spread_images_b64,
                    raw_text=raw_text,
                    spread_label=spread_label,
                    log_cb=log_cb
                )
                # Task 3: Graph RAG Visual (gemma4:31b multimodal)
                t3 = self.coordinator.run_worker3_graph_rag(
                    dokumen_id, completed_sections,
                    spread_images_b64=spread_images_b64,
                    raw_text=raw_text,
                    spread_label=spread_label,
                    log_cb=log_cb
                )
                # Task 4: Vision RAG (PNG render + Visual Diagram/Workflow Extraction via Gemma-4 31B)
                t4 = self.coordinator.run_worker4_vision_rag(
                    dokumen_id, spread_pages, reader,
                    spread_images_b64=spread_images_b64,
                    spread_label=spread_label,
                    raw_text=raw_text,
                    log_cb=log_cb
                )

                results = await asyncio.gather(t1, t2, t3, t4, return_exceptions=True)

                # Validasi hasil paralel
                w1_res = results[0] if not isinstance(results[0], Exception) else {"count": 0, "items": []}
                w1_chunks = w1_res.get("count", 0) if isinstance(w1_res, dict) else (w1_res if isinstance(w1_res, int) else 0)
                w1_items = w1_res.get("items", []) if isinstance(w1_res, dict) else []

                w2_qa = results[1] if not isinstance(results[1], Exception) else []

                w3_res = results[2] if not isinstance(results[2], Exception) else {"count": 0, "triplets": []}
                w3_relations = w3_res.get("count", 0) if isinstance(w3_res, dict) else (w3_res if isinstance(w3_res, int) else 0)
                w3_triplets = w3_res.get("triplets", []) if isinstance(w3_res, dict) else []

                w4_res = results[3] if not isinstance(results[3], Exception) else {"saved_images": 0, "visual_chunks": 0, "items": []}
                w4_saved = w4_res.get("saved_images", 0) if isinstance(w4_res, dict) else (w4_res if isinstance(w4_res, int) else 0)
                w4_chunks = w4_res.get("visual_chunks", 0) if isinstance(w4_res, dict) else 0
                w4_items = w4_res.get("items", []) if isinstance(w4_res, dict) else []

                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        logger.error(f"❌ [WORKER_PARALLEL_ERROR] Worker {i+1} error: {res}")
                        self.add_terminal_log(f"W{i+1}", "ERROR", f"Error pada worker {i+1}: {str(res)}")

                self.worker_states["w1_text"] = "DONE"
                self.worker_states["w2_qa"] = "DONE"
                self.worker_states["w3_graph"] = "DONE"
                self.worker_states["w4_vision"] = "DONE"

                for qa in w2_qa[:2]:
                    self.add_terminal_log("W2_QA", "INFO", f"  • Highlight: \"{qa.get('question')}\"")

                for tr in w3_triplets[:2]:
                    self.add_terminal_log("W3_GRAPH", "INFO", f"  • Graph: ({tr.get('source')}) ──[{tr.get('relation')}]──> ({tr.get('target')})")

                for vis in w4_items[:2]:
                    self.add_terminal_log("W4_VISION", "INFO", f"  • Visual: [{vis.get('type')}] {vis.get('title', '')[:50]}")

                # Task 5: LoRA Fine-Tuning dataset ingest
                self.worker_states["w5_lora"] = "RUNNING"
                w5_res = await self.coordinator.run_worker5_lora_ingest(dokumen_id, w2_qa, log_cb=log_cb)
                w5_count = w5_res.get("count", 0) if isinstance(w5_res, dict) else (w5_res if isinstance(w5_res, int) else 0)
                w5_samples = w5_res.get("samples", []) if isinstance(w5_res, dict) else []
                self.worker_states["w5_lora"] = "DONE"

                # Simpan artefak nyata dari bentangan ini untuk live inspector
                self.last_spread_artifacts = {
                    "doc_id": dokumen_id,
                    "doc_title": judul,
                    "nomor_dokumen": self.current_nomor_dokumen,
                    "spread_label": spread_label,
                    "page_left": page_left,
                    "page_right": page_right,
                    "total_pages": total_pages,
                    "chunks": w1_items,
                    "qa_pairs": w2_qa,
                    "graph_triplets": w3_triplets,
                    "visual_diagrams": w4_items,
                    "lora_samples": w5_samples
                }

                # 5. Commit Checkpoint Bentangan Halaman
                commit_page_num = spread_pages[-1]
                await CheckpointManager.commit_page_checkpoint(
                    dokumen_id=dokumen_id,
                    page_num=commit_page_num,
                    total_pages=total_pages,
                    pending_buffer=spread_data.get("pending_buffer", {}),
                    qa_count_delta=len(w2_qa),
                    graph_count_delta=w3_relations
                )
                last_page = commit_page_num
                self.add_terminal_log("SYSTEM", "SUCCESS", f"💾 Checkpoint Halaman {commit_page_num}/{total_pages} berhasil di-commit ke ragdb.")

            except Exception as page_err:
                self.latest_log = f"Error pada Bentangan {spread_label}: {str(page_err)}"
                logger.error(f"❌ [SPREAD_ERROR] Error pada Bentangan {spread_label} Dokumen {dokumen_id}: {page_err}")
                await CheckpointManager.rollback_dirty_pages(dokumen_id, spread_pages, last_page)
                reader.close()
                raise page_err

        reader.close()
        self.latest_log = f"Dokumen {dokumen_id} selesai diproses 100%"
        logger.info(f"🎉 [DOC_FINISHED] Dokumen {dokumen_id} ({judul}) SELESAI DIPROSES 100%!")
        return True

    async def run_nightly_loop(
        self,
        force_run: bool = False,
        max_docs: Optional[int] = None,
        page_limit: Optional[int] = None,
        specific_doc_id: Optional[int] = None
    ):
        """
        Siklus utama training malam.
        """
        self.is_running = True
        self.stop_requested = False
        self.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.latest_log = "Sinkronisasi antrean dokumen dari ragdb..."

        logger.info("=" * 70)
        logger.info(f"🚀 CAKRA AI NIGHTLY TRAINING ENGINE DIMULAI (Model: {self.model_name})")
        logger.info(f"⏰ Jendela Waktu: 18:00 WIB s/d 07:30 WIB (Hard stop 08:00 WIB)")
        logger.info(f"🎯 Database Target: ragdb (Eksklusif)")
        logger.info("=" * 70)

        # 1. Sync & enroll dokumen dari ragdb
        await self.sync_ragdb_documents_to_checkpoints()

        # 2. Ambil antrean dokumen prioritas
        if specific_doc_id:
            async with get_ragdb_conn() as conn:
                row = await conn.fetchrow("SELECT * FROM nightly_training_checkpoints WHERE dokumen_id = $1", specific_doc_id)
                queue = [dict(row)] if row else []
        else:
            raw_queue = await CheckpointManager.get_next_documents_queue(limit=50)
            queue = [d for d in raw_queue if d.get("file_path") and os.path.exists(d["file_path"])]

        if not queue:
            self.latest_log = "Semua dokumen di ragdb sudah selesai! Antrean kosong."
            logger.info("✅ [NIGHTLY_ORCHESTRATOR] Semua dokumen di ragdb sudah selesai diproses! Antrean kosong.")
            self.is_running = False
            return

        logger.info(f"📋 [QUEUE] Ditemukan {len(queue)} dokumen dalam antrean prioritas training.")

        docs_processed = 0
        for doc in queue:
            if self.stop_requested:
                self.latest_log = "Training dihentikan oleh user"
                break

            if not self.is_within_training_window(force_run):
                self.latest_log = "Jendela waktu malam berakhir (07:30 WIB)"
                logger.info("⏰ [SCHEDULE] Jendela training malam berakhir (Pukul 07:30 WIB). Sistem standby hingga 18:00 besok.")
                break

            try:
                success = await self.process_single_document(doc, force_run=force_run, page_limit=page_limit)
                if success:
                    docs_processed += 1
                if max_docs and docs_processed >= max_docs:
                    logger.info(f"🎯 [LIMIT] Mencapai batas maksimal {max_docs} dokumen untuk sesi ini.")
                    break
            except Exception as e:
                logger.error(f"❌ [ORCHESTRATOR_DOC_FAILED] Dokumen {doc['dokumen_id']} gagal diproses: {e}")
                continue

        self.latest_log = f"Selesai. Total {docs_processed} dokumen tuntas."
        logger.info(f"🏁 [NIGHTLY_FINISHED] Sesi training selesai. Total {docs_processed} dokumen diproses.")
        await self.coordinator.close()
        self.is_running = False


# ── GLOBAL SINGLETON ENGINE UNTUK DASHBOARD UI ──────────────────────────────────
_global_orchestrator: Optional[NightlyTrainingOrchestrator] = None
_global_task: Optional[asyncio.Task] = None

def get_orchestrator_instance() -> NightlyTrainingOrchestrator:
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = NightlyTrainingOrchestrator()
    return _global_orchestrator

async def trigger_nightly_training(
    force_now: bool = True,
    max_docs: Optional[int] = None,
    page_limit: Optional[int] = None,
    specific_doc_id: Optional[int] = None
) -> Dict[str, Any]:
    """Memicu training dari tombol Dashboard Analytics atau API"""
    global _global_task
    orchestrator = get_orchestrator_instance()
    
    if orchestrator.is_running:
        return {"status": "already_running", "message": "Training malam sudah sedang berjalan!"}

    orchestrator.stop_requested = False
    _global_task = asyncio.create_task(
        orchestrator.run_nightly_loop(
            force_run=force_now,
            max_docs=max_docs,
            page_limit=page_limit,
            specific_doc_id=specific_doc_id
        )
    )
    return {
        "status": "started",
        "message": "Nightly Training Engine berhasil dimulai!",
        "started_at": datetime.now().isoformat()
    }

async def stop_nightly_training() -> Dict[str, Any]:
    """Menghentikan training secara aman & simpan checkpoint dari tombol Dashboard Analytics"""
    orchestrator = get_orchestrator_instance()
    if not orchestrator.is_running:
        return {"status": "not_running", "message": "Training tidak sedang berjalan."}

    orchestrator.stop_requested = True
    return {
        "status": "stopping",
        "message": "Sinyal stop telah dikirim. Sistem akan menghentikan proses di halaman saat ini dan menyimpan checkpoint aman."
    }

_last_dash_status_cache: Optional[Dict[str, Any]] = None
_last_dash_status_time: float = 0.0

async def get_nightly_dashboard_status() -> Dict[str, Any]:
    """Mengambil status live dan ringkasan checkpoint ragdb untuk Dashboard Analytics"""
    global _last_dash_status_cache, _last_dash_status_time
    import time
    now = time.time()
    orchestrator = get_orchestrator_instance()

    # Jika cache masih berumur < 3 detik, kembalikan data cache dengan status worker/log realtime
    if _last_dash_status_cache is not None and (now - _last_dash_status_time < 3.0):
        cached = dict(_last_dash_status_cache)
        cached["is_running"] = orchestrator.is_running
        cached["started_at"] = orchestrator.started_at
        cached["latest_log"] = orchestrator.latest_log
        cached["workers"] = dict(orchestrator.workers)
        cached["current_doc"] = orchestrator.current_doc
        cached["current_spread_left"] = orchestrator.current_spread_left
        cached["current_spread_right"] = orchestrator.current_spread_right
        return cached

    # Query ringkasan statistik dari ragdb
    stats = {
        "total_docs": 0,
        "completed_docs": 0,
        "in_progress_docs": 0,
        "pending_docs": 0,
        "total_qa": 0,
        "total_graph_nodes": 0
    }

    try:
        async with get_ragdb_conn() as conn:
            row_counts = await conn.fetch("""
                SELECT status, COUNT(*) as count 
                FROM nightly_training_checkpoints 
                GROUP BY status
            """)
            for r in row_counts:
                st = r["status"]
                cnt = r["count"]
                stats["total_docs"] += cnt
                if st == "COMPLETED":
                    stats["completed_docs"] += cnt
                elif st in ("IN_PROGRESS", "PAUSED"):
                    stats["in_progress_docs"] += cnt
                elif st == "PENDING":
                    stats["pending_docs"] += cnt

            total_qa = await conn.fetchval("SELECT COUNT(*) FROM rag_document_questions")
            stats["total_qa"] = total_qa or 0

            total_nodes = await conn.fetchval("SELECT COUNT(*) FROM knowledge_graph_nodes")
            stats["total_graph_nodes"] = total_nodes or 0
    except Exception as e:
        logger.warning(f"[DASHBOARD_STATUS] Gagal fetch stats ragdb: {e}")

    tiered_stats = {}
    try:
        tiered_stats = await CheckpointManager.get_training_statistics()
    except Exception as e:
        logger.warning(f"[DASHBOARD_STATUS] Gagal fetch tiered stats: {e}")

    result = {
        "is_running": orchestrator.is_running,
        "started_at": orchestrator.started_at,
        "current_doc": {
            "id": orchestrator.current_doc_id,
            "title": orchestrator.current_doc_title,
            "current_page": orchestrator.current_page,
            "total_pages": orchestrator.current_total_pages
        } if orchestrator.is_running else None,
        "workers": orchestrator.worker_states,
        "latest_log": orchestrator.latest_log,
        "stats": stats,
        "tiered_stats": tiered_stats,
        "schedule": {
            "window": "18:00 WIB s/d 07:30 WIB",
            "hard_stop": "08:00 WIB",
            "mode": "Otomatis via Cronjob & Tombol Manual"
        }
    }
    _last_dash_status_cache = result
    _last_dash_status_time = now
    return result

async def get_live_monitor_data() -> Dict[str, Any]:
    """Mengambil payload data realtime bentangan 2 halaman, status worker, log terminal, dan training artifacts"""
    orchestrator = get_orchestrator_instance()
    return orchestrator.get_live_monitor_payload()
