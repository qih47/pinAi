#!/usr/bin/env python3
"""
Skrip untuk debugging fungsi chunk_ik
"""

import re

def debug_chunk_ik(text: str):
    """
    Debug versi dari fungsi chunk_ik untuk melihat apa yang terjadi di setiap tahap
    """
    print("=== AWAL TEXT ===")
    print(repr(text[:200]))
    print("\n")
    
    text = re.sub(r'={5,}\s*PAGE\s+\d+\s*={5,}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    print("=== SETELAH PENGHAPUSAN PAGE ===")
    print(repr(text[:200]))
    print("\n")
    
    # Pisahkan bagian utama dari LEMBAR PENGESAHAN
    pengesahan_match = re.search(r'(\n\s*LEMBAR\s+PENGESAHAN.*$)', text, re.IGNORECASE | re.DOTALL)
    print("=== PENCOCOKAN PENGESAHAN ===")
    print(f"Pengesahan match: {bool(pengesahan_match)}")
    if pengesahan_match:
        print(f"Match group: {repr(pengesahan_match.group(1)[:100])}")
        
    if pengesahan_match:
        pengesahan_content = pengesahan_match.group(1).strip()
        main_content = text[:pengesahan_match.start()].strip()
        print(f"Main content akhir: {repr(main_content[-100:])}")
    else:
        pengesahan_content = ""
        main_content = text
    
    print(f"\n=== MAIN CONTENT ===")
    print(repr(main_content[:300]))
    print("\n")
    
    # Cek apakah ada pola angka diikuti titik
    numbers = re.findall(r'\n\s*(\d+)\.\s+', main_content)
    print(f"Angka yang ditemukan: {numbers}")
    
    # Ekstrak header (judul, nomor, edisi)
    header = ""
    # Cari pola INSTRUKSI KERJA sampai sebelum angka pertama yang diikuti titik
    header_match = re.search(r'(INSTRUKSI\s+KERJA.*?)((?=\n\s*\d+\.\s+)|(?=\n\s*1.\s+))', main_content, re.IGNORECASE | re.DOTALL)
    print(f"\n=== HEADER MATCH ===")
    print(f"Header match: {bool(header_match)}")
    if header_match:
        print(f"Header group 1: {repr(header_match.group(1)[:200])}")
    
    if header_match:
        header = header_match.group(1).strip()
        main_content = main_content[header_match.end():].strip()
        print(f"Sisa main_content setelah ekstraksi header: {repr(main_content[:200])}")
    
    print(f"\n=== HASIL AKHIR ===")
    print(f"Header: {repr(header[:100])}")
    print(f"Main content setelah header: {repr(main_content[:100])}")
    print(f"Pengesahan content: {repr(pengesahan_content[:100])}")
    
    # Split berdasarkan bagian utama: 1., 2., 3., 4. (angka 1 digit + titik)
    parts = re.split(r'(\n?\s*\d+\.\s+)', main_content)
    print(f"\n=== SPLIT PARTS ===")
    for i, part in enumerate(parts):
        print(f"Part {i}: {repr(part[:100])}")

# Contoh teks dari dokumen Instruksi Kerja
sample_text = """INSTRUKSI KERJA
PENGOPERASIAN MESIN PAINTING PENAMBAT REL
DEP. PRASKA DIV. MANUFAKTUR DAN REKAYASA INDUSTRI

I-03-MI-555
Edisi/Revisi :001/000

1. TUJUAN
a. Sebagai panduan operator dalam mengoperasikan mesin painting penambat rel
b. Menjadi standar kerja untuk semua operator dalam mengoperasikan mesin
c. Mencegah terjadi kerusakan mesin akibat kesalahan prosedur pengoperasian
d. Meningkatkan life time mesin

2. DEFINISI
a. Mesin painting penambat rel adalah mesin yang digunakan untuk proses pengecat penambat rel dengan sistem pencelupan dan pengeringan dengan sistem udara dan heater
b. Penambat rel adalah pengikat rel ke bantalan rel kereta api
c. Temperatur adalah alat yang menunjukkan derajat atau ukuran panas suatu benda
d. Heater adalah alat yang berfungsi untuk memanaskan udara atau air
e. Blower adalah mesin atau alat yang berfungsi untuk menggerakan bau dari cat ke arah tertentu
f. CW (ClockWise) adalah putaran searah jarum jam
g. CCW (Counter ClockWise) adalah putaran berlawanan arah jarum jam

3. URAIAN INSTRUKSI
a. Izin Kerja
Personil yang diijinkan menggunakan mesin painting adalah personil yang memiliki kemampuan pengecat berdasarkan matrix kompetensi terbaru yang telah divalidasi
b. Mesin yang Digunakan
1) Mesin Painting Penambat Rel.
c. Alat Keselamatan Kerja
1) Wearpack,
2) Safety helmet,
3) Safety shoes,
4) Sarung Tangan,
5) Masker.
Alat keselamatan kerja yang diperlukan lainnya dituangkan dalam dokumen IBARD (Identifikasi Bahaya/Aspek dan penilaian Risiko/Dampak) terkait.
d. Langkah Kerja
1) Pemeriksaan Kondisi Mesin
- Periksa apakah masih ada penambat rel yang masih tersangkut di dalam mesin
- Periksa apakah rantai pembawa berada pada jalurnya
- Periksa kondisi gantungan penambat rel dari sisa cat, bersihkan jika sudah menggumpal
- Pastikan area pengecatan bebas dari ceceran cat dan thinner.
2) Gambar Mesin
Keterangan:
1. Saklar mesin,
2. Saklar heater
3. Saklar temperatur,
4.Saklar blower
5. Tombol on,
6.Tombol of,
7.Saklar arah putaran rantai
8.Blower
3) Persiapan
- Siapkan cat simacylic dipping red dan thinner dipping
- Campurkan cat simacylic dipping red dan thinner dipping dengan perbandingan 1:1
- Tuangkan cat yang telah dicampurkan pada bak penampung cat di mesin
4) Menyalakan Mesin
- Naikkan saklar mesin pada panel utama
- Naikkan saklar (1) blower
- Naikkan saklar heater dan lampu
- Naikkan saklar temperatur
- Setting temperature di suhu 230°C - 250°C
5) Pengoperasian
- Nyalakan saklar (2) blower
- Tekan tombol on untuk menyalakan mesin
- Putar switch putaran pembawa penambat rel ke kanan untuk melakukan proses pengecat (putaran CW)
- Jika diperlukan penyesuaian, putaran pembawa penambat rel dapat diputar CCW dengan memutar switch putaran pembawa ke kiri
- Gantungkan penambat rel pada gantungan pembawa penambat rel
- Lakukan berulang dan bertahap hingga penambat rel dalam container habis
6) Mematikan Mesin
- Pastikan semua penambat rel yang sedang di cat telah selesai dan keluar dari mesin
- Posisikan switch putaran pembawa penambat rel ke tengah
- Tekan tombol off untuk mematikan mesin
- Matikan saklar (2) blower
- Naikkan saklar temperatur
- Naikkan saklar heater dan lampu
- Naikkan saklar mesin pada panel utama
e. Yang Harus Diperhatikan
1) Dilarang merokok disekitar area mesin,
2) Pastikan area mesin bebas dari ceceran cat dan thinner,
3) Simpan kembali cat yang masih tersisa di bak penampung cat ke dalam kaleng setiap selesai bekerja,
4) Bersihkan gantungan penambat rel dari sisa cat jika sudah menggumpal.
f. Kondisi Darurat
1) Jika rantai pembawa penambat rel keluar dari jalur, segera matikan mesin dan hubungi fungsi pemeliharaan mesin.
4. REFERENSI DOKUMEN TERKAIT
a. Surat Keputusan Direksi PT. Pindad nomor SKEP/4/P/BD/X/2022 dan SKEP/4a/P/BD/X/2022 tanggal 6 April 2023 tentang Ketentuan Pelaksanaan Produksi Beserta Perubahannya.
b. Surat Keputusan Direksi PT. Pindad nomor: S kep/13/P/BD/V/2023 tentang Kebijakan Mutu & K3LH PT Pindad.
c. Prosedur nomor P-02-P-059 tentang Prosedur Produksi.

LEMBAR PENGESAHAN
NO DISI |NO REVISI |DESKRIPSI                                                 |TANGGAL    |STATUS *) |DISETUJUI OLEH                                        |DISAHKAN OLEH
001     | 000      | Instruksi Kerja Pengoperasian Mesin Painting Penambat Rel| 11-09-2015| Baru     | WS. MANAGER TEMPA & PRODUKSI PRASARANA KA OMA PURNAMA| GM MANUFAKTUR DAN REKAYASA INDUSTRI AMBAR MARDIYOTO, ST"""

debug_chunk_ik(sample_text)