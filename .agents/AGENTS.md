# CAKRA AI PROJECT-SCOPED RULES

Aturan-aturan di bawah ini **selalu aktif** dan wajib dipatuhi pada setiap *task* atau instruksi di *workspace* ini.

## 1. STRUKTUR FOLDER PROJECT UTAMA (CAKRA AI)
Kamu berada dalam *repository* yang memisahkan antara `backend` (FastAPI) dan `webui` (React/Vite). 
Berikut adalah struktur dasar dan pembagian tugas folder:

- `/backend/` : Folder utama untuk *Backend* (Python/FastAPI)
  - `/backend/app/api/` : Rute API (*Endpoint routers*). Jangan taruh logika bisnis di sini.
  - `/backend/app/services/` : Logika bisnis utama, akses *database*, manajemen *AI/LLM*, dan *RAG pipeline*.
  - `/backend/app/core/` : Konfigurasi aplikasi, setup database, keamanan, dll.
- `/webui/` : Folder utama untuk *Frontend* (JavaScript/React/Vite)
  - `/webui/src/components/` & `/webui/src/features/` : Komponen antarmuka (UI). Jangan taruh logika atau *state* kotor di sini.
  - `/webui/src/stores/` : Manajemen *state* global (Zustand).
  - `/webui/src/services/` : Layanan komunikasi dengan API *backend*.

## 2. ATURAN ARSITEKTUR WAJIB (PINNED REFERENCE)
Kamu WAJIB mematuhi semua aturan dasar dan membaca detailnya jika diperlukan pada *skill* **cakra-architecture-enforcer** (`.agents/skills/cakra_architecture_enforcer/SKILL.md`) **sebelum** melakukan eksekusi perintah pembuatan atau modifikasi kode apa pun.

**Ringkasan Aturan Anti-Spaghetti & Standar Sistem:**
- **Backend:** Pisahkan antara *Router* (di `api/`) dan *Logika Bisnis* (di `services/`). Jangan pernah melakukan eksekusi logika kompleks langsung di endpoint router.
- **Frontend:** Pisahkan *UI/Components* dari *State/Logic* (gunakan *Zustand store* & *hooks*).
- **Registrasi Otomatis & i18n:** Fitur, endpoint, atau mode pipeline yang baru dibuat HARUS langsung didaftarkan ke *router master* atau modul pusat (*hub*) yang relevan. Jika fitur baru menambahkan teks UI, status bar, tombol, atau event pesan SSE baru yang berinteraksi dengan pengguna, **WAJIB mendaftarkannya ke `webui/src/utils/translations.js`** (ID & EN) agar terstandarisasi multibahasa.
- **Prinsip Percabangan Aman (Non-Destruktif):** JANGAN MERUSAK sistem yang sudah stabil. Prioritaskan percabangan terisolasi (contoh: jika kasus A masuk ke sub-jalur A1, jika kasus B masuk ke B1) sehingga tidak merusak alur global yang sudah berjalan dengan baik.
- **Sinkronisasi Parameter Lintas Jalur:** Alur penambahan/perubahan parameter wajib mengecek sinkronisasi ke seluruh fungsi dan jalur lain yang mengonsumsinya. Jangan sampai saat memperbaiki 1 fungsi, fungsi lain yang semestinya ikut ke jalur tersebut malah patah atau tidak bekerja.
- **Integrasi Security Firewall:** Wajib selalu memeriksa hubungan fitur/input baru dengan `backend/app/utils/security_firewall.py` (Rate Limiting, Input Validation, Injection Detection, Content Safety, Semantic Anomaly) agar payload aman dan tidak memicu false-positive blokir.
- **Prompt Universal (Bukan Selalu Regex):** Call 1 Router (Gemma 4) sudah sangat pintar dan memiliki pemahaman semantik yang tinggi. Rancang instruksi prompt Call 1 yang universal, agnostik topik, dan tegas; jangan selalu mengandalkan tumpukan hardcoded regex rapuh sebagai solusi tunggal. Dilarang keras melakukan overfitting topik (misal mengunci contoh topik anak/keluarga/spesifik) di dalam prompt sistem.
- **Cleanup:** Jika kamu membuat file *testing/scratch* atau file bantuan lainnya selama pengerjaan, kamu **WAJIB MENGHAPUS** file tersebut setelah perintah/tugas kamu selesai dieksekusi agar *repository* tetap bersih.

