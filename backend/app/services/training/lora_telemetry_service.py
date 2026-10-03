"""
CAKRA AI — LoRA Training Telemetry Service
=========================================
Membaca dan mem-parsing telemetri live dari log training QLoRA (train_cakra_router.log)
serta metrik utilisasi GPU NVIDIA secara real-time.
"""

import os
import re
import glob
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("CAKRA_LORA_TELEMETRY")

ROOT_DIR = "/home/qisthi/pinAi"
LOG_PATH = os.path.join(ROOT_DIR, "logs/training/train_cakra_router.log")


class LoRATelemetryService:
    @staticmethod
    def get_telemetry() -> Dict[str, Any]:
        """Membaca status real-time proses training LoRA dan utilisasi GPU."""
        telemetry = {
            "is_running": False,
            "target": "cakra-router-lora",
            "model": "unsloth/gemma-4-31B-it-unsloth-bnb-4bit",
            "current_step": 0,
            "total_steps": 2098,
            "percentage": 0.0,
            "speed": "0.0s/it",
            "eta": "00:00:00",
            "elapsed": "00:00",
            "batch_size": 24,
            "loss": None,
            "learning_rate": None,
            "gpu_memory": "N/A",
            "gpu_utilization": "N/A",
            "raw_status": "Idle",
            "checkpoints": []
        }

        # 1. Cek apakah proses aktif di OS
        try:
            res = subprocess.run(["pgrep", "-f", "train_dispatcher_router.py"], capture_output=True, text=True)
            if res.stdout.strip():
                telemetry["is_running"] = True
                telemetry["raw_status"] = "Training Active"
            else:
                telemetry["raw_status"] = "Stopped / Completed"
        except Exception:
            pass

        # 2. Cek GPU via nvidia-smi
        try:
            res_gpu = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if res_gpu.stdout.strip():
                parts = [p.strip() for p in res_gpu.stdout.strip().split(",")]
                if len(parts) >= 3:
                    used_mb = int(parts[0])
                    total_mb = int(parts[1])
                    util = int(parts[2])
                    telemetry["gpu_memory"] = f"{used_mb:,} MiB / {total_mb:,} MiB"
                    telemetry["gpu_utilization"] = f"{util}%"
        except Exception:
            pass

        # 3. Parse log file
        if os.path.exists(LOG_PATH):
            try:
                with open(LOG_PATH, "rb") as f:
                    # Baca 64KB terakhir
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    offset = max(0, size - 65536)
                    f.seek(offset)
                    content = f.read().decode("utf-8", errors="ignore")

                # Ubah carriage return menjadi newline agar terbaca rapi
                clean_lines = content.replace("\r", "\n").split("\n")
                clean_lines = [l.strip() for l in clean_lines if l.strip()]

                # Cari pola tqdm: "  2%|▏         | 47/2098 [11:46<8:35:10, 15.07s/it]"
                step_pattern = re.compile(r'(\d+)%\s*\|.*?\|\s*(\d+)/(\d+)\s*\[([^<]+)<([^,]+),\s*([^\]]+)\]')
                for line in reversed(clean_lines):
                    m = step_pattern.search(line)
                    if m:
                        telemetry["percentage"] = float(m.group(1))
                        telemetry["current_step"] = int(m.group(2))
                        telemetry["total_steps"] = int(m.group(3))
                        telemetry["elapsed"] = m.group(4).strip()
                        telemetry["eta"] = m.group(5).strip()
                        telemetry["speed"] = m.group(6).strip()
                        break

                # Cari loss jika ada dict log: {'loss': 0.8123, 'learning_rate': 0.0002, ...}
                loss_pattern = re.compile(r"\{'loss':\s*([0-9\.]+)")
                lr_pattern = re.compile(r"'learning_rate':\s*([0-9e\.\-]+)")
                for line in reversed(clean_lines):
                    if telemetry["loss"] is None:
                        lm = loss_pattern.search(line)
                        if lm:
                            telemetry["loss"] = float(lm.group(1))
                    if telemetry["learning_rate"] is None:
                        lrm = lr_pattern.search(line)
                        if lrm:
                            telemetry["learning_rate"] = float(lrm.group(1))
                    if telemetry["loss"] is not None and telemetry["learning_rate"] is not None:
                        break

            except Exception as e:
                logger.warning(f"Error parsing training log: {e}")

        # 4. Cek Checkpoint yang sudah tersimpan
        ckpt_dir = os.path.join(ROOT_DIR, "models/adapters/cakra-router-lora")
        if os.path.exists(ckpt_dir):
            ckpts = glob.glob(os.path.join(ckpt_dir, "checkpoint-*"))
            telemetry["checkpoints"] = sorted([os.path.basename(c) for c in ckpts])

        return telemetry


lora_telemetry_service = LoRATelemetryService()
