# 🛡️ CAKRA AI — Enterprise Architecture & System Documentation (PT Pindad)

> Platform asisten dan analitik enterprise terpadu berbasis **Two-Tier Neural Pipeline**, **Microservices Mesh**, **Triple-Database Architecture**, dan **Dual-LoRA Adaptation** yang dirancang khusus untuk ekosistem **PT Pindad (Persero)**.

---

## 📑 Daftar Isi

1. [Ikhtisar Arsitektur Enterprise](#-ikhtisar-arsitektur-enterprise)
2. [Topologi Jaringan Microservices & Inference Cluster](#-topologi-jaringan-microservices--inference-cluster)
3. [Arsitektur Pipeline Kognitif (Dispatcher & Responder)](#-arsitektur-pipeline-kognitif-dispatcher--responder)
   - [Lapisan 0: Security Firewall & Identity Resolution](#lapisan-0-security-firewall--identity-resolution)
   - [Lapisan 1: Call 1 — Intent Router & Query Dispatcher](#lapisan-1-call-1--intent-router--query-dispatcher)
   - [Lapisan 1.5: Admission Controller & GPU Semaphore (TDAAC)](#lapisan-15-admission-controller--gpu-semaphore-tdaac)
   - [Lapisan 2: Call 2 — Synthesizer & Persona Responder](#lapisan-2-call-2--synthesizer--persona-responder)
   - [Modern RAG Engine: Dual-Pathway Architecture](#modern-rag-engine-dual-pathway-architecture)
   - [Stream Demuxer & Benchmarking Realtime](#stream-demuxer--benchmarking-realtime)
4. [Katalog Lengkap Mode Hub (12 Execution Handlers)](#-katalog-lengkap-mode-hub-12-execution-handlers)
5. [Mesin Training, Fine-Tuning & Pembelajaran Mandiri](#-mesin-training-fine-tuning--pembelajaran-mandiri)
   - [Fine-Tuning QLoRA (Call 1 Router & Call 2 Core)](#fine-tuning-qlora-call-1-router--call-2-core)
   - [Arsitektur 6 Worker Multimodal (Nightly Sync)](#arsitektur-6-worker-multimodal-nightly-sync)
   - [Two-Page Spread Book Reader](#two-page-spread-book-reader)
   - [Jadwal Operasional & Manual Override Safe Window](#jadwal-operasional--manual-override-safe-window)
6. [Integrasi Ekosistem Enterprise Pindad](#-integrasi-ekosistem-enterprise-pindad)
   - [Nextcloud Deck (Pincloud) Integration & Kanban Engine](#nextcloud-deck-pincloud-integration--kanban-engine)
   - [Collab Rooms (Ruang Kolaborasi Real-Time Multi-Agent)](#collab-rooms-ruang-kolaborasi-real-time-multi-agent)
   - [Document Writer BUMN Workspace](#document-writer-bumn-workspace)
7. [Frontend Architecture & Dynamic Response Renderer](#-frontend-architecture--dynamic-response-renderer)
   - [State Management Zustand (Multi-Session Background Streaming)](#state-management-zustand-multi-session-background-streaming)
   - [Komponen Visual & Artifact Execution Engines](#komponen-visual--artifact-execution-engines)
   - [Standarisasi Multibahasa i18n](#standarisasi-multibahasa-i18n)
8. [Skema Triple-Database & Session Brain](#-skema-triple-database--session-brain)
9. [Struktur Repositori](#-struktur-repositori)
10. [Matriks Endpoint API Lengkap](#-matriks-endpoint-api-lengkap)
11. [Panduan Operasional & Service Management](#-panduan-operasional--service-management)

---

## 🏛️ Ikhtisar Arsitektur Enterprise

CAKRA AI mengimplementasikan pemisahan layanan bersih (**Clean Service Separation**) dan jaring layanan mikro (**Microservices Mesh**). Frontend (React/Vite) tidak pernah berkomunikasi langsung dengan proses inferensi model berat secara sinkronus; seluruh alur pesan mengalir melalui **API Gateway**, didistribusikan ke layanan mikro independen, dan disalurkan ke pengguna via protokol **Server-Sent Events (SSE)** berkecepatan tinggi.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FRONTEND WEBUI (React 18 + Vite)                       │
│     Zustand Multi-Stream Slices │ Responsive Canvas │ Dynamic Artifact Renderer        │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / SSE (Port 5173 ──▶ 8000)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (run_gateway.py : Port 8000)                  │
│       Reverse Proxy Hub │ Header Propagation │ Global CORS │ SSE Streaming Pipe        │
└───────┬───────────────────────────────────┬────────────────────────────────────┬───────┘
        │                                   │                                    │
        ▼ (Port 8001)                       ▼ (Port 8002)                        ▼ (Port 8003)
┌───────────────────────────────┐   ┌───────────────────────────────┐   ┌───────────────────────────────┐
│     CHAT SERVICE (CORE)       │   │      ANALYTICS SERVICE        │   │        AUTH SERVICE           │
│ • Two-Tier Neural Pipeline    │   │ • Prompt Studio Dynamic Engine│   │ • JWT Cross-Auth HRIS         │
│ • Dispatcher & Responder Hub  │   │ • Pipeline Latency Metrics    │   │ • Session Token Validation    │
│ • Nextcloud Deck & SKEP RAG   │   │ • Token & Thinking Audit Logs │   │ • User Quotas & Storage Stats │
│ • Dual-Pathway RAG Engine     │   │ • Model Performance Profiling │   │ • Identity Profile Mapping    │
└───────────────┬───────────────┘   └───────────────────────────────┘   └───────────────────────────────┘
                │
                ├──────────────────────────────────────┬──────────────────────────────────────┐
                ▼                                      ▼                                      ▼
┌───────────────────────────────┐      ┌───────────────────────────────┐      ┌───────────────────────────────┐
│        RAG DATABASE           │      │        HRIS DATABASE          │      │      PERATURAN DATABASE       │
│ PostgreSQL 15 + pgvector      │      │ PostgreSQL Remote (Read-Only) │      │ MySQL Legacy (Read-Only)      │
│ • 91.854 Embedded Chunks HNSW │      │ • Master Person & Master Unit │      │ • Berita Regulasi (SKEP)      │
│ • Primary Data Feeder (No I/O)│      │ • Validasi NPP Pegawai Pindad │      │ • Secondary Fallback Branch & │
│ • Chat History & Checkpoints  │      │ • Pemetaan Struktur Organisasi│      │   Silsilah Hukum Lineage      │
└───────────────────────────────┘      └───────────────────────────────┘      └───────────────────────────────┘
                │
                ▼ INFERENCE CLUSTER (GPU Engine)
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ • vLLM Server (Port 8005)      : gemma-4-31B-it-AWQ Base + Native Multi-LoRA Serving   │
│                                  ├── cakra-router : Deterministic Intent & Anaphora    │
│                                  └── cakra-core   : Domain Knowledge, CoT & Generative UI│
│ • Ollama Server (Port 11434)   : Fallback Engine & mxbai-embed-large (1024-dim Vector) │
│ • GPU Reranker Core            : BAAI/bge-reranker-v2-m3 (Cross-Encoder Scoring)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Topologi Jaringan Microservices & Inference Cluster

| Komponen | Host & Port | Peran Utama | Protokol / Engine |
| :--- | :--- | :--- | :--- |
| **Frontend WebUI** | `http://0.0.0.0:5173` | Antarmuka pengguna, workspace kolaborasi, chat | React 18, Vite, Tailwind/Vanilla CSS |
| **API Gateway** | `http://0.0.0.0:8000` | Gerbang tunggal, router reverse-proxy, SSE pipe | FastAPI, httpx asinkronus |
| **Chat Core Service** | `http://0.0.0.0:8001` | Logika pipeline AI, Dual-Pathway RAG, Deck | FastAPI, asyncpg, PyMuPDF, Jinja2 |
| **Analytics Service** | `http://0.0.0.0:8002` | Dashboard metrik, prompt studio, audit log | FastAPI, asyncpg, JSONL streaming |
| **Auth Service** | `http://0.0.0.0:8003` | Otentikasi HRIS Pindad, manajemen sesi token | FastAPI, asyncpg, passlib, JWT |
| **vLLM Inference** | `http://127.0.0.1:8005` | Base AWQ 31B + Native Multi-LoRA (`cakra-router` & `cakra-core`) | vLLM Engine (AWQ + Multi-Adapter Serving) |
| **Ollama Inference** | `http://127.0.0.1:11434`| Eksekusi model pendukung, embeddings | Ollama API, GGML/GGUF (mxbai-embed-large) |

---

## 🧠 Arsitektur Pipeline Kognitif (Dispatcher & Responder)

Sistem menggunakan alur pemrosesan modular **Two-Tier Neural Pipeline** (`backend/app/services/pipeline/`):

```text
[Incoming User Request]
         │
         ▼
[0. SECURITY FIREWALL & IDENTITY RESOLVER]
  ├── Validasi NPP & JWT Token
  ├── Scan Injeksi Prompt & Content Safety
  └── Identity Linker: Nama Dinas Resmi (full_name) + Sapaan Akrab (employee_name)
         │
         ▼
[1. PRECHECK & CALL 1: DISPATCHER ROUTER (Gemma 4 + cakra-router-lora)]
  ├── Deterministic JSON Schema Extraction (temp=0.0, num_predict=200, Latensi ~150ms)
  ├── 12 Parameter Kontrol Intensi (need_rag, is_deck_query, is_ambiguous, dll.)
  └── Multi-Turn Coreference & Anaphora Resolution (Penguncian dokumen aktif)
         │
         ├── Ambigu? ──▶ [Interactive Clarification Wizard (Mode Flash)]
         │
         ▼
[1.5. ADMISSION CONTROLLER & GPU SEMAPHORE (TDAAC)]
  ├── Dynamic Claim Slot Antrean GPU (Pencegahan VRAM Crash/OOM)
  └── Tracking Queue Wait Time
         │
         ▼
[1.8. DUAL-PATHWAY RAG ENGINE]
  ├── Jalur Utama (Primary): 91.854 Embedded Chunks PostgreSQL (Hybrid pgvector + FTS RRF)
  └── Jalur Percabangan (Fallback): Pencarian Katalog / Tag Dokumen MySQL Berita
         │
         ▼
[2. CALL 2: SYNTHESIZER / RESPONDER (Gemma 4 31B AWQ + cakra-core-lora)]
  ├── Dynamic Lego Prompts Assembly (Mermaid, DataGrid, Deck, Math, dll.)
  ├── Token Streaming & Structured Reasoning (<think>...</think>)
  └── Direct Artifact Emission (```deck_tasks, ```chart, ```doc_media)
         │
         ▼
[Client Output via SSE Stream (Chunk, Status, Thinking, Artifacts, Done)]
```

### Lapisan 0: Security Firewall & Identity Resolution
- **Security Firewall (`security_firewall.py`):** Mencegah injeksi prompt, manipulasi sistem, kebocoran data rahasia (*content safety*), dan anomali semantik secara proaktif sebelum payload mencapai LLM.
- **Dual Identity Resolution (`pipeline_orchestrator.py`):**
  - **`full_name` & `current_user_npp`:** Nama lengkap resmi kedinasan dari HRIS (misal: `06652 Qisthi Iskandar Haqiki`). Digunakan untuk pencocokan keabsahan hukum, daftar SK penugasan, dan klausul dokumen.
  - **`employee_name`:** Nama panggilan sesuai preferensi di pengaturan akun (misal: `Qisthi`). Digunakan untuk sapaan percakapan dinas natural.

### Lapisan 1: Call 1 — Intent Router & Query Dispatcher
Modul [`dispatcher_router.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/dispatcher_router.py) berjalan dengan dukungan adapter LoRA deterministik `cakra-router`:
- **Karakteristik Operasional:** Latensi inferensi cepat (~150-200ms), `temperature: 0.0`, `num_predict: 200`, `num_ctx: 4096`, `is_thinking: False`.
- **12 Parameter Kontrol JSON:**
  1. `need_rag`: Menentukan kebutuhan pengambilan konteks regulasi internal.
  2. `is_chitchat`: Percakapan umum atau sapaan langsung tanpa data luar.
  3. `is_web_search`: Penelusuran informasi eksternal internet terkini.
  4. `is_generate_file`: Permintaan pembuatan berkas fisik Word, Excel, atau PDF.
  5. `is_generate_email`: Draf korespondensi dinas resmi BUMN.
  6. `is_docwriter`: Penulisan surat dinas dan SOP pada workspace Document Writer.
  7. `is_deck_query`: Pertanyaan tugas, proyek, dan kartu di Nextcloud Deck (Pincloud).
  8. `is_map_query`: Informasi geolokasi dan peta fasilitas operasional.
  9. `is_chart_query`: Permintaan data visual analitik atau grafik perbandingan.
  10. `is_ambiguous`: Pertanyaan multi-tafsir yang membutuhkan panduan wizard interaktif.
  11. `needs_history`: Menentukan relevansi riwayat percakapan sesi untuk diinjeksi ke Call 2.
  12. `pronoun`: Penyesuaian register bahasa (*formal dinas* vs *komunikasi santai*).
- **Multi-Turn Anaphora & Coreference Resolution:** Menghubungkan kueri eliptis (seperti *"tunjukin lampiran E nya"*) dengan dokumen induk yang sedang aktif dibahas pada sesi sebelumnya.

### Lapisan 1.5: Admission Controller & GPU Semaphore (TDAAC)
- Menggunakan tiket *Time-Decayed Adaptive Admission Control* (TDAAC).
- Mengunci antrean pemanggilan GPU sehingga saat banyak permintaan masuk bersamaan, model 31B tetap beroperasi stabil di VRAM tanpa tabrakan memori atau lonjakan latensi.

### Modern RAG Engine: Dual-Pathway Architecture (Zero Disk I/O)
Sistem RAG menerapkan prinsip percabangan terisolasi (*Safe Branching: A ➔ A1, B ➔ B1*):
1. **Jalur Utama (Primary Vector Engine):**
   - Mengambil data langsung dari **91.854 chunks bervektor** pada PostgreSQL `dokumen_chunk` menggunakan pencarian hibrida (`pgvector <=> embedding` + PostgreSQL Full-Text Search dengan perankingan RRF).
   - Seluruh teks pasal, nomor halaman fisik (`page_number`), bab, dan metadata dokumen (`dokumen_id`, `nomor`, `judul`, `filename`) disuplai langsung dari database tanpa melakukan I/O baca file gambar atau dokumen PDF fisik di disk server.
2. **Jalur Percabangan (Secondary Catalog Search & Fallback):**
   - Mengakses tabel MySQL `berita` untuk pencarian berbasis kata kunci judul, tag regulasi, atau nomor surat mentah secara spesifik, serta bertindak sebagai *safety net* jika dokumen baru belum selesai di-embed.
3. **On-Demand Visual Rendering (`DocumentPageViewer`):**
   - File citra fisik halaman dokumen (`page_XXX.png`) hanya dipanggil ketika pengguna meminta penelusuran visual atau saat model mengaktifkan blok widget visual lampiran.

### Lapisan 2: Call 2 — Synthesizer & Persona Responder
Modul [`llm_client.py`](file:///home/qisthi/pinAi/backend/app/core/llm_client.py) menjalankan inferensi dengan adapter LoRA `cakra-core`:
- **Domain Grounding & Reasoning:** Melakukan penalaran eksplisit di dalam blok `<think>...</think>` sebelum menyajikan jawaban berbasis dasar hukum yang valid.
- **Dynamic Lego Blocks Assembly:** Merakit instruksi sistem sesuai kebutuhan output (Mermaid, XYFlow, Chart.js, Interactive DataGrid, Infographic, Document Writer, Nextcloud Deck Kanban).
- **Generative UI & Visual Document Viewer:** Mengeluarkan blok kode terstruktur seperti ````datagrid`, ````mermaid`, dan ````doc_media` untuk merender tampilan visual halaman lampiran asli.

### Stream Demuxer & Benchmarking Realtime
- **`_StreamDemuxer`:** Memisahkan token penalaran (*reasoning channel*) `<|channel>thought ... <channel|>` dari jawaban final secara asinkron tanpa memutus aliran SSE.
- **Diagnostic ASCII Table:** Menampilkan visualisasi matriks TTFT (Time-to-First-Token), kecepatan prefill (tok/s), kecepatan generasi (tok/s), dan pemakaian memori per permintaan.

---

## 🎛️ Katalog Lengkap Mode Hub (12 Execution Handlers)

`ModeHub` (`backend/app/services/pipeline/mode_hub.py`) mendelegasikan eksekusi ke handler khusus:

| Mode | Modul Handler | Deskripsi & Alur Kerja |
| :--- | :--- | :--- |
| **`flash`** | [`mode_flash.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_flash.py) | Respons instan untuk chit-chat dan konsultasi umum. Mengaktifkan *Interactive Decision Wizard* jika intent ambigu. |
| **`documents`** | [`mode_documents.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_documents.py) | Mode RAG utama berbasis Dual-Pathway (PostgreSQL pgvector 91k chunks sebagai sumber utama + fallback MySQL berita). Mendukung preservasi rujukan dokumen aktif pada percakapan multi-turn. |
| **`focus`** | [`mode_focus.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_focus.py) | Analisis dokumen tunggal secara mendalam. Menggunakan *2-Stage Rerank Clustering* untuk membedah dokumen hingga ratusan halaman. |
| **`attachment`** | [`mode_attachment.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_attachment.py) | Menangani berkas PDF, Word, Excel, dan gambar unggahan. Dilengkapi OCR multimodal vision, integrasi `DocumentPageViewer` (widget `doc_media` visual lampiran), dan alur *multi-turn document audit*. |
| **`deck`** | [`mode_deck.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_deck.py) | **Integrasi Nextcloud Deck (Pincloud).** Mengambil kartu tugas penugasan pegawai, merangkum progres, dan mengalirkan widget Kanban interaktif. |
| **`insight`** | [`mode_insight.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_insight.py) | Rangkuman instan satu berkas PDF dan bagan relasi pencabutan Surat Keputusan (Silsilah SKEP) dari basis data MySQL legacy. |
| **`generate_file`**| [`mode_generate_file.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_generate_file.py)| *Interceptor-Analyst Pipeline*. Memproduksi dokumen fisik siap unduh (`.docx`, `.xlsx`, `.pdf`) menggunakan sintaks `<create_file>`. |
| **`email`** | [`mode_email.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_email.py) | Penyusun draf korespondensi email formal berstandar BUMN lengkap dengan subject, header dinas, dan penutup representatif. |
| **`collab`** | [`mode_collab.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_collab.py) | Ruang kerja kolaborasi multi-agent dan multi-user dengan integrasi live stream room, badge undangan, dan event SSE terpusat. |
| **`compliance`** | [`mode_compliance.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_compliance.py)| Evaluasi kesesuaian SOP internal perusahaan terhadap regulasi BUMN, ISO, dan peraturan perundangan terkait. |
| **`redteam`** | [`mode_redteam.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_redteam.py) | Pengujian keamanan internal dan simulasi penyerangan prompt guna mengevaluasi ketahanan sistem pertahanan Cakra AI. |
| **`guest`** | [`mode_guest.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_guest.py) | Mode terbatas untuk pengguna publik/tamu; memblokir akses ke dokumen internal, regulasi rahasia, dan integrasi enterprise. |

---

## 🔬 Mesin Training, Fine-Tuning & Pembelajaran Mandiri

Sistem CAKRA AI mengombinasikan dua pilar pembelajaran model:
1. **Fine-Tuning QLoRA (`backend/scripts/finetune/`)**: Melatih adapter LoRA spesifik per peran kognitif (Call 1 Router dan Call 2 Responder Core).
2. **Nightly Orchestrator (`backend/app/services/training/nightly/`)**: Ekstraksi dan penyusunan dataset berkelanjutan dari basis data regulasi secara otomatis.

### Fine-Tuning QLoRA (Call 1 Router & Call 2 Core)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   DUAL-LORA SPECIALIZED ADAPTATION                     │
├───────────────────────────────────┬────────────────────────────────────┤
│  CALL 1 ROUTER ADAPTER            │  CALL 2 RESPONDER CORE ADAPTER     │
│  (cakra-router-lora)              │  (cakra-core-lora)                 │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Script: train_dispatcher_router │ • Script: train_responder_core.py  │
│ • Base: Gemma 4 31B (BNB 4-bit)   │ • Base: Gemma 4 31B (BNB 4-bit)    │
│ • Rank: 8 | Alpha: 16             │ • Rank: 16 | Alpha: 32             │
│ • Max Seq: 1024 tokens            │ • Max Seq: 2048 tokens             │
│ • Effective Batch: 24             │ • Effective Batch: 16 (Batch 4 x 4)│
│ • Fokus: Deterministic Intent,    │ • Fokus: CoT (<think>), Regulasi   │
│   Query Rewriting & Anaphora      │   Pindad, Generative UI Synthesizer│
└───────────────────────────────────┴────────────────────────────────────┘
```

- **Safety Shield Orchestrator (`weekend_adapter_trainer.py` & `run_nightly_training.py`):**
  Sistem dilengkapi sensor `pgrep` yang mendeteksi proses training manual aktif di GPU. Jika salah satu training sedang berjalan, proses otomatisasi malam (cronjob) akan di-skip demi mencegah tabrakan VRAM.
- **Checkpoint Resilience:**
  Pelatihan menyimpan checkpoint secara bertahap (`save_steps=1000`) sehingga model terlatih dapat langsung dimuat ke vLLM tanpa harus menunggu tuntas 100%.

### Arsitektur 6 Worker Multimodal (Nightly Sync)
1. **Worker 1 (Text & Hybrid Chunking):** Memotong teks regulasi dengan pemahaman hierarki perundang-undangan (Bab, Bagian, Paragraf, Pasal, Ayat) dan menyimpannya ke `dokumen_chunk` dengan vektor embeddings 1024-dim.
2. **Worker 2 (QA Pair Synthesis):** Menghasilkan ribuan variasi pertanyaan faktual, kontekstual, dan analisis implikasi hukum beserta jawaban rujukan resmi ke tabel `rag_document_questions`.
3. **Worker 3 (Knowledge Graph Engine):** Memetakan entitas kunci (jabatan, divisi, wewenang, sanksi) dan relasinya ke tabel `knowledge_graph_nodes` dan `knowledge_graph_edges`.
4. **Worker 4 (Vision & Diagram OCR):** Mengekstrak informasi dari gambar bentangan (diagram alur, struktur organisasi, tabel matriks) dan menyimpannya ke memori visual.
5. **Worker 5 (LoRA / SFT Data Formatter):** Menyusun pasangan instruksi-respons berformat JSONL untuk pelatihan model adaptif lokal Pindad.
6. **Worker 6 (Agentic Tool Synthesizer):** Menyusun dataset skenario pemanggilan fungsi dan kalkulasi analitik.

### Two-Page Spread Book Reader
Menggunakan `BookPageReader` (`page_parser.py`) berbasis PyMuPDF yang memproses dokumen dalam format **bentangan 2 halaman (kiri & kanan)** sekaligus, merefleksikan cara pandang manusia dalam membaca dokumen fisik dan mencegah terputusnya tabel atau kalimat yang melintasi batas halaman.

### Jadwal Operasional & Manual Override Safe Window
- **Hari Kerja (Senin s.d. Jumat):** Berjalan otomatis pada jam luar kantor (**18:00 – 07:30 WIB**). Menjelang jam kerja kantor (**07:50 – 08:15 WIB**), sistem melakukan *Hard Stop* untuk mengosongkan VRAM GPU demi kelancaran operasional kerja pegawai.
- **Weekend Marathon:** Dimulai **Jumat pukul 17:00 WIB hingga Senin pukul 08:00 WIB** berjalan nonstop 24 jam tanpa batasan jam.
- **Manual Start Override:** Jika pengguna menekan tombol **Start Manual** di Dashboard Analytics pada jam berapa pun (misal jam 09:00 pagi atau 16:30 sore), sistem menandai `is_manual_run=True` dan akan **terus berjalan nonstop** hingga dihentikan manual atau mencapai batas jam kerja pagi berikutnya (07:50–08:15 WIB).

---

## 🤝 Integrasi Ekosistem Enterprise Pindad

### Nextcloud Deck (Pincloud) Integration & Kanban Engine
- **Service Layer (`deck_service.py`):** Berkomunikasi langsung dengan API Nextcloud Deck (`/apps/deck/api/v1.0`). Menarik seluruh board, stack tahapan proyek, kartu penugasan, dan anggota tim terdaftar.
- **Conversational AI (`mode_deck.py`):** Ketika pengguna bertanya tentang proyeknya (*"project yang di-assign ke saya apa aja?"*), sistem merangkum tugas aktif, deadline, dan rekan tim tanpa mengharuskan model mengetik ulang JSON mentah.
- **Interactive UI Widget (`DeckTasksWidget.jsx`):**
  - **Board Switcher:** Berpindah antar papan proyek (PROYEK 2026, PROYEK 2025).
  - **Tab Filter:** Menyaring kartu (*Semua*, *Sedang Berjalan*, *Selesai*).
  - **Live Search Bar:** Pencarian cepat berbasis judul kartu, tahapan, maupun nama rekan tim.
  - **Clean Team Layout:** Label `👥 Tim:` terlindungi dari *word-wrapping*, dengan deduplikasi nama otomatis.
  - **Deep-Links:** Tombol pintas untuk membuka kartu langsung di aplikasi web Pincloud Deck.

### Collab Rooms (Ruang Kolaborasi Real-Time Multi-Agent)
- **Modul [`mode_collab.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_collab.py):** Mengelola ruang kerja terpadu di mana beberapa pegawai dan AI dapat berdiskusi dalam satu kanvas bersama.
- Mendukung *unread badge counter*, undangan kolaborator (*invitations*), dan sinkronisasi stream asinkron.

### Document Writer BUMN Workspace
- **Modul [`doc_writer/`](file:///home/qisthi/pinAi/webui/src/features/doc_writer/):** Editor naskah dinas profesional terintegrasi yang mengikuti template tata naskah resmi BUMN/Pindad.
- Dilengkapi fitur *Ghost Writer Modal* untuk bantuan koreksi tata bahasa, parafrase formal, dan ekspor instan ke format DOCX/PDF.

---

## 💻 Frontend Architecture & Dynamic Response Renderer

Dibangun di atas **React 18 + Vite** dengan arsitektur berbasis fitur (*feature-driven architecture*) di folder `webui/src/`:

### State Management Zustand (Multi-Session Background Streaming)
- Seluruh manajemen state dipecah ke dalam *slices* independen (`streamSlice`, `sessionSlice`, `uiSlice`, `authStore`).
- **Multi-Session Background Streaming:** Pengguna dapat mengirim prompt di Sesi A, berpindah ke Sesi B untuk membaca riwayat, dan proses streaming di Sesi A tetap berjalan di latar belakang tanpa terputus (*zero flickering*).

### Komponen Visual & Artifact Execution Engines
Renderer respons [`CakraResponseRenderer.jsx`](file:///home/qisthi/pinAi/webui/src/features/chat/components/CakraResponseRenderer.jsx) mem-parsing blok kode terstruktur menjadi komponen antarmuka interaktif:

| Blok Output LLM | Komponen Widget Frontend | Kemampuan Interaktif |
| :--- | :--- | :--- |
| ````deck_tasks` | `DeckTasksWidget` | Papan Kanban penugasan, board switcher, filter tab, live search |
| ````chart` | `ChartViewer` | Grafik batang, garis, pie, dan radar berbasis Chart.js |
| ````flowchart` | `ReactFlowViewer` | Diagram alur node interaktif berbasis XYFlow (zoom, pan, drag) |
| ````mermaid` | `MermaidViewer` | Diagram arsitektur, sequence diagram, ER-diagram |
| ````gantt` | `GanttViewer` | Garis waktu milestone dan durasi jadwal proyek |
| ````datagrid` | `DataGridViewer` | Tabel data dinamis dengan sortir, filter, dan ekspor Excel |
| ````map` | `MapViewer` | Peta interaktif fasilitas dan unit produksi PT Pindad |
| ````infographic` | `TimelineInfographic`| Visualisasi grafis ringkasan informasi dan linimasa |
| ````codesandbox` | `CodeSandboxViewer` | Editor dan eksekusi koding Python/JavaScript terisolasi |
| ````smartmail` | `SmartMailChatWidget`| Pratinjau draf email dinas siap kirim |
| ````doc_media` | `DocumentPageViewer` | Penampil halaman pindaian/visual dokumen asli Pindad |
| `<create_file>` | `FileGenerationCard` | Kartu notifikasi berkas fisik siap diunduh pengguna |
| `<pipeline_canvas>` | `PipelineFlowCanvas` | Visualisasi alur eksekusi pipeline kognitif dua tahap |

### Standarisasi Multibahasa i18n
Seluruh teks antarmuka, status bar, tombol kontrol, dan event SSE wajib terdaftar secara terpusat pada [`webui/src/utils/translations.js`](file:///home/qisthi/pinAi/webui/src/utils/translations.js) dalam dua bahasa:
- **`id` (Bahasa Indonesia)**
- **`en` (English)**

---

## 🗄️ Skema Triple-Database & Session Brain

```text
                                  ┌────────────────────────┐
                                  │   CAKRA AI BACKEND     │
                                  └───────────┬────────────┘
                      ┌───────────────────────┼───────────────────────┐
                      ▼                       ▼                       ▼
            ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
            │      ragdb       │    │     hris_db      │    │   peraturan_db   │
            │ (PostgreSQL 15+) │    │ (PostgreSQL Rem) │    │  (MySQL Legacy)  │
            └──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 1. `ragdb` (PostgreSQL 15+ dengan ekstensi `pgvector`)
Basis data operasional utama dan memori semantik sistem CAKRA:
- **`dokumen_chunk`**: Menyimpan **91.854 chunk regulasi ter-embed** dengan vektor dense 1024-dimensi berindeks HNSW. Berfungsi sebagai **sumber data primer RAG (*Zero Disk I/O*)**, menyuplai teks regulasi presisi tinggi langsung ke konteks prompt LLM tanpa perlu membaca berkas fisik dari media penyimpanan.
- **`dokumen`**: Menyimpan metadata relasional 2.258 berkas hukum internal (nomor peraturan, judul, tahun, rentang halaman, path berkas pindaian, dan tingkat akses).
- **`users`** & **`session_login`**: Akun pengguna hasil sinkronisasi HRIS dan pencatatan token sesi JWT aktif.
- **`chat_sessions`** & **`chat_messages`**: Riwayat obrolan lengkap dengan dukungan varian regenerasi percabangan dan *in-place edit*.
- **`rag_document_questions`**: Pasangan tanya-jawab sintetis hasil ekstraksi otomatis untuk validasi akurasi retrieval RAG.
- **`knowledge_graph_nodes`** & **`knowledge_graph_edges`**: Triplet graf pengetahuan relasi entitas hukum dan struktur regulasi PT Pindad.
- **`nightly_training_checkpoints`**: Pelacak progres pembacaan buku per halaman untuk *resumable self-learning*.
- **`llm_thinking_audit`** & **`security_logs`**: Rekaman jejak penalaran `<think>` model dan audit keamanan firewall.

### 2. `hris_db` (PostgreSQL Remote HRIS — Read-Only)
- **`tabel_user`**, **`master_person`**, **`master_unit`**: Sumber data primer kepegawaian PT Pindad untuk memvalidasi kredensial NPP, memetakan unit kerja, dan verifikasi hak otorisasi.

### 3. `peraturan_db` (MySQL Legacy — Read-Only)
- **`berita`** & **`kategori`**: Basis data katalog historis Surat Keputusan (SKEP) dan regulasi lama. Berfungsi sebagai **jalur pencarian cadangan (*fallback catalog lookup*)** dan pemetaan silsilah pencabutan hukum (*lineage*). Dokumen gambar fisik dari basis data ini hanya diakses secara *on-demand* saat pengguna meminta pratinjau halaman asli via widget `doc_media`.

---

## 📂 Struktur Repositori

```text
pinAi/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/               # Routing Layer (Hanya validasi skema & delegasi)
│   │   │   │   ├── chat/                # SSE Stream (/stream) & manajemen percakapan
│   │   │   │   ├── deck.py              # Endpoint Nextcloud Deck (/boards, /my-tasks)
│   │   │   │   ├── collab.py            # Endpoint ruang kolaborasi multi-user
│   │   │   │   ├── training.py          # Endpoint kontrol Nightly Training & live monitor
│   │   │   │   ├── documents.py         # Endpoint RAG search, lineage, & insight
│   │   │   │   ├── auth.py              # Otentikasi HRIS & verifikasi sesi
│   │   │   │   └── analytics.py         # Metrik latensi & Prompt Studio
│   │   │   ├── router.py                # Master API router
│   │   │   └── schemas/                 # Skema Pydantic validasi I/O
│   │   │
│   │   ├── core/                        # Konfigurasi aplikasi, pool database, llm_client
│   │   ├── services/                    # ★ LOGIKA BISNIS UTAMA (Clean Architecture) ★
│   │   │   ├── integrations/            # DeckService, LDAP, Nextcloud API
│   │   │   ├── pipeline/                # Orkestrator Pipeline Kognitif
│   │   │   │   ├── mode_hub.py          # Dispatcher Mode Utama
│   │   │   │   ├── dispatcher_router.py # Logika Call 1 Intent Classifier (Gemma 4)
│   │   │   │   ├── pipeline_orchestrator.py # Orkestrator Call 2 Responder
│   │   │   │   ├── agentic_interceptor.py   # ReAct Loop & Function Calling
│   │   │   │   ├── modes/               # 12 Handler mode independen
│   │   │   │   └── prompts/             # Template Jinja2 prompt lego
│   │   │   ├── training/                # Mesin Nightly Self-Learning & 6 Workers
│   │   │   ├── session/                 # Session Brain Memory Service
│   │   │   ├── rag/                     # Vector Service, Reranker, Suggestion
│   │   │   ├── documents/               # Parser dokumen, chunking, silsilah SKEP
│   │   │   └── collab/                  # Room coordination & notification hub
│   │   └── utils/                       # Security firewall, OCR helpers, formatters
│   ├── scripts/
│   │   ├── finetune/                    # Skrip Pelatihan QLoRA (Unsloth + SFTTrainer)
│   │   │   ├── train_dispatcher_router.py # Fine-tuning Call 1 Router (Gemma 4 31B)
│   │   │   ├── train_responder_core.py    # Fine-tuning Call 2 Responder Core (Gemma 4 31B)
│   │   │   ├── generate_synthetic_router_dataset.py # Generator 10k dataset Call 1
│   │   │   └── run_finetune_pipeline.sh   # Pipeline eksekusi training otomatis
│   │   └── scheduler/                   # Automasi & Penjadwalan Pelatihan Akhir Pekan
│   │       └── weekend_adapter_trainer.py # Watchdog & automasi training weekend
│   └── tests/
│
├── webui/                               # React + Vite Frontend
│   ├── src/
│   │   ├── features/                    # Feature-based Component Modules
│   │   │   ├── chat/                    # Antarmuka Chat, Bubble, Input, Navigator
│   │   │   │   └── components/          # DeckTasksWidget, CakraResponseRenderer, dll.
│   │   │   ├── collab/                  # Ruang kerja kolaborasi multi-agent
│   │   │   ├── doc_writer/              # Workspace penulisan naskah dinas BUMN
│   │   │   └── analytics/               # Dashboard analitik performa sistem
│   │   ├── stores/                      # Zustand State Management (Multi-Stream Slices)
│   │   ├── services/                    # Client API Axios & Native SSE fetcher
│   │   └── utils/translations.js        # Kamus Multibahasa Terstandar (ID & EN)
│   └── package.json
│
├── data/
│   └── finetune/                        # Dataset JSONL (nightly_cakra_core, router, dll.)
│
├── models/                              # Direktori Adapter LoRA & Checkpoints (Git Ignored)
│   └── adapters/
│       ├── cakra-router-lora/           # LoRA Adapter Call 1 Intent Classifier
│       └── cakra-core-lora/             # LoRA Adapter Call 2 Responder Core
│
├── run_gateway.py                       # API Gateway Microservice (Port 8000)
├── run_chat_service.py                  # Core Chat Service (Port 8001)
├── run_analytics_service.py             # Analytics Service (Port 8002)
├── run_auth_service.py                  # Auth Service (Port 8003)
├── start_services.sh                    # Skrip terpadu manajemen layanan
└── README.md
```

---

## 🔌 Matriks Endpoint API Lengkap

| Layanan | Method | Path | Keterangan & Hak Akses |
| :--- | :---: | :--- | :--- |
| **Gateway / Chat** | `POST` | `/api/chat/stream` | Endpoint utama streaming SSE (Two-Tier Neural Pipeline). |
| **Chat** | `GET` | `/api/chat/sessions` | Mengambil daftar riwayat sesi percakapan pengguna. |
| **Chat** | `PUT` | `/api/chat/messages/{id}` | Melakukan *in-place edit* pesan teks pengguna. |
| **Chat** | `POST` | `/api/chat/messages/{id}/regenerate` | Membuat varian respons baru dari posisi pesan tertentu. |
| **Nextcloud Deck** | `GET` | `/api/deck/my-tasks` | Mengambil seluruh kartu tugas & proyek penugasan pegawai. |
| **Nextcloud Deck** | `GET` | `/api/deck/boards` | Mengambil daftar papan proyek (*boards*) aktif dari Pincloud. |
| **Nextcloud Deck** | `GET` | `/api/deck/boards/{id}/stacks` | Mengambil kolom tahapan (*stacks*) pada papan tertentu. |
| **Collab** | `GET` | `/api/collab/rooms` | Mengambil daftar ruang kolaborasi pengguna. |
| **Collab** | `GET` | `/api/collab/rooms/{id}/stream` | Sinkronisasi pesan dan aktivitas ruang kolaborasi via SSE. |
| **Training** | `GET` | `/api/training/nightly/status` | Status live eksekusi training mandiri & statistik ragdb. |
| **Training** | `GET` | `/api/training/nightly/live-monitor`| Payload live bentangan 2 halaman, status 6 worker, terminal stream. |
| **Training** | `POST` | `/api/training/nightly/start` | Memicu training manual (override batas jam siang). |
| **Training** | `POST` | `/api/training/nightly/stop` | Menghentikan training dengan aman & simpan checkpoint. |
| **Training** | `POST` | `/api/training/nightly/reset` | Mereset seluruh progres training ke titik awal (Dokumen 1 Halaman 1). |
| **Documents** | `GET` | `/api/documents/search` | Pencarian regulasi hibrida (vektor pgvector HNSW + kata kunci). |
| **Documents** | `GET` | `/api/documents/{id}/lineage` | Mengambil silsilah hukum (mencabut / dicabut oleh) suatu SKEP. |
| **Documents** | `GET` | `/api/documents/{id}/insight` | Ekstraksi ringkasan eksekutif dokumen via model kognitif. |
| **Analytics** | `GET` | `/api/analytics/pipeline` | Metrik latensi TTFT, throughput token, dan statistik mode. |
| **Auth** | `POST` | `/api/auth/login` | Otentikasi silang kredensial pegawai (NPP & password HRIS). |
| **Auth** | `GET` | `/api/auth/verify-session` | Memverifikasi validitas JWT session token aktif. |

---

## 🛠️ Panduan Operasional & Service Management

### Prasyarat Lingkungan
- **Sistem Operasi:** Linux (Ubuntu 22.04 LTS / Debian direkomendasikan)
- **Hardware:** GPU NVIDIA (Minimal 24GB VRAM seperti RTX 3090 / RTX 4090 / A5000 / A100 untuk model 31B AWQ)
- **Runtime:** Python 3.10+, Node.js 18+, npm 9+
- **Basis Data:** PostgreSQL 15+ (dengan ekstensi `pgvector`), MySQL 8.0+

### 1. Manajemen Layanan Cepat (start_services.sh)
Direkomendasikan menggunakan skrip terpadu [`start_services.sh`](file:///home/qisthi/pinAi/start_services.sh):

```bash
# Menjalankan atau merestart seluruh microservices dan frontend secara paralel
./start_services.sh

# Hanya merestart service tertentu (contoh: chat service core)
./start_services.sh chat

# Menghentikan seluruh service yang berjalan
./start_services.sh stop

# Menghentikan seluruh service dan membersihkan alokasi VRAM GPU
./start_services.sh reset-vram
```

### 2. Menjalankan Layanan Secara Manual
Jika ingin menjalankan setiap service pada terminal terpisah untuk kebutuhan debugging:

```bash
# Aktifkan virtual environment Python
source rag_env/bin/activate

# 1. Jalankan Auth Service (Port 8003)
python run_auth_service.py

# 2. Jalankan Analytics Service (Port 8002)
python run_analytics_service.py

# 3. Jalankan Chat Core Service (Port 8001)
python run_chat_service.py

# 4. Jalankan API Gateway (Port 8000)
python run_gateway.py

# 5. Jalankan Frontend Web UI (Port 5173)
cd webui
npm install
npm run dev
```

Buka peramban pada `http://localhost:5173`. Sistem CAKRA AI siap digunakan dengan fitur lengkap!

### 3. Eksekusi Pelatihan Model (Fine-Tuning QLoRA)
Pelatihan adapter LoRA untuk model dasar **Gemma 4 31B** menggunakan pustaka Unsloth dan HuggingFace SFTTrainer:

```bash
# 1. Bersihkan alokasi VRAM GPU sebelum memulai pelatihan
./start_services.sh reset-vram

# 2. Jalankan pelatihan Call 1 Router (cakra-router-lora)
./backend/scripts/finetune/run_finetune_pipeline.sh router

# 3. Jalankan pelatihan Call 2 Responder Core (cakra-core-lora)
./backend/scripts/finetune/run_finetune_pipeline.sh core

# 4. Memantau progres pelatihan dan statistik loss secara realtime
tail -f logs/training/train_cakra_core.log
tail -f logs/training/train_router.log
```

> [!NOTE]
> Seluruh skrip pelatihan dilengkapi pelindung benturan VRAM (*Safety Shield*). Jika proses training aktif terdeteksi, daemon cron `run_nightly_training.py` dan `weekend_adapter_trainer.py` akan otomatis menunda eksekusi agar alokasi memori GPU tetap stabil tanpa risiko CUDA Out-Of-Memory. Checkpoint adapter disimpan secara berkala pada `models/adapters/`.

---

*Hak Cipta © 2026 PT Pindad (Persero). Seluruh hak cipta dilindungi undang-undang.*
