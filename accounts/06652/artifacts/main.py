
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PT Pindad Internal API")

# Konfigurasi CORS biar frontend React bisa akses API ini tanpa diblokir browser
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skema data untuk request login
class LoginSchema(BaseModel):
    email: str
    password: str

@app.post("/api/login")
async def login(data: LoginSchema):
    # Logika validasi sederhana (Nanti bisa diganti dengan koneksi database asli)
    if data.email == "admin@pindad.co.id" and data.password == "Pindad123":
        return {"message": "Login berhasil", "status": "success"}
    else:
        # Mengirim status 401 jika kredensial salah
        raise HTTPException(status_code=401, detail="Email atau password salah")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
</create_file>

Berikut adalah perbaikan untuk file Login.jsx:

<edit_file filename="Login.jsx">
import React, { useState } from 'react';
import './Login.css';

const LoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok) {
        alert('Login Berhasil! Selamat datang kembali.');
        console.log(data);
      } else {
        setError(data.detail || 'Email atau password salah. Coba lagi.');
      }
    } catch (err) {
      console.error("Error connecting to backend:", err);
      setError('Gagal terhubung ke server. Pastikan backend sudah berjalan.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <form className="login-form" onSubmit={handleSubmit}>
        <h2 className="login-title">Welcome Back</h2>
        <p className="login-subtitle">Silakan masuk ke akun PT Pindad Anda.</p>
        
        {error && <div className="error-message">{error}</div>}

        <div className="input-group">
          <label htmlFor="email">Email</label>
          <input 
            id="email"
            type="email" 
            placeholder="Masukkan email" 
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required 
          />
        </div>
        <div className="input-group">
          <label htmlFor="password">Password</label>
          <input 
            id="password"
            type="password" 
            placeholder="Masukkan password" 
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required 
          />
        </div>
        <button type="submit" className="login-button" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
        <div className="footer-text">
          Lupa password? Hubungi admin internal.
        </div>
      </form>
    </div>
  );
};

export default LoginForm;
</edit_file>

**Update yang gue lakuin:**

1.  **main.py (Backend FastAPI):**
    *   Gue tambahin **CORSMiddleware** supaya frontend React lo bisa "ngobrol" sama backend tanpa diblokir oleh kebijakan keamanan browser.
    *   Gue buat struktur `LoginSchema` pakai Pydantic biar data yang masuk ke API selalu valid.
    *   Gue set up endpoint `POST /api/login` yang bakal ngerespon dengan JSON sesuai standar API modern.

2.  **Login.jsx (Frontend React):**
    *   **Loading State:** Gue tambahin state `loading`. Jadi pas tombol diklik, tombolnya bakal berubah jadi "Logging in..." dan nggak bisa diklik berkali-kali sampai proses selesai.
    *   **Better Error Handling:** Sekarang pesan error diambil langsung dari response JSON backend (misal: `data.detail`), bukan cuma teks statis.
    *   **Refined UI Logic:** Gue balikin class CSS yang tadi sempat hilang biar tampilan tetap konsisten dengan file `.css` yang lo punya.

> 💡 **Tips Tambahan:**
> Untuk jalanin backend-nya, jangan lupa install dulu library yang dibutuhin: `pip install fastapi uvicorn`. Terus jalankan pakai perintah `python main.py`. Pastikan port-nya sama (8000) biar sinkron dengan frontend!