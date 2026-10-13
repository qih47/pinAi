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
- **Prinsip Percabangan Aman & Anti-Penghilangan Fitur (Non-Destruktif):** JANGAN PERNAH MERUSAK, MEMBATASI, ATAU MEMATIKAN sistem dan percabangan dinamis yang sudah berjalan (contoh: DILARANG mengunci web search atau tool calling hanya saat pill tag diklik dari UI, DILARANG mendowngrade kueri pencarian/tugas substantif menjadi sekadar chitchat kosong). Mode `auto` harus tetap dinamis, cerdas, dan leluasa memanggil tool. Prioritaskan percabangan terisolasi (jika kasus A masuk ke sub-jalur A1, jika kasus B masuk ke B1) dan jangan memotong kemampuan ekosistem yang sudah stabil.
- **Sinkronisasi Parameter Lintas Jalur & Audit Rantai Utuh:** Alur penambahan/perubahan parameter wajib mengecek sinkronisasi ke seluruh fungsi dan jalur konsumen (Call 1 Router ➔ Mode Hub ➔ Modul Responder ➔ Call 2 Interceptor ➔ SSE Stream ➔ Frontend Renderer). Jangan sampai saat memperbaiki 1 fungsi, fungsi lain yang semestinya ikut ke jalur tersebut malah patah, terpotong, atau tidak bekerja.
- **Prompt Universal & Dilarang Menggunakan Contoh Kalimat (Anti-Overfitting):**
  - **Dilarang Keras Memberikan Contoh Kalimat Baku:** JANGAN PERNAH menyertakan contoh frasa verbal atau kalimat dialog (misal: *"Bentar ya cuy..."*, *"Tunggu sebentar..."*) di dalam prompt sistem. LLM akan membeo dan meniru kalimat contoh tersebut secara kaku.
  - **Prinsip Konseptual & Mekanika Perilaku:** Rancang instruksi secara konseptual, universal, dan berfokus pada mekanika tindakan (misal: *Wajib sampaikan pernyataan pengantar secara transparan sebelum memanggil blok alat*). Biarkan model merangkai kata-katanya sendiri secara dinamis dan luwes sesuai pronoun dan nada bicara aktif.
  - **Agnostik Topik (Bukan Selalu Regex):** Call 1 Router (Gemma 4) sudah sangat pintar dan memiliki pemahaman semantik yang tinggi. Rancang instruksi yang universal dan tegas tanpa mengunci contoh topik spesifik (anak, keluarga, kopi, dsb.) dan jangan selalu mengandalkan tumpukan hardcoded regex rapuh sebagai solusi tunggal.
- **Integrasi Security Firewall:** Wajib selalu memeriksa hubungan fitur/input baru dengan `backend/app/utils/security_firewall.py` (Rate Limiting, Input Validation, Injection Detection, Content Safety, Semantic Anomaly) agar payload aman dan tidak memicu false-positive blokir.
- **Cleanup:** Jika kamu membuat file *testing/scratch* atau file bantuan lainnya selama pengerjaan, kamu **WAJIB MENGHAPUS** file tersebut setelah perintah/tugas kamu selesai dieksekusi agar *repository* tetap bersih.

