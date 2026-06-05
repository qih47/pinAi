import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from backend.app.core.paths import LOGS_DIR

def setup_root_logger():
    """
    Konfigurasi sistem logging terpusat untuk CAKRA AI.
    Output dialirkan ke dua arah secara asinkronus-kompatibel:
    1. StreamHandler (Terminal/MobaXterm via stdout dengan format taktis).
    2. RotatingFileHandler (Berkas fisik di folder logs/ agar log lama tidak membengkak).
    """
    # Ambil root logger sistem
    root_logger = logging.getLogger()
    
    # Jika logger sudah dikonfigurasi, skip agar tidak ada double log output
    if root_logger.hasHandlers():
        return root_logger

    # Kunci level terendah yang ditangkap (INFO agar tidak terlalu bising, DEBUG jika butuh oprek daleman)
    root_logger.setLevel(logging.INFO)

    # 1. FORMATTER TAKTIS (Menampilkan Waktu, Nama Modul, Level, dan Pesan)
    log_format = logging.Formatter(
        fmt="🕒 %(asctime)s [%(levelname)s] (%(name)s) ──> %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 2. HANDLER 1: STREAM (TERMINAL & JOURNALCTL)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_format)
    stream_handler.setLevel(logging.INFO)
    root_logger.addHandler(stream_handler)

    # 3. HANDLER 2: ROTATING FILE (PENGAMAN STORAGE SERVER)
    # File log disimpan secara absolut memanfaatkan paths.py
    log_file_path = os.path.join(LOGS_DIR, "cakra_backend.log")
    
    # MaxBytes: 10MB per file, BackupCount: 5 file. Jika penuh, log lama otomatis di-rotate!
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10 Megabytes
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Matikan log bising dari library pihak ketiga (Uvicorn / HTTPX) agar tidak memenuhi journalctl lo
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    print(f"📝 [LOGGING] Sistem logging terpusat aktif! File fisik: {log_file_path}")
    return root_logger