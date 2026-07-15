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

**Ringkasan Aturan Anti-Spaghetti:**
- **Backend:** Pisahkan antara *Router* (di `api/`) dan *Logika Bisnis* (di `services/`). Jangan pernah melakukan eksekusi logika kompleks langsung di endpoint router.
- **Frontend:** Pisahkan *UI/Components* dari *State/Logic* (gunakan *Zustand store* & *hooks*).
- **Registrasi Otomatis:** Fitur/endpoint/mode pipeline yang baru dibuat HARUS langsung didaftarkan ke *router master* atau modul pusat (*hub*) yang relevan.
- **Cleanup:** Jika kamu membuat file *testing/scratch* atau file bantuan lainnya selama pengerjaan, kamu **WAJIB MENGHAPUS** file tersebut setelah perintah/tugas kamu selesai dieksekusi agar *repository* tetap bersih.
