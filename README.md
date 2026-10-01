# 🛡️ CAKRA AI — Enterprise Cognitive Intelligence Platform (PT Pindad)

> **Cerdas, Adaptif, Konstruktif, Responsif, Analitik**  
> Platform asisten kecerdasan kognitif enterprise terpadu berbasis **Two-Tier Neural Pipeline**, **Microservices Mesh**, **Triple-Database Architecture**, dan **Deep Knowledge Synthesis** yang dirancang khusus untuk ekosistem **PT Pindad (Persero)**.

---

## 📑 Daftar Isi

1. [Ikhtisar Arsitektur Enterprise](#-ikhtisar-arsitektur-enterprise)
2. [Topologi Jaringan Microservices & Inference Cluster](#-topologi-jaringan-microservices--inference-cluster)
3. [Arsitektur Pipeline Kognitif (Dispatcher & Responder)](#-arsitektur-pipeline-kognitif-dispatcher--responder)
   - [Lapisan 0: Security Firewall & Identity Resolution](#lapisan-0-security-firewall--identity-resolution)
   - [Lapisan 1: Call 1 — Intent Router & Query Dispatcher](#lapisan-1-call-1--intent-router--query-dispatcher)
   - [Lapisan 1.5: Admission Controller & GPU Semaphore (TDAAC)](#lapisan-15-admission-controller--gpu-semaphore-tdaac)
   - [Lapisan 2: Call 2 — Synthesizer & Persona Responder](#lapisan-2-call-2--synthesizer--persona-responder)
   - [Stream Demuxer & Benchmarking Realtime](#stream-demuxer--benchmarking-realtime)
4. [Katalog Lengkap Mode Hub (12 Execution Handlers)](#-katalog-lengkap-mode-hub-12-execution-handlers)
5. [Mesin Deep Training & Pembelajaran Mandiri (Nightly Orchestrator)](#-mesin-deep-training--pembelajaran-mandiri-nightly-orchestrator)
   - [Arsitektur 6 Worker Multimodal](#arsitektur-6-worker-multimodal)
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

CAKRA AI meninggalkan paradigma monolitik tradisional dan beralih ke arsitektur **Clean Service Separation** dan **Microservices Mesh**. Frontend (React/Vite) tidak pernah berkomunikasi langsung dengan inferensi model berat secara sinkronus; seluruh alur pesan mengalir melalui **API Gateway**, didistribusikan ke layanan mikro independen, dan disalurkan ke pengguna via protokol **Server-Sent Events (SSE)** berkecepatan tinggi.

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
│ • Nightly Training Engine     │   │ • Model Performance Profiling │   │ • Identity Profile Mapping    │
└───────────────┬───────────────┘   └───────────────────────────────┘   └───────────────────────────────┘
                │
                ├──────────────────────────────────────┬──────────────────────────────────────┐
                ▼                                      ▼                                      ▼
┌───────────────────────────────┐      ┌───────────────────────────────┐      ┌───────────────────────────────┐
│        RAG DATABASE           │      │        HRIS DATABASE          │      │      PERATURAN DATABASE       │
│ PostgreSQL 15 + pgvector      │      │ PostgreSQL Remote (Read-Only) │      │ MySQL Legacy (Read-Only)      │
│ • 1024-dim Vector Chunks HNSW │      │ • Master Person & Master Unit │      │ • Berita Regulasi (SKEP)      │
│ • Chat History & Sessions     │      │ • Validasi NPP Pegawai Pindad │      │ • Silsilah Hukum (Mencabut /  │
│ • Nightly Training Checkpoints│      │ • Pemetaan Struktur Organisasi│      │   Dicabut Oleh)               │
└───────────────────────────────┘      └───────────────────────────────┘      └───────────────────────────────┘
                │
                ▼ INFERENCE CLUSTER (GPU Engine)
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ • vLLM Server (Port 8005)      : gemma-4-31B-it-AWQ (High-Throughput Tensor Core)      │
│ • Ollama Server (Port 11434)   : gemma4:31b (Fallback / Router) & mxbai-embed-large   │
│ • GPU Reranker Core            : BAAI/bge-reranker-v2-m3 (Cross-Encoder Scoring)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Topologi Jaringan Microservices & Inference Cluster

| Komponen | Host & Port | Peran Utama | Protokol / Engine |
| :--- | :--- | :--- | :--- |
| **Frontend WebUI** | `http://0.0.0.0:5173` | Antarmuka pengguna, workspace kolaborasi, chat | React 18, Vite, Tailwind/Vanilla CSS |
| **API Gateway** | `http://0.0.0.0:8000` | Gerbang tunggal, router reverse-proxy, SSE pipe | FastAPI, httpx asinkronus |
| **Chat Core Service** | `http://0.0.0.0:8001` | Logika pipeline AI, RAG, Deck, file processing | FastAPI, asyncpg, PyMuPDF, Jinja2 |
| **Analytics Service** | `http://0.0.0.0:8002` | Dashboard metrik, prompt studio, audit log | FastAPI, asyncpg, JSONL streaming |
| **Auth Service** | `http://0.0.0.0:8003` | Otentikasi HRIS Pindad, manajemen sesi token | FastAPI, asyncpg, passlib, JWT |
| **vLLM Inference** | `http://127.0.0.1:8005` | Eksekusi model utama (Synthesizer & Persona) | vLLM Engine (AWQ Quantization) |
| **Ollama Inference** | `http://127.0.0.1:11434`| Eksekusi model pendukung, embeddings | Ollama API, GGML/GGUF |

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
[1. PRECHECK & CALL 1: DISPATCHER ROUTER (Gemma 4)]
  ├── Deterministic JSON Schema Extraction (temp=0.0, num_predict=200)
  ├── 12 Parameter Kontrol Intensi (need_rag, is_deck_query, is_ambiguous, dll.)
  └── Web Query Decomposition (Pemisahan pertanyaan majemuk jadi kueri terarah)
         │
         ├── Ambigu? ──▶ [Interactive Clarification Wizard (Mode Flash)]
         │
         ▼
[1.5. ADMISSION CONTROLLER & GPU SEMAPHORE (TDAAC)]
  ├── Dynamic Claim Slot Antrean GPU (Pencegahan VRAM Crash/OOM)
  └── Tracking Queue Wait Time
         │
         ▼
[2. CALL 2: SYNTHESIZER / RESPONDER (Gemma 4 31B AWQ)]
  ├── Dynamic Lego Prompts Assembly (Mermaid, DataGrid, Deck, Math, dll.)
  ├── Token Streaming & Thinking Demuxing
  └── Direct Artifact Emission (```deck_tasks, ```chart, ```flowchart)
         │
         ▼
[Client Output via SSE Stream (Chunk, Status, Thinking, Artifacts, Done)]
```

### Lapisan 0: Security Firewall & Identity Resolution
- **Security Firewall (`security_firewall.py`):** Mencegah injeksi prompt, manipulasi sistem, kebocoran data rahasia (*content safety*), dan anomali semantik secara proaktif sebelum payload mencapai LLM.
- **Dual Identity Resolution (`pipeline_orchestrator.py`):**
  - **`full_name` & `current_user_npp`:** Nama lengkap resmi kedinasan dari HRIS (misal: `06652 Qisthi Iskandar Haqiki`). Digunakan untuk pencocokan keabsahan hukum, daftar SK penugasan, dan klausul dokumen.
  - **`employee_name`:** Nama panggilan santai sesuai preferensi di pengaturan akun (misal: `Qisthi`). Digunakan untuk sapaan hangat percakapan alami.

### Lapisan 1: Call 1 — Intent Router & Query Dispatcher
Modul [`dispatcher_router.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/dispatcher_router.py) bertindak sebagai otak routing dengan karakteristik deterministik:
- **Konfigurasi Eksekusi:** `temperature: 0.0`, `num_predict: 200`, `num_ctx: 4096`, `is_thinking: False`.
- **12 Parameter Kontrol JSON:**
  1. `need_rag`: Apakah memerlukan penelusuran regulasi/dokumen internal Pindad.
  2. `is_chitchat`: Obrolan kasual atau sapaan langsung tanpa data luar.
  3. `is_web_search`: Membutuhkan penelusuran fakta eksternal internet terkini.
  4. `is_generate_file`: Permintaan pembuatan berkas fisik Word, Excel, atau PDF.
  5. `is_generate_email`: Draf korespondensi dinas resmi BUMN.
  6. `is_docwriter`: Penulisan surat dinas dan SOP pada workspace Document Writer.
  7. `is_deck_query`: Pertanyaan tugas, proyek, dan kartu di Nextcloud Deck (Pincloud).
  8. `is_map_query`: Informasi geolokasi dan peta fasilitas operasional.
  9. `is_chart_query`: Permintaan data visual analitik atau grafik perbandingan.
  10. `is_ambiguous`: Pertanyaan multi-tafsir yang membutuhkan panduan wizard interaktif.
  11. `needs_history`: Menentukan apakah riwayat obrolan masa lalu relevan dibawa ke Call 2.
  12. `pronoun`: Menyesuaikan gaya bahasa (*formal dinas* vs *informal santai*).
- **Smart Signal Stripping:** Menyingkirkan kode pemrograman panjang atau log error mentah saat mengevaluasi intensi, sehingga proses prefill Call 1 selesai dalam < 1.2 detik.

### Lapisan 1.5: Admission Controller & GPU Semaphore (TDAAC)
- Menggunakan tiket *Time-Decayed Adaptive Admission Control* (TDAAC).
- Mengunci antrean pemanggilan GPU sehingga ketika puluhan pengguna mengirim prompt bersamaan, model 31B tetap berjalan stabil di VRAM tanpa tabrakan memori atau latensi *jitter*.

### Lapisan 2: Call 2 — Synthesizer & Persona Responder
Modul [`llm_client.py`](file:///home/qisthi/pinAi/backend/app/core/llm_client.py) merakit instruksi sistem berbasis balok lego prompt (*Dynamic Lego Blocks*):
- **Visual Lego Blocks:** Mermaid diagram, XYFlow flowchart, Chart.js engine, Gantt timeline, Interactive DataGrid, Infographic.
- **Domain Lego Blocks:** Troubleshooting matrix, Deep Research, Coding Sandbox, Smart Mail, BUMN Document Writer, Nextcloud Deck Kanban.

### Stream Demuxer & Benchmarking Realtime
- **`_StreamDemuxer`:** Memisahkan token penalaran (*reasoning channel*) `<|channel>thought ... <channel|>` dari jawaban final secara asinkron tanpa memutus aliran SSE.
- **Diagnostic ASCII Table:** Menampilkan visualisasi matriks TTFT (Time-to-First-Token), kecepatan prefill (tok/s), kecepatan generasi (tok/s), dan pemakaian memori per permintaan.

---

## 🎛️ Katalog Lengkap Mode Hub (12 Execution Handlers)

`ModeHub` (`backend/app/services/pipeline/mode_hub.py`) mendelegasikan eksekusi ke handler khusus:

| Mode | Modul Handler | Deskripsi & Alur Kerja |
| :--- | :--- | :--- |
| **`flash`** | [`mode_flash.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_flash.py) | Respons instan untuk chit-chat dan konsultasi umum. Mengaktifkan *Interactive Decision Wizard* jika intent ambigu. |
| **`documents`** | [`mode_documents.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_documents.py) | Mode RAG utama. Menelusuri arsip regulasi, Surat Keputusan (SKEP), dan dokumen teknis via pgvector (HNSW) & reranker BGE-M3. |
| **`focus`** | [`mode_focus.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_focus.py) | Analisis dokumen tunggal secara mendalam. Menggunakan *2-Stage Rerank Clustering* untuk membedah dokumen hingga ratusan halaman. |
| **`attachment`** | [`mode_attachment.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_attachment.py) | Menangani berkas PDF, Word, Excel, dan gambar unggahan. Dilengkapi OCR multimodal vision dan alur *multi-turn document audit*. |
| **`deck`** | [`mode_deck.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_deck.py) | **Integrasi Nextcloud Deck (Pincloud).** Mengambil kartu tugas penugasan pegawai, merangkum progres, dan mengalirkan widget Kanban interaktif. |
| **`insight`** | [`mode_insight.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_insight.py) | Rangkuman instan satu berkas PDF dan bagan relasi pencabutan Surat Keputusan (Silsilah SKEP) dari basis data MySQL legacy. |
| **`generate_file`**| [`mode_generate_file.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_generate_file.py)| *Interceptor-Analyst Pipeline*. Memproduksi dokumen fisik siap unduh (`.docx`, `.xlsx`, `.pdf`) menggunakan sintaks `<create_file>`. |
| **`email`** | [`mode_email.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_email.py) | Penyusun draf korespondensi email formal berstandar BUMN lengkap dengan subject, header dinas, dan penutup representatif. |
| **`collab`** | [`mode_collab.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_collab.py) | Ruang kerja kolaborasi multi-agent dan multi-user dengan integrasi live stream room, badge undangan, dan event SSE terpusat. |
| **`compliance`** | [`mode_compliance.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_compliance.py)| Evaluasi kesesuaian SOP internal perusahaan terhadap regulasi BUMN, ISO, dan peraturan perundangan terkait. |
| **`redteam`** | [`mode_redteam.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_redteam.py) | Pengujian keamanan internal dan simulasi penyerangan prompt guna mengevaluasi ketahanan sistem pertahanan Cakra AI. |
| **`guest`** | [`mode_guest.py`](file:///home/qisthi/pinAi/backend/app/services/pipeline/modes/mode_guest.py) | Mode terbatas untuk pengguna publik/tamu; memblokir akses ke dokumen internal, regulasi rahasia, dan integrasi enterprise. |

---

## 🔬 Mesin Deep Training & Pembelajaran Mandiri (Nightly Orchestrator)

Modul [`backend/app/services/training/nightly/`](file:///home/qisthi/pinAi/backend/app/services/training/nightly/) adalah mesin ekstraksi dan pembentukan basis pengetahuan berkelanjutan (*Continuous Self-Learning Engine*):

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   NIGHTLY TRAINING ORCHESTRATOR                        │
├───────────────────────────────────┬────────────────────────────────────┤
│  Two-Page Spread Book Reader      │  Multi-Tier Document Prioritization│
│  (Bentangan 2 Halaman Visual)     │  Tier 1: Aktif │ Tier 2: Dicabut   │
└─────────────────┬─────────────────┴──────────────────┬─────────────────┘
                  │                                    │
                  ▼                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      6 WORKER MULTIMODAL SIMULTAN                      │
│                                                                        │
│ • Worker 1 (Text & Hybrid Chunking) : Struktur BAB, Pasal, Ayat HNSW   │
│ • Worker 2 (QA Pair Synthesis)      : Pasangan Tanya-Jawab SFT/LoRA    │
│ • Worker 3 (Knowledge Graph Engine) : Triplet Entity-Relation Graph    │
│ • Worker 4 (Vision & Diagram OCR)   : Analisis Bagan, Tabel, Alur Visual│
│ • Worker 5 (LoRA / SFT Data Formatter): Dataset Pelatihan Model Masa Depan│
│ • Worker 6 (Agentic Tool Synthesizer): Pola Eksekusi Function Calling  │
└─────────────────┬──────────────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Checkpoint Manager (nightly_training_checkpoints di ragdb)            │
│  Resumable Page-by-Page │ Live Monitor Terminal Stream │ Artifact View │
└────────────────────────────────────────────────────────────────────────┘
```

### Arsitektur 6 Worker Multimodal
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
Renderer respons [`CakraResponseRenderer.jsx`](file:///home/qisthi/pinAi/webui/src/features/chat/components/CakraResponseRenderer.jsx) secara cerdas menerjemahkan blok kode khusus menjadi antarmuka interaktif:

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
| `<create_file>` | `FileGenerationCard` | Kartu notifikasi berkas fisik siap diunduh pengguna |

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
Basis data utama sistem CAKRA:
- **`users`** & **`session_login`**: Akun pengguna hasil sinkronisasi HRIS dan pencatatan token sesi aktif.
- **`chat_sessions`** & **`chat_messages`**: Riwayat obrolan dengan dukungan varian regenerasi dan *in-place edit*.
- **`dokumen`** & **`dokumen_chunk`**: Metadata dokumen internal beserta vektor embedding 1024-dimensi berindeks HNSW.
- **`rag_document_questions`**: Pasangan tanya-jawab sintetis hasil ekstrak Worker 2 untuk evaluasi akurasi RAG.
- **`knowledge_graph_nodes`** & **`knowledge_graph_edges`**: Triplet graf pengetahuan entitas hukum Pindad.
- **`nightly_training_checkpoints`**: Pelacak progres pembacaan buku per halaman untuk *resumable training*.
- **`llm_thinking_audit`** & **`security_logs`**: Rekaman jejak penalaran model dan audit keamanan sistem.

### 2. `hris_db` (PostgreSQL Remote HRIS — Read-Only)
- **`tabel_user`**, **`master_person`**, **`master_unit`**: Sumber data primer kepegawaian PT Pindad untuk memvalidasi kredensial NPP dan memetakan struktur direktorat.

### 3. `peraturan_db` (MySQL Legacy — Read-Only)
- **`berita`** & **`kategori`**: Basis data historis Surat Keputusan (SKEP) dan regulasi lama untuk pemetaan silsilah pencabutan hukum (*lineage*).

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

---

*Hak Cipta © 2026 PT Pindad (Persero). Seluruh hak cipta dilindungi undang-undang.*
