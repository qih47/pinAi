
import React, { useState } from 'react';
import { Link } from 'react-router-dom';

const Sidebar = () => {
  const [isOpen, setIsOpen] = useState(true);

  const menuItems = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'Inventory', path: '/inventory' },
    { name: 'Maintenance', path: '/maintenance' },
    { name: 'Reports', path: '/reports' },
    { name: 'Settings', path: '/settings' },
  ];

  return (
    <div className="sidebar-container">
      <div className="sidebar-header">
        <h2>PT Pindad System</h2>
      </div>
      <nav className="sidebar-nav">
        <ul>
          {menuItems.map((item, index) => (
            <li key={index}>
              <Link to={item.path} className="nav-link">
                {item.name}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
};

export default Sidebar;
</create_file>

Halo Qisthi! File **Sidebar.jsx** sudah jadi. Ini bakal jadi menu navigasi utama yang ada di sisi kiri layar buat memudahkan user pindah antar modul.

Berikut adalah detail teknisnya:

### 1. Ringkasan Singkat
Komponen ini berfungsi sebagai navigasi vertikal (sidebar). Tujuannya adalah memberikan akses cepat ke berbagai fitur utama aplikasi seperti Inventory, Maintenance, dan Reporting dalam satu tampilan yang konsisten.

### 2. Cara Menggunakan
Lo bisa pasang komponen ini di layout utama atau langsung di dalam halaman dashboard:
*   Panggil dengan cara: `import Sidebar from './components/Sidebar';`
*   Pastikan kamu sudah menginstal `react-router-dom` agar tag `<Link>` berfungsi untuk navigasi tanpa reload halaman.

### 3. Fitur & Komponen Kunci
*   **Mapping Array:** Gue pakai array `menuItems` supaya kalau nanti ada penambahan fitur baru (misal: "User Management"), lo tinggal nambahin objek di dalam array itu aja, nggak perlu ngedit struktur HTML-nya.
*   **React Router Link:** Menggunakan `<Link>` bukan `<a>` agar navigasi antar halaman terasa instan (Single Page Application).
*   **Clean Structure:** Struktur kode yang bersih memudahkan tim pengembang lain untuk nambahin icon atau styling khusus di setiap item menu.

### 4. Dependensi
*   **react-router-dom:** Digunakan untuk menangani routing internal.
*   **CSS Custom Property (Saran):** Disarankan menggunakan variabel warna dari file CSS utama supaya warna sidebar konsisten dengan branding PT Pindad.

> 💡 **Saran dari gue:**
> Karena kita mau bikin ini profesional, nanti lo bisa tambahin library icon seperti `react-icons` di dalam loop `menuItems`. Jadi setiap menu (Dashboard, Inventory, dll) bakal punya ikon yang keren di samping teksnya!