#!/usr/bin/env python3
"""
Simple test for SE chunking
"""

from embeddings.chunk_se import chunk_se

def test_simple_se():
    # Simple SE text
    simple_text = """PERATURAN
Nomor : SE/123/PER/2023
Tentang
PENGELOLAAN KEUANGAN PERUSAHAAN

DENGAN RAHMAT TUHAN YANG MAHA ESA

MENTERI PERTAHANAN REPUBLIK INDONESIA,

Menimbang : a. bahwa dalam rangka pelaksanaan pengelolaan keuangan perusahaan;
             b. bahwa berdasarkan pertimbangan sebagaimana dimaksud dalam huruf a.

Mengingat : 1. Undang-Undang Nomor 19 Tahun 2003;
            2. Undang-Undang Nomor 1 Tahun 2004;
            3. Peraturan Pemerintah Nomor 41 Tahun 2006;

MEMUTUSKAN:

Menetapkan : PERATURAN TENTANG PENGELOLAAN KEUANGAN PERUSAHAAN.

BAB I
KETENTUAN UMUM

Pasal 1
Dalam Peraturan ini yang dimaksud dengan:
1. Perusahaan adalah perusahaan milik negara.
2. Pengelolaan Keuangan adalah keseluruhan proses.
3. Anggaran adalah rencana keuangan.

Pasal 2
Ruang Lingkup Pengelolaan Keuangan
Ruang lingkup pengelolaan keuangan sebagaimana dimaksud dalam Pasal 1 meliputi:
a. penganggaran;
b. pelaksanaan anggaran;
c. pertanggungjawaban;
d. pengawasan.

BAB II
PENGANGGARAN

Pasal 3
Prinsip Penganggaran
(1) Penganggaran dilakukan berdasarkan prinsip:
   a. tahunan;
   b. terarah;
   c. efisien.
   
(2) Ketentuan lebih lanjut mengenai tata cara penganggaran.

Ditetapkan di : Jakarta
Pada tanggal : 15 Maret 2023

MENTERI PERTAHANAN
REPUBLIK INDONESIA,

ttd.

PRABOWO SUBIANTO
"""

    print("Testing simple SE chunking...")
    print("=" * 60)
    
    # Chunk the text
    sections = chunk_se(simple_text)
    print(f"Chunked into {len(sections)} sections")
    
    # Print all sections
    for i, sec in enumerate(sections):
        print(f"\nSection {i+1}:")
        print(f"  Type: {sec['type']}")
        print(f"  Title: {sec['title']}")
        print(f"  Level: {sec['level']}")
        print(f"  Order: {sec['order']}")
        print(f"  Parent ID: {sec['parent_id']}")
        print(f"  Content preview: {sec['content'][:100]}...")

if __name__ == "__main__":
    test_simple_se()