# 🛠️ SYNC OPTIMIZATION — IMPLEMENTATION GUIDE

**Goal**: Implement HIGH priority recommendations (1-2 hours)  
**Files to Modify**: 3 files  
**Complexity**: Easy  
**Testing**: Manual + E2E

---

## STEP 1: Create API Contract Document

**File**: Create `backend/docs/API_CONTRACT.md`

```markdown
# CAKRA AI — Frontend-Backend API Contract

**Version**: 1.0  
**Last Updated**: June 14, 2026  
**Owner**: Engineering Team (Backend + Frontend)

## 1. Chat Stream Endpoint

### Request
```

POST /api/chat/stream
Content-Type: application/json
Authorization: Bearer {jwt_token}
X-NPP-Header: {employee_npp}
X-Request-ID: {uuid}

{
"session_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
"messages": [
{"role": "user", "content": "What is X?"},
{"role": "assistant", "content": "X is..."}
],
"mode": "auto",
"temperature": 0.7,
"attachment_paths": ["document.pdf", "image.png"],
"isolated_doc_id": null
}

````

### Response (SSE Stream)

Endpoints emit JSON-Lines format (one JSON object per line):

**Event 1: Thinking Process**
```json
{"thinking": "Analyzing question...", "chunk": null, "done": false, "sources": null, "event_type": "thinking", "timestamp": "2026-06-14T10:30:00Z"}
````

**Event 2: Search Results**

```json
{
  "thinking": null,
  "chunk": null,
  "done": false,
  "sources": [
    {
      "id": "doc_123",
      "content": "Relevant excerpt",
      "source_file": "policy.pdf",
      "page": 5
    },
    {
      "id": "doc_124",
      "content": "Another excerpt",
      "source_file": "manual.pdf",
      "page": 12
    }
  ],
  "event_type": "sources",
  "timestamp": "2026-06-14T10:30:01Z"
}
```

**Event 3: Response Chunks (Streamed)**

```json
{"thinking": null, "chunk": "Based on the documentation, ", "done": false, "sources": null, "event_type": "chunk", "timestamp": "2026-06-14T10:30:02Z"}
{"thinking": null, "chunk": "X is a core concept that...", "done": false, "sources": null, "event_type": "chunk", "timestamp": "2026-06-14T10:30:02Z"}
```

**Event 4: Stream Complete**

```json
{
  "thinking": null,
  "chunk": null,
  "done": true,
  "sources": null,
  "event_type": "done",
  "timestamp": "2026-06-14T10:30:05Z"
}
```

### Field Definitions

- **thinking**: string | null — Intermediate reasoning (for display in expandable section)
- **chunk**: string | null — Response content (accumulate for final answer)
- **sources**: array | null — RAG citations (display below response)
- **done**: boolean — Stream completion flag
- **event_type**: string — For debugging ('thinking', 'chunk', 'sources', 'done')
- **timestamp**: string — ISO 8601 timestamp for sync

### Validation Rules

- Each event must have at least one non-null field
- Sources must be array with {id, content, ...} objects
- Chunk can be empty string but not null
- Done event must have done=true

## 2. Error Response Format

```json
{
  "status": 400,
  "code": "SESSION_NOT_FOUND",
  "message": "Sesi chat tidak ditemukan",
  "detail": "Session f47ac10b-58cc-4372-a567-0e02b2c3d479 does not exist in database",
  "request_id": "ABC12345",
  "timestamp": "2026-06-14T10:30:00Z"
}
```

### Error Codes Reference

| Code              | HTTP | Meaning                      | User Message                  |
| ----------------- | ---- | ---------------------------- | ----------------------------- |
| UNAUTHORIZED      | 401  | No valid JWT token           | Silakan login terlebih dahulu |
| FORBIDDEN         | 403  | Token expired or invalid NPP | Sesi Anda telah berakhir      |
| SESSION_NOT_FOUND | 404  | Session doesn't exist        | Sesi tidak ditemukan          |
| INVALID_REQUEST   | 400  | Malformed request            | Format request tidak valid    |
| FILE_TOO_LARGE    | 413  | Upload > 100MB               | File terlalu besar            |
| ATTACHMENT_ERROR  | 400  | PDF/image processing failed  | Gagal memproses lampiran      |
| RAG_ERROR         | 500  | Search engine failed         | Gagal mencari konteks         |
| LLM_ERROR         | 500  | Model inference failed       | Gagal menghasilkan respons    |
| INTERNAL_ERROR    | 500  | Unexpected server error      | Terjadi kesalahan server      |

````

---

## STEP 2: Implement Backend Validation

**File**: `backend/app/services/pipeline/sse_validation.py` (NEW)

```python
"""
SSE Event validation and formatting for backend-frontend synchronization.

This module ensures SSE events conform to the API Contract defined in docs/API_CONTRACT.md
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
        """Validate thinking event"""
        thinking = data.get("thinking")
        if not isinstance(thinking, str) or not thinking.strip():
            return False
        return True

    @staticmethod
    def validate_chunk(data: Dict[str, Any]) -> bool:
        """Validate chunk event"""
        chunk = data.get("chunk")
        if chunk is None or not isinstance(chunk, str):
            return False
        return True

    @staticmethod
    def validate_sources(data: Dict[str, Any]) -> bool:
        """Validate sources event"""
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
        """Validate entire SSE event"""
        # Must have at least one non-null field
        has_content = (
            data.get("thinking") is not None or
            data.get("chunk") is not None or
            data.get("sources") is not None or
            data.get("done") is True
        )

        if not has_content:
            logger.warning("[SSE_VALIDATION] Empty event, all fields null")
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

    Args:
        chunk: Main response text
        thinking: Intermediate reasoning
        done: Stream completion flag
        sources: RAG citations [{id, content, ...}]
        event_type: One of SSEEventType values (for logging)

    Returns:
        JSON string ready for streaming (or empty string if event invalid)

    Example:
        >>> format_sse(chunk="Hello ", event_type="chunk")
        '{"chunk": "Hello ", "thinking": null, "done": false, "sources": null, "event_type": "chunk", "timestamp": "2026-06-14T..."}'
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
        logger.debug(f"[SSE] Skipping empty event: {event}")
        return ""  # Don't emit empty events

    # Serialize to JSON
    try:
        json_str = json.dumps(event, ensure_ascii=False)
        return json_str
    except (TypeError, ValueError) as e:
        logger.error(f"[SSE] JSON serialization error: {e}")
        return ""


def format_sse_error(code: str, message: str, detail: str = None, request_id: str = None) -> str:
    """
    Format SSE error event.

    Args:
        code: Error code (e.g., 'RAG_ERROR', 'LLM_ERROR')
        message: User-friendly message
        detail: Developer detail (optional)
        request_id: Request ID for tracing

    Returns:
        JSON string for error event
    """
    event = {
        "chunk": None,
        "thinking": None,
        "done": True,
        "sources": None,
        "event_type": "error",
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "request_id": request_id,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    return json.dumps(event, ensure_ascii=False)
````

**Update**: `backend/app/services/pipeline/layer2_executor.py`

Replace old imports and \_format_sse calls:

```python
# OLD
from backend.app.services.pipeline.system_prompts import _format_sse

# NEW
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType

# Then replace all calls:
# OLD: yield _format_sse("hello", "thinking...", False)
# NEW: yield format_sse(chunk="hello", thinking="thinking...", event_type=SSEEventType.CHUNK)
```

---

## STEP 3: Update Frontend Event Parsing

**File**: `webui/src/services/endpoints.js`

```javascript
// ADD THIS VALIDATION FUNCTION
function validateSSEEvent(parsedData) {
  // ✅ Validate event has at least one field
  const hasValidFields =
    parsedData.thinking !== undefined ||
    parsedData.chunk !== undefined ||
    parsedData.sources !== undefined ||
    parsedData.done === true;

  if (!hasValidFields) {
    console.warn(
      "[SSE_VALIDATION] Empty event, all fields undefined",
      parsedData,
    );
    return false;
  }

  // ✅ Validate sources format if present
  if (parsedData.sources !== null && parsedData.sources !== undefined) {
    if (!Array.isArray(parsedData.sources)) {
      console.warn("[SSE_VALIDATION] Sources not array:", parsedData.sources);
      return false;
    }

    // Validate each source has required fields
    for (const source of parsedData.sources) {
      if (!source.id || !source.content) {
        console.warn("[SSE_VALIDATION] Source missing id or content:", source);
        return false;
      }
    }
  }

  return true;
}

// THEN UPDATE streamChat FUNCTION
export async function streamChat(
  { sessionUuid, messages, chatMode, isolatedDocId, attachmentPaths, npp },
  { onThinking, onSources, onChunk, onDone, onError },
  options = {},
) {
  const { timeoutMs = 5 * 60 * 1000 } = options; // 5 minute default timeout

  try {
    // ✅ ADD: Timeout support
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      console.warn("[SSE_TIMEOUT] Request timeout after " + timeoutMs + "ms");
      controller.abort();
    }, timeoutMs);

    const token = localStorage.getItem("cakra_token");
    const headers = {
      "Content-Type": "application/json",
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const cleanNpp = (npp || "").trim();
    const isPlaceholder = !cleanNpp || cleanNpp.startsWith("NPP");
    if (!isPlaceholder) {
      headers["X-NPP-Header"] = cleanNpp;
    }

    const baseURL = apiClient.defaults.baseURL || "/api";
    const response = await fetch(`${baseURL}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        session_uuid: sessionUuid,
        messages: messages,
        mode: chatMode,
        temperature: 0.7,
        isolated_doc_id: isolatedDocId,
        attachment_paths: attachmentPaths,
      }),
      signal: controller.signal, // ✅ ADD: Abort signal
    });

    clearTimeout(timeoutId); // ✅ ADD: Clear timeout on success

    if (!response.ok) {
      // ✅ Extract rich error info
      let errorData = {};
      try {
        errorData = await response.json();
      } catch (e) {
        errorData = { message: "Unknown error" };
      }

      const errorCode = errorData.code || "UNKNOWN_ERROR";
      const errorMessage = errorData.message || `HTTP ${response.status}`;
      const requestId = errorData.request_id;

      console.error(`[SSE_ERROR] ${errorCode}: ${errorMessage}`, { requestId });

      throw new Error(
        JSON.stringify({
          code: errorCode,
          message: errorMessage,
          requestId,
        }),
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let streamBuffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      streamBuffer += decoder.decode(value, { stream: true });
      const lines = streamBuffer.split("\n");
      streamBuffer = lines.pop();

      for (const line of lines) {
        const cleanedLine = line.trim();
        if (!cleanedLine) continue;

        try {
          const parsedData = JSON.parse(cleanedLine);

          // ✅ ADD: Validate event structure
          if (!validateSSEEvent(parsedData)) {
            console.debug("[SSE] Skipping invalid event:", parsedData);
            continue;
          }

          // ✅ ADD: Log event for debugging
          console.debug(
            `[SSE_EVENT] ${parsedData.event_type || "?"} @ ${parsedData.timestamp}`,
          );

          // ✅ Handle error events
          if (parsedData.error) {
            console.error(
              `[SSE_ERROR_EVENT] ${parsedData.error.code}: ${parsedData.error.message}`,
              parsedData.error,
            );
            if (onError) {
              onError(new Error(JSON.stringify(parsedData.error)));
            }
            continue;
          }

          // Handle regular events
          if (
            parsedData.thinking !== undefined &&
            parsedData.thinking &&
            onThinking
          ) {
            onThinking(parsedData.thinking);
          }

          if (
            parsedData.sources &&
            Array.isArray(parsedData.sources) &&
            parsedData.sources.length > 0 &&
            onSources
          ) {
            onSources(parsedData.sources);
          }

          if (parsedData.chunk !== undefined && parsedData.chunk && onChunk) {
            onChunk(parsedData.chunk);
          }

          if (parsedData.done === true && onDone) {
            onDone();
          }
        } catch (jsonErr) {
          console.warn(`[SSE_PARSE_ERROR] ${jsonErr.message}`);
          // Continue on parse errors (might be incomplete line)
        }
      }
    }
  } catch (error) {
    clearTimeout(timeoutId); // ✅ Cleanup

    // ✅ Handle abort error
    if (error.name === "AbortError") {
      const timeoutError = new Error(
        `Request timeout. Backend did not respond within ${options.timeoutMs || 300000}ms`,
      );
      if (onError) onError(timeoutError);
      return;
    }

    if (onError) {
      onError(error);
    } else {
      throw error;
    }
  }
}
```

---

## STEP 4: Test the Changes

### Backend Testing

```python
# python -c "
from backend.app.services.pipeline.sse_validation import format_sse, SSEValidator

# Test thinking event
event = {'thinking': 'Analyzing...', 'chunk': None, 'done': False, 'sources': None}
assert SSEValidator.validate_event(event, 'thinking'), 'Thinking validation failed'
print('✅ Thinking event valid')

# Test chunk event
event = {'thinking': None, 'chunk': 'Response text', 'done': False, 'sources': None}
assert SSEValidator.validate_event(event, 'chunk'), 'Chunk validation failed'
print('✅ Chunk event valid')

# Test sources event
event = {'thinking': None, 'chunk': None, 'done': False, 'sources': [{'id': '1', 'content': 'text'}]}
assert SSEValidator.validate_event(event, 'sources'), 'Sources validation failed'
print('✅ Sources event valid')

# Test empty event (should fail)
event = {'thinking': None, 'chunk': None, 'done': False, 'sources': None}
assert not SSEValidator.validate_event(event), 'Empty event should be invalid'
print('✅ Empty event correctly rejected')
#"
```

### Frontend Testing

```javascript
// console in browser after loading endpoints.js

// Test valid thinking event
validateSSEEvent({
  thinking: "Analyzing...",
  chunk: null,
  done: false,
  sources: null,
  event_type: "thinking",
}); // Should log: true

// Test invalid sources
validateSSEEvent({
  thinking: null,
  chunk: null,
  done: false,
  sources: ["not an object"], // Invalid
  event_type: "sources",
}); // Should log: false

console.log("✅ Frontend validation working");
```

---

## STEP 5: Verify Integration

After implementing above changes, verify:

```bash
# 1. Backend imports work
cd backend && python -c "from backend.app.services.pipeline.sse_validation import format_sse; print('✅ Backend imports OK')"

# 2. Frontend no errors
# Open browser console in webui, check no import errors

# 3. Manual E2E test
# 1. Start backend: python -m uvicorn backend.app.main:app --reload
# 2. Start frontend: npm run dev
# 3. Send chat message
# 4. Monitor browser console for [SSE_EVENT] logs
# 5. Check all events have event_type and timestamp
```

---

## Summary of Changes

| File                   | Change                                    | Lines | Time  |
| ---------------------- | ----------------------------------------- | ----- | ----- |
| NEW: sse_validation.py | Create validation module                  | 200   | 30min |
| layer2_executor.py     | Update imports + function calls           | 10    | 10min |
| endpoints.js           | Add validation + timeout + error handling | 80    | 30min |
| docs/API_CONTRACT.md   | Create contract document                  | 100   | 30min |

**Total Time**: ~2 hours  
**Impact**: HIGH (improves reliability + debugging)
