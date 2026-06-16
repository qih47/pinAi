"""
SSE Event validation and formatting for backend-frontend synchronization.

This module ensures SSE events conform to the API Contract defined in docs/API_CONTRACT.md
Provides validation and formatting utilities for Server-Sent Events (SSE) streaming.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SSEEventType(str, Enum):
    """SSE event type constants matching API Contract"""
    THINKING = "thinking"
    CHUNK = "chunk"
    SOURCES = "sources"
    DONE = "done"
    ERROR = "error"


class SSEValidator:
    """Validate SSE events conform to schema"""

    @staticmethod
    def validate_thinking(data: Dict[str, Any]) -> bool:
        """Validate thinking event has required fields"""
        thinking = data.get("thinking")
        if not isinstance(thinking, str) or not thinking.strip():
            return False
        return True

    @staticmethod
    def validate_chunk(data: Dict[str, Any]) -> bool:
        """Validate chunk event has content"""
        chunk = data.get("chunk")
        if chunk is None or not isinstance(chunk, str):
            return False
        return True

    @staticmethod
    def validate_sources(data: Dict[str, Any]) -> bool:
        """Validate sources event has proper array structure"""
        sources = data.get("sources")
        if not isinstance(sources, list) or len(sources) == 0:
            return False
        
        for source in sources:
            if not isinstance(source, dict) or "id" not in source or "content" not in source:
                return False
        
        return True

    @staticmethod
    def validate_done(data: Dict[str, Any]) -> bool:
        """Validate done event"""
        return data.get("done") is True

    @staticmethod
    def validate_event(data: Dict[str, Any], event_type: str = None) -> bool:
        """
        Validate entire SSE event structure.
        
        Args:
            data: Event dictionary to validate
            event_type: Optional specific event type to validate against
            
        Returns:
            True if event is valid, False otherwise
        """
        # Must have at least one non-null field
        has_content = (
            data.get("thinking") is not None or
            data.get("chunk") is not None or
            data.get("sources") is not None or
            data.get("done") is True
        )
        
        if not has_content:
            logger.debug("[SSE_VALIDATION] Empty event, all fields null")
            return False

        # If event_type specified, validate accordingly
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
    
    Formats a Server-Sent Event as a JSON string ready for streaming to frontend.
    Each event includes metadata (timestamp, event_type) for debugging and sync.
    
    Args:
        chunk: Main response text content (default: empty string)
        thinking: Intermediate reasoning/analysis (default: empty string)
        done: Stream completion flag (default: False)
        sources: RAG citations array [{id, content, ...}] (default: None)
        event_type: One of SSEEventType values for logging/debugging (default: None)
    
    Returns:
        JSON string ready for streaming (or empty string if event invalid)
        
    Example:
        >>> format_sse(chunk="Hello ", event_type="chunk")
        '{"chunk": "Hello ", "thinking": null, "done": false, "sources": null, ...}'
        
        >>> format_sse(thinking="Analyzing...", event_type="thinking")
        '{"chunk": null, "thinking": "Analyzing...", "done": false, "sources": null, ...}'
    """
    
    # Build event object
    event = {
        "chunk": chunk if chunk else None,
        "thinking": thinking if thinking else None,
        "done": done,
        "sources": sources,
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    
    # Validate event has content
    if not SSEValidator.validate_event(event, event_type):
        logger.debug(f"[SSE_VALIDATION] Skipping empty event")
        return ""  # Don't emit empty events
    
    # Serialize to JSON
    try:
        json_str = json.dumps(event, ensure_ascii=False)
        return json_str
    except (TypeError, ValueError) as e:
        logger.error(f"[SSE_VALIDATION] JSON serialization error: {e}")
        return ""


def format_sse_error(
    code: str,
    message: str,
    detail: str = None,
    request_id: str = None,
) -> str:
    """
    Format SSE error event.
    
    Args:
        code: Error code (e.g., 'RAG_ERROR', 'LLM_ERROR')
        message: User-friendly message in Indonesian
        detail: Developer detail (optional)
        request_id: Request ID for tracing (optional)
    
    Returns:
        JSON string for error event
        
    Example:
        >>> format_sse_error("LLM_ERROR", "Gagal menghasilkan respons", request_id="ABC123")
        '{"chunk": null, "thinking": null, "done": true, "error": {...}}'
    """
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
    
    return json.dumps(event, ensure_ascii=False)
