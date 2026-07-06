"""
B11 — Structured Logging dengan Request ID Tracing
Middleware untuk inject X-Request-ID dan structured logging per-request.
"""

import uuid
import time
import logging
from collections import deque
from datetime import datetime
from typing import Callable, Optional
from contextvars import ContextVar
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Buffer untuk menyimpan 100 metrik request latency terakhir untuk dashboard
recent_latencies = deque(maxlen=100)


# Context variable untuk request ID (accessible di semua threads/tasks dalam request context)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


def get_request_id() -> str:
    """Get current request ID dari context."""
    req_id = request_id_var.get()
    return req_id or "no-id"


class RequestIDLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware untuk inject X-Request-ID header dan structured logging.
    
    Fitur:
    - Generate atau reuse X-Request-ID header
    - Store request ID di context variable
    - Log request/response dengan request ID
    - Track request duration
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request dan inject request ID.
        
        Args:
            request: HTTP request
            call_next: Next middleware/endpoint
        
        Returns:
            HTTP response dengan X-Request-ID header
        """
        # Ambil dari header atau generate baru
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())[:8]
        
        # Set ke context variable (accessible di seluruh request lifetime)
        token = request_id_var.set(request_id)
        
        # Log request
        logger = logging.getLogger("cakra.http")
        start_time = time.time()
        
        logger.info(
            f"[{request_id}] → {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Store in latency buffer
            recent_latencies.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "latency": round(duration_ms)
            })
            
            # Log response
            logger.info(
                f"[{request_id}] ← {response.status_code} ({duration_ms:.1f}ms)",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{request_id}] ✗ Error: {str(e)[:100]} ({duration_ms:.1f}ms)",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "duration_ms": duration_ms
                },
                exc_info=True
            )
            raise
        
        finally:
            # Reset context (cleanup)
            request_id_var.reset(token)


def setup_request_id_logging():
    """
    Setup structured logging dengan request ID.
    Call ini di main.py saat startup.
    """
    
    # Create custom logger formatter dengan request ID
    class RequestIDFormatter(logging.Formatter):
        """Custom formatter yang inject request ID ke log message."""
        
        def format(self, record):
            # Ambil request ID dari context
            request_id = request_id_var.get()
            
            # Add ke record
            if request_id:
                record.request_id = request_id
                if '[' not in record.getMessage():
                    record.msg = f"[{request_id}] {record.msg}"
            
            return super().format(record)
    
    # Apply formatter ke semua handlers
    logger = logging.getLogger("CAKRA_REQUEST_LOGGING")
    for handler in logging.root.handlers:
        formatter = RequestIDFormatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
    
    logger.info("[REQUEST_LOGGING] Request ID tracing setup completed")
