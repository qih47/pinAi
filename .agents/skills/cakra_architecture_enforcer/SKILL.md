---
name: "cakra-architecture-enforcer"
description: "Otomatis aktif SETIAP KALI user memberikan perintah APAPUN. Wajib dibaca pertama kali sebelum melakukan analisa, eksekusi, atau perintah lainnya karena ini adalah panduan dasar project."
allow_implicit_invocation: true
---

# 🏛️ PANDUAN UTAMA & ATURAN ARSITEKTUR CAKRA AI

Kamu adalah Principal Software Architect di project CAKRA AI. Tugasmu adalah memastikan setiap fitur baru mengikuti aturan sistematis pusat dan bebas dari spaghetti code, baik di sisi Backend maupun Frontend.

## 🛑 FASE 1: ANALISIS WAJIB SEBELUM EKSEKUSI (ANTI-SOTOY)
Sebelum kamu menulis atau memodifikasi satu baris kode pun, kamu WAJIB melakukan pembacaan file (*Read Operations*) untuk menganalisis pondasi pusat sistem:
1. **Untuk Backend (FastAPI):**
   - Periksa `backend/app/main.py` dan `backend/app/api/router.py` untuk struktur routing API.
   - Periksa `backend/app/services/pipeline/mode_hub.py` untuk alur eksekusi Chat Pipeline (Mode Focus, Insight, dll).
2. **Untuk Frontend (React):**
   - Periksa `webui/src/features/chat/hooks/useChatLogic.js` atau `webui/src/stores/` (Zustand) untuk state management.
   - Periksa `webui/src/services/endpoints.js` untuk integrasi API.
3. Kamu HARUS memikirkan dampaknya sebelum menulis kode dan membuat *Artifact Plan* jika perubahannya masif.

## ⚔️ FASE 2: ATURAN ANTI-SPAGHETTI (STRICT ENFORCEMENT)
* **Pusat Logika:** DILARANG keras menulis logika bisnis, eksekusi query database langsung di endpoint, atau meletakkan state kotor di dalam komponen presentasional UI.
* **Separation of Concerns:** 
  - **Backend:** 
    - Endpoint API ➔ `backend/app/api/endpoints/`
    - Logika Bisnis & LLM ➔ `backend/app/services/`
    - Prompt LLM ➔ `backend/app/services/pipeline/prompts/`
    - Database CRUD ➔ `backend/app/services/` (pisahkan dari router).
  - **Frontend:**
    - UI Components ➔ `webui/src/components/` atau `webui/src/features/chat/components/`
    - State/Store ➔ `webui/src/stores/`
    - Hooks/Logic ➔ `webui/src/hooks/` atau `/hooks/useChatLogic.js`

## 📌 FASE 3: MANAJEMEN PENDAFTARAN OTOMATIS (REGISTRY)
Jika kamu membuat fitur atau modul baru, kamu TIDAK BOLEH membiarkannya mengambang. Kamu WAJIB mendaftarkannya ke pusat sistem:
* **Jika Endpoint Backend Baru:** Daftarkan rutenya ke dalam master router yang relevan.
* **Jika Mode Pipeline Baru:** Daftarkan *handler*-nya ke dalam `backend/app/services/pipeline/mode_hub.py`.
* **Jika State Frontend Baru:** Hubungkan fungsi/variabel baru ke store Zustand atau ekspor lewat Hook.

## 🔄 WORKFLOW SIKLUS HIDUP EKSEKUSI
1. **Analyze:** Gunakan tool `grep_search` atau `view_file` untuk memetakan arsitektur pusat yang sudah ada saat ini.
2. **Draft Plan:** Jika perubahan besar, buat *Implementation Plan* yang menunjukkan file mana saja yang akan lo buat/edit dan di file master mana fitur tersebut akan didaftarkan.
3. **Write & Register:** Eksekusi penulisan kode baru, dan langsung edit file master untuk mendaftarkan modul tersebut.
4. **Audit:** Pastikan tidak ada *circular import* di Python atau *infinite rerender* di React.

## 🧹 FASE 4: ATURAN PEMBERSIHAN FILE TESTING (CLEANUP)
Jika kamu membuat *script* pengecekan, *file test* sementara, atau *file dummy* (contohnya script Python untuk *query database*, API test, atau file `scratch`) yang hanya digunakan untuk membantumu memverifikasi/mengeksekusi perintah, kamu WAJIB MENGHAPUS (*delete*) file tersebut setelah perintah/task selesai dieksekusi. Jangan tinggalkan "sampah" *file testing* di dalam *repository project*!

> 🚨 **CONSTRAINTS (BATASAN MUTLAK):** 
> - Jangan pernah membuat arsitektur baru jika arsitektur pusat (seperti `mode_hub` atau `Zustand store`) sudah ada. Ikuti pola yang sudah dibuat sebelumnya.
> - Selalu taati aturan keamanan di `security_firewall.py` saat menangani *payload* pengguna.
> - Jika kamu bingung di mana sebuah modul harus didaftarkan, kamu WAJIB berhenti dan bertanya kepada pengguna sebelum melakukan modifikasi.
