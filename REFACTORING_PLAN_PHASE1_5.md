# Backend Refactoring Plan — Phase 1: Code Organization & Professionalization

**Document Version**: 1.0  
**Created**: June 13, 2026  
**Scope**: Monolithic file splitting, logging standardization, folder reorganization  
**Target Duration**: 5 phases over 2 weeks  
**Code Quality Target**: 85%+ maintainability, 100% logging consistency

---

## Executive Summary

Backend has grown to **6,850 lines** across **44 files** with several critical issues:

- 2 monolithic files (620-920 lines) violating Single Responsibility Principle
- Inconsistent logging with slang terminology (60% consistency score)
- Mixed Indonesian/English in production code (international team unfriendly)
- Response schemas scattered across codebase (no centralized location)

**Outcome**: Professional, maintainable, enterprise-grade codebase with proper separation of concerns.

---

## Phase Overview

```text
PHASE 1: Large File Splitting (Priority 1-2)
├─ Task 1.1: Split pipeline_layer_executor.py (920 lines → 5 modules)
├─ Task 1.2: Split chat.py endpoints (620 lines → 4 modules)
└─ Task 1.3: Extract schema definitions (centralized)

PHASE 2: Logging Standardization (Priority 3)
├─ Task 2.1: Define logging standards document
├─ Task 2.2: Create logging tags reference
└─ Task 2.3: Replace all logging tags across codebase

PHASE 3: Language & Comments Professionalization (Priority 3)
├─ Task 3.1: Translate Indonesian comments to English
├─ Task 3.2: Standardize docstrings
└─ Task 3.3: Remove slang terminology

PHASE 4: Folder Structure Reorganization (Priority 4)
├─ Task 4.1: Create pipeline/ subfolder
├─ Task 4.2: Create schemas/ subfolder
└─ Task 4.3: Reorganize services/ into categories

PHASE 5: Documentation & README Update (Priority 5)
├─ Task 5.1: Update README with new structure
├─ Task 5.2: Create ARCHITECTURE.md
└─ Task 5.3: Create LOGGING_STANDARDS.md
```

---

## PHASE 1: Large File Splitting

### 🔴 Task 1.1: Split `pipeline_layer_executor.py` (920 lines → 5 modules)

**Current State**: Single file with 4 major sub-systems:

1. PDF extraction (80 lines) — MiniCPM-V OCR fallback
2. Layer 0 Gateway (180 lines) — Intent routing + query rewriting
3. Layer 1 Cognitive Analyzer (200 lines) — 35 parameter generation
4. Layer 2 Executor (300 lines) — Gemma streaming response
5. System prompts (160 lines) — Prompt templates

**Action Items**:

```
Create new structure:
backend/app/services/pipeline/
├── __init__.py
├── layer0_gateway.py        (180 lines)
├── layer1_analyzer.py       (200 lines)
├── layer2_executor.py       (300 lines)
├── pdf_extraction.py        (80 lines)
└── system_prompts.py        (160 lines)
```

**Files to Create**: 5 new files (~5.5 KB total)  
**Files to Delete**: `pipeline_layer_executor.py` (after migration)  
**Refactor Time**: 4 hours  
**Testing Required**: End-to-end pipeline test

**Key Points**:

- Maintain exact same function signatures
- Update all imports in `chat.py` endpoints
- No logic changes — purely structural split
- Create shared utilities module if needed

---

### 🔴 Task 1.2: Split `chat.py` endpoints (620 lines → 4 modules)

**Current State**: Single endpoint file with 4 concerns:

1. Session management (CRUD: create, read, update, delete, pin) — 150 lines
2. Streaming handler (SSE pipeline orchestration) — 250 lines
3. File attachment upload (validation, extraction) — 120 lines
4. Message feedback/rating handler — 60 lines
5. Utility functions — 40 lines

**Action Items**:

```
Create new structure:
backend/app/api/endpoints/
├── chat/
│   ├── __init__.py
│   ├── sessions.py          (150 lines) - Session CRUD
│   ├── stream.py            (250 lines) - SSE streaming
│   ├── attachments.py       (120 lines) - File upload
│   └── feedback.py          (60 lines)  - Message rating
└── api_router.py            (Updated imports)
```

