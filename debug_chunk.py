#!/usr/bin/env python3
"""
Debug script untuk memahami mengapa chunk_se hanya menghasilkan 1 chunk
"""

import re
from embeddings.chunk_se import chunk_se

# Contoh dokumen SE seperti yang disebutkan oleh user
se_document = """SURAT EDARAN
Nomor : SE/3/P/BD/XI/2019

Tentang
PAKAIAN SERAGAM PEGAWAI
-----------------------------

1. Berdasarkan :
a. Surat Keputusan Direksi Nomor : Skep/14/P/BD/IV/2018 tanggal 17 April 2018
beserta perubahannya Nomor : Skep/14a/P/BD/IV/2018 tanggal 19 Desember
2018 tentang Pakaian Seragam Pegawai.
b. Surat Edaran Direksi Nomor : SE/1/P/BD/IV/2016 tanggal 28 April 2016 tentang
Ketentuan pemakaian pakaian seragam kerja umum bagi pegawai PT Pindad
(Persero) Tahun 2016
c. Surat Edaran Direksi Nomor : SE/1/P/BD/V/2018 tanggal 8 Mei 2018 tentang
Pakaian Seragam

2. Bersama ini diberitahukan kepada seluruh pegawai PT Pindad (Persero) mengenai
ketentuan pemakaian pakaian seragam kerja umum (PSKU) sebagai berikut :
a. Hari Senin s/d Kamis menggunakan pakaian seragam kerja umum (PSKU)
sesuai ketentuan di dalam Surat Keputusan. Khusus pegawai laki-laki kemeja
kerja wajib dimasukkan ke dalam celana.
b. Untuk pegawai wanita yang berkerudung, ditetapkan sebagai berikut :
- Hari Senin dan Rabu menggunakan kerudung warna Merah.
- Hari Selasa dan Kamis menggunakan kerudung warna Kuning.
- Hari Jum'at menggunakan kerudung bebas menyesuaikan dengan batiknya
c. Hari Jumat setelah melaksanakan olah raga (Pindad Sport) seluruh pegawai
kecuali pegawai satuan pengamanan dan pemadam kebakaran wajib memakai
pakaian Batik.
d. Khusus Upacara Bendera :
- Pegawai laki-laki : menggunakan pakaian seragam kerja umum (PSKU) dan
pakaian peci hitam.
- Pegawai wanita : pakaian seragam kerja umum (PSKU) serta kerudung
merah bagi yang berhijab.
e. Tanggal 2 Oktober menggunakan baju Batik.
f. Hal-hal lain diluar ketentuan butir a. s/d e. akan diatur tersendiri melalui Surat
Edaran.
g. Pelaksanaan ketentuan pemakaian pakaian seragam kerja umum (PSKU)
berlaku terhitung mulai tanggal dikeluarkannya surat edaran ini.

3. Dengan berlakunya surat edaran ini, maka surat edaran Direksi PT Pindad (Persero) Nomor : SE/1/P/BD/IV/2016 tanggal 28 April 2016 tentang Ketentuan pemakaian pakaian seragam kerja umum bagi pegawai PT Pindad (Persero) Tahun 2016 dan Nomor : SE/1/P/BD/IV/2018 tanggal 8 Mei 2018 tentang Pakaian Seragam, dicabut dan dinyatakan tidak berlaku lagi.

4. Demikian surat edaran ini untuk dapat di perhatikan dan dilaksanakan sebagaimana mestinya

Dikeluarkan di : Bandung
Pada tanggal : 15 November 2019

PT PINDAD (PERSERO)
DIREKSI
ABRAHAM MOSE
DIREKTUR UTAMA"""

print("Debug: Memeriksa apakah pola regex untuk butir bekerja...")
lines = se_document.splitlines()
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped:
        # Cek apakah baris ini cocok dengan pola butir
        if re.match(r'^\s*\d+\.\\s*$', stripped) or re.match(r'^\s*\d+\.\\s+\S', stripped):
            print(f"Line {i+1}: '{stripped}' -> cocok dengan pola butir")
        elif re.match(r'^\s*\d+\\.', stripped):
            print(f"Line {i+1}: '{stripped}' -> cocok dengan pola dasar \\d+\\.")

print("\nDebug: Menjalankan fungsi chunk_se dengan tambahan logging...")
chunks = chunk_se(se_document)
print(f"Jumlah chunks yang dihasilkan: {len(chunks)}")

print("\nDetail chunks:")
for i, chunk in enumerate(chunks):
    print(f"\nChunk {i+1}:")
    print(f"  Type: {chunk['type']}")
    print(f"  Title: {chunk['title']}")
    print(f"  Level: {chunk['level']}")
    print(f"  Order: {chunk['order']}")
    print(f"  Content preview (first 100 chars): {repr(chunk['content'][:100])}")
    print(f"  Content length: {len(chunk['content'])}")