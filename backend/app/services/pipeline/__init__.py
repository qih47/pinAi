"""
CAKRA AI Pipeline Package
=========================

Single-model Gemma4 Agentic Engine.
Layer 0 (qwen3 gateway) dan Layer 2 (gemma executor) sudah digabung
menjadi satu engine: execute_gemma_agentic().

Layer 1 (cognitive analyzer) sudah deprecated sebelumnya dan tidak dipakai.
"""

from .pdf_extraction import extract_pdf_text
from .gemma_agentic_engine import execute_gemma_agentic
from .sse_validation import (
    format_sse,
    format_sse_error,
    SSEEventType,
    SSEValidator,
)

__all__ = [
    # Core agentic engine
    "execute_gemma_agentic",

    # PDF utility
    "extract_pdf_text",

    # SSE utilities
    "format_sse",
    "format_sse_error",
    "SSEEventType",
    "SSEValidator",
]
