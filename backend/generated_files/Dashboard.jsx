
import React from '1';

const Dashboard = () => {
  const stats = [
    { label: "Total Pengguna", value: "1,240" },
    { label: "Aset Terdaftar", value: "560" },
    { label: "Status Sistem", value: "Aktif" }
  ];

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Selamat Datang Kembali, Qisthi</h1>
        <p>Ringkasan data internal PT Pindad hari ini.</p>
      </header>
      
      <section className="stats-grid">
        {stats.map((item, index) => (
          <div key={index} className="stat-card">
            <h3 className="stat-label">{item.label}</h3>
            <p className="stat-value">{item.value}</p>
          </div>
        ))}
      </section>

      <section className="content-area">
        <h2>Aktivitas Terbaru</h2>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nama Aset</th>
                <th>Lokasi</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>#102</td>
                <td>Unit Kendaraan X</td>
                <td>Workshop A</td>
                <td><span className="badge success">Tersedia</span></td>
              </tr>
              <tr>
                <td>#105</td>
                <td>Modul Sensor Y</td>
                <td>Gudang B</td>
                <td><span className="badge warning">Maintenance</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
</create_file>

File **Dashboard.jsx** sudah jadi! Ini analisis teknis yang perlu lo tahu biar enak pas mau modifikasi:

1. **Ringkasan Singkat**
   Komponen ini adalah *Main Hub* setelah login sukses. Fokusnya adalah menampilkan ringkasan data (KPI) dan tabel aktivitas terbaru dengan struktur yang terorganisir rapi.

2. **Fitur & Komponen Kunci**
   *   **Data Mapping:** Menggunakan array `stats` supaya lo gampang kalau mau nambahin atau ngambil data dari API nantinya.
   *   **Conditional Styling:** Bagian badge (success/warning) sudah disiapkan untuk membedakan status aset secara visual.
   *   **Clean Structure:** Pemisahan antara header, grid statistik, dan konten utama supaya struktur HTML-nya valid dan mudah di-style.

3. **Cara Integrasi dengan Backend**
   Karena lo punya backend FastAPI tadi:
   *   Data di dalam variabel `stats` bisa lo ganti jadi hasil dari *fetch* atau *axios* ke endpoint `/api/dashboard`.
   *   Tabel "Aktivitas Terbaru" bisa di-looping secara dinamis dari data JSON yang dikirim server.

4. **Rekomendasi Styling**
   Gunakan file `Dashboard.css` yang tadi kita buat untuk styling class seperti `.dashboard-container`, `.stat-card`, dan `.data-table`.

> 💡 **Saran Pengembangan:**
> Pas nanti lo integrasiin sama backend FastAPI, pakai `useEffect` di dalam komponen ini buat ambil data awal saat halaman dashboard pertama kali di-load.