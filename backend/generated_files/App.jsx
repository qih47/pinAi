
import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';

const App = () => {
  return (
    <Router>
      <Routes>
        {/* Route untuk halaman login */}
        <Route path="/login" element={<Login />} />
        
        {/* Route utama atau dashboard setelah login sukses */}
        <Route path="/" element={<Dashboard />} />
        
        {/* Redirect otomatis dari / ke /dashboard jika diperlukan */}
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </Router>
  );
};

export default App;
</create_file>

Halo Qisthi! File **App.jsx** sudah siap. Ini adalah "jantung" navigasi aplikasi lo yang bakal ngatur perpindahan antar halaman secara mulus.

Berikut detail teknisnya buat lo:

### 1. Ringkasan Singkat
File ini menggunakan `react-router-dom` untuk mendefinisikan jalur (routes) di aplikasi web. Fungsinya adalah memastikan user diarahkan ke komponen yang benar (Login atau Dashboard) saat mereka mengakses URL tertentu.

### 2. Cara Menggunakan
Pastikan lo sudah install library router sebelum jalanin file ini:
1. Jalankan perintah: `npm install react-router-dom` atau `yarn add react-router-dom`.
2. Pastikan path import (misal: `./components/Login`) sesuai dengan struktur folder project yang lo buat.

### 3. Fitur & Komponen Kunci
*   **BrowserRouter:** Membungkus seluruh aplikasi agar URL di browser bisa dibaca oleh React.
*   **Routes & Route:** Struktur untuk memetakan URL (seperti `/login`) ke komponen UI tertentu.
*   **Scalable Structure:** Struktur ini gampang banget ditambahin kalau nanti ada halaman baru (misal: `/profile` atau `/settings`).
*   **Default Landing:** Saya sudah set agar `/` dan `/dashboard` mengarah ke Dashboard sebagai halaman utama setelah login.

### 4. Dependensi
*   **React Router DOM:** Library standar industri untuk routing di aplikasi React.
*   **React Core:** Sebagai basis komponen fungsional.

> 💡 **Saran buat Qisthi:**
> Kalau nanti fitur login sudah jadi, lo bisa ganti `<Dashboard />` dengan *Protected Route*. Jadi, kalau user belum login tapi nekat buka `/`, mereka bakal otomatis dilempar balik ke halaman `/login`.