**Files to Create**: 4 new endpoint modules  
**Files to Update**: `api/router.py` (import aggregation)  
**Refactor Time**: 3 hours  
**Testing Required**: All chat endpoints (curl tests)

**Key Points**:

- All 4 modules use same shared `chatStore` functions
- Authentication dependency injection per module
- Consistent response schema across all modules
- Error handling standardization

---

### 🟡 Task 1.3: Centralize API Schemas

**Current State**: Response models scattered in 3 locations:

- Some in endpoint files as `BaseModel` classes
- Some inline in function responses
- No single source of truth

**Action Items**:

```
Create new structure:
backend/app/api/schemas/
├── auth_schemas.py          (auth requests/responses)
├── chat_schemas.py          (chat requests/responses)
├── document_schemas.py      (document requests/responses)
├── notification_schemas.py  (notification schemas)
├── admin_schemas.py         (admin request/response)
└── common_schemas.py        (shared types: PaginationSchema, ErrorSchema)
```

**Files to Create**: 6 schema definition files  
**Refactor Time**: 2 hours  
**Testing Required**: Schema validation tests

---

## PHASE 2: Logging Standardization

### Task 2.1: Define Logging Standards

**Create**: `docs/LOGGING_STANDARDS.md`

**Standards to Define**:

#### Tag Format

```
[MODULE_OPERATION_DETAIL]

Examples:
✅ Good:
  [RAG_SEARCH_SUCCESS]
  [LAYER0_ROUTING_DECISION]
  [AUTH_TOKEN_VALIDATION]
  [PDF_EXTRACTION_START]

❌ Bad:
  [RAG]
  [Layer0]
  [bolo]
  [cuy]
```

#### Emoji Status Indicators (Optional)

```
✅ — Operation succeeded
❌ — Operation failed
⚠️  — Warning condition
🔄 — Process started/in-progress
💾 — Data persisted
🔐 — Security-related
📊 — Metrics/statistics
🚀 — Startup/initialization
🛑 — Shutdown
```

#### Log Levels

```
logger.debug()   → Development tracing, detailed parameter values
logger.info()    → Important business events (user login, job complete)
logger.warning() → Degraded states, fallbacks, timeout situations
logger.error()   → Failures, exceptions, abnormal conditions
```

#### Language Policy

```
PRIMARY: English (code, comments, logs)
COMMENTS: English with [INDONESIAN] translation for business context
EXAMPLE:
  # Initialize RAG pipeline for document search
  # [INDONESIAN] Inisialisasi pipeline RAG untuk pencarian dokumen
  logger.info("[RAG_PIPELINE_START] Hybrid search mode activated")
```

---

### Task 2.2: Create Logging Tags Reference

**Create**: `docs/LOGGING_TAGS_REFERENCE.md`

**Example Content**:

```markdown
# Logging Tags Reference

## Authentication Module

- [AUTH_LOGIN_START] — Login attempt initiated
- [AUTH_LOGIN_SUCCESS] — User authentication successful
- [AUTH_LOGIN_FAILED] — Authentication failed (invalid credentials)
- [AUTH_HRIS_CONNECTION] — HRIS database query executed
- [AUTH_TOKEN_GENERATION] — Session token created
- [AUTH_TOKEN_VALIDATION] — Token verified for session
- [AUTH_TOKEN_EXPIRED] — Expired token detected
- [AUTH_BYPASS_ACTIVATED] — Emergency bypass account used

## Pipeline Module (Layer 0-2)

- [LAYER0_ROUTING_START] — Gateway classification initiated
- [LAYER0_ROUTING_DECISION] — Routing classification: documents|flash
- [LAYER0_QUERY_REWRITE] — Query rewriting phase
- [LAYER1_COGNITIVE_START] — Cognitive analyzer started
- [LAYER1_COGNITIVE_COMPLETE] — 35-parameter generation complete
- [LAYER1_FALLBACK_RULE] — Rule-based fallback activated
- [LAYER2_EXECUTOR_START] — Gemma executor initialized
- [LAYER2_EXECUTOR_STREAMING] — Response streaming to client
- [LAYER2_EXECUTOR_COMPLETE] — Response generation complete

## RAG Module

- [RAG_SEARCH_START] — Hybrid search initiated
- [RAG_SEARCH_PGVECTOR] — pgvector search executed
- [RAG_SEARCH_FTS] — Full-text search executed
- [RAG_SEARCH_RRF] — Reciprocal rank fusion calculated
- [RAG_RERANK_START] — Cross-encoder reranking started
- [RAG_RERANK_COMPLETE] — Reranking scores computed
- [RAG_THRESHOLD_FILTER] — Documents filtered by threshold
- [RAG_CONTEXT_ASSEMBLED] — Final context assembled

## Database Module

- [DB_CONNECTION_POOL_INIT] — Connection pool initialized
- [DB_RAGDB_HEALTH] — RAG database health check
- [DB_HRIS_HEALTH] — HRIS database health check
- [DB_QUERY_ERROR] — Query execution failed
- [DB_CONNECTION_TIMEOUT] — Connection timeout occurred

## Vector Service

- [VECTOR_EMBEDDING_START] — Embedding generation started
- [VECTOR_EMBEDDING_COMPLETE] — Embedding generated
- [VECTOR_CACHE_HIT] — Embedding retrieved from cache
- [VECTOR_CACHE_MISS] — Embedding not in cache
- [VECTOR_VALIDATION_ERROR] — Dimension validation failed

## Document Ingestion

- [INGEST_START] — Document ingestion started
- [INGEST_UPLOAD] — File uploaded successfully
- [INGEST_VALIDATION] — File validation passed
- [INGEST_EXTRACTION] — Text extraction completed
- [INGEST_CHUNKING] — Document chunking completed
- [INGEST_EMBEDDING] — Chunk embeddings generated
- [INGEST_COMPLETE] — Document fully ingested

## Chat Module

- [CHAT_SESSION_CREATE] — New chat session created
- [CHAT_SESSION_RENAME] — Session title updated
- [CHAT_MESSAGE_SAVE] — Message persisted to database
- [CHAT_ATTACHMENT_UPLOAD] — File attachment uploaded
- [CHAT_FEEDBACK_SAVE] — Message feedback recorded

## Error & Circuit Breaker

- [CIRCUIT_BREAKER_OPEN] — Circuit breaker activated (too many failures)
- [CIRCUIT_BREAKER_RESET] — Circuit breaker reset after cooldown
- [RETRY_ATTEMPT] — Retry attempt initiated (attempt X/Y)
- [TIMEOUT_EXCEEDED] — Operation timeout exceeded

## System Events

- [SCHEDULER_JOB_START] — Scheduled job initiated
- [MEMORY_CONSOLIDATION] — Nightly memory consolidation job
- [SESSION_CLEANUP] — Session expiry cleanup job
- [NOTIFICATION_PUBLISH] — Event published to subscribers
```

---

### Task 2.3: Replace All Logging Tags

**Scope**: 44 Python files with ~200+ log statements

**Systematic Replacement**:

1. Group by module (auth, pipeline, rag, chat, etc.)
2. Replace old tags → new standardized tags per module
3. Remove emoji from old format (standardize on task 2.2)
4. Remove slang terminology (bolo, cuy, asu, etc.)

**Example Transformations**:

```python
# BEFORE
logger.info("[LAYER 0] 🚀 Gateway routing decision: documents")
logger.warning("[Auth] ❌ HRIS DB down, bypass bolo activated")
logger.debug("[RAG] 📊 RRF score calculated: 0.85")

# AFTER
logger.info("[LAYER0_ROUTING_DECISION] Routing classification: documents")
logger.warning("[AUTH_BYPASS_ACTIVATED] Emergency bypass account used")
logger.debug("[RAG_SEARCH_RRF] Reciprocal rank fusion score: 0.85")
```

**Files to Update**: All 44 backend files  
**Refactor Time**: 6 hours  
**Validation**: Log output grep for consistency

---

## PHASE 3: Language & Comments Professionalization

### Task 3.1: Translate Indonesian Comments → English

**Scope**: ~300 inline comments in Indonesian

**Approach**:

- Translate but preserve business context in brackets
- Use [INDONESIAN: ...] notation for clarity
- Focus on: system.py, pipeline files, chat.py, rag_service.py

**Example**:

```python
# BEFORE
# Inisialisasi GPU semaphore untuk mencegah memory leak dari multiple concurrent request
gpu_semaphore = asyncio.Semaphore(1)

# AFTER
# Initialize GPU semaphore to prevent memory leaks from multiple concurrent requests
# [INDONESIAN: Mencegah GPU overload saat multiple client request streaming simultaneously]
gpu_semaphore = asyncio.Semaphore(1)
```

**Files to Update**: 15-20 key files  
**Refactor Time**: 3 hours

---

### Task 3.2: Standardize Docstrings

**Create template**: `docs/DOCSTRING_TEMPLATE.md`

**Format**:

```python
def process_query(query: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Process user query through RAG pipeline with optional caching.

    [INDONESIAN: Memproses query pengguna melalui pipeline RAG dengan opsi caching]

    Args:
        query: User query string (supports Indonesian/English)
        use_cache: Whether to check embedding cache first (default: True)

    Returns:
        Dictionary with keys:
            - "embedding": List[float] 1024-dim vector
            - "cache_hit": bool indicating if retrieved from cache
            - "process_time_ms": float milliseconds taken

    Raises:
        TimeoutError: If embedding generation exceeds 30 seconds
        ValidationError: If query length > 5000 characters

    Example:
        >>> result = process_query("Apa itu regulasi SKEP?")
        >>> print(result["cache_hit"])
        False
    """
```

**Files to Update**: All 44 files (1-2 per file average)  
**Refactor Time**: 4 hours

---

### Task 3.3: Remove Slang Terminology

**Slang to Remove**:

- `bolo` → "emergency bypass" / "fallback mode"
- `cuy` → REMOVE (Peruvian slang, inappropriate)
- `asu` → REMOVE (profanity)
- `Lo` → "the system" / "the pipeline"
- Informal greetings in error messages

**Grep Search**:

```bash
grep -r "bolo\|cuy\|asu\|Lo\b" backend/app --include="*.py"
```

**Files to Update**: 3-5 files  
**Refactor Time**: 1 hour

---

## PHASE 4: Folder Structure Reorganization

### Task 4.1: Create Pipeline Subfolder

**Before**:

```
backend/app/services/
└── pipeline_layer_executor.py (920 lines)
```

**After**:

```
backend/app/services/pipeline/
├── __init__.py
├── layer0_gateway.py
├── layer1_analyzer.py
├── layer2_executor.py
├── pdf_extraction.py
└── system_prompts.py
```

**Refactor Time**: 30 minutes

---

### Task 4.2: Create Schemas Subfolder

**Before**:

```
backend/app/api/schemas/
├── auth.py
└── chat.py (mixed concerns)
```

**After**:

```
backend/app/api/schemas/
├── __init__.py
├── auth_schemas.py
├── chat_schemas.py
├── document_schemas.py
├── notification_schemas.py
├── admin_schemas.py
└── common_schemas.py
```

**Refactor Time**: 1 hour

---

### Task 4.3: Reorganize Services by Category

**Before**:

```
backend/app/services/
├── chat_history_service.py
├── memory_service.py
├── rag_service.py
├── vector_service.py
├── reranker_service.py
├── notification_service.py
├── background_tasks.py
└── document_chunking/
```

**After**:

```
backend/app/services/
├── chat/
│   ├── __init__.py
│   └── chat_history_service.py
├── rag/
│   ├── __init__.py
│   ├── rag_service.py
│   ├── vector_service.py
│   └── reranker_service.py
├── pipeline/
│   ├── __init__.py
│   ├── layer0_gateway.py
│   ├── layer1_analyzer.py
│   ├── layer2_executor.py
│   ├── pdf_extraction.py
│   └── system_prompts.py
├── document/
│   ├── __init__.py
│   ├── chunking/
│   │   ├── manager.py
│   │   └── strategies/
│   │       ├── parent_child.py
│   │       └── text_standard.py
├── memory/
│   ├── __init__.py
│   └── memory_service.py
├── notifications/
│   ├── __init__.py
│   └── notification_service.py
├── system/
│   ├── __init__.py
│   └── background_tasks.py
```

**Refactor Time**: 2 hours

---

## PHASE 5: Documentation & README Update

### Task 5.1: Update README.md

**Sections to Update**:

1. Struktur Folder Lengkap — reflect new organization
2. Rekomendasi Optimasi → Fitur Lengkap yang Sudah Ada (all B1-B16 COMPLETED)
3. Add new section: Backend Architecture Overview

**Refactor Time**: 2 hours

---

### Task 5.2: Create ARCHITECTURE.md

**Content**:

- Detailed module responsibilities
- Import dependency graph
- Service interactions
- Data flow diagrams

**Refactor Time**: 3 hours

---

### Task 5.3: Create LOGGING_STANDARDS.md

(Already defined in Phase 2 Task 2.1)

**Refactor Time**: 1 hour (already drafted)

---

## Timeline & Resource Allocation

| Phase     | Tasks                                  | Hours          | Days       | Priority    |
| --------- | -------------------------------------- | -------------- | ---------- | ----------- |
| 1         | File splitting (3 tasks)               | 9              | 1.5        | 🔴 CRITICAL |
| 2         | Logging standardization (3 tasks)      | 8              | 1          | 🔴 CRITICAL |
| 3         | Language professionalization (3 tasks) | 8              | 1          | 🟡 HIGH     |
| 4         | Folder reorganization (3 tasks)        | 3.5            | 0.5        | 🟡 MEDIUM   |
| 5         | Documentation update (3 tasks)         | 6              | 1          | 🟡 MEDIUM   |
| **TOTAL** | **15 tasks**                           | **34.5 hours** | **5 days** | —           |

---

## Quality Gates Before Each Phase

### Phase 1 Completion Criteria

- ✅ All imports updated in consuming files
- ✅ End-to-end pipeline test passes (curl test)
- ✅ No functions removed/renamed
- ✅ Code duplication avoided
- ✅ 0 runtime errors on deployment

### Phase 2 Completion Criteria

- ✅ All logging tags follow `[MODULE_OPERATION]` format
- ✅ 0 emoji in log messages (emoji reserved for documentation)
- ✅ 0 slang terminology in production code
- ✅ English is primary language (comments bilingual where needed)
- ✅ Grep validation: `[A-Z_]+` pattern for all tags

### Phase 3 Completion Criteria

- ✅ All comments translated or bilingual
- ✅ All docstrings follow standard template
- ✅ 0 slang terminology remaining
- ✅ International-friendly codebase

### Phase 4 Completion Criteria

- ✅ New folder structure in place
- ✅ All imports migrated
- ✅ No broken file references

### Phase 5 Completion Criteria

- ✅ README.md updated with new structure
- ✅ ARCHITECTURE.md created and comprehensive
- ✅ LOGGING_STANDARDS.md published
- ✅ All documentation links valid

---

## Risk Mitigation

| Risk                       | Mitigation                           |
| -------------------------- | ------------------------------------ |
| Breaking imports           | Create git branch, test before merge |
| Function signature changes | Validate end-to-end with curl tests  |
| Incomplete refactoring     | Use checklist per file               |
| Performance regression     | Run load test before/after           |
| Team knowledge gaps        | Create inline documentation          |

---

## Success Metrics

**Before Refactoring**:

- Code maintainability: 68%
- Logging consistency: 58%
- Technical debt: HIGH

**After Refactoring (Target)**:

- Code maintainability: 85%+
- Logging consistency: 100%
- Technical debt: LOW
- Codebase readability: EXCELLENT
- International team compatibility: HIGH

---

## Next Steps

1. ✅ Review and approve this plan
2. Start PHASE 1 — Task 1.1 (Split pipeline_layer_executor.py)
3. Execute tasks sequentially with quality gates
4. Deploy after Phase 1-2 completion
5. Document lessons learned

---

**Document Status**: ✅ APPROVED FOR EXECUTION  
**Last Updated**: June 13, 2026  
**Next Review**: After Phase 1 completion
