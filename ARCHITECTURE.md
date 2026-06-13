# CAKRA AI — Architecture Reference

> **Version**: 2.0 (Post-Refactoring)
> **Last Updated**: 2026-06-14

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Agentic Pipeline — 4 Layer Sequential](#agentic-pipeline--4-layer-sequential)
3. [Backend Module Structure](#backend-module-structure)
4. [Frontend Module Structure](#frontend-module-structure)
5. [Database Schema](#database-schema)
6. [Logging Standards](#logging-standards)
7. [Deprecation Shims](#deprecation-shims)

---

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         cakra/ (Monorepo)                                    │
├────────────────────────────────┬─────────────────────────────────────────────┤
│   webui/ (React + Vite)        │   backend/ (FastAPI + asyncpg)              │
│   Port: 5173 (dev)             │   Port: 5000                                │
│   State: Zustand               │   LLM: Ollama (localhost:11434)             │
│   HTTP Client: Axios (REST)    │   Embedding: mxbai-embed-large (1024-dim)   │
│   Stream: native fetch/SSE     │   Reranker: BAAI/bge-reranker-v2-m3 (GPU)  │
└────────────────────────────────┴─────────────────────────────────────────────┘
                                          │
              ┌───────────────────────────┴────────────────────────┐
              ▼                                                     ▼
      ┌──────────────────┐                               ┌──────────────────┐
      │  ragdb           │                               │  hris_db         │
      │  (PostgreSQL +   │                               │  (PostgreSQL     │
      │   pgvector)      │                               │   remote HRIS    │
      │                  │                               │   192.168.11.55) │
      │  • chat_sessions │                               │  • master_unit   │
      │  • chat_messages │                               │  • master_person │
      │  • dokumen       │                               │  • tabel_user    │
      │  • dokumen_chunk │                               └──────────────────┘
      │  • ai_memory     │
      │  • session_login │
      └──────────────────┘
```

---

## Agentic Pipeline — 4 Layer Sequential

Every chat message passes through this sequential pipeline. Each layer has its own module.

```text
User Message
      │
      ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 0 — Gateway                                            │
│ Module: services/pipeline/layer0_gateway.py                  │
│ Model: Qwen 0.5B (MODEL_GATEWAY)                             │
│                                                              │
│  Mode auto  → classify: documents | flash                    │
│  Mode docs  → generate 3 rewritten_queries                   │
│  Mode flash → flash intent analysis (is_coding, is_greeting) │
│                                                              │
│  Output: { target_pipeline, rewritten_queries, is_greeting,  │
│            is_coding, confidence, detected_language }        │
│                                                              │
│  Reliability: retry_with_backoff (max 2) + circuit_breaker   │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         ▼                            ▼
  target="documents"           target="flash"
         │                            │
         ▼                            ▼
┌──────────────────┐    ┌──────────────────────────────────────┐
│ RAG Parallel     │    │ BYPASS Layer 1 — Rule-Based Params   │
│ asyncio.gather   │    │ (Instant, no LLM call)               │
│                  │    │                                      │
│ 3 queries        │    │ Module: services/pipeline/           │
│ → pgvector+FTS   │    │         layer1_analyzer.py           │
│ → RRF scoring    │    │         _get_fallback_cognitive_params│
│ → BGE Reranker   │    │         _rule_based()                │
│ → Dynamic thresh │    └──────────────────────────────────────┘
└────────┬─────────┘
         │ (Parallel with Layer 1)
         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1 — Cognitive Analyzer                                 │
│ Module: services/pipeline/layer1_analyzer.py                 │
│ Model: Qwen 3B (MODEL_ROUTER)                                │
│                                                              │
│  Input: user message + gateway_result + 5-turn history       │
│         + employee memory + OCR text (if present)           │
│                                                              │
│  Output: 35 cognitive parameters                             │
│   • emotion, urgency_level, empathy_phrase                   │
│   • detected_intent, action_plan, response_structure         │
│   • tone, estimated_response_length, key_points              │
│   • linguistic_mirroring_strategy, user_pronoun_preference   │
│                                                              │
│  Reliability: retry_with_backoff (max 2, 30s timeout)        │
│               + layer1_circuit_breaker                       │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2 — Gemma Agentic Executor                             │
│ Module: services/pipeline/layer2_executor.py                 │
│ Model: Gemma4 12B (MODEL_PERSONA)                            │
│                                                              │
│  Input: system_prompt (built from 35 params) + RAG context   │
│         + 5-turn history + OCR text                          │
│                                                              │
│  Features:                                                   │
│  • Adaptive num_ctx: 2048 (chitchat) → 32768 (RAG)          │
│  • Adaptive temperature: 0.3 (code) → 0.75 (greeting)       │
│  • <think> tag parsing → logged to terminal only            │
│  • Leak filter: [PANGGIL_RAG:] stripped at chunk level       │
│  • SSE streaming directly to browser                         │
│                                                              │
│  Output: SSE chunks { chunk, thinking, done, sources }       │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ DATABASE PERSISTENCE (Post-stream)                           │
│  • auto_update_session_title (LLM-based via title_generator) │
│  • save_chat_message (role=assistant)                        │
│  • save_dialogue_corpus (ai_dialogue_corpus)                 │
└──────────────────────────────────────────────────────────────┘
```

---

## Backend Module Structure

```text
backend/
├── app/
│   ├── api/
│   │   ├── dependencies/
│   │   │   └── auth.py                  # get_current_user_npp (token validator)
│   │   ├── endpoints/
│   │   │   ├── chat/                    # Chat endpoint package
│   │   │   │   ├── __init__.py          # Aggregates all sub-routers
│   │   │   │   ├── sessions.py          # Session CRUD (list, create, rename, pin, delete)
│   │   │   │   ├── stream.py            # POST /chat/stream — SSE pipeline orchestration
│   │   │   │   ├── attachments.py       # POST /chat/documents/upload
│   │   │   │   └── feedback.py          # POST /chat/messages/{id}/feedback
│   │   │   ├── auth.py                  # POST /login, GET /verify-session, POST /logout
│   │   │   ├── documents.py             # CRUD for RAG regulatory documents
│   │   │   ├── health.py                # GET /health — server + model status
│   │   │   ├── admin.py                 # Admin endpoints (audit logs, cache management)
│   │   │   ├── notifications.py         # SSE notifications + audit_router
│   │   │   └── chat.py                  # [DEPRECATED] backward-compat shim → chat/
│   │   ├── schemas/                     # Centralized Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── common_schemas.py        # Pagination, error responses
│   │   │   ├── auth_schemas.py          # LoginRequest, SessionResponse
│   │   │   ├── chat_schemas.py          # ChatStreamRequest, FeedbackRequest
│   │   │   ├── document_schemas.py      # DocumentCreate, DocumentResponse
│   │   │   ├── admin_schemas.py         # Admin panel schemas
│   │   │   └── notification_schemas.py  # Notification event schemas
│   │   └── router.py                    # Main APIRouter — mounts all sub-routers
│   │
│   ├── core/
│   │   ├── config.py                    # Settings (pydantic_settings, .env loader)
│   │   ├── database.py                  # asyncpg dual-pool (ragdb + hris_db)
│   │   ├── hardware.py                  # GPU/RAM info
│   │   ├── llm_client.py                # stream_ollama_chat, generate_json_response
│   │   ├── logging_setup.py             # Logging configuration
│   │   └── paths.py                     # UPLOAD_DIR path resolver
│   │
│   ├── services/
│   │   ├── agent/
│   │   │   ├── cognitive_loop.py        # Agent cognitive loop
│   │   │   └── router_engine.py         # Qwen Model Slot 1 router
│   │   ├── chat/
│   │   │   ├── __init__.py
│   │   │   └── chat_history_service.py  # CRUD: sessions, messages, attachments, corpus
│   │   ├── document_chunking/
│   │   │   ├── manager.py               # Chunking orchestrator
│   │   │   └── strategies/
│   │   │       ├── parent_child.py      # Hierarchical chunking strategy
│   │   │       └── text_standard.py     # Standard text chunking
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   └── memory_service.py        # Long-term memory (ai_memory table)
│   │   ├── notifications/
│   │   │   ├── __init__.py
│   │   │   └── notification_service.py  # SSE real-time notification broker
│   │   ├── pipeline/                    # Agentic pipeline package (refactored)
│   │   │   ├── __init__.py              # Re-exports all public functions
│   │   │   ├── layer0_gateway.py        # Layer 0: intent classification + query rewrite
│   │   │   ├── layer1_analyzer.py       # Layer 1: 35 cognitive params + fallback
│   │   │   ├── layer2_executor.py       # Layer 2: Gemma stream executor
│   │   │   ├── pdf_extraction.py        # PDF text extraction (pymupdf + vision fallback)
│   │   │   └── system_prompts.py        # Gemma system prompt builder
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── rag_service.py           # Hybrid RAG: RRF + reranker
│   │   │   ├── vector_service.py        # mxbai-embed-large via Ollama API
│   │   │   └── reranker_service.py      # BGE cross-encoder (CUDA)
│   │   ├── system/
│   │   │   ├── __init__.py
│   │   │   └── background_tasks.py      # APScheduler: memory consolidation, session cleanup
│   │   └── vision/
│   │       └── vision_service.py        # MiniCPM-V OCR service
│   │
│   └── utils/
│       ├── connection_manager.py        # StreamConnectionManager for SSE cleanup
│       ├── embedding_cache.py           # LRU embedding cache (SHA256 key, 1h TTL)
│       ├── employee_cache.py            # In-memory employee name cache (1h TTL)
│       ├── request_logging.py           # X-Request-ID middleware + structured logging
│       ├── retry_handler.py             # retry_with_backoff + CircuitBreaker
│       ├── title_generator.py           # LLM-based session title generator (async)
│       ├── token_expiry.py              # Token expiry management (8h TTL)
│       └── vector_index.py              # HNSW index management (pgvector)
│
└── main.py                              # FastAPI app, lifespan, CORS, routers
```

---

## Frontend Module Structure

```text
webui/
├── src/
│   ├── App.jsx                          # Root app with router
│   ├── components/
│   │   ├── ui/
│   │   │   ├── GuestWelcome.jsx         # Guest landing page
│   │   │   └── ToastProvider.jsx        # Global toast notification wrapper
│   │   ├── NotificationBell.jsx         # Bell icon + badge counter
│   │   ├── NotificationPanel.jsx        # Slide-out notification history
│   │   └── SessionExpiryStatus.jsx      # Countdown + extend session button
│   ├── features/
│   │   ├── admin/
│   │   │   ├── AuditLogsPage.jsx        # Audit log browser (admin only)
│   │   │   └── CacheStatsPage.jsx       # Embedding cache monitoring
│   │   └── chat/
│   │       ├── ChatPage.jsx             # Main orchestrator
│   │       ├── chatPage.styles.js       # Centralized style objects
│   │       └── components/
│   │           ├── ChatArea.jsx          # Virtuoso virtual list renderer
│   │           ├── ChatBubble.jsx        # Message bubble router
│   │           ├── CakraResponseRenderer.jsx # Markdown + code block renderer
│   │           ├── CodeBlockHeader.jsx   # Copy/download code block UI
│   │           ├── CustomModeSelector.jsx # Mode selector: auto|flash|documents
│   │           ├── HeaderDropdownMenu.jsx # Theme, logout menu
│   │           ├── PlusButton.jsx        # File attachment trigger
│   │           ├── RAGMetrics.jsx        # RAG timing + cache hit display
│   │           ├── SendButton.jsx        # Submit + loading state
│   │           ├── Sidebar.jsx           # Chat history + navigation
│   │           ├── SourceCitation.jsx    # RAG source cards
│   │           └── UserBubble.jsx        # User message + attachment viewer
│   ├── hooks/
│   │   ├── useNotifications.js          # SSE-based real-time notifications
│   │   ├── useSessionExpiry.js          # Countdown timer + extension
│   │   ├── useSessionTitle.js           # Polling for LLM-generated title
│   │   ├── useToast.js                  # Toast notification hook
│   │   └── useTokenRefresh.js           # Background token refresh (3 strategies)
│   ├── services/
│   │   ├── apiClient.js                 # Axios instance + X-Request-ID interceptor
│   │   ├── auditService.js              # Audit log API calls + CSV/JSON export
│   │   └── endpoints.js                 # Centralized API + SSE function library
│   └── stores/
│       ├── authStore.js                 # Zustand: user, token, expiresAt
│       └── chatStore.js                 # Zustand: sessions, messages, streaming state
└── index.html
```

---

## Database Schema

### ragdb — Primary Operational Database

| Table                | Purpose                                                                |
| -------------------- | ---------------------------------------------------------------------- |
| `users`              | Employee records (npp, fullname, divisi, role) — synced from HRIS on login |
| `session_login`      | Active session tokens + IP + expires_at (8h TTL)                       |
| `history_login`      | Audit trail: LOGIN/LOGOUT events per NPP                               |
| `chat_sessions`      | Chat sessions (uuid, title, is_pinned, is_deleted, npp)                |
| `chat_messages`      | Messages per session (role, message_text, thought, timestamp)          |
| `chat_attachments`   | File upload metadata (file_name, path, mime_type, extracted_text)      |
| `ai_dialogue_corpus` | User-assistant pairs for future fine-tuning and retrieval              |
| `ai_memory`          | Long-term employee memory (mem_key, mem_value) — consolidated nightly  |
| `dokumen`            | Regulatory document registry (title, number, type_id)                  |
| `dokumen_chunk`      | Text chunks + 1024-dim pgvector embeddings                             |
| `dokumen_section`    | Hierarchical section metadata                                           |
| `jenis_dokumen`      | Document type categories (SKEP, SK Direksi, SOP, etc.)                 |

### Dual-Pool Connection

```python
# ragdb — primary operational store
asyncpg pool: min=5, max=20

# hris_db — remote HRIS credential validation only
asyncpg pool: min=3, max=10
```

### Vector Index (pgvector)

```sql
-- HNSW index on dokumen_chunk.embedding
CREATE INDEX IF NOT EXISTS dokumen_chunk_embedding_hnsw_idx
ON dokumen_chunk USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

---

## Logging Standards

All log messages follow the structured bracketed tag format:

```
[TAG_NAME] message text | key=value | key2=value2
```

### Tag Naming Convention

| Module              | Logger Name        | Tag Examples                              |
| ------------------- | ------------------ | ----------------------------------------- |
| `router.py`         | `CAKRA_ROUTER`     | `[ROUTER_INIT]`                           |
| `layer0_gateway.py` | `CAKRA_PIPELINE`   | `[LAYER_0_GATEWAY]`, `[LAYER_0_FLASH]`   |
| `layer1_analyzer.py`| `CAKRA_PIPELINE`   | `[LAYER_1_ANALYZER]`, `[LAYER_1_FALLBACK]`|
| `layer2_executor.py`| `CAKRA_PIPELINE`   | `[LAYER_2_EXECUTOR]`, `[LAYER_2_THINK]`  |
| `stream.py`         | `CAKRA_CHAT_API`   | `[PIPELINE]`, `[PARALLEL_RAG]`           |
| Auth middleware      | `CAKRA_AUTH`       | `[AUTH_PASS]`, `[AUTH_REJECT]`           |
| RAG service         | `CAKRA_RAG`        | `[RAG_SEARCH]`, `[RAG_RERANK]`           |

### Log Levels

| Level     | Usage                                                         |
| --------- | ------------------------------------------------------------- |
| `DEBUG`   | Full payload dumps (cognitive_params, gateway JSON), disabled in prod |
| `INFO`    | Normal operation flow, key metrics, state transitions         |
| `WARNING` | Recoverable errors, fallbacks triggered, unexpected conditions |
| `ERROR`   | Unrecoverable errors, exception traces, pipeline failures     |

> **Prohibited**: emoji prefixes (🔥, ⚡, ✅), Indonesian slang (cuy, bolo, asu, bro), ALL-CAPS exclamations

---

## Deprecation Shims

The following files are **deprecated backward-compatibility shims** that re-export from their respective packages. They will be removed in a future version.

| Deprecated File                              | Replaced By                          |
| -------------------------------------------- | ------------------------------------ |
| `services/pipeline_layer_executor.py`        | `services/pipeline/` package         |
| `api/endpoints/chat.py`                      | `api/endpoints/chat/` package        |
| `services/chat_history_service.py`           | `services/chat/chat_history_service.py` |
| `services/memory_service.py`                 | `services/memory/memory_service.py`  |
| `services/notification_service.py`           | `services/notifications/notification_service.py` |
| `services/rag_service.py`                    | `services/rag/rag_service.py`        |
| `services/vector_service.py`                 | `services/rag/vector_service.py`     |
| `services/reranker_service.py`               | `services/rag/reranker_service.py`   |
| `services/background_tasks.py`               | `services/system/background_tasks.py` |
