"""
CAKRA AI — Agentic & Dynamic Synthetic Generator Service (Worker 7)
===================================================================
Service pengelola background task untuk membangkitkan dataset sintetis:
- 25.000 Sampel Call 2 Core (Coding, XML tags, Tools, Memory, Anti-Sycophancy, Widgets, Persona, Guest)
- 25.000 Sampel Call 1 Router (Normal Chat, Preset UI, Collab Space)

Berjalan mandiri di background, non-destruktif, dan melaporkan telemetri real-time ke UI Dashboard.
"""

import os
import sys
import json
import time
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("CAKRA_AGENTIC_GENERATOR")

STATUS_FILE = Path("/home/qisthi/pinAi/data/finetune/agentic_generator_status.json")
GENERATOR_SCRIPT = Path("/home/qisthi/pinAi/backend/scripts/finetune/generate_agentic_dataset.py")
PYTHON_BIN = "/home/qisthi/pinAi/rag_env/bin/python" if Path("/home/qisthi/pinAi/rag_env/bin/python").exists() else sys.executable


class AgenticGeneratorService:
    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._is_running = False
        self._started_at: Optional[str] = None
        self._last_log: str = "Standby (Siap memproduksi sampel agentic 25k)"

    def get_status(self) -> Dict[str, Any]:
        """Membaca status terkini dari memori dan file status IPC."""
        is_proc_alive = False
        if self._process is not None and self._process.returncode is None:
            is_proc_alive = True
        elif not is_proc_alive and self._is_running:
            # Periksa jika proses selesai sendiri
            self._is_running = False

        default_stats = {
            "is_running": self._is_running or is_proc_alive,
            "status": "RUNNING" if (self._is_running or is_proc_alive) else "IDLE",
            "started_at": self._started_at,
            "latest_log": self._last_log,
            "target_samples": 25000,
            "core_progress": {
                "total": 0,
                "target": 25000,
                "coding_files": 0,
                "instream_tools": 0,
                "anti_sycophancy": 0,
                "memory_recall": 0,
                "visual_widgets": 0,
                "persona_modes": 0,
                "guest_guard": 0
            },
            "router_progress": {
                "total": 0,
                "target": 25000,
                "normal_chat": 0,
                "preset_mode": 0,
                "collab_space": 0
            },
            "output_files": {
                "core_file": "/home/qisthi/pinAi/data/finetune/agentic_core_train.jsonl",
                "router_file": "/home/qisthi/pinAi/data/finetune/agentic_router_train.jsonl"
            }
        }

        if STATUS_FILE.exists():
            try:
                data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
                # Timpa status running jika proses lokal masih aktif
                data["is_running"] = self._is_running or is_proc_alive
                data["status"] = "RUNNING" if (self._is_running or is_proc_alive) else ("DONE" if data.get("core_progress", {}).get("total", 0) >= 25000 else "IDLE")
                if self._started_at and not data.get("started_at"):
                    data["started_at"] = self._started_at
                return data
            except Exception as e:
                logger.warning(f"[AGENTIC_GEN] Gagal baca status file: {e}")

        return default_stats

    async def start_generator(self, target_samples: int = 25000) -> Dict[str, Any]:
        """Memicu background process pembuat dataset sintetis."""
        status = self.get_status()
        if status.get("is_running"):
            return {
                "status": "already_running",
                "message": "Worker 7 (Agentic Generator) sudah sedang berjalan!",
                "data": status
            }

        os.makedirs(STATUS_FILE.parent, exist_ok=True)
        self._started_at = datetime.now().isoformat()
        self._is_running = True
        self._last_log = f"Memulai pembangkitan {target_samples} sampel agentic..."

        cmd = [
            str(PYTHON_BIN),
            str(GENERATOR_SCRIPT),
            "--samples", str(target_samples),
            "--output_dir", "/home/qisthi/pinAi/data/finetune",
            "--status_file", str(STATUS_FILE)
        ]

        logger.info(f"[AGENTIC_GEN] Meluncurkan generator: {' '.join(cmd)}")
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Monitor stdout di background task terpisah
        asyncio.create_task(self._monitor_stream(self._process))

        return {
            "status": "started",
            "message": f"Worker 7 berhasil dimulai dengan target {target_samples} sampel!",
            "started_at": self._started_at
        }

    async def _monitor_stream(self, proc: asyncio.subprocess.Process):
        """Membaca output terminal generator secara asinkron."""
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    self._last_log = text
                    logger.debug(f"[AGENTIC_GEN_LOG] {text}")

            await proc.wait()
            if proc.returncode == 0:
                self._last_log = "Pembangkitan 25.000 sampel agentic selesai! Memulai blending dataset siap latih..."
                logger.info("[AGENTIC_GEN] Pembangkitan dataset selesai sukses. Memulai blending dataset siap latih...")

                blender_script = Path("/home/qisthi/pinAi/backend/scripts/finetune/blend_training_datasets.py")
                if blender_script.exists():
                    blender_proc = await asyncio.create_subprocess_exec(
                        str(PYTHON_BIN),
                        str(blender_script),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await blender_proc.wait()
                    if blender_proc.returncode == 0:
                        self._last_log = "Pembangkitan & Blending (75k Core & 65k Router) SELESAI SUKSES!"
                        logger.info("[AGENTIC_GEN] Blending dataset selesai sukses.")
                    else:
                        self._last_log = f"Pembangkitan selesai, tetapi blending gagal (code {blender_proc.returncode})"
                else:
                    self._last_log = "Pembangkitan 25.000 sampel agentic selesai sukses!"

                self._is_running = False
                if STATUS_FILE.exists():
                    try:
                        st = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
                        st["is_running"] = False
                        st["status"] = "DONE"
                        st["latest_log"] = self._last_log
                        st["output_files"] = {
                            "agentic_core_file": "/home/qisthi/pinAi/data/finetune/agentic_core_train.jsonl",
                            "agentic_router_file": "/home/qisthi/pinAi/data/finetune/agentic_router_train.jsonl",
                            "merged_core_file": "/home/qisthi/pinAi/data/finetune/merged_cakra_core.jsonl",
                            "merged_router_file": "/home/qisthi/pinAi/data/finetune/merged_dispatcher_router.jsonl"
                        }
                        STATUS_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")
                    except Exception:
                        pass
            else:
                self._is_running = False
                err = await proc.stderr.read()
                err_text = err.decode("utf-8", errors="replace")[:200]
                self._last_log = f"Generator berhenti dengan error ({proc.returncode}): {err_text}"
                logger.error(f"[AGENTIC_GEN] Error code {proc.returncode}: {err_text}")
        except Exception as e:
            logger.error(f"[AGENTIC_GEN] Exception in monitor stream: {e}")
            self._is_running = False

    async def stop_generator(self) -> Dict[str, Any]:
        """Menghentikan proses generator dengan aman."""
        if self._process is not None and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.sleep(0.5)
                if self._process.returncode is None:
                    self._process.kill()
            except Exception as e:
                logger.warning(f"[AGENTIC_GEN] Error saat kill proses: {e}")

        self._is_running = False
        self._last_log = "Generator dihentikan oleh pengguna."

        # Update file status jika ada
        if STATUS_FILE.exists():
            try:
                data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
                data["is_running"] = False
                data["status"] = "STOPPED"
                data["latest_log"] = self._last_log
                STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

        return {
            "status": "stopped",
            "message": "Worker 7 (Agentic Generator) berhasil dihentikan."
        }


# Singleton Instance
_agentic_service_instance: Optional[AgenticGeneratorService] = None

def get_agentic_generator_service() -> AgenticGeneratorService:
    global _agentic_service_instance
    if _agentic_service_instance is None:
        _agentic_service_instance = AgenticGeneratorService()
    return _agentic_service_instance
