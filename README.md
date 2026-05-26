# CAKRA AI — Intelligent Agentic RAG System 🧠🤖

CAKRA AI adalah sistem asisten cerdas berbasis **Agentic RAG** dengan arsitektur **Three-Engine** yang dirancang untuk menangani asimilasi dokumen proyek secara dinamis (*Jalur 2/Cold Knowledge*) sekaligus interaksi kontekstual real-time & memori jangka panjang (*Jalur 1/Warm Knowledge*).

---

## 📐 Arsitektur Sistem & Aliran Data

Sistem ini digerakkan oleh tiga model AI lokal via Ollama/VLM dengan peran yang terisolasi demi performa kencang dan akurat:

```text
               +----------------------------------------+
               |           USER PROMPT / CHAT           |
               +----------------------------------------+
                                   |
                                   v
             [ SLOT 1: ROUTER ENGINE (Qwen2.5 / Intent) ]
               |---> Deteksi Emosi & Sentimen User
               |---> Ekstraksi Entitas Memori Jangka Panjang
                                   |
                +------------------+------------------+
                |                                     |
                v                                     v
       (Jalur 1: Chat/Spontan)              (Jalur 2: RAG Dokumen)
     Membaca tabel `ai_memory`           Melakukan Hybrid Search di
     & interaksi harian user             tabel `dokumen_chunk` (HNSW)
                |                                     |
                +------------------+------------------+
                                   |
                                   v
          [ SLOT 2: AGENT COGNITIVE LOOP (DeepSeek-R1:8b) ]
            Siklus: Thought -> Plan -> Action (Call Tools DB)
            *Menghasilkan teks pemikiran mendalam di <thought>*
                                   |
                                   v
              [ SLOT 3: GENERATOR ENGINE (Gemma2:9b) ]
            Merangkai hasil observasi agen & context menjadi
            jawaban akhir yang humanis, aman, dan anti-halusinasi.

pinAi/
├── backend/                  # 🐍 SEKTOR BACKEND (FastAPI Asynchronous)
│   └── app/
│       ├── main.py           # Entrypoint Utama Aplikasi
│       ├── core/             # Konfigurasi, DB Pools (asyncpg), & Hardware GPU
│       ├── api/              # Layer Routing, Endpoint API, & Validasi Pydantic
│       │   ├── dependencies/ # Auth Guarding: Pegawai (NPP) vs Guest Mode
│       │   ├── endpoints/    # Controller API (Auth, Chat Stream, Learning)
│       │   └── schemas/      # Pydantic V2 Models
│       └── services/         # Core Business Logic
│           ├── agent/        # Logika Kognitif Agen (Cognitive Loop & Router)
│           ├── document_chunking/ # Pipeline Potong Dokumen (Parent-Child Strategy)
│           ├── vision/       # Pemrosesan VLM (Skema/Diagram ke Mermaid.js)
│           └── rag_service.py # Orkestrator RAG Dokumen Statis
│
├── webui/                    # 💻 SEKTOR FRONTEND (React JS + Vite)
│   └── src/
│       ├── stores/           # Global State Management (Zustand: Auth & Chat Store)
│       ├── services/         # API Client & Axios Interceptor
│       └── features/         # Feature-Based Components & Pages
│           ├── auth/         # Login Page Pegawai (NPP Validation)
│           ├── chat/         # Halaman Utama AI Chat (Sidebar, ChatArea, ThoughtAccordion)
│           └── learning/     # Dashboard Latihan Dokumen untuk Admin
│
└── data/nosql/               # Tempat dump berkas scraping atau data eksternal


full strukture

pinAi/
├── backend/                  # 🔥 SEKTOR BACKEND (FastAPI Async)
│   ├── app/
│   │   ├── main.py           # Bootstrap & urutan load (paths → hotfix → hardware → app)
│   │   ├── core/
│   │   │   ├── config.py     # Konfigurasi ENV & kredensial
│   │   │   ├── database.py   # asyncpg connection pools (PostgreSQL + pgvector)
│   │   │   ├── hardware.py   # Manajemen CUDA / PyTorch GPU allocation
│   │   │   ├── llm_client.py # Client session untuk Ollama & Vision LLM
│   │   │   ├── paths.py      # Manajemen absolute path berkas/upload
│   │   │   └── logging_setup.py
│   │   ├── api/
│   │   │   ├── router.py     # Hub penggabung semua sub-router
│   │   │   ├── dependencies/
│   │   │   │   └── auth.py   # Proteksi Route: Validasi NPP Pegawai vs Guest Mode
│   │   │   ├── schemas/      # Validasi Pydantic (V2)
│   │   │   │   ├── auth.py   # Schema Login NPP
│   │   │   │   ├── chat.py   # Schema Payload Chat, Stream, & Feedback
│   │   │   │   └── document.py
│   │   │   └── endpoints/
│   │   │       ├── auth.py   # Endpoint session login/logout pegawai
│   │   │       ├── chat.py   # Endpoint streaming chat (Three-Engine Controller)
│   │   │       ├── documents.py # API upload & management dokumen admin
│   │   │       └── health.py
│   │   ├── services/
│   │   │   ├── agent/        # 🧠 Otak Agen Terpisah (Pecahan rag_service Lama)
│   │   │   │   ├── cognitive_loop.py # Siklus Agen (Thought → Plan → Call Tool)
│   │   │   │   └── router_engine.py  # Slot 1: Deteksi Intensi, Emosi & Memory Extraction
│   │   │   ├── memory_service.py # Pengelola tabel ai_memory & job konsolidasi malam
│   │   │   ├── rag_service.py    # Murni orkestrasi penarikan context dokumen (Diet Ketat)
│   │   │   ├── vector_service.py # Hybrid search (BM25 + Cosine Similarity pgvector)
│   │   │   ├── chat_history_service.py # Pengelola CRUD riwayat chat, PIN, Edit, Delete
│   │   │   ├── document_chunking/ # 📂 Pipeline Ingestion (Jalur 2)
│   │   │   │   ├── manager.py    # Koordinator pemotong dokumen
│   │   │   │   └── strategies/
│   │   │   │       ├── parent_child.py   # Taktik chunking bertingkat (parent_id)
│   │   │   │       └── text_standard.py  # Pemotong berkas teks murni/SOP
│   │   │   ├── vision/           # 👁️ Pipeline Ingestion Gambar/Skema
│   │   │   │   ├── vlm_ocr_service.py # Ekstraktor teks & layout tabel via MiniCPM-V
│   │   │   │   └── diagram_parser.py  # Generator skema otomatis ke kode Mermaid.js
│   │   │   └── background_tasks.py # Async Worker untuk pemrosesan file berat
│   │   └── utils/            # Helper shim kompatibilitas
│   └── requirements.txt
│
├── webui/                    # 💻 SEKTOR FRONTEND (React JS + Vite)
│   ├── public/
│   ├── src/
│   │   ├── assets/           # Logo CAKRA, Icon, & Gambar Statis
│   │   ├── components/       # Shared / Reusable UI Components
│   │   │   ├── ui/           # Atom components (Button, Input, Tooltip, Dialog)
│   │   │   ├── Layout.jsx    # Kerangka utama aplikasi (Sidebar + Chat Area wrapper)
│   │   │   └── Loading.jsx
│   │   ├── stores/           # ⚡ GLOBAL STATE MANAGEMENT (Zustand)
│   │   │   ├── authStore.js  # State login NPP Pegawai vs Guest Mode
│   │   │   └── chatStore.js  # State Utama: Streaming chat, thought process, & Sidebar actions
│   │   ├── services/         # Layer Komunikasi API (Axios Instance)
│   │   │   ├── apiClient.js  # Interceptor token / NPP header
│   │   │   └── endpoints.js  # Koleksi hit API Backend (Auth, Chat, Doc)
│   │   ├── features/         # 🎯 FEATURE-BASED PAGES
│   │   │   ├── auth/
│   │   │   │   └── LoginPage.jsx # Halaman input NPP Pegawai
│   │   │   ├── chat/
│   │   │   │   ├── ChatPage.jsx  # Container utama halaman Chat
│   │   │   │   └── components/
│   │   │   │       ├── Sidebar.jsx          # Sidebar History (New Chat, Pin, Edit, Delete)
│   │   │   │       ├── ChatArea.jsx         # Window percakapan aktif
│   │   │   │       ├── ChatBubble.jsx       # Balasan AI (Markdown Renderer)
│   │   │   │       ├── ThoughtAccordion.jsx # Dropdown animasi khusus teks <thought> DeepSeek
│   │   │   │       └── SourceCitation.jsx   # Komponen kecil penampil rujukan metadata dokumen
│   │   │   └── learning/
│   │   │       ├── LearningPage.jsx     # Dashboard Latihan Admin (Upload Doc/URL)
│   │   │       └── components/
│   │   │           ├── UploadZone.jsx
│   │   │           └── DocumentTable.jsx
│   │   ├── App.jsx           # Router Guarding (NPP check → Load Sidebar / Block Doc access)
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── data/nosql/               # Tempat berkas JSON dump atau scraping eksternal