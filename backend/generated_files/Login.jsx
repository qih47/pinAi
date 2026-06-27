
import React, { useState } from 'react';
import './Login.css';

const Login = () => {
    const [formData, setFormData] = useState({
        email: '',
        password: ''
    });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData({ ...formData, [name]: value });
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        // Integrasi API ke backend PT Pindad bisa dilakukan di sini
        console.log("Data Login:", formData);
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <h2 className="login-title">Portal Internal</h2>
                <p className="login-subtitle">Silakan masuk untuk mengakses sistem</p>
                
                <form className="login-form" onSubmit={handleSubmit}>
                    <div className="input-group">
                        <label htmlFor="email">Email Kantor</label>
                        <input 
                            type="email" 
                            id="email" 
                            name="email" 
                            placeholder="nama.user@pindad.co.id" 
                            value={formData.email}
                            onChange={handleChange}
                            required 
                        />
                    </div>

                    <div className="input-group">
                        <label htmlFor="password">Kata Sandi</label>
                        <input 
                            type="password" 
                            id="password" 
                            name="password" 
                            placeholder="Masukkan kata sandi" 
                            value={formData.password}
                            onChange={handleChange}
                            required 
                        />
                    </div>

                    <button type="submit" className="login-button">
                        Masuk Sekarang
                    </button>
                </form>
                
                <div className="footer-text">
                    Lupa sandi? Hubungi Administrator Sistem.
                </div>
            </div>
        </div>
    );
};

export default Login;
</create_file>
<create_file filename="Login.css">
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    background-color: #f4f7f6;
    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

.login-card {
    background: white;
    padding: 40px;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
    width: 100%;
    max-width: 400px;
    text-align: center;
}

.login-title {
    margin-bottom: 8px;
    color: #333;
    font-size: 24px;
    font-weight: bold;
}

.login-subtitle {
    color: #777;
    margin-bottom: 30px;
    font-size: 14px;
}

.login-form {
    text-align: left;
}

.input-group {
    margin-bottom: 20px;
}

.input-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: bold;
    color: #555;
    font-size: 14px;
}

.input-group input {
    width: 100%;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    box-sizing: border-box;
    font-size: 14px;
}

.login-button {
    width: 100%;
    padding: 12px;
    background-color: #0056b3;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
    transition: background 0.3s ease;
}

.login-button:hover {
    background-color: #004494;
}

.footer-text {
    margin-top: 20px;
    font-size: 12px;
    color: #999;
}
</create_file>

Oke Qisthi, file sudah beres! Berikut adalah poin pentingnya buat lo:

*   **Sinkronisasi Class:** Gue udah pastiin `className` di file `.jsx` sama persis dengan selector di file `.css`.
*   **Struktur Clean:** Kode JSX fokus ke struktur data, sedangkan CSS fokus ke tampilan. Jadi kalau mau ganti warna tombol atau ukuran font, lo tinggal edit file `.css`-nya aja tanpa ngerusak logika komponen.
*   **Responsif:** Styling yang gue kasih sudah mendukung tampilan mobile karena pakai `max-width` dan `box-sizing`.

> 💡 **Saran buat Qisthi:**
> Pastikan kedua file ini berada di dalam folder yang sama supaya `import './Login.css';` bisa jalan dengan lancar. Kabari gue kalau ada bagian yang mau lo modif lagi!