import os
import torch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def optimize_torch():
    """Optimize PyTorch settings for A40 - Full Hardware Acceleration"""
    if torch.cuda.is_available():
        # --- 0. PREPARATION ---
        # Pastikan folder offload ada untuk menghindari OSError
        offload_path = "/tmp/offload"
        if not os.path.exists(offload_path):
            try:
                os.makedirs(offload_path, exist_ok=True)
                logger.info(f"📁 Created offload folder at {offload_path}")
            except Exception as e:
                logger.error(f"❌ Failed to create offload folder: {e}")

        # --- 1. AMPERE OPTIMIZATION (TF32) ---
        # Ini wajib untuk A40 (Ampere) agar perkalian matriks 3x lebih cepat
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

        # --- 2. KERNEL OPTIMIZATION ---
        # Mencari algoritma terbaik untuk hardware lo (cuDNN Autotuner)
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False

        # --- 3. MEMORY MANAGEMENT ---
        # Bersihkan sisa VRAM dari reload sebelumnya
        torch.cuda.empty_cache()
        # Mengunci alokasi agar tidak rebutan dengan proses background/system
        # Menggunakan 85% dari total 16GB A40
        torch.cuda.set_per_process_memory_fraction(0.85)

        # --- 4. ATTENTION BOOSTER (XFORMERS / SDPA) ---
        try:
            # Memaksa PyTorch menggunakan jalur tercepat: Flash Attention & Memory Efficient
            # Jalur ini sangat optimal untuk CUDA 11.8 + A40
            torch.backends.cuda.enable_mem_efficient_sdp(True)
            torch.backends.cuda.enable_flash_sdp(True)

            # Matikan fallback jalur lambat (Math/Vanilla Attention)
            # supaya kita tahu pasti kalau kita pakai hardware acceleration
            torch.backends.cuda.enable_math_sdp(False)

            # Cek apakah library xformers benar-benar bisa di-load
            import xformers

            logger.info(
                "🚀 Xformers detected: Flash Attention / SDPA forced to High Speed."
            )
        except ImportError:
            # Jika xformers tidak ada, tetap aktifkan SDPA bawaan PyTorch 2.x
            torch.backends.cuda.enable_math_sdp(True)
            logger.warning(
                "⚠️ Xformers not found. Falling back to standard PyTorch SDPA."
            )
        except Exception as e:
            logger.error(f"⚠️ Attention optimization error: {e}")

        logger.info(
            "🔥 PyTorch A40 (CUDA 11.8) Full Optimization Applied Successfully."
        )
    else:
        logger.warning("☁️ CUDA not available. Running on CPU mode (No Acceleration).")
