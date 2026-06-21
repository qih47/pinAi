"""
SSE Event validation and formatting for backend-frontend synchronization.

This module ensures SSE events conform to the API Contract defined in docs/API_CONTRACT.md
Provides validation and formatting utilities for Server-Sent Events (SSE) streaming.

Event types:
  - THINKING      : intermediate step info → diteruskan ke frontend
  - CHUNK         : teks respons Gemma → diteruskan ke frontend
  - SOURCES       : metadata dokumen RAG → diteruskan ke frontend
  - DONE          : penanda stream selesai → diteruskan ke frontend
  - ERROR         : error event → diteruskan ke frontend
  - PIPELINE_DATA : payload internal antar layer → TIDAK diteruskan ke frontend,
                    ditangkap oleh chat.py untuk mengekstrak result (Opsi B pattern)
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SSEEventType(str, Enum):
    """SSE event type constants matching API Contract"""
    THINKING      = "thinking"
    STATUS        = "status"
    CHUNK         = "chunk"
    SOURCES       = "sources"
    DONE          = "done"
    ERROR         = "error"
    # Internal-only — ditangkap chat.py, tidak diteruskan ke frontend
    PIPELINE_DATA = "pipeline_data"


class SSEValidator:
    """Validate SSE events conform to schema"""

    @staticmethod
    def validate_thinking(data: Dict[str, Any]) -> bool:
        thinking = data.get("thinking")
        if not isinstance(thinking, str) or not thinking.strip():
            return False
        return True

    @staticmethod
    def validate_chunk(data: Dict[str, Any]) -> bool:
        chunk = data.get("chunk")
        if chunk is None or not isinstance(chunk, str):
            return False
        return True

    @staticmethod
    def validate_sources(data: Dict[str, Any]) -> bool:
        sources = data.get("sources")
        if not isinstance(sources, list) or len(sources) == 0:
            return False
        for source in sources:
            if not isinstance(source, dict) or ("id" not in source and "dokumen_id" not in source):
                return False
        return True

    @staticmethod
    def validate_done(data: Dict[str, Any]) -> bool:
        return data.get("done") is True

    @staticmethod
    def validate_pipeline_data(data: Dict[str, Any]) -> bool:
        """Pipeline data harus punya payload dict."""
        return isinstance(data.get("payload"), dict)

    @staticmethod
    def validate_event(data: Dict[str, Any], event_type: str = None) -> bool:
        """
        Validate entire SSE event structure.
        PIPELINE_DATA divalidasi terpisah — tidak butuh chunk/thinking/sources/done.
        """
        if event_type == SSEEventType.PIPELINE_DATA:
            return SSEValidator.validate_pipeline_data(data)

        has_content = (
            data.get("thinking") is not None
            or data.get("chunk") is not None
            or data.get("sources") is not None
            or data.get("done") is True
        )
        if not has_content:
            logger.debug("[SSE_VALIDATION] Empty event, all fields null")
            return False

        if event_type == SSEEventType.THINKING:
            return SSEValidator.validate_thinking(data)
        elif event_type == SSEEventType.CHUNK:
            return SSEValidator.validate_chunk(data)
        elif event_type == SSEEventType.SOURCES:
            return SSEValidator.validate_sources(data)
        elif event_type == SSEEventType.DONE:
            return SSEValidator.validate_done(data)

        return True


def format_sse(
    chunk: str = "",
    thinking: str = "",
    done: bool = False,
    sources: Optional[List[Dict]] = None,
    event_type: Optional[str] = None,
) -> str:
    """
    Format SSE event conforming to API Contract.
    Untuk internal pipeline_data, gunakan format_sse_pipeline_data().
    """
    event = {
        "chunk": chunk if chunk else None,
        "thinking": thinking if thinking else None,
        "done": done,
        "sources": sources,
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if not SSEValidator.validate_event(event, event_type):
        logger.debug("[SSE_VALIDATION] Skipping empty event")
        return ""

    try:
        return json.dumps(event, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as e:
        logger.error(f"[SSE_VALIDATION] JSON serialization error: {e}")
        return ""


def format_sse_pipeline_data(payload: Dict[str, Any]) -> str:
    """
    Format SSE internal bertipe pipeline_data.

    Event ini TIDAK diteruskan ke frontend — hanya dikonsumsi chat.py
    untuk mengekstrak result dari layer (Opsi B pattern).

    Usage di layer:
        yield format_sse_pipeline_data({"result": gateway_result})

    Usage di chat.py:
        async for sse in execute_layer_0_gateway(...):
            data = json.loads(sse)
            if data.get("event_type") == SSEEventType.PIPELINE_DATA:
                gateway_result = data["payload"]["result"]
            else:
                yield sse
    """
    event = {
        "chunk": None,
        "thinking": None,
        "done": False,
        "sources": None,
        "event_type": SSEEventType.PIPELINE_DATA,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if not SSEValidator.validate_pipeline_data(event):
        logger.error("[SSE_VALIDATION] pipeline_data payload must be a dict")
        return ""

    try:
        return json.dumps(event, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as e:
        logger.error(f"[SSE_VALIDATION] pipeline_data serialization error: {e}")
        return ""


def format_sse_error(
    code: str,
    message: str,
    detail: str = None,
    request_id: str = None,
) -> str:
    """Format SSE error event."""
    event = {
        "chunk": None,
        "thinking": None,
        "done": True,
        "sources": None,
        "event_type": SSEEventType.ERROR,
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "request_id": request_id,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return json.dumps(event, ensure_ascii=False) + "\n"