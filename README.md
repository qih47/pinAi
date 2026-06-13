# CAKRA AI — Sistem Asisten Inteligensia Terpadu PT Pindad

**CAKRA AI** (_Cerdas, Adaptif, Konstruktif, Responsif, Analitik_) adalah platform kognitif enterprise untuk **PT Pindad (Persero)** — bukan chatbot generik, melainkan sistem RAG agentic multi-layer dengan memori jangka panjang, empati sentimen, dan routing intent otomatis.

---

## Daftar Isi

1. [Arsitektur Sistem](#arsitektur-sistem)
2. [Agentic Pipeline (4 Layer)](#agentic-pipeline-4-layer)
3. [Model AI — Three-Engine Stack](#model-ai--three-engine-stack)
4. [RAG Engine — Hybrid Search](#rag-engine--hybrid-search)
5. [Struktur Folder Lengkap](#struktur-folder-lengkap)
6. [API Endpoints](#api-endpoints)
7. [WebUI — Arsitektur Frontend](#webui--arsitektur-frontend)
8. [Database Schema](#database-schema)
9. [Cara Menjalankan](#cara-menjalankan)
10. [Rekomendasi Optimasi & Fitur Baru](#rekomendasi-optimasi--fitur-baru)

---

## Arsitektur Sistem

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

## Agentic Pipeline (4 Layer)

Setiap pesan chat melewati pipeline sequential yang terdiri dari 4 layer berurutan. Diagram alur lengkap:

```text
User Kirim Pesan
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 0 — Gateway (Qwen 0.5B)                                │
│                                                              │
│  MODE auto  → Klasifikasi: documents | flash                 │
│  MODE docs  → Langsung generate 3 rewritten_queries          │
│  MODE flash → Langsung Flash analysis (intent, is_coding…)  │
│                                                              │
│  Output: { target_pipeline, rewritten_queries, is_greeting,  │
│            is_coding, confidence, detected_language }        │
└──────────────────────┬──────────────────────────────────────-┘
                       │
         ┌─────────────┴──────────────┐
         ▼                            ▼
  target="documents"           target="flash"
         │                            │
         ▼                            ▼
┌──────────────────┐    ┌──────────────────────────────────────┐
│ RAG Paralel      │    │ BYPASS Layer 1 — Rule-Based Params   │
│ (asyncio.gather) │    │ (Instan, tanpa LLM call)             │
│                  │    │                                      │
│ 3 queries        │    │ Output: 35 cognitive params          │
│ → pgvector + FTS │    │ (rule-based dari kata kunci)         │
│ → RRF scoring    │    └──────────────────────────────────────┘
│ → BGE Reranker   │
│ → Dynamic thresh │
└────────┬─────────┘
         │ (Paralel dengan Layer 1)
         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1 — Cognitive Analyzer (Qwen 3B)                       │
│                                                              │
│  Input: pesan user + gateway_result + history 5 turn         │
│         + memory pegawai + OCR text (jika ada)              │
│                                                              │
│  Output: 35 parameter kognitif                               │
│   • emotion, urgency_level, empathy_phrase                   │
│   • detected_intent, action_plan, response_structure         │
│   • tone, estimated_response_length, key_points              │
│   • linguistic_mirroring_strategy, user_pronoun_preference   │
│   • ... (+ 25 parameter lainnya)                            │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2 — Gemma4 12B Agentic Executor                        │
│                                                              │
│  Input: system_prompt (dari 35 params) + RAG context         │
│         + history 5 turn + OCR text                         │
│                                                              │
│  Features:                                                   │
│  • Adaptive num_ctx: 2048 (chitchat) → 32768 (RAG)          │
│  • Adaptive temperature: 0.3 (code) → 0.75 (greeting)       │
│  • <think> tag parsing → log terminal saja, tidak ke FE     │
│  • Leak filter: [PANGGIL_RAG:] disaring di level chunk       │
│  • SSE streaming langsung ke browser                         │
│                                                              │
│  Output: SSE chunks { chunk, thinking, done, sources }       │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ DATABASE PERSISTENCE (Post-stream)                           │
│  • auto_update_session_title (jika masih "Obrolan Baru")     │
│  • save_chat_message (role=assistant)                        │
│  • save_dialogue_corpus (ai_dialogue_corpus)                 │
└──────────────────────────────────────────────────────────────┘
```

### SSE Event Format

Seluruh komunikasi streaming menggunakan format JSON per line:

```json
{ "chunk": "teks jawaban...", "thinking": "", "done": false }
{ "chunk": "", "thinking": "Layer sedang berpikir...", "done": false }
{ "sources": [{ "id": 1, "title": "SK Direksi...", "score": 0.94 }], "chunk": "", "done": false }
{ "chunk": "", "thinking": "", "done": true }
```

---

## Model AI — Three-Engine Stack

| Layer     | Model                 | Ukuran | Fungsi                           | keep_alive  |
| --------- | --------------------- | ------ | -------------------------------- | ----------- |
| Layer 0   | `qwen2.5:0.5b`        | ~500MB | Gateway: routing + intent        | 300s        |
| Layer 1   | `qwen2.5:3b-instruct` | ~2GB   | Cognitive: 35 params + blueprint | 300s        |
| Layer 2   | `gemma4:12b`          | ~8GB   | Executor: response streaming     | -1 (always) |
| Vision    | `minicpm-v:latest`    | ~5GB   | OCR fallback untuk PDF gambar    | on-demand   |
| Embedding | `mxbai-embed-large`   | ~670MB | RAG: 1024-dim vector             | on-demand   |

**GPU Concurrency:** Diatur via `asyncio.Semaphore` (1 slot GPU) pada `request.app.state.gpu_limit`. Semua LLM call antre sebelum eksekusi.

---

## RAG Engine — Hybrid Search

Pipeline RAG berjalan dalam **4 fase berurutan**:

### Fase 1 — Hybrid Search (PostgreSQL)

- **pgvector**: Cosine similarity dengan embedding `mxbai-embed-large` (1024-dim)
- **Full-Text Search**: `to_tsquery('indonesian', ...)` dengan stopword removal
- **RRF Scoring**: `1/(60 + rank_vector) + 1/(60 + rank_fts)` untuk menggabungkan dua score
- **Fallback**: Pure vector search jika FTS hybrid zero match

### Fase 2 — Parent-Child Hierarchical Assembly

- Ambil **N±1 chunk** (chunk sebelum + target + sesudah) per dokumen kandidat
- JOIN dengan `dokumen_section` untuk injeksi `section_title` dan `section_type`
- Grouping per `dokumen_id` untuk konteks yang koheren

### Fase 3 — BGE Cross-Encoder Re-ranker

- Model: `BAAI/bge-reranker-v2-m3` (~570MB GPU)
- Inference via `run_in_executor` agar tidak blokir event loop FastAPI
- Output: relevance score [0.0, 1.0] per dokumen kandidat
- Lazy-load dengan `@lru_cache(maxsize=1)` — hanya dimuat sekali

### Fase 4 — Dynamic Threshold Filtering

```python
best_score = max(scores)
effective_min_score = max(best_score * 0.15, 0.05)  # ratio=0.15, floor=0.05
```

Dokumen di bawah threshold dibuang. Mencegah dokumen tidak relevan masuk konteks Gemma.

### Parallel RAG (Mode Documents)

Jika `target_pipeline == "documents"`, semua `rewritten_queries` (3 variasi) dijalankan **paralel** via `asyncio.gather`, hasil digabung dengan deduplication by `source_id`.

---

## Struktur Folder Lengkap

```text
cakra/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies/
│   │   │   │   └── auth.py              # get_current_user_npp (token validator)
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py              # POST /login, GET /verify-session, POST /logout
│   │   │   │   ├── chat.py              # GET|POST /sessions, POST /stream, POST /documents/upload
│   │   │   │   ├── documents.py         # [KOSONG — belum diimplementasikan]
│   │   │   │   └── health.py            # GET /health
│   │   │   └── schemas/
│   │   │       └── chat.py              # ChatStreamRequest, TitleUpdateSchema
│   │   ├── core/
│   │   │   ├── config.py                # Settings (pydantic_settings, .env loader)
│   │   │   ├── database.py              # asyncpg dual-pool (ragdb + hris_db)
│   │   │   ├── hardware.py              # GPU/RAM info
│   │   │   ├── llm_client.py            # stream_ollama_chat, generate_json_response
│   │   │   ├── logging_setup.py         # Logging configuration
│   │   │   └── paths.py                 # UPLOAD_DIR path resolver
│   │   └── services/
│   │       ├── agent/
│   │       │   ├── cognitive_loop.py    # [Agent loop — status unknown]
│   │       │   └── router_engine.py     # [Router engine — status unknown]
│   │       ├── document_chunking/
│   │       │   ├── manager.py           # Chunking orchestrator
│   │       │   └── strategies/
│   │       │       ├── parent_child.py  # Hierarchical chunking strategy
│   │       │       └── text_standard.py # Standard text chunking
│   │       ├── vision/
│   │       │   └── ...                  # Vision processing modules
│   │       ├── background_tasks.py      # [KOSONG — belum diimplementasikan]
│   │       ├── chat_history_service.py  # CRUD sesi, pesan, attachment, corpus
│   │       ├── memory_service.py        # Long-term memory (ai_memory table)
│   │       ├── pipeline_layer_executor.py # Orchestrator 4-layer pipeline
│   │       ├── rag_service.py           # Hybrid RAG: RRF + reranker
│   │       ├── reranker_service.py      # BGE cross-encoder (CUDA)
│   │       ├── vector_service.py        # mxbai-embed-large via Ollama API
│   │       └── vision_service.py        # MiniCPM-V OCR service
│   └── main.py                          # FastAPI app, lifespan, CORS, routers
│
└── webui/
    ├── src/
    │   ├── components/ui/
    │   │   ├── GuestWelcome.jsx          # Halaman selamat datang tamu
    │   │   └── ToastProvider.jsx         # ★ Global toast notification system
    │   ├── features/chat/
    │   │   ├── ChatPage.jsx              # Main orchestrator chat page
    │   │   ├── chatPage.styles.js        # Centralized style objects + helpers
    │   │   └── components/
    │   │       ├── ChatArea.jsx          # Virtuoso virtual list renderer
    │   │       ├── ChatBubble.jsx        # Message bubble (user + assistant router)
    │   │       ├── CakraResponseRenderer.jsx # Markdown/code renderer
    │   │       ├── CodeBlockHeader.jsx   # Copy/download code block header
    │   │       ├── CustomModeSelector.jsx # Mode: auto|flash|documents
    │   │       ├── HeaderDropdownMenu.jsx # Kebab menu header (theme, login)
    │   │       ├── PlusButton.jsx        # File attachment button
    │   │       ├── SendButton.jsx        # Submit button dengan loading state
    │   │       ├── Sidebar.jsx           # Chat history sidebar
    │   │       ├── SourceCitation.jsx    # RAG source card
    │   │       └── UserBubble.jsx        # User message + attachment viewer
    │   ├── hooks/
    │   │   └── useToast.js               # ★ Toast notification hook
    │   ├── services/
    │   │   ├── apiClient.js              # Axios instance + base config
    │   │   └── endpoints.js              # ★ Centralized API + SSE functions
    │   └── stores/
    │       ├── authStore.js              # Zustand: auth state (user, token)
    │       └── chatStore.js              # Zustand: sessions, messages, streaming
    └── index.html
```

---

## API Endpoints

### Auth — `/api/auth`

| Method | Endpoint                          | Deskripsi                                                  |
| ------ | --------------------------------- | ---------------------------------------------------------- |
| `POST` | `/api/auth/login`                 | Login dengan NPP + password (MD5), validasi ke HRIS remote |
| `GET`  | `/api/auth/verify-session?token=` | Verifikasi token session aktif                             |
| `POST` | `/api/auth/logout`                | Invalidasi token + audit trail                             |

### Chat — `/api/chat`

| Method   | Endpoint                             | Deskripsi                                          |
| -------- | ------------------------------------ | -------------------------------------------------- |
| `GET`    | `/api/chat/sessions`                 | Ambil semua sesi aktif milik user                  |
| `POST`   | `/api/chat/sessions/create`          | Buat sesi baru                                     |
| `PUT`    | `/api/chat/sessions/{uuid}/title`    | Rename judul sesi                                  |
| `PUT`    | `/api/chat/sessions/{uuid}/pin`      | Pin/unpin sesi                                     |
| `DELETE` | `/api/chat/sessions/{uuid}`          | Soft delete sesi                                   |
| `GET`    | `/api/chat/sessions/{uuid}/messages` | Ambil semua pesan dalam sesi                       |
| `POST`   | `/api/chat/stream`                   | **Main endpoint SSE streaming** (pipeline 4-layer) |
| `POST`   | `/api/chat/documents/upload`         | Upload file attachment (image/PDF)                 |

### Health — `/api`

| Method | Endpoint      | Deskripsi             |
| ------ | ------------- | --------------------- |
| `GET`  | `/api/health` | Status server + model |

### ChatStreamRequest Schema

```json
{
  "messages": [{ "role": "user", "content": "pertanyaan..." }],
  "session_uuid": "uuid-sesi-aktif",
  "attachment_paths": ["path/file1.pdf"],
  "mode": "auto | flash | documents"
}
```

---

## WebUI — Arsitektur Frontend

### State Management (Zustand)

```text
chatStore.js
├── messages[]             ← Daftar pesan aktif
├── sessionUuid            ← UUID sesi aktif
├── isStreaming / isThinking
├── stagedAttachments[]    ← File yang sudah diupload, menunggu dikirim
├── chatMode               ← auto | flash | documents
├── activeIsolatedDocId    ← Untuk mode isolated document context
└── Methods:
    ├── sendMessage()      → POST /api/chat/stream (SSE via fetch ReadableStream)
    ├── createNewSession() → POST /api/chat/sessions/create
    ├── loadSession()      → GET /api/chat/sessions/{uuid}/messages
    ├── fetchChatHistory() → GET /api/chat/sessions
    ├── renameChat()       → PUT /api/chat/sessions/{uuid}/title
    ├── pinChat()          → PUT /api/chat/sessions/{uuid}/pin
    └── deleteChat()       → DELETE /api/chat/sessions/{uuid}

authStore.js
├── user { npp, fullname, divisi, role }
├── token (session token)
├── isAuthenticated
└── Methods: login(), logout(), verifySession()
```

### Data Flow Frontend

```text
[ChatPage]
    ↓ user ketik + attach file
[handleFileChange/handlePaste/handleDrop]
    → validateFile() → max 10MB, image/* | application/pdf
    → setSelectedFiles()  (local state preview)
    ↓ tombol Send
[handleSubmit]
    → jika ada files → POST /api/chat/documents/upload
                     → toast.info + toast.success
    → chatStore.sendMessage()
        → fetch() + ReadableStream reader
        → parse SSE line-by-line:
            chunk    → append ke messages (streaming)
            sources  → setStagedSources
            done=true → setIsStreaming(false)
    → sessionStorage.removeItem(draft_key)  ← hapus draft
    → selectedFiles = []
```

### Toast Notification System

```text
ToastProvider.jsx (global wrapper di App.jsx)
  ↕
useToast.js hook → { toast.success, toast.error, toast.warning, toast.info }
```

Digunakan di: validasi file, upload feedback, error pipeline, koneksi error.

### Draft Persistence

Input textarea disimpan ke `sessionStorage` dengan key `cakra_draft_${sessionId}` setiap keystroke. Dipulihkan otomatis saat pindah sesi.

---

## Database Schema (ragdb)

### Tabel Utama

| Tabel                | Fungsi                                                                 |
| -------------------- | ---------------------------------------------------------------------- |
| `users`              | Data pegawai (npp, fullname, divisi, role) — sync dari HRIS saat login |
| `session_login`      | Token sesi aktif + IP + last_activity                                  |
| `history_login`      | Audit trail LOGIN/LOGOUT per NPP                                       |
| `chat_sessions`      | Sesi obrolan (session_uuid, judul, is_pinned, is_deleted, npp)         |
| `chat_messages`      | Pesan per sesi (role, message_text, thought, timestamp)                |
| `chat_attachments`   | Metadata file upload (file_name, file_path, mime_type, extracted_text) |
| `ai_dialogue_corpus` | Pasangan user-assistant untuk fine-tuning/retrieval masa depan         |
| `ai_memory`          | Memori jangka panjang per NPP (mem_key, mem_value) — diisi nightly job |
| `dokumen`            | Dokumen regulasi Pindad (judul, nomor, id_jenis)                       |
| `dokumen_chunk`      | Chunk teks + embedding 1024-dim (pgvector)                             |
| `dokumen_section`    | Hierarki section dokumen                                               |
| `jenis_dokumen`      | Kategori dokumen (SKEP, SK Direksi, SOP, dll)                          |

### Dual-Database Connection Pool

- **ragdb** (asyncpg pool: min=5, max=20) — semua data operasional CAKRA
- **hris_db** (asyncpg pool: min=3, max=10) — validasi login kredensial remote

---

## Cara Menjalankan

### Prasyarat

- Python 3.11+ dengan virtual environment
- Node.js 18+ + npm/yarn
- PostgreSQL 15+ dengan ekstensi `pgvector`
- Ollama dengan model: `qwen2.5:0.5b`, `qwen2.5:3b-instruct`, `gemma4:12b`, `mxbai-embed-large`
- GPU NVIDIA (CUDA) untuk reranker BGE

### Backend

```bash
# 1. Install dependencies
cd cakra
pip install -r requirements.txt

# 2. Buat file .env (salin dari .env.example)
cp .env.example .env
# Edit .env: DB_HOST, DB_USER, DB_PASSWORD, DB_LOGIN_HOST, OLLAMA_BASE_URL, dll

# 3. Jalankan FastAPI
uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload
```

### Frontend (WebUI)

```bash
cd webui
npm install
npm run dev      # Development (port 5173)
npm run build    # Production build ke /dist
```

---

## Rekomendasi Optimasi & Fitur Baru

> **Catatan**: Seluruh item di bawah ini adalah roadmap pengembangan. Setiap item sudah dianalisa dan siap untuk dieksekusi secara independen.

---

### 🔴 BACKEND — Prioritas Tinggi (Critical)

#### B1 — Hapus `print()` dari Kode Produksi, Gunakan Logger Terstruktur

**Status**: ✅ COMPLETED

**Masalah**: Seluruh backend (chat.py, pipeline_layer_executor.py, rag_service.py, memory_service.py, database.py, dll.) menggunakan `print()` langsung untuk debugging. Di produksi, ini memperlambat performa, tidak bisa dikontrol level-nya (DEBUG/INFO/WARNING), dan mencemari stdout.

**Solusi**: Ganti semua `print()` dengan `logger.info()` / `logger.debug()` / `logger.warning()`. File `logging_setup.py` sudah ada namun belum dipakai optimal.

**File terdampak**: `chat.py`, `pipeline_layer_executor.py`, `rag_service.py`, `memory_service.py`, `auth.py`, `llm_client.py`, `database.py`, `vector_service.py`, `chat_history_service.py`

---

#### B2 — Background Task: Implementasi `background_tasks.py` (File Kosong)

**Status**: ✅ COMPLETED

**Masalah**: File `background_tasks.py` saat ini **kosong**. Fungsi `consolidate_nightly_memory()` di `memory_service.py` tidak pernah dipanggil secara otomatis. Memori jangka panjang pegawai tidak pernah diperbarui.

**Solusi**:

- Implementasikan APScheduler atau FastAPI `BackgroundTasks` / `asyncio` scheduled task
- Jalankan `memory_service.consolidate_nightly_memory()` setiap pukul 02:00 WIB
- Tambahkan endpoint admin `POST /api/admin/run-memory-consolidation` untuk trigger manual

---

#### B3 — Validasi File Upload di Server (Duplikasi Validasi)

**Status**: ✅ COMPLETED

**Masalah**: Saat ini validasi tipe file di `chat.py` hanya mengecek `content_type`. MIME type bisa dipalsukan. Tidak ada validasi ukuran file di sisi server.

**Solusi**:

- Tambahkan validasi ukuran: `file.size > 10 * 1024 * 1024` → reject 400
- Tambahkan validasi magic bytes untuk PDF (`%PDF`) dan gambar
- Rate limiting per user/IP untuk endpoint upload

---

#### B4 — Timeout & Retry Layer 0/1 Tidak Konsisten

**Status**: ✅ COMPLETED

**Masalah**: `generate_json_response` di Layer 0 menggunakan timeout 25s (routing) dan 15s (query rewriter), namun Layer 1 hanya 15s. Jika Qwen 3B lambat, Layer 1 timeout dan fallback ke rule-based — tanpa retry.

**Solusi** (IMPLEMENTED):

- ✅ Tambahkan exponential backoff retry (maks 2x) untuk Layer 0/1
- ✅ Timeout Layer 1 dinaikkan ke 30s (Qwen 3B lebih berat dari 0.5B)
- ✅ Circuit breaker: jika Layer 0/1 gagal >3x dalam 60s, langsung flash mode
- ✅ File baru: `backend/app/utils/retry_handler.py` dengan `RetryWithBackoff` + `CircuitBreaker`
- ✅ Updated `pipeline_layer_executor.py`: Layer 0 gateway, Layer 0 rewriter, Layer 1 analyzer semua menggunakan retry + circuit breaker

**Files Modified**:
- `backend/app/utils/retry_handler.py` (NEW)
- `backend/app/services/pipeline_layer_executor.py`

---

#### B5 — Employee Name Query per Request (N+1 Problem)

**Status**: ✅ COMPLETED

**Masalah**: Di `chat.py` baris 378-405, setiap request pipeline membuka koneksi DB baru hanya untuk mengambil `fullname` user. Ini N+1 query yang tidak perlu karena data ini statis per sesi.

**Solusi** (IMPLEMENTED):

- ✅ Cache nama pegawai menggunakan in-memory cache dengan TTL 1 jam
- ✅ File baru: `backend/app/utils/employee_cache.py` dengan `get_cached_employee_fullname()`
- ✅ Updated `chat.py`: menggunakan cached lookup instead of direct DB call
- ✅ Cache invalidation supported via `invalidate_employee_cache()`

**Files Modified**:
- `backend/app/utils/employee_cache.py` (NEW)
- `backend/app/api/endpoints/chat.py`

---

#### B6 — Implementasi `documents.py` Endpoint (File Kosong)

**Status**: ✅ COMPLETED

**Masalah**: `backend/app/api/endpoints/documents.py` kosong. Tidak ada endpoint untuk manajemen dokumen regulasi (list, upload, delete, reindex).

**Solusi** (IMPLEMENTED):

- ✅ `GET /api/documents` — list semua dokumen dengan paginasi (offset, limit)
- ✅ `POST /api/documents/ingest` — upload + chunk + embed dokumen baru (background task)
- ✅ `DELETE /api/documents/{id}` — hapus dokumen + chunk + embedding cascade
- ✅ `POST /api/documents/{id}/reindex` — re-embed dokumen yang sudah ada
- ✅ `GET /api/documents/stats` — statistik dokumen (total, chunks, file size, status)
- ✅ Document schemas dengan pydantic validation
- ✅ Background task untuk chunking + embedding asynchronous

**Files Created**:
- `backend/app/api/schemas/document.py` (NEW) — DocumentSchema, DocumentListSchema, etc.
- `backend/app/api/endpoints/documents.py` (REPLACED) — Full CRUD implementation

---

#### B7 — Auth: Hardcoded Bypass Account & MD5 Password (Security)

**Status**: ✅ COMPLETED

**Masalah**:

1. `auth.py` line 104: akun bypass `npp=99999, password=123456` hardcoded di kode
2. Password divalidasi menggunakan MD5 (sudah deprecated, mudah di-crack)

**Solusi**:

- Pindahkan bypass account ke environment variable: `BYPASS_NPP`, `BYPASS_PASSWORD_HASH`
- Pertimbangkan migrasi ke bcrypt/Argon2 untuk password baru (koordinasi dengan HRIS team)
- Tambahkan rate limiting login: max 5 attempt per IP per menit

---

#### B8 — Koneksi DB per-request di Pipeline (Resource Leak Risk)

**Status**: ⏳ NOT STARTED

**Masalah**: Di `chat.py` baris 378, ada pola `async with get_db() as conn:` di dalam generator pipeline SSE. Jika streaming terhenti di tengah jalan (client disconnect), koneksi DB mungkin tidak langsung dikembalikan ke pool.

**Solusi**:

- Tangkap `asyncio.CancelledError` di `_sequential_pipeline_generator`
- Ensure DB connections selalu dikembalikan ke pool via proper `finally` block
- Pisahkan employee name fetch ke fungsi tersendiri sebelum streaming dimulai

---

### 🟡 BACKEND — Prioritas Sedang (Enhancement)

#### B9 — Caching Embedding Query (Vector Service)

**Masalah**: Setiap RAG query selalu memanggil Ollama untuk generate embedding, meskipun query yang sama sudah pernah ditanyakan sebelumnya.

**Solusi**:

- Implementasikan in-memory LRU cache untuk query embedding (maks 500 entry)
- Key: `hash(query_string)`, Value: `List[float]` embedding
- TTL 1 jam untuk mencegah stale data

---

#### B10 — Session Token Expiry (Auth)

**Masalah**: Token session tidak memiliki expiry time. Jika user tidak logout, token valid selamanya.

**Solusi**:

- Tambahkan kolom `expires_at TIMESTAMP` di tabel `session_login`
- Auto-expire token setelah 8 jam (satu shift kerja)
- `verify-session` endpoint harus cek `expires_at > NOW()`

---

#### B11 — Structured Logging dengan Request ID Tracing

**Masalah**: Log saat ini tidak bisa di-trace per request. Sulit debugging ketika ada request bersamaan.

**Solusi**:

- Tambahkan middleware FastAPI yang inject `X-Request-ID` header
- Semua log dalam satu pipeline menggunakan `request_id` yang sama
- Format log: `[2026-06-13 14:00:00] [req-abc123] [LAYER 0] Gateway completed in 1.2s`

---

#### B12 — Auto-Title menggunakan LLM (bukan slice 4 kata)

**Masalah**: `auto_update_session_title` saat ini menggunakan `" ".join(trigger_text.split()[:4]) + "..."` — tidak informatif dan sering menghasilkan judul yang janggal.

**Solusi**: Tambahkan opsi generate title via LLM (Qwen 0.5B) secara async background task setelah streaming selesai:

```python
title = await generate_session_title(user_message, first_response[:200])
```

---

#### B13 — RAG: Index HNSW untuk pgvector (Performance)

**Masalah**: Comment di `rag_service.py` menyebutkan "seq scan, HNSW aktif otomatis saat data bertambah" — ini tidak akurat. HNSW harus dibuat manual.

**Solusi**: Buat HNSW index jika belum ada:

```sql
CREATE INDEX IF NOT EXISTS idx_dokumen_chunk_embedding_hnsw
ON dokumen_chunk USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Signifikan mempercepat vector search saat `dokumen_chunk` > 10.000 baris.

---

### 🟢 FITUR BARU — Backend

#### B14 — Feedback & Rating Respons AI

**Status**: ✅ COMPLETED

Tambahkan endpoint `POST /api/chat/messages/{id}/feedback` dengan payload `{ rating: 1-5, comment: string }`. Data disimpan ke tabel baru `ai_feedback` untuk evaluasi kualitas model.

#### B15 — WebSocket untuk Real-time Notification

**Status**: ⏳ NOT STARTED

Ganti polling sidebar dengan WebSocket atau Server-Sent Events untuk notifikasi: sesi baru dari device lain, memory consolidation selesai, dll.

#### B16 — Audit Log Admin Dashboard

**Status**: ⏳ NOT STARTED

Buat endpoint `GET /api/admin/audit-logs` yang menampilkan history_login + query log per pegawai untuk keperluan compliance.

---

### 🟡 WEBUI — Prioritas Sedang

#### ✅ W1 — Scroll-to-Bottom Button pada ChatArea (SELESAI)

Saat user scroll ke atas untuk membaca riwayat, tombol "↓ Kembali ke Bawah" muncul otomatis (terintegrasi dengan callback `atBottomStateChange` React Virtuoso).

#### ✅ W2 — Skeleton Loading untuk Riwayat Chat (SELESAI)

Saat `loadChatSession` dipanggil, riwayat memuat shimmer effect skeleton bubble (`SkeletonChat`) untuk meningkatkan perceived performance.

#### ✅ W3 — Retry Mekanisme untuk SSE Stream Terputus (SELESAI)

Jika koneksi SSE putus di tengah streaming, frontend otomatis melakukan retry (maks 3x) dengan exponential backoff dan toast info "Menghubungkan kembali...".

#### ✅ W4 — Message Search / Filter dalam Sesi (SELESAI)

Dilengkapi dengan fitur pencarian kata kunci (`Ctrl+F`) yang menandai kemunculan teks secara rekursif menggunakan tag `<mark>` kustom di dalam bubble percakapan.

#### ✅ W5 — Export Chat History (SELESAI)

Menambahkan tombol ekspor di header dropdown untuk format Markdown (.md) dan PDF (.pdf via native print window).

#### ✅ W6 — Indikator "Sedang Mengetik" yang Akurat (SELESAI)

Status indicator menyajikan tahapan pipeline yang sedang berlangsung secara real-time (Layer 0, RAG, dan Layer 2).

#### ✅ W7 — Mode Isolated Document Context (UI) (SELESAI)

Menyediakan Modal "Daftar Dokumen" di sidebar yang terhubung dengan `/api/documents` di backend. Memilih dokumen akan menyalakan mode isolasi context.

---

### 🟢 FITUR BARU — WebUI

#### ✅ W8 — Dark/Light Mode Persistence yang Tepat (SELESAI)

Mode tema yang diubah pada satu tab browser disinkronkan ke seluruh tab lainnya secara instan via `storage` event listener.

#### ✅ W9 — Keyboard Shortcuts (SELESAI)

- `Ctrl+/` → New Chat
- `Ctrl+K` → Fokus ke pencarian riwayat obrolan sesi di sidebar
- `Esc` → Menutup dialog / modal aktif

#### ✅ W10 — Markdown Export dengan Syntax Highlight (SELESAI)

Tombol "Salin Markdown" di setiap bubble percakapan asisten menyalin raw text markdown lengkap.

---

_README ini di-generate dan diperbarui pada: 2026-06-13 berdasarkan analisa lengkap seluruh kode backend dan frontend._
