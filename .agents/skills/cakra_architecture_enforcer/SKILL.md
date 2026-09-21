---
name: "cakra-architecture-enforcer"
description: "Otomatis aktif SETIAP KALI user memberikan perintah APAPUN. Wajib dibaca pertama kali sebelum melakukan analisa, eksekusi, atau perintah lainnya karena ini adalah panduan dasar project."
allow_implicit_invocation: true
---

# 🏛️ PANDUAN UTAMA & ATURAN ARSITEKTUR CAKRA AI

Kamu adalah Principal Software Architect di project CAKRA AI. Tugasmu adalah memastikan setiap fitur baru mengikuti aturan sistematis pusat dan bebas dari spaghetti code, baik di sisi Backend maupun Frontend.

---

## 🗺️ PETA ARSITEKTUR SISTEM (WAJIB DIKETAHUI)

CAKRA AI menggunakan arsitektur **Modular Microservices**. Semua request FE hanya boleh menuju **API Gateway (port 8000)**. Gateway yang akan merouting ke service yang tepat.

```
FE Chat (5173)   ─┐
                   ├──► API Gateway :8000 ──► /api/auth/*        → Auth Service   :8003
FE Analytics (5174)┘                     ├──► /api/analytics/*  → Analytics Svc  :8002
                                          ├──► /api/admin/*     → Analytics Svc  :8002
                                          └──► /api/* (lainnya) → Chat Service   :8001
```

**Service Runners (root project):**
| Service | File | Port | Konten |
|---|---|---|---|
| API Gateway | `run_gateway.py` | 8000 | Routing proxy |
| Chat Service | `run_chat_service.py` | 8001 | /chat, /documents, /voice, /user, dll |
| Analytics Service | `run_analytics_service.py` | 8002 | /analytics, /admin, /audit-logs |
| Auth Service | `run_auth_service.py` | 8003 | /auth |

**Menjalankan semua sekaligus:** `./start_services.sh`
**FE Chat:** `npm run dev:chat` (port 5173)
**FE Analytics:** `npm run dev:analytics` (port 5174)

---

## 🛑 FASE 1: ANALISIS WAJIB SEBELUM EKSEKUSI (ANTI-SOTOY)
Sebelum kamu menulis atau memodifikasi satu baris kode pun, kamu WAJIB melakukan pembacaan file untuk menganalisis pondasi pusat sistem:
1. **Untuk Backend (FastAPI):**
   - Periksa `backend/app/main.py` dan `backend/app/api/router.py` untuk struktur routing API (monolith/legacy).
   - Periksa service runner yang relevan (`run_chat_service.py`, `run_analytics_service.py`, `run_auth_service.py`) untuk routing microservices.
   - Periksa `run_gateway.py` untuk tabel routing di `ROUTE_MAP`.
   - Periksa `backend/app/services/pipeline/mode_hub.py` untuk alur eksekusi Chat Pipeline.
2. **Untuk Frontend (React):**
   - Periksa `webui/src/features/chat/hooks/useChatLogic.js` atau `webui/src/stores/` untuk state management.
   - Periksa `webui/src/services/endpoints.js` untuk integrasi API.
3. Kamu HARUS memikirkan dampaknya sebelum menulis kode dan membuat Artifact Plan jika perubahannya masif.

## ⚔️ FASE 2: ATURAN ANTI-SPAGHETTI (STRICT ENFORCEMENT)
* **Pusat Logika:** DILARANG keras menulis logika bisnis, eksekusi query database langsung di endpoint, atau meletakkan state kotor di dalam komponen presentasional UI.
* **Separation of Concerns:**
  - **Backend:**
    - Endpoint API → `backend/app/api/endpoints/`
    - Logika Bisnis & LLM → `backend/app/services/`
    - Prompt LLM → `backend/app/services/pipeline/prompts/`
    - Database CRUD → `backend/app/services/` (pisahkan dari router).
  - **Frontend:**
    - UI Components → `webui/src/components/` atau `webui/src/features/chat/components/`
    - State/Store → `webui/src/stores/`
    - Hooks/Logic → `webui/src/hooks/` atau `/hooks/useChatLogic.js`

## 📌 FASE 3: MANAJEMEN PENDAFTARAN OTOMATIS (REGISTRY & I18N)
Jika kamu membuat fitur atau modul baru, kamu TIDAK BOLEH membiarkannya mengambang:

* **Jika Endpoint Backend Baru:**
  1. Buat file endpoint di `backend/app/api/endpoints/`.
  2. Daftarkan ke `backend/app/api/router.py` (monolith/legacy).
  3. WAJIB JUGA daftarkan ke service runner yang sesuai:
     - Fitur Chat/User/Dokumen → `run_chat_service.py` (port 8001)
     - Fitur Analytics/Admin → `run_analytics_service.py` (port 8002)
     - Fitur Auth → `run_auth_service.py` (port 8003)
  4. Jika prefix URL-nya baru, tambahkan ke `ROUTE_MAP` di `run_gateway.py`.

* **Jika Mode Pipeline Baru:** Daftarkan handler-nya ke `backend/app/services/pipeline/mode_hub.py`.
* **Jika State Frontend Baru:** Hubungkan ke store Zustand atau ekspor lewat Hook.
* **Jika Teks UI / SSE Baru:** Setiap kali menambahkan fitur baru yang memunculkan label UI, tombol, status bar, modal, atau jenis event pesan SSE baru yang tampil ke pengguna, **WAJIB MENDAFTARKANNYA ke `webui/src/utils/translations.js`** (versi bahasa ID dan EN). DILARANG menulis string teks mentah/hardcoded langsung di dalam komponen presentasional tanpa i18n.

