import torch
import logging

logger = logging.getLogger("CAKRA_HARDWARE")

def check_gpu_status():
    """Melakukan pengecekan VRAM dan memastikan CUDA tersedia untuk Pindad Server."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"🚀 [HARDWARE] GPU Terdeteksi: {gpu_name}")
        print(f"💾 [HARDWARE] Total VRAM: {vram_total:.2f} GB")
        return True
    else:
        print("⚠️ [HARDWARE] Peringatan: CUDA tidak tersedia, sistem berjalan di CPU mode!")
        return False

# Kita bisa tambah fungsi untuk mengatur alokasi memory di sini nanti