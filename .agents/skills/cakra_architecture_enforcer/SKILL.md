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

## 📌 FASE 3: MANAJEMEN PENDAFTARAN OTOMATIS (REGISTRY)
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

## 🔄 WORKFLOW SIKLUS HIDUP EKSEKUSI
1. **Analyze:** Gunakan `grep_search` atau `view_file` untuk memetakan arsitektur yang sudah ada.
2. **Draft Plan:** Jika perubahan besar, buat Implementation Plan terlebih dahulu.
3. **Write & Register:** Tulis kode baru dan langsung daftarkan ke file master yang sesuai.
4. **Audit:** Pastikan tidak ada circular import di Python atau infinite rerender di React.

## 🧹 FASE 4: ATURAN PEMBERSIHAN FILE TESTING (CLEANUP)
Jika kamu membuat script pengecekan, file test sementara, atau file dummy yang hanya digunakan untuk memverifikasi, kamu WAJIB MENGHAPUS file tersebut setelah task selesai.

> 🚨 **CONSTRAINTS (BATASAN MUTLAK):**
> - Jangan pernah membuat arsitektur baru jika arsitektur pusat sudah ada. Ikuti pola yang sudah dibuat.
> - Selalu taati aturan keamanan di `security_firewall.py` saat menangani payload pengguna.
> - Jika kamu bingung di mana sebuah modul harus didaftarkan, WAJIB berhenti dan bertanya kepada pengguna.
> - **FE HANYA BOLEH MENEMBAK PORT 8000 (API GATEWAY)**. Jangan hardcode port 8001/8002/8003 di kode FE.
