# CAKRA AI — Sistem Asisten Inteligensia Terpadu PT Pindad

**CAKRA AI** (_Cerdas, Adaptif, Konstruktif, Responsif, Analitik_) adalah platform kognitif enterprise berbasis RAG (Retrieval-Augmented Generation) yang dibangun khusus untuk **PT Pindad (Persero)**. Sistem ini menggunakan arsitektur **Anti-Spaghetti Service Layer**, **Pipeline Mode Hub**, **Triple-Database Integration**, serta kapabilitas **Multi-Session Background Streaming** untuk pengalaman interaksi AI yang asinkronus dan aman.

---

## 📑 Daftar Isi
1. [Arsitektur Sistem (Triple-Database & Multi-Stream)](#arsitektur-sistem-triple-database--multi-stream)
2. [Fitur Unggulan Enterprise](#fitur-unggulan-enterprise)
3. [Alur Pipeline & Mode Hub](#alur-pipeline--mode-hub)
4. [Struktur Folder (Clean Architecture)](#struktur-folder-clean-architecture)
5. [Skema Triple-Database](#skema-triple-database)
6. [API Endpoints Utama](#api-endpoints-utama)
7. [Panduan Menjalankan Sistem](#panduan-menjalankan-sistem)

---

## 🏛️ Arsitektur Sistem (Triple-Database & Multi-Stream)

CAKRA AI menerapkan pemisahan tanggung jawab (*Separation of Concerns*) yang ketat. Frontend menggunakan state management **Zustand** untuk *streaming* independen, sedangkan Backend memisahkan *Router* dari *Business Logic* (Service Layer).

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         cakra/ (Monorepo)                                    │
├────────────────────────────────┬─────────────────────────────────────────────┤
│   [FRONTEND] webui/            │   [BACKEND] backend/                        │
│   React + Vite                 │   FastAPI + asyncpg/aiomysql                │
│   State: Zustand (Multi-Stream)│   LLM: Ollama (localhost:11434)             │
│   HTTP Client: Axios           │   Embedding: mxbai-embed-large (1024-dim)   │
│   Stream: native fetch/SSE     │   Reranker: BAAI/bge-reranker-v2-m3 (GPU)   │
└────────────────────────────────┴─────────────────────────────────────────────┘
                                          │ (Connection Pools)
             ┌────────────────────────────┼────────────────────────────┐
             ▼                            ▼                            ▼
    ┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
    │ 1. ragdb         │         │ 2. hris_db       │         │ 3. peraturan_db  │
    │ (PostgreSQL +    │         │ (PostgreSQL      │         │ (MySQL Legacy)   │
    │  pgvector)       │         │  Remote HRIS)    │         │                  │
    │                  │         │                  │         │                  │
    │ • chat_sessions  │         │ • master_unit    │         │ • berita (SKEP)  │
    │ • chat_messages  │         │ • master_person  │         │ • kategori       │
    │ • dokumen (KB)   │         │ • tabel_user     │         │                  │
    │ • dokumen_chunk  │         └──────────────────┘         └──────────────────┘
    │ • system_prompts │
    │ • training_jobs  │
    │ • api_keys       │
    └──────────────────┘
```

---

## 🚀 Fitur Unggulan Enterprise

### Frontend (Web UI)
1. **Multi-Session Background Streaming**
   - Pengguna dapat mengirim *prompt* panjang dan melakukan navigasi pindah sesi *chat* di sidebar tanpa memutus proses AI (*return without block*).
   - Mendukung maksimal 2 proses asinkron paralel untuk menjaga stabilitas.
2. **Context Isolation (Mode Fokus)**
   - Obrolan terisolasi khusus untuk membedah 1 file Surat Keputusan (SKEP) atau dokumen tanpa kontaminasi *chat history* lain.
3. **Seamless Resumption**
   - Berpindah antar sesi tidak akan menyebabkan kedipan UI (*flicker*) atau memuat ulang dari API jika sesi masih berjalan, berkat *caching activeStreams* di Zustand.

### Backend (Service Layer)
1. **Anti-Spaghetti API Delegation**
   - API Router `endpoints/` tidak memiliki kueri SQL. Semua di-*handle* oleh folder `services/` secara modular.
2. **Smart Insight & Lineage (Silsilah SKEP)**
   - Rangkuman PDF otomatis dan diagram hubungan pencabutan peraturan (Mencabut/Dicabut Oleh) yang ditarik dari *peraturan_db* MySQL.
3. **Security Firewall & Audit Logging**
   - Pencegahan *Prompt Injection* dan *Jailbreak*, *Global Rate Limiting*, serta tabel `llm_thinking_audit` dan `history_login` untuk *compliance*.
4. **Token Continuation Orchestrator**
   - LLM tidak akan pernah mengalami *Crash Out-of-Memory (OOM)* karena konteks disesuaikan dinamis (*Chunking Window*).

---

## 🔀 Alur Pipeline & Mode Hub

Semua request chat masuk secara asinkron (Server-Sent Events) melewati tahapan berikut:

```text
[Frontend ChatPage.jsx (Zustand Stream)]
          │
          ▼ (POST /api/chat/stream)
┌──────────────────────────────────────────────┐
│  Security Firewall (Global Dependency)       │
│  - Validasi JWT HRIS & Rate Limiting         │
│  - Injection Scan pada Payload Input         │
└─────────────────┬────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────┐
│  MODE HUB (Pipeline Dispatcher)              │
│                                              │
│  ├── Bypass 1: Mode Insight (Ringkasan)      │
│  ├── Bypass 2: Mode Focus (Isolasi File)     │
│  ├── Bypass 3: Mode Guest (Tamu)             │
│  │                                           │
│  └── AUTO-ROUTING (Qwen/Classifier)          │
│       ├─▶ Mode Documents (RAG + pgvector)    │
│       ├─▶ Mode Flash (Instan Chit-chat)      │
│       └─▶ Mode Generate File (Data Analisis) │
└─────────────────┬────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────┐
│  Ollama Execution Layer (Gemma4/Llama3)      │
│  - Streaming *Chunk* Token demi Token        │
│  - Injeksi RAG ke dalam System Prompt        │
└──────────────────────────────────────────────┘
```

---

## 📂 Struktur Folder (Clean Architecture)

```text
cakra/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/                 # Routing Layer (Hanya mendelegasikan Request)
│   │   │   │   ├── chat/                  # Endpoint chat & SSE streaming
│   │   │   │   ├── documents.py           # Endpoint RAG, Lineage, Search
│   │   │   │   ├── analytics.py           # Endpoint Prompt Studio & Meta stats
│   │   │   │   ├── auth.py                # Endpoint Login & Verifikasi HRIS
│   │   │   │   ├── training.py            # Endpoint Knowledge Base Ingestion
│   │   │   │   └── admin.py               # Endpoint Optimisasi DB
│   │   │   └── schemas/                   # Skema Pydantic (Validasi Request/Response)
│   │   │
│   │   ├── core/
│   │   │   └── database.py                # Konfigurasi Triple-Pool (ragdb, hris, peraturan)
│   │   │
│   │   ├── services/                      # ★ LOGIKA BISNIS UTAMA (No SQL in Routers) ★
│   │   │   ├── auth/                      # auth_service (HRIS login), api_key_service
│   │   │   ├── chat/                      # session_repository, chat_history_service
│   │   │   ├── documents/                 # documents_service (MySQL/PG logic), document_manager
│   │   │   ├── notifications/             # audit_service (history_login)
│   │   │   ├── system/                    # background_tasks, scheduler
│   │   │   ├── training/                  # training_service, job_manager
│   │   │   ├── pipeline/                  # KELUARGA ORCHESTRATOR
│   │   │   │   ├── mode_hub.py            # Mode Dispatcher
│   │   │   │   ├── modes/                 # Handler Mode (Insight, Focus, Flash, dll)
│   │   │   │   └── prompt_manager.py      # Pengelola System Prompts Dinamis
│   │   │   └── rag/                       # vector_service (pgvector HNSW), rag_service
│   │   │
│   │   └── utils/                         # Helper fungsionalitas murni
│   └── docs/                              # Catatan integrasi, roadmap, panduan teknis
│
└── webui/
    ├── src/
    │   ├── features/
    │   │   └── chat/
    │   │       ├── hooks/useChatLogic.js  # Abstraksi kompleks UI & Binding data
    │   │       └── components/            # Komponen visual (ChatArea, Sidebar, Modal)
    │   ├── stores/                        
    │   │   ├── chatStore.js               # State Management Multi-Stream Zustand
    │   │   └── authStore.js               # State Profil User HRIS
    │   └── services/                      # Konfigurasi Axios
    └── index.html
```

---

## 🗄️ Skema Triple-Database

Sistem CAKRA terhubung ke tiga entitas pangkalan data besar secara bersamaan lewat koneksi asinkronus (`asyncpg` & `aiomysql`).

### 1. `ragdb` (PostgreSQL + pgvector)
Database operasional utama aplikasi.
- **`users`** : Data pegawai hasil sinkronisasi dari HRIS saat login.
- **`session_login`** : Melacak sesi login, JWT token, IP, dan histori login user.
- **`chat_sessions`** & **`chat_messages`** : Manajemen riwayat obrolan (*Conversation Memory*).
- **`dokumen`** & **`dokumen_chunk`** : Katalog dokumen *Knowledge Base* beserta vektor *1024-dimension* untuk HNSW *similarity search*.
- **`system_prompts`** : Kumpulan prompt dinamis untuk *Prompt Studio* (analytics).
- **`api_keys`** : Kunci akses webhook untuk sistem eksternal Pindad.
- **`training_jobs`** : Antrean proses ekstraksi dokumen latar belakang.
- **`security_logs`** & **`llm_thinking_audit`** : Audit kepatuhan (Compliance) dan keamanan *jailbreak*.

### 2. `hris_db` (PostgreSQL Remote)
Database kepegawaian eksisting Pindad (Read-Only).
- **`tabel_user`**, **`master_person`**, **`master_unit`** : Digunakan oleh `auth_service` untuk memverifikasi kredensial NPP (Nomor Pokok Pegawai).

### 3. `peraturan_db` (MySQL Legacy)
Database perpustakaan hukum dan kebijakan lama Pindad.
- **`berita`** : Menyimpan metadata dan referensi file PDF Surat Keputusan (SKEP) masa lampau beserta kolom `mencabut`/`statusaktif`.
- **`kategori`** : Klasifikasi dokumen regulasi.

---

## 🔌 API Endpoints Utama

| Modul Service | Method | Endpoint                              | Fungsi Utama                                |
| ------------- | ------ | ------------------------------------- | ------------------------------------------- |
| **Pipeline**  | `POST` | `/api/chat/stream`                    | Eksekusi SSE LLM dengan Mode Routing        |
| **Chat**      | `GET`  | `/api/chat/sessions`                  | Histori Sesi Chat                           |
| **Auth**      | `POST` | `/api/auth/login`                     | Autentikasi silang ke HRIS & ragdb          |
| **Documents** | `GET`  | `/api/documents/search`               | RAG Fulltext + Vector Search                |
| **Documents** | `GET`  | `/api/documents/{id}/lineage`         | Query Silsilah (Mencabut) SKEP via MySQL    |
| **Documents** | `GET`  | `/api/documents/{id}/insight`         | Ekstraksi poin penting PDF via LLM          |
| **Analytics** | `GET`  | `/api/analytics/system_prompts`       | Konfigurasi Prompt Studio (CRUD)            |
| **Training**  | `POST` | `/api/training/upload`                | Ingesti dokumen baru ke Vector DB           |

---

## 🛠️ Panduan Menjalankan Sistem

### Prasyarat
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (Pastikan ekstensi `pgvector` terinstal)
- MySQL 8.0+
- Ollama Engine (Model yang dibutuhkan: `qwen2.5:0.5b`, `gemma4:12b`, `mxbai-embed-large`)

### 1. Menjalankan Backend
```bash
cd backend
# Buat virtual environment & install dependensi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Sesuaikan environment (Pastikan URL ketiga DB disetel)
cp .env.example .env

# Jalankan server FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

### 2. Menjalankan Frontend
```bash
cd webui
npm install
npm run dev
```

Buka `http://localhost:5173` di peramban (browser). Platform sudah siap dengan kapabilitas Multi-Streaming dan RAG.
