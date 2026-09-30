# 🛡️ CAKRA AI — Enterprise Cognitive Intelligence System (PT Pindad)

**CAKRA AI** (*Cerdas, Adaptif, Konstruktif, Responsif, Analitik*) adalah platform kecerdasan buatan terpadu enterprise yang dibangun khusus untuk ekosistem **PT Pindad (Persero)**. Sistem ini menggabungkan arsitektur *microservices* terisolasi, orkestrasi model dua lapis (*Two-Tier Neural Pipeline*), manajemen konteks multi-database (*Triple-Database Architecture*), serta antarmuka web interaktif modern yang mendukung kolaborasi *real-time* dan visualisasi dinamis.

---

## 📑 Daftar Isi

1. [Topologi Arsitektur Microservices](#-topologi-arsitektur-microservices)
2. [Alur Pipeline Kognitif (Two-Tier Model Routing)](#-alur-pipeline-kognitif-two-tier-model-routing)
3. [Daftar Mode Operasi (Mode Hub)](#-daftar-mode-operasi-mode-hub)
4. [Integrasi Enterprise & Ekosistem Pindad](#-integrasi-enterprise--ekosistem-pindad)
5. [Skema Triple-Database](#-skema-triple-database)
6. [Struktur Repositori](#-struktur-repositori)
7. [Daftar Endpoint API Utama](#-daftar-endpoint-api-utama)
8. [Panduan Menjalankan Sistem](#-panduan-menjalankan-sistem)
9. [Standar Pengembangan & Aturan Arsitektur](#-standar-pengembangan--aturan-arsitektur)

---

## 🏛️ Topologi Arsitektur Microservices

Sistem beroperasi di atas pola *API Gateway Pattern* dengan port-port layanan terisolasi untuk menjamin ketersediaan tinggi (*high availability*), isolasi proses, dan efisiensi alokasi VRAM GPU:

```text
                                  ┌─────────────────────────────┐
                                  │   Frontend (React + Vite)   │
                                  │   Port: 5173 (Zustand Slices│
                                  └──────────────┬──────────────┘
                                                 │ HTTP / SSE Stream
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    API Gateway (FastAPI)    │
                                  │    Port: 8000 (Proxy Hub)   │
                                  └──────────────┬──────────────┘
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
      ┌───────────────────────────┐┌───────────────────────────┐┌───────────────────────────┐
      │   Chat Service (8001)     ││ Analytics Service (8002)  ││   Auth Service (8003)     │
      │ • Pipeline Orchestration  ││ • Prompt Studio & Metrics ││ • JWT Verification        │
      │ • Mode Hub & Dispatcher   ││ • Pipeline Latency Logs   ││ • HRIS Cross-Auth         │
      │ • Nextcloud Deck & RAG    ││ • LLM Token Auditing      ││ • Storage Stats           │
      └─────────────┬─────────────┘└───────────────────────────┘└───────────────────────────┘
                    │
                    ▼ Inference Engine (GPU)
      ┌─────────────────────────────────────────────────────────┐
      │  LLM Engine: vLLM (8005) / Ollama (11434)               │
      │  • Router: Gemma 4 / Classifier Fast-Path               │
      │  • Responder/Persona: Gemma 4 (31B AWQ / 16K Ctx)       │
      │  • Embeddings: mxbai-embed-large (1024-dim)             │
      │  • Reranker: BAAI/bge-reranker-v2-m3 (GPU-accelerated)  │
      └─────────────────────────────────────────────────────────┘
```

---

## 🧠 Alur Pipeline Kognitif (Two-Tier Model Routing)

Setiap pesan dari pengguna diproses melalui orkestrasi asinkronus dua lapis untuk meminimalkan *Time-to-First-Token* (TTFT) dan menghindari halusinasi:

```text
[User Prompt] ──▶ [Security Firewall (Injection Scan & Rate Limiter)]
                         │
                         ▼
        ┌───────────────────────────────────┐
        │   Step 1: Precheck & Intent Scan  │
        │   - Deteksi Berkas & URL          │
        │   - Cek Kontinuitas Sesi / Brain  │
        └─────────────────┬─────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────┐
        │   Step 2: Call 1 (Router Model)   │
        │   - Intent Classification         │
        │   - Slot & Entity Extraction      │
        │   - Ambiguity & Query Decomposition
        └─────────────────┬─────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
    [Explicit Bypass]            [Dynamic Dispatcher]
    • Forced Mode (Preset)       • Evaluasi Kebutuhan RAG
    • Ongoing Doc Audit          • Penentuan Mode Operasi
          │                               │
          └───────────────┬───────────────┘
                          ▼
        ┌───────────────────────────────────┐
        │   Step 3: Mode Hub Execution      │
        │   (Eksekusi Handler Spesifik)     │
        └─────────────────┬─────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────┐
        │   Step 4: Call 2 (Synthesizer)    │
        │   - Dynamic Lego Prompts Assembly │
        │   - Streaming Tokens & Thinking   │
        │   - Emisi SSE Widget / Artifact   │
        └───────────────────────────────────┘
```

### 1. Security Firewall
- **Rate Limiting:** Proteksi *abuse* berbasis NPP pengguna.
- **Injection Detection:** Memindai upaya *jailbreak*, manipulasi instruksi sistem, dan anomali semantik.
- **Identity Resolver:** Menghubungkan identitas dinas resmi (`full_name` dan `npp`) untuk pencocokan regulasi, sekaligus mempertahankan nama panggilan akrab pengguna (`employee_name`).

### 2. Call 1 — Intent Router
- Mengklasifikasikan intensi pengguna tanpa *hardcoded regex* rapuh.
- Mengekstrak parameter pencarian, mendeteksi ambiguitas (`is_ambiguous`), serta membedah kueri penelusuran web paralel.

### 3. Admission Controller & GPU Semaphore
- Mengatur antrean pemanggilan GPU (*TDAAC Claim & Release*) agar model 31B tetap stabil di VRAM tanpa *Out-of-Memory (OOM)* saat melayani banyak pengguna konkuren.

---

## 🎛️ Daftar Mode Operasi (Mode Hub)

`ModeHub` mendelegasikan eksekusi ke modul-modul independen (*Isolated Mode Handlers*):

| Mode | Handler | Fungsi & Perilaku Utama |
| :--- | :--- | :--- |
| **Flash** | `ModeFlash` | Percakapan instan, chit-chat ramah, klarifikasi *Interactive Decision Wizard* jika pertanyaan ambigu, dan penulisan dokumen dinas via Document Writer. |
| **Documents (RAG)** | `ModeDocuments` | Penelusuran regulasi, Surat Keputusan (SKEP), dan arsip dokumen internal PT Pindad via pgvector (HNSW) dan *similarity reranking*. |
| **Focus** | `ModeFocus` | Pemeriksaan mendalam pada satu dokumen rujukan spesifik. Menggunakan *2-stage rerank clustering* untuk membedah ratusan halaman tanpa kehilangan konteks. |
| **Attachment** | `ModeAttachment` | Analisis berkas unggahan pengguna (PDF, DOCX, XLSX, Gambar) dengan OCR/Vision, ekstraksi tabular, dan alur audit bertahap (*multi-turn audit*). |
| **Insight** | `ModeInsight` | Ringkasan eksekutif instan dari suatu dokumen/SKEP beserta visualisasi bagan silsilah hukum (*lineage*: mencabut / dicabut oleh). |
| **Deck** | `ModeDeck` | **Integrasi Nextcloud Deck (Pincloud).** Mengambil kartu tugas & proyek pegawai, merangkum progres, dan merender widget Kanban interaktif. |
| **Generate File** | `ModeGenerateFile` | *Interceptor-Analyst Pipeline* untuk memproduksi dokumen fisik siap unduh (`.docx`, `.xlsx`, `.pdf`, atau skrip kode) menggunakan tag `<create_file>`. |
| **Smart Mail** | `ModeEmail` | Penyusunan draf korespondensi email resmi berstandar BUMN dengan format penerima, subjek, dan salam dinas. |
| **Collab** | `ModeCollab` | Ruang kerja kolaborasi multi-pengguna dan agen AI *real-time* berbasis *Room SSE* dengan notifikasi dan sinkronisasi pesan. |
| **Compliance & RedTeam** | `ModeCompliance`, `ModeRedTeam` | Modul evaluasi kepatuhan terhadap aturan legal perusahaan dan pengujian ketahanan terhadap skenario *adversarial prompt*. |
| **Guest** | `ModeGuest` | Mode terbatas bagi pengguna non-pegawai (tanpa akses ke basis data rahasia atau regulasi internal perusahaan). |

---

## 🤝 Integrasi Enterprise & Ekosistem Pindad

### 1. Nextcloud Deck (Pincloud) Integration
- **REST Endpoints:** `/api/deck/boards`, `/api/deck/boards/{board_id}/stacks`, dan `/api/deck/my-tasks`.
- **Fitur AI Conversational:** Pengguna dapat menanyakan proyek tugasnya (misal: *"project yang di-assign ke saya apa saja?"*). AI membaca API Nextcloud Deck, memetakan status kolom (*In Progress*, *Done*, dll.), tenggat waktu, dan rekan tim penugasan.
- **Frontend Kanban Widget (`DeckTasksWidget`):**
  - Pemilih papan (*Board Selector*: Proyek 2026, Proyek 2025, dll.).
  - Tab filter cepat (*Semua*, *Sedang Berjalan*, *Selesai*).
  - Kolom pencarian instan (*search tasks & team members*).
  - Tombol tautan langsung ke aplikasi web Pincloud Deck.

### 2. Multi-Session Background Streaming
- Frontend menggunakan **Zustand** dengan pembagian *slices* terisolasi.
- Pengguna dapat mengirim pesan di satu sesi chat, berpindah ke sesi lain untuk membaca arsip, dan kembali lagi tanpa memutus aliran respons (*zero flickering*).

### 3. In-Place Edit vs Variant Regeneration
- **Edit Pesan:** Memperbarui teks pesan pengguna secara langsung di basis data (`message_id`) tanpa membuang respons yang ada.
- **Regenerate:** Menjalankan stream pembentukan respons baru dari posisi pesan terkait tanpa merusak riwayat percakapan.

### 4. Visual Execution Engines (Frontend Dynamic Artifacts)
Respons AI secara otomatis diubah menjadi widget interaktif oleh `CakraResponseRenderer`:
- 📊 **Chart.js:** Grafik batang, garis, dan donat untuk visualisasi finansial/operasional.
- 🔀 **Mermaid & XYFlow:** Bagan alur proses SOP, diagram relasi, dan flowchart probis.
- 📅 **Gantt Viewer:** Garis waktu jadwal proyek dan tonggak pencapaian (*milestones*).
- 🗃️ **Data Grid:** Tabel interaktif dengan kemampuan pencarian, filter, dan ekspor data.
- 🗺️ **Peta & Geolokasi:** Penandaan titik fasilitas dan aset strategis Pindad.

---

## 🗄️ Skema Triple-Database

Sistem CAKRA AI terhubung secara bersamaan ke tiga basis data melalui connection pool asinkronus (`asyncpg` & `aiomysql`):

```text
                     ┌──────────────────────────────────────────────┐
                     │          Backend Service Layer               │
                     └───────┬──────────────┬──────────────┬────────┘
                             │              │              │
                             ▼              ▼              ▼
                    ┌────────────────┐┌────────────────┐┌────────────────┐
                    │ 1. ragdb       ││ 2. hris_db     ││3. peraturan_db │
                    │ (PostgreSQL +  ││ (PostgreSQL    ││ (MySQL         │
                    │  pgvector)     ││  Remote HRIS)  ││  Legacy)       │
                    └────────────────┘└────────────────┘└────────────────┘
```

1. **`ragdb` (PostgreSQL 15+ dengan `pgvector`)**
   - Basis data operasional inti aplikasi.
   - Tabel: `users`, `chat_sessions`, `chat_messages`, `dokumen`, `dokumen_chunk` (vektor 1024 dimensi dengan indeks HNSW), `system_prompts`, `security_logs`, `collab_rooms`, dan `llm_thinking_audit`.

2. **`hris_db` (PostgreSQL Remote HRIS — Read-Only)**
   - Basis data kepegawaian resmi PT Pindad.
   - Tabel: `tabel_user`, `master_person`, `master_unit` untuk otentikasi kredensial NPP dan sinkronisasi struktur organisasi.

3. **`peraturan_db` (MySQL Legacy)**
   - Basis data perpustakaan hukum dan kebijakan lampau Pindad.
   - Tabel: `berita` (Surat Keputusan / SKEP), relasi pencabutan aturan, dan pengelompokan kategori dokumen.

---

## 📂 Struktur Repositori

```text
pinAi/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/               # Router endpoints (Hanya validasi & delegasi)
│   │   │   │   ├── chat/                # SSE Stream & sesi percakapan
│   │   │   │   ├── deck.py              # Endpoint Nextcloud Deck
│   │   │   │   ├── collab.py            # Ruang kolaborasi multi-user
│   │   │   │   ├── documents.py         # RAG search, lineage, & insight
│   │   │   │   ├── auth.py              # Otentikasi HRIS & session token
│   │   │   │   └── ...
│   │   │   ├── router.py                # Master API router registry
│   │   │   └── schemas/                 # Pydantic schemas
│   │   │
│   │   ├── core/                        # Konfigurasi aplikasi, database pools, LLM client
│   │   ├── services/                    # ★ LOGIKA BISNIS UTAMA (Service Layer) ★
│   │   │   ├── integrations/            # Nextcloud Deck, LDAP, External APIs
│   │   │   ├── pipeline/                # Orkestrator Pipeline Kognitif
│   │   │   │   ├── mode_hub.py          # Mode Dispatcher utama
│   │   │   │   ├── dispatcher_router.py # Logika Call 1 Router
│   │   │   │   ├── modes/               # Mode handlers (deck, focus, rag, dll.)
│   │   │   │   └── prompts/             # Dynamic Prompt Templates (Jinja2)
│   │   │   ├── session/                 # Session Brain & Memory Organizer
│   │   │   └── rag/                     # Vector & Semantic Search Services
│   │   └── utils/                       # Security firewall, text utilities, PDF parsers
│   └── tests/
│
├── webui/                               # React + Vite Frontend
│   ├── src/
│   │   ├── features/                    # Feature-driven UI Modules
│   │   │   ├── chat/                    # Chat components, bubbles, widgets, inputs
│   │   │   │   └── components/          # DeckTasksWidget, CakraResponseRenderer, dll.
│   │   │   └── collab/                  # Real-time room components & hooks
│   │   ├── stores/                      # Zustand Stores & Modular Slices
│   │   │   ├── chatStore.js             # Master chat state
│   │   │   └── slices/                  # streamSlice, sessionSlice, uiSlice, dll.
│   │   ├── services/                    # API client layer (Axios & fetch)
│   │   └── utils/translations.js        # Multilingual Dictionary (ID & EN)
│   └── package.json
│
├── run_gateway.py                       # API Gateway (Port 8000)
├── run_chat_service.py                  # Core Chat Service (Port 8001)
├── run_analytics_service.py             # Analytics Service (Port 8002)
├── run_auth_service.py                  # Auth Service (Port 8003)
├── start_services.sh                    # Service manager script (parallel launch)
└── README.md
```

---

## 🔌 Daftar Endpoint API Utama

| Layanan | Method | Path | Keterangan |
| :--- | :---: | :--- | :--- |
| **Chat / Pipeline** | `POST` | `/api/chat/stream` | Endpoint utama *Server-Sent Events* (SSE) dengan Call 1 & 2. |
| **Chat** | `GET` | `/api/chat/sessions` | Mengambil daftar riwayat sesi percakapan pengguna. |
| **Chat** | `PUT` | `/api/chat/messages/{id}` | Melakukan *in-place edit* pesan pengguna. |
| **Nextcloud Deck** | `GET` | `/api/deck/my-tasks` | Mengambil kartu tugas & proyek pengguna dari Pincloud Deck. |
| **Nextcloud Deck** | `GET` | `/api/deck/boards` | Mengambil daftar papan proyek (*boards*) aktif. |
| **Collab** | `GET` | `/api/collab/rooms` | Daftar ruang kerja kolaborasi interaktif. |
| **Collab** | `GET` | `/api/collab/rooms/{id}/stream` | Sinkronisasi pesan dan aktivitas ruang kolaborasi secara *real-time*. |
| **Documents** | `GET` | `/api/documents/search` | Pencarian semantik regulasi & arsip internal (pgvector HNSW). |
| **Documents** | `GET` | `/api/documents/{id}/lineage` | Mengambil bagan silsilah pencabutan Surat Keputusan (SKEP). |
| **Auth** | `POST` | `/api/auth/login` | Otentikasi pegawai via NPP dan verifikasi basis data HRIS. |

---

## 🛠️ Panduan Menjalankan Sistem

### Prasyarat
- **Sistem Operasi:** Linux (Ubuntu 22.04 LTS / Debian direkomendasikan)
- **Runtime:** Python 3.10+, Node.js 18+, npm 9+
- **Basis Data:** PostgreSQL 15+ (dengan ekstensi `pgvector`), MySQL 8.0+
- **Inference Engine:** vLLM (Port 8005) atau Ollama (Port 11434) dengan model `gemma4:31b` / `gemma-4-31B-it-AWQ` dan embedding `mxbai-embed-large`.

### 1. Manajemen Layanan Cepat (Direkomendasikan)
Gunakan skrip terpadu `start_services.sh` untuk mengelola seluruh *microservices* dan *frontend* sekaligus:

```bash
# Menjalankan atau restart seluruh service secara paralel
./start_services.sh

# Hanya restart layanan tertentu (contoh: chat service)
./start_services.sh chat

# Menghentikan seluruh service yang berjalan
./start_services.sh stop

# Menghentikan service sekaligus membersihkan alokasi VRAM GPU
./start_services.sh reset-vram
```

### 2. Menjalankan Layanan Secara Manual

#### Backend Services
Aktifkan virtual environment Python (`rag_env`):
```bash
source rag_env/bin/activate

# 1. Jalankan Auth Service (Port 8003)
python run_auth_service.py

# 2. Jalankan Analytics Service (Port 8002)
python run_analytics_service.py

# 3. Jalankan Chat Core Service (Port 8001)
python run_chat_service.py

# 4. Jalankan API Gateway (Port 8000)
python run_gateway.py
```

#### Frontend Web UI
```bash
cd webui
npm install
npm run dev
```

Akses browser di `http://localhost:5173` (Frontend) yang terhubung otomatis ke API Gateway di `http://localhost:8000`.

---

## 📐 Standar Pengembangan & Aturan Arsitektur

Setiap kontribusi atau penambahan fitur di repositori ini wajib mematuhi aturan baku:
1. **Clean Separation of Concerns:**
   - Dilarang menaruh logika bisnis atau query SQL di folder `api/endpoints/`. Seluruh logika wajib berada di `services/`.
   - Komponen UI React di `webui/src/components/` tidak boleh menyimpan *state* kotor; gunakan *custom hooks* dan *Zustand stores*.
2. **Prinsip Percabangan Aman (Non-Destruktif):**
   - Penambahan fitur baru tidak boleh merusak parameter atau jalur yang sudah stabil. Selalu gunakan isolasi mode atau *fallback* yang aman.
3. **Standarisasi Multibahasa (i18n):**
   - Setiap teks baru, tombol UI, status bar, maupun event pesan SSE wajib didaftarkan pada `webui/src/utils/translations.js` (Bahasa Indonesia & Bahasa Inggris).
4. **Keamanan & Guardrails:**
   - Setiap input teks dari pengguna wajib divalidasi melalui `security_firewall.py` sebelum mencapai LLM.
