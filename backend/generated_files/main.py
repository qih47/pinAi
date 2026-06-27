
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

app = FastAPI(title="PT Pindad Internal API")

# Model data untuk validasi input dari frontend
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.get("/")
def read_root():
    return {"message": "Selamat datang di API Gateway PT Pindad"}

@app.post("/api/login")
async def login(data: LoginRequest):
    # Di sini nanti lo bisa tambahin logika pengecekan database 
    # atau integrasi dengan sistem autentikasi internal.
    
    if data.email == "admin@pindad.co.id" and data.password == "PindadPass123":
        return {
            "status": "success",
            "message": "Login berhasil",
            "user_info": {"username": "admin", "role": "staff"}
        }
    else:
        raise HTTPException(status_code=401, detail="Email atau password salah")

@app.get("/api/status")
async def get_status():
    return {"system_status": "online", "server": "Pindad-Node-01"}
</create_file>

Berikut adalah analisis teknis untuk file **main.py** di atas:

1. **Ringkasan Singkat**
   * File ini adalah *entry point* untuk backend menggunakan framework FastAPI.
   * Dirancang khusus untuk menangani request autentikasi dari frontend yang sudah kita buat sebelumnya.

2. **Fitur & Keunggulan**
   * **Pydantic Integration**: Menggunakan `BaseModel` untuk validasi otomatis (misal: memastikan format email benar sebelum masuk ke logika bisnis).
   * **Asynchronous Support**: Menggunakan `async def` agar server bisa menangani banyak request sekaligus secara efisien.
   * **Auto Documentation**: FastAPI bakal otomatis bikin dokumentasi interaktif di `/docs` (Swagger UI), jadi lo gampang buat ngetes API tanpa perlu aplikasi luar.

3. **Cara Menjalankan**
   * Install library dulu: `pip install fastapi uvicorn`
   * Jalankan servernya: `uvicorn main:app --reload`
   * Akses dokumentasi di browser: `http://127.0.0.1:8000/docs`

4. **Koneksi ke Frontend**
   * Di file `Login.jsx`, pada bagian `handleSubmit`, lo tinggal ganti `console.log` dengan fetch request ke endpoint `/api/login`.

> 💡 **Catatan Analisis:**
> Gue pakai `EmailStr` dari library Pydantic. Kalau belum ada, lo bisa install lewat `pip install "pydantic[email]"` atau ganti jadi `str` biasa kalau mau simpel di awal.