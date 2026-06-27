
# Dokumentasi Komponen Login

Modul ini menyediakan antarmuka dasar untuk proses autentikasi pengguna ke dalam sistem.

## Fitur Utama:
1. **Form Handling**: Menggunakan React Hooks (`useState`) untuk mengelola input username dan password secara real-time.
2. **Validasi Dasar**: Menggunakan atribut HTML5 `required` untuk memastikan field tidak kosong sebelum pengiriman.
3. **Struktur Modular**: Komponen dipisahkan dari styling agar mudah dikustomisasi.

## Struktur Kode:
*   **State Management**: Objek `formData` menyimpan seluruh nilai input dalam satu state terpusat.
*   **Event Handling**: Fungsi `handleChange` menangani perubahan pada semua input secara dinamis berdasarkan atribut `name`.
*   **Submit Action**: Fungsi `handleSubmit` mencegah perilaku default browser dan menyiapkan data untuk dikirim ke API.

> 💡 **Catatan Pengembangan:**
> Pastikan file `Login.css` telah dibuat untuk mengatur tata letak visual agar sesuai dengan standar UI PT Pindad.

## Cara Penggunaan:
1. Import komponen `Login` ke dalam halaman utama atau router yang ditentukan.
2. Hubungkan fungsi `handleSubmit` dengan endpoint API autentikasi yang valid.
3. Sesuaikan desain CSS pada file pendukung untuk menyesuaikan identitas visual perusahaan.
