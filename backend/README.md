# CAKRA AI Pro - Backend dengan FastAPI dan AsyncPG

## Deskripsi
Backend untuk sistem AI chat PT Pindad yang dikonversi dari Quart ke FastAPI dengan asyncpg untuk manajemen database yang lebih efisien.

## Struktur Folder
```
backend/
├── api/                 # Endpoint API
├── config/              # Konfigurasi aplikasi
│   └── settings.py      # Pengaturan aplikasi
├── database/            # Koneksi dan manajemen database
│   └── connection.py    # Manajer koneksi asyncpg
├── models/              # Model data Pydantic
│   ├── auth.py          # Model otentikasi
│   └── chat.py          # Model chat dan dokumen
├── routers/             # Route handlers
│   ├── auth.py          # Route otentikasi
│   └── chat.py          # Route chat
├── services/            # Business logic
│   ├── auth_service.py  # Layanan otentikasi
│   ├── chat_service.py  # Layanan chat
│   └── document_service.py # Layanan dokumen
├── utils/               # Utilitas
│   └── embedding_utils.py # Utilitas embedding
├── main.py              # Aplikasi utama
└── requirements.txt     # Dependensi
```

## Fitur Utama
- Otentikasi pengguna dengan validasi terhadap dua database (HRIS dan lokal)
- Chat interaktif dengan mode normal, dokumen, dan pencarian
- Integrasi dengan model AI Ollama (Qwen3 series)
- Pencarian dokumen dengan pendekatan hybrid (vector + full-text search)
- Manajemen sesi dan riwayat percakapan

## Konfigurasi
Aplikasi menggunakan variabel lingkungan yang dapat dikonfigurasi melalui file `.env`:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ragdb
DB_USER=pindadai
DB_PASSWORD=Pindad123!
# ... dll
```

## Instalasi
```bash
pip install -r requirements.txt
```

## Menjalankan Aplikasi
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoint API
- `POST /api/login` - Login pengguna
- `POST /api/logout` - Logout pengguna
- `GET /api/verify-session` - Verifikasi sesi
- `POST /api/chat` - Endpoint utama chat
- `POST /api/search` - Pencarian informasi
- `GET /api/available-models` - Daftar model yang tersedia
- `GET /health` - Health check

## Perubahan dari Versi Quart ke FastAPI
1. Konversi dari Quart ke FastAPI untuk performa dan skalabilitas yang lebih baik
2. Penggunaan asyncpg sebagai pengganti psycopg2 untuk operasi database asynchronous
3. Strukturisasi kode menjadi arsitektur berbasis service untuk modularitas
4. Penggunaan Pydantic untuk validasi request/response
5. Implementasi dependency injection dan lifecycle management