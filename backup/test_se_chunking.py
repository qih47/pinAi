#!/usr/bin/env python3
"""
Test script to verify the chunking of Surat Edaran (SE) documents
"""

from embeddings.chunk_se import chunk_se

def test_se_chunking():
    # Sample SE text
    sample_text = """PERATURAN
Nomor : SE/123/PER/2023
Tentang
PENGELOLAAN KEUANGAN PERUSAHAAN

=================== PAGE 1 ===================
DENGAN RAHMAT TUHAN YANG MAHA ESA

MENTERI PERTAHANAN REPUBLIK INDONESIA,

Menimbang : a. bahwa dalam rangka pelaksanaan pengelolaan keuangan perusahaan yang efektif dan efisien, perlu ditetapkan ketentuan mengenai pengelolaan keuangan;
             b. bahwa berdasarkan pertimbangan sebagaimana dimaksud dalam huruf a, perlu menetapkan Peraturan Menteri Pertahanan tentang Pengelolaan Keuangan Perusahaan.

Mengingat : 1. Undang-Undang Nomor 19 Tahun 2003 tentang Keuangan Negara;
            2. Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara;
            3. Peraturan Pemerintah Nomor 41 Tahun 2006 tentang Pengelolaan Utang;

MEMUTUSKAN:

Menetapkan : PERATURAN TENTANG PENGELOLAAN KEUANGAN PERUSAHAAN.

BAB I
KETENTUAN UMUM

Pasal 1
Dalam Peraturan ini yang dimaksud dengan:
1. Perusahaan adalah perusahaan milik negara yang bergerak di bidang pertahanan.
2. Pengelolaan Keuangan adalah keseluruhan proses pengelolaan dana yang meliputi perencanaan, pelaksanaan, pengawasan, dan pertanggungjawaban keuangan.
3. Anggaran adalah rencana keuangan yang disusun berdasarkan pendapatan dan belanja yang diperkirakan dalam satu periode tertentu.

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
(1) Penganggaran sebagaimana dimaksud dalam Pasal 2 huruf a dilakukan berdasarkan prinsip:
   a. tahunan;
   b. terarah;
   c. efisien.
   
(2) Ketentuan lebih lanjut mengenai tata cara penganggaran sebagaimana dimaksud pada ayat (1) diatur dalam Peraturan Direksi.

Pasal 4
Penyusunan Anggaran
(1) Penyusunan anggaran sebagaimana dimaksud dalam Pasal 3 dilakukan oleh unit kerja yang bersangkutan.
(2) Anggaran yang telah disusun sebagaimana dimaksud pada ayat (1) wajib disetujui oleh Direksi.

BAB III
PELAKSANAAN ANGGARAN

Pasal 5
Pelaksanaan Anggaran
(1) Pelaksanaan anggaran dilakukan sesuai dengan ketentuan yang berlaku.
(2) Pelaksanaan anggaran wajib dilakukan secara tertib, taat pada peraturan perundang-undangan, dan efisien.

Pasal 6
Tata Cara Pelaksanaan
Tata cara pelaksanaan anggaran sebagaimana dimaksud dalam Pasal 5 diatur dalam dokumen terpisah.

BAB IV
PERTANGGUNGJAWABAN

Pasal 7
Laporan Pertanggungjawaban
(1) Setiap akhir periode, wajib disusun laporan pertanggungjawaban pelaksanaan anggaran.
(2) Laporan pertanggungjawaban sebagaimana dimaksud pada ayat (1) wajib mencakup realisasi anggaran dan analisisnya.

BAB V
PENGAWASAN

Pasal 8
Ketentuan Pengawasan
Pengawasan dilakukan secara berkala dan/atau sewaktu-waktu terhadap pelaksanaan pengelolaan keuangan.

Pasal 9
Hasil Pengawasan
Hasil pengawasan sebagaimana dimaksud dalam Pasal 8 wajib ditindaklanjuti secara tepat dan akurat.

BAB VI
KETENTUAN PERALIHAN

Pasal 10
Pada saat Peraturan ini mulai berlaku, ketentuan mengenai pengelolaan keuangan yang mengatur hal yang sama dengan ketentuan dalam Peraturan ini tetap berlaku sepanjang belum diubah atau dicabut dengan peraturan yang baru.

BAB VII
KETENTUAN PENUTUP

Pasal 11
Peraturan ini mulai berlaku pada tanggal diundangkan.

Ditetapkan di : J a k a r t a
Pada tanggal : 15 Maret 2023

MENTERI PERTAHANAN
REPUBLIK INDONESIA,

ttd.

PRABOWO SUBIANTO
"""

    print("Testing SE chunking...")
    print("=" * 60)
    
    # Chunk the text
    sections = chunk_se(sample_text)
    print(f"Chunked into {len(sections)} sections")
    
    # Print first few sections as preview
    for i, sec in enumerate(sections[:5]):
        print(f"\nSection {i+1}:")
        print(f"  Type: {sec['type']}")
        print(f"  Title: {sec['title']}")
        print(f"  Level: {sec['level']}")
        print(f"  Order: {sec['order']}")
        print(f"  Parent ID: {sec['parent_id']}")
        print(f"  Content preview: {sec['content'][:100]}...")
    
    # Print last few sections
    print(f"\n... and {len(sections) - 5} more sections")
    
    # Test specific sections
    print(f"\nDetailed analysis:")
    bab_sections = [s for s in sections if 'BAB' in s['title'].upper()]
    pasal_sections = [s for s in sections if 'Pasal' in s['title']]
    
    print(f"  BAB sections: {len(bab_sections)}")
    print(f"  Pasal sections: {len(pasal_sections)}")
    
    # Check parent-child relationships
    child_sections = [s for s in sections if s['parent_id'] is not None]
    print(f"  Child sections (with parent): {len(child_sections)}")
    
    print("\nSE chunking test completed successfully!")

if __name__ == "__main__":
    test_se_chunking()