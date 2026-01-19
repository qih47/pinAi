# Pindad AI Chat Backend

Backend untuk aplikasi Pindad AI Chat yang dikonversi dari Quart ke FastAPI dengan asyncpg.

## Struktur Proyek

```
backend/
├── main.py                 # Entry point aplikasi FastAPI
├── api/                    # Router API
│   ├── __init__.py
│   ├── auth_router.py      # Endpoint autentikasi (login, logout, dll)
│   ├── chat_router.py      # Endpoint chat dan percakapan
│   ├── file_router.py      # Endpoint file dan upload
│   └── search_router.py    # Endpoint pencarian
├── core/                   # Konfigurasi aplikasi
│   ├── __init__.py
│   └── config.py          # Pengaturan aplikasi
├── database/               # Konektivitas database
│   ├── __init__.py
│   └── connection.py      # Pool koneksi asyncpg
├── logging/               # Manajemen log
│   ├── __init__.py
│   └── logger_config.py   # Konfigurasi logging
├── models/                # Model database (akan ditambahkan)
├── schemas/               # Schema Pydantic (akan ditambahkan)
└── utils/                 # Utilitas dan helper
    ├── __init__.py
    └── embedding_utils.py # Utilitas embedding
```

## Fitur

- **Autentikasi**: Login/logout dengan validasi terhadap database HRIS
- **Chat**: Sistem percakapan dengan berbagai mode (normal, dokumen, pencarian)
- **Pencarian Dokumen**: Pencarian vektor dan teks penuh dengan hybrid search
- **Upload File**: Mendukung berbagai jenis file (PDF, gambar, teks)
- **Web Scraping**: Fungsi untuk mengambil informasi dari website Pindad
- **Manajemen Log**: Sistem logging komprehensif dengan berbagai level

## Instalasi

1. Install dependensi:
```bash
pip install -r requirements.txt
```

2. Install browser untuk Playwright:
```bash
playwright install chromium
```

3. Konfigurasi variabel lingkungan (buat file `.env`):
```env
LOCAL_DB_HOST=localhost
LOCAL_DB_NAME=ragdb
LOCAL_DB_USER=pindadai
LOCAL_DB_PASSWORD=Pindad123!

LOGIN_DB_HOST=192.168.11.55
LOGIN_DB_NAME=qa_payroll_db
LOGIN_DB_USER=qisthi
LOGIN_DB_PASSWORD=q1sthi

OLLAMA_URL=http://localhost:11434/api/chat
PRIMARY_MODEL=qwen3:8b
VISION_MODEL=qwen3-vl:8b
SIMILARITY_THRESHOLD=0.7
LIMIT=10
```

## Menjalankan Aplikasi

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Atau dengan Docker:

```bash
docker build -t pindad-ai-chat .
docker run -p 8000:8000 pindad-ai-chat
```

## Endpoint API

- `POST /api/login` - Autentikasi pengguna
- `POST /api/logout` - Keluar dari sesi
- `GET /api/verify-session` - Verifikasi sesi
- `POST /api/chat` - Endpoint utama untuk percakapan
- `GET /api/chat-history/{npp}` - Riwayat percakapan pengguna
- `GET /api/chat-messages/{session_uuid}` - Pesan dalam sesi tertentu
- `POST /api/upload` - Upload file
- `POST /api/search` - Pencarian dokumen
- `GET /api/documents` - Daftar dokumen
- `GET /api/document/{doc_id}` - Detail dokumen
- `GET /api/available-models` - Daftar model yang tersedia

## Logging

Aplikasi menyediakan tiga jenis log:
- `logs/app.log` - Log aplikasi umum
- `logs/error.log` - Log error
- `logs/audit.log` - Log audit dalam format JSON

## Konversi dari Quart ke FastAPI

Perubahan utama dalam konversi dari Quart ke FastAPI:

1. **Async Framework**: Tetap menggunakan async/await tapi dengan sintaks FastAPI
2. **Database**: Mengganti psycopg2 synchronous dengan asyncpg asynchronous
3. **Routing**: Menggunakan decorator @router.post/get daripada @app.route
4. **Request/Response**: Menggunakan Pydantic schema untuk validasi
5. **Middleware**: Menggunakan middleware FastAPI
6. **Logging**: Menggunakan sistem logging yang lebih canggih

## Catatan

- Aplikasi masih menjaga logika dan alur kerja asli dari kode awal
- Nama variabel dan fungsi dipertahankan sesuai dengan kode asli
- Ditambahkan manajemen log yang komprehensif untuk monitoring
- Struktur folder diorganisir sesuai praktik terbaik FastAPI