import os
import sys
import json
import logging
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from backend.app.core.paths import LOGS_DIR

# Import context variable untuk mengambil ID Request secara global
try:
    from backend.app.utils.request_logging import request_id_var
except ImportError:
    request_id_var = None


class RequestIDFilter(logging.Filter):
    """
    Filter global yang bertugas menyuntikkan (inject) atribut `request_id` 
    ke setiap baris log yang dihasilkan oleh sistem.
    """
    def filter(self, record):
        if request_id_var:
            req_id = request_id_var.get()
            record.request_id = req_id if req_id else "SYSTEM"
        else:
            record.request_id = "SYSTEM"
        return True


class AnalyticJSONFormatter(logging.Formatter):
    """
    Formatter kustom untuk mengubah LogRecord Python menjadi string JSON berformat analytic.
    Sangat cocok untuk ingest ke ELK Stack, Datadog, atau di-parsing oleh skrip Python.
    """
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "SYSTEM"),
            "message": record.getMessage(),
            "module": record.module,
            "filename": record.filename,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }

        # Jika log mengandung info exception/error, ekstrak stack trace-nya
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        
        # Ekstrak data tambahan apa pun (extra fields) yang dipassing via logger.info(extra={...})
        # Record standar memiliki keys tetap, kita ambil sisanya.
        standard_keys = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName", "processName",
            "process", "message", "request_id"
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in standard_keys}
        if extra:
            log_obj["extra"] = extra

        return json.dumps(log_obj)


def setup_root_logger():
    """
    Konfigurasi sistem logging terpusat untuk CAKRA AI dengan arsitektur Dual-Output.
    Output dialirkan ke:
    1. StreamHandler: Teks estetik untuk developer (dibaca di terminal).
    2. RotatingFileHandler: Format JSONL murni untuk kebutuhan analitik server.
    """
    # Ambil root logger sistem
    root_logger = logging.getLogger()
    
    # Jika logger sudah dikonfigurasi, skip agar tidak double logging
    if root_logger.hasHandlers():
        return root_logger

    root_logger.setLevel(logging.INFO)
    
    # Tambahkan Filter Global untuk menyuntikkan Request-ID
    req_filter = RequestIDFilter()

    # 1. HANDLER 1: STREAM (TERMINAL / CONSOLE) - Estetik untuk Manusia
    console_format = logging.Formatter(
        fmt="🕒 %(asctime)s [%(levelname)s] [%(request_id)s] (%(name)s) ──> %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(console_format)
    stream_handler.setLevel(logging.INFO)
    stream_handler.addFilter(req_filter)
    root_logger.addHandler(stream_handler)

    # 2. HANDLER 2: ROTATING FILE (ANALITIK JSON) - Terstruktur untuk Mesin
    log_file_path = os.path.join(LOGS_DIR, "cakra_analytics.jsonl")
    
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10 Megabytes
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(AnalyticJSONFormatter())
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(req_filter)
    root_logger.addHandler(file_handler)

    # Matikan log bising dari library pihak ketiga (Uvicorn / HTTPX / asyncpg)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    root_logger.info(f"[LOGGING] Analytic Logging system initialized. Log file: {log_file_path}")
    return root_logger