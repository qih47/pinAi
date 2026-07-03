# CAKRA AI — Sistem Asisten Inteligensia Terpadu PT Pindad

**CAKRA AI** (_Cerdas, Adaptif, Konstruktif, Responsif, Analitik_) adalah platform kognitif enterprise untuk **PT Pindad (Persero)** — bukan chatbot generik, melainkan sistem RAG agentic dengan arsitektur **Hub-and-Spoke Mode**, perlindungan keamanan (Security Firewall), dan *seamless context continuation*.

---

## Daftar Isi

1. [Arsitektur Sistem (Hub-and-Spoke)](#arsitektur-sistem-hub-and-spoke)
2. [Fitur Unggulan Enterprise](#fitur-unggulan-enterprise)
3. [Alur Pipeline & Mode Hub](#alur-pipeline--mode-hub)
4. [Struktur Folder Lengkap](#struktur-folder-lengkap)
5. [API Endpoints](#api-endpoints)
6. [Database Schema](#database-schema)
7. [Cara Menjalankan](#cara-menjalankan)

---

## Arsitektur Sistem (Hub-and-Spoke)

Arsitektur CAKRA AI telah berevolusi dari sekuensial statis menjadi **Orchestrator Dinamis** yang secara efisien mengatur request dari pengguna ke berbagai model LLM.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         cakra/ (Monorepo)                                    │
├────────────────────────────────┬─────────────────────────────────────────────┤
│   webui/ (React + Vite)        │   backend/ (FastAPI + asyncpg)              │
│   Port: 5173 (dev)             │   Port: 5000                                │
│   State: Zustand               │   LLM: Ollama (localhost:11434)             │
│   HTTP Client: Axios (REST)    │   Embedding: mxbai-embed-large (1024-dim)   │
│   Stream: native fetch/SSE     │   Reranker: BAAI/bge-reranker-v2-m3 (GPU)   │
└────────────────────────────────┴─────────────────────────────────────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   ▼                                             ▼
          ┌──────────────────┐                         ┌──────────────────┐
          │  ragdb           │                         │  hris_db         │
          │  (PostgreSQL +   │                         │  (PostgreSQL     │
          │   pgvector)      │                         │   remote HRIS    │
          │                  │                         │   192.168.11.55) │
          │  • chat_sessions │                         │  • master_unit   │
          │  • chat_messages │                         │  • master_person │
          │  • dokumen       │                         │  • tabel_user    │
          │  • dokumen_chunk │                         └──────────────────┘
          │  • ai_memory     │
          │  • session_login │
          └──────────────────┘
```

---

## Fitur Unggulan Enterprise

1. **Smart Insight & Lineage (Silsilah SKEP)**
   - Rangkuman eksekutif cerdas via LLM untuk dokumen PDF.
   - Silsilah status dokumen (Mencabut/Dicabut Oleh/Aktif).
2. **Context Isolation (Mode Fokus)**
   - Pengguna dapat memasuki obrolan terisolasi khusus untuk membahas 1 file SKEP/dokumen tanpa distraksi memori dari chat lain.
3. **Security Firewall Terpusat**
   - Perlindungan anti Prompt-Injection dan Jailbreak (mendeteksi pola-pola Bypass).
   - Global Rate Limiting dan pembatasan Payload Size per-IP.
4. **Ollama Continuation Orchestrator**
   - CAKRA AI mendukung obrolan dengan *context length* tanpa batas via Chunking Window. Model tak akan pernah *crash* karena melebihi *Token Limit* berkat mekanisme `token_continuation_layer`.

---

## Alur Pipeline & Mode Hub

Setiap request masuk (khususnya ke `/api/chat/stream`) melewati beberapa lapisan penjagaan sebelum di-dispatch ke Model.

```text
[Request dari Frontend]
          │
          ▼
┌──────────────────────────────────────────────┐
│  Security Firewall (Global Dependency)       │
│  - Rate Limiting                             │
│  - URL/Payload Injection Scan                │
└─────────────────┬────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────┐
│  Pipeline Orchestrator (Pre-processing)      │
│  - Ekstrak PDF / OCR via MiniCPM-V           │
│  - Content Safety Filter (SARA/Pornografi)   │
│  - Tarik Employee Context dari Cache         │
└─────────────────┬────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────┐
│  MODE HUB (Central Dispatcher)               │
│                                              │
│  ├── Bypass 1: Mode Insight (Ringkasan)      │
│  ├── Bypass 2: Mode Focus (Isolasi File)     │
│  ├── Bypass 3: Mode Guest (Tamu)             │
│  ├── Bypass 4: Mode Attachment (Upload)      │
│  │                                           │
│  └── AUTO-ROUTING (Qwen 0.5B Classifier)     │
│       ├─▶ Mode Documents (RAG + pgvector)    │
│       ├─▶ Mode Flash (Instan Chit-chat)      │
│       └─▶ Mode Generate File (Data Analisis) │
└─────────────────┬────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────┐
│  Ollama Execution Layer (Gemma4 12B)         │
│  - Seamless Token Continuation               │
│  - Live SSE Streaming ke Browser             │
└──────────────────────────────────────────────┘
```

---

## Struktur Folder Lengkap

Pemisahan tanggung jawab sudah sangat jelas antara *routing*, *orchestration*, *mode execution*, dan *prompts*.

```text
cakra/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/
│   │   │   │   ├── chat/                  # Chat session & SSE streaming endpoint
│   │   │   │   ├── documents.py           # Insight, Lineage, Search CRUD
│   │   │   │   └── ...                    # Auth, Admin, Health, dsb
│   │   │   └── schemas/                   # Pydantic Schemas
│   │   ├── core/
│   │   │   └── database.py                # Setup PostgreSQL Dual-Pool
│   │   ├── services/
│   │   │   ├── chat/                      # Chat History (DB CRUD)
│   │   │   ├── pipeline/                  # ★ KELUARGA ORCHESTRATOR ★
│   │   │   │   ├── pipeline_orchestrator.py
│   │   │   │   ├── mode_hub.py            # Central mode router
│   │   │   │   ├── modes/                 # Handlers per-mode (focus, insight, dll)
│   │   │   │   │   ├── mode_focus.py
│   │   │   │   │   ├── mode_insight.py
│   │   │   │   │   └── ...
│   │   │   │   ├── prompts/               # Kumpulan prompt LLM (rag_prompts, dll)
│   │   │   │   └── ollama_raw_client.py   # Streaming client + Token Continuation
│   │   │   └── rag/                       # pgvector, bm25, bge_reranker
│   │   └── utils/
│   │       ├── security_firewall.py       # Global Security Interceptor
│   │       ├── employee_cache.py          # LRU Caching HRIS
│   │       └── ...
│   └── tests/                             # Unit Test (Ollama Token, Prefill, dll)
│
└── webui/
    ├── src/
    │   ├── features/
    │   │   └── chat/
    │   │       ├── ChatPage.jsx           # Entry point utama UI
    │   │       ├── hooks/useChatLogic.js  # Abstraksi business-logic React
    │   │       └── components/            # Render UI (CakraRenderer, Sidebar, Modals)
    │   ├── stores/                        # Zustand stores (chatStore, authStore)
    │   └── services/                      # Axios endpoints & API Client
    └── index.html
```

---

## API Endpoints

### Documents & Insight
| Method | Endpoint                              | Deskripsi                                 |
| ------ | ------------------------------------- | ----------------------------------------- |
| `GET`  | `/api/documents/search`               | RAG Fulltext & Vector Search              |
| `GET`  | `/api/documents/{id}/insight`         | Generate Smart Insight ringkasan PDF (LLM)|
| `GET`  | `/api/documents/{id}/lineage`         | Ambil hierarki silsilah (Dicabut/Mencabut)|

### Chat
| Method | Endpoint                              | Deskripsi                                 |
| ------ | ------------------------------------- | ----------------------------------------- |
| `GET`  | `/api/chat/sessions`                  | List semua sesi chat user                 |
| `POST` | `/api/chat/stream`                    | **Endpoint SSE Pipeline Orchestrator**    |
| `POST` | `/api/chat/documents/upload`          | Attachment handler untuk gambar/PDF       |

### Auth & Security
| Method | Endpoint                              | Deskripsi                                 |
| ------ | ------------------------------------- | ----------------------------------------- |
| `POST` | `/api/auth/login`                     | HRIS Login Auth                           |
| `GET`  | `/api/auth/verify-session`            | Validasi JWT Session                      |

*(Endpoint lain seperti `/health` dan Admin tersedia di direktori router)*

---

## Database Schema (ragdb)

| Tabel                | Fungsi                                                                 |
| -------------------- | ---------------------------------------------------------------------- |
| `users`              | Data pegawai (npp, fullname, divisi, role) — sync dari HRIS saat login |
| `session_login`      | Token sesi aktif + IP + last_activity                                  |
| `chat_sessions`      | Sesi obrolan (session_uuid, judul, is_pinned, is_deleted, npp)         |
| `chat_messages`      | Pesan per sesi (role, message_text, thought, timestamp)                |
| `dokumen`            | Dokumen regulasi Pindad (judul, nomor, status)                         |
| `dokumen_chunk`      | Chunk teks + embedding 1024-dim (pgvector)                             |
| `silsilah_dokumen`   | Hubungan pencabutan dokumen / perubahan                                |

---

## Cara Menjalankan

### Prasyarat
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ dengan ekstensi `pgvector`
- Ollama ter-install dengan model: `qwen2.5:0.5b`, `gemma4:12b`, `mxbai-embed-large`

### 1. Jalankan Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env # Atur konfigurasi DB dan Ollama
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

### 2. Jalankan Frontend
```bash
cd webui
npm install
npm run dev
```

Platform akan aktif dan siap menerima stream respon *Real-Time* di port `5173`.