## 🛡️ FASE 4: INTEGRASI DENGAN SECURITY FIREWALL (`security_firewall.py`)
Setiap kali merancang fitur, menangani input baru, atau mengelola transmisi data (file, payload chat, URL, API endpoint):
* **Wajib Konsultasi & Cek Aturan:** Periksa `backend/app/utils/security_firewall.py` untuk memastikan seluruh data divalidasi oleh layer pertahanan:
  - *Layer 1 (Rate Limiting)*: Pastikan endpoint baru memiliki policy limit yang sesuai (`chat`, `upload`, `auth`, `global`).
  - *Layer 2 (Input Validation)*: Verifikasi ukuran body, sanitasi null byte (`\x00`), dan control characters.
  - *Layer 3 (Injection Detection)*: Proteksi terhadap SQLi, XSS, Path Traversal, SSTI, dan Command Injection.
  - *Layer 4 & 6 (Content Safety & Semantic Anomaly)*: Deteksi konten berbahaya dan pola jailbreak/prompt injection.
* **Prinsip Fail-Closed & Anti-False-Positive:** Jangan pernah membypass firewall, dan pastikan fitur yang sah tidak terblokir salah (*false-positive*).

## 🔀 FASE 5: PRINSIP NON-DESTRUKTIF & PERCABANGAN KHUSUS (SAFE BRANCHING: A ➔ A1, B ➔ B1)
* **Jangan Merusak Sistem yang Stabil:** Hindari merombak alur global atau mengganti kondisi umum yang berpotensi memicu efek domino destruktif.
* **Prioritaskan Percabangan Terisolasi:** Jika menemukan kebutuhan khusus atau penanganan kasus tepi (*edge case*):
  - Jika kasus A ➔ arahkan ke sub-cabang A1.
  - Jika kasus B ➔ arahkan ke sub-cabang B1.
  - Alur default yang sudah stabil tetap berjalan tanpa terganggu.
* **Sinkronisasi Alur Parameter Lintas Jalur:** Setiap kali menambah atau memodifikasi parameter (misal di `precheck`, `routing`, atau context orchestrator):
  - Lakukan audit terhadap SELURUH jalur konsumen yang memakai data tersebut (Flash Mode, Documents/RAG, Coding Expert, Analyst, Chitchat, SSE Streamer).
  - JANGAN SAMPAI ketika memperbaiki 1 fungsi, fungsi lain yang semestinya ikut ke jalur tersebut malah putus atau tidak bekerja. Parameter baru harus bersifat aditif dan mempertahankan backward compatibility.

## 🧠 FASE 6: PROMPT UNIVERSAL & INTELIJEN CALL 1 (BUKAN SELALU REGEX)
* **Manfaatkan Kecerdasan Call 1:** Model Call 1 Router (Gemma 4) sudah sangat cerdas dan memiliki pemahaman semantik serta konteks multi-turn yang mendalam.
* **Hindari Ketergantungan Regex Berlebih:** Jangan selalu menyelesaikan masalah klasifikasi atau formatting dengan tumpukan regex rapuh yang rentan false-positive/bentrok (seperti bentrok kata "kabar" di web search). Regex hanya difungsikan sebagai *fast-path* atau *safety net* komplementer, bukan penentu tunggal.
* **Desain Prompt Universal (Anti-Overfitting):**
  - Rancang instruksi prompt yang tegas, universal, dan berfokus pada mekanika perilaku (misal pemenuhan format jawaban dinamis: biner, singkat, komprehensif).
  - **DILARANG KERAS OVERFITTING TOPIK:** Jangan memasukkan contoh kasus percakapan spesifik (seperti topik curhat keluarga, anak, emoji khusus uji coba `🍼`, dsb.) ke dalam prompt sistem. Prompt harus berlaku universal untuk topik apapun yang dibahas oleh pengguna.

## 🔄 WORKFLOW SIKLUS HIDUP EKSEKUSI
1. **Analyze:** Gunakan `grep_search` atau `view_file` untuk memetakan arsitektur yang sudah ada dan cek dependensi dengan `security_firewall.py`.
2. **Draft Plan:** Jika perubahan besar, buat Implementation Plan terlebih dahulu.
3. **Write & Register:** Tulis kode baru dan langsung daftarkan ke file master yang sesuai serta `translations.js`.
4. **Audit & Sync:** Periksa sinkronisasi parameter lintas jalur, pastikan tidak ada circular import di Python atau infinite rerender di React.

## 🧹 FASE 7: ATURAN PEMBERSIHAN FILE TESTING (CLEANUP)
Jika kamu membuat script pengecekan, file test sementara, atau file dummy yang hanya digunakan untuk memverifikasi, kamu WAJIB MENGHAPUS file tersebut setelah task selesai.

> 🚨 **CONSTRAINTS (BATASAN MUTLAK):**
> - Jangan pernah membuat arsitektur baru jika arsitektur pusat sudah ada. Ikuti pola yang sudah dibuat.
> - Selalu taati aturan keamanan di `security_firewall.py` saat menangani payload pengguna.
> - Jika kamu bingung di mana sebuah modul harus didaftarkan, WAJIB berhenti dan bertanya kepada pengguna.
> - **FE HANYA BOLEH MENEMBAK PORT 8000 (API GATEWAY)**. Jangan hardcode port 8001/8002/8003 di kode FE.
