#!/usr/bin/env python3
"""
Test script to verify the chunk_skep function works correctly with the sample SKEP text
"""

from embeddings.chunk_skep import chunk_skep

# Sample SKEP text from the user
sample_text = """SURAT KEPUTUSAN
Nomor : Skep/32/P/BD/I/2018
Tentang
KETENTUAN REKRUTMEN DAN SELEKSI CALON PEGAWAI
------------------------------
DIREKSI PT PINDAD (PERSERO)

Menimbang : Bahwa dalam rangka memenuhi kebutuhan Pegawai yang sesuai dengan tujuan organisasi, perlu ditetapkan ketentuan mengenai Rekrutmen dan Seleksi Calon Pegawai.

Mengingat : 
1. Undang-Undang No. 13 tahun 2003 tanggal 25 Maret 2003 tentang Ketenagakerjaan.
2. Akta Notaris Nining Puspitaningtyas, S.H., M.H. no 273 tanggal 24 Februari 2017 mengenai Akta Perubahan Anggaran Dasar PT Pindad (Persero).
3. Perjanjian Kerja Bersama Antara PT Pindad (Persero) dengan Serikat Pekerja Tahun 2017-2019.
4. Surat Keputusan Direksi PT. Pindad (Persero) nomor: Skep/2/P/BD/II/2017 tanggal 10 Februari 2016 tentang Organisasi dan Tata Kerja PT. Pindad (Persero).

MEMUTUSKAN

Menetapkan : Keputusan Direksi PT Pindad (Persero) tentang Ketentuan Rekrutmen dan Seleksi Calon Pegawai PT Pindad (Persero) sebagai berikut:

BAB I
PENDAHULUAN
Pasal 1
Pengertian

Dalam ketentuan ini yang dimaksud dengan:
1. Rekrutmen adalah kegiatan mencari atau mengundang calon-calon Pelamar untuk mengikuti seleksi di waktu yang ditentukan Perusahaan.
2. Seleksi adalah kegiatan memilih individu-individu yang mempunyai kemampuan sesuai dengan rencana dan kebutuhan Perusahaan melalui cara atau tahapan yang ditetapkan Perusahaan.
3. Pelamar adalah seseorang yang mengajukan lamaran pekerjaan kepada Perusahaan.
4. Fresh Graduate adalah pemenuhan dari lulusan baru atau yang telah memiliki pengalaman kerja kurang dari 3 tahun di satu tempat.
5. Berpengalaman adalah pemenuhan Pegawai yang telah memiliki pengalaman kerja minimal 5 tahun pada bidang keahlian/keterampilan yang dibutuhkan Perusahaan untuk melakukan suatu pekerjaan tertentu.
6. Seleksi administrasi adalah seleksi kelengkapan dan keabsahan surat-surat lamaran kerja sesuai dengan persyaratan yang sudah ditentukan.
7. Tes Potensi Akademik adalah tes tertulis yang bersifat teori/ ilmiah untuk mengukur kemampuan verbal, numeris dan figural.
8. Tes Psikologi adalah seleksi untuk mengetahui potensi dan kondisi psikologis Pelamar.
9. Penelitian Khusus adalah proses seleksi untuk mewujudkan personil yang memiliki kesetiaan dan ketaatan terhadap Pancasila, UUD Negara Republik Indonesia Tahun 1945, Negara, Pemerintah dan Perusahaan.
10. Tes Kesehatan adalah seleksi untuk mengetahui keadaan fisik dan kondisi kesehatan Pelamar.
11. Wawancara adalah seleksi tanya jawab mengenai kompetensi dan pengalaman Pelamar sesuai kebutuhan Perusahaan.
12. Calon Pegawai (Capeg) adalah status bagi Pelamar yang lulus seluruh tahapan seleksi.
13. Perusahaan adalah PT Pindad (Persero).

Pasal 2
Maksud & Tujuan
1. Ketentuan ini disusun dengan maksud sebagai pedoman bagi Perusahaan dalam pelaksanaan rekrutmen dan seleksi Calon Pegawai.
2. Ketentuan ini disusun dengan tujuan untuk mendapatkan Calon Pegawai yang memenuhi persyaratan yang ditetapkan Perusahaan sehingga mampu melaksanakan tugas pekerjaan dan memberi kontribusi sesuai yang diharapkan.

Pasal 3
Ruang Lingkup
Ruang lingkup Ketentuan Rekrutmen dan Seleksi Calon Pegawai meliputi :
1. Dasar rekrutmen,
2. Jenis rekrutmen,
3. Persyaratan administrasi pelamar,
4. Proses rekrutmen dan seleksi.

BAB II
REKRUTMEN
Pasal 4
Dasar Rekrutmen
1. Rekrutmen dilakukan berdasarkan rencana kebutuhan pegawai yang telah ditetapkan dalam Rencana Kerja Anggaran Perusahaan (RKAP).
2. Ketentuan mengenai perencanaan kebutuhan pegawai ditetapkan dalam surat keputusan tersendiri.

Pasal 5
Jenis Rekrutmen

1. Jenis rekrutmen dibedakan menjadi 2 yaitu:
a. Fresh Graduate
b. Berpengalaman

2. Khusus untuk rekrutmen Berpengalaman dibuktikan dengan pertimbangan tertulis meliputi:
a. Kompetensi yang dibutuhkan tidak dimiliki Perusahaan baik jenis maupun tingkat kompetensinya.
b. Pengalaman dalam menangani bidang tertentu.
c. Hanya untuk menduduki posisi paling tinggi setara strata 3, kecuali untuk menduduki posisi di atas strata 3 dengan kebutuhan spesifikasi sangat khusus, ditetapkan oleh Direksi.

Pasal 6
Persyaratan Administrasi

1. Persyaratan umum Pelamar adalah sebagai berikut:
a. Warga Negara Indonesia (WNI)
b. Sehat jasmani dan rohani
c. Mempunyai kualifikasi pendidikan, kecakapan, keahlian dan keterampilan yang diperlukan
d. Tidak pernah diberhentikan secara tidak hormat oleh Perusahaan sebelumnya bagi yang pernah bekerja.
e. Tidak pernah terlibat tindak pidana.

2. Untuk Pelamar fresh graduate memenuhi persyaratan sebagai berikut:

NO | PENDIDIKAN | USIA MAKSIMAL | RATA-RATA MINIMAL NILAI IJAZAH | IPK MINIMAL / AKREDITASI | KEMAMPUAN BERBAHASA INGGRIS
1  | SMA / SMK  | 21 tahun      | 7,5                           | -                         | -
2  | D1         | 22 tahun      | -                             | 2,80 (A) / 3,00 (B)       | -
3  | D2         | 23 tahun      | -                             | 2,80 (A) / 3,00 (B)       | -
4  | D3         | 24 tahun      | -                             | 2,80 (A) / 3,00 (B)       | TOEFL: 475
5  | D4 / S1    | 25 tahun      | -                             | 2,80 (A) / 3,00 (B)       | TOEFL: 500
6  | S2         | 28 tahun      | -                             | 3,25                      | TOEFL: 500
7  | S3         | 33 tahun      | -                             | 3,25                      | TOEFL: 500

3. Untuk Pelamar berpengalaman:
a. Usia maksimal 40 tahun.
b. Nilai TOEFL minimal 500.
c. Memiliki pengalaman kerja minimal 5 (lima) tahun pada Bidang / Jabatan yang sama yang dibuktikan dengan Surat Keterangan Kerja dari Perusahaan sebelumnya.
d. Memiliki kompetensi yang dibutuhkan Perusahaan dan dibuktikan dengan sertifikat untuk fungsi-fungsi tertentu yang dipersyaratkan.

Pasal 7
Proses Rekrutmen

1. Berdasarkan persetujuan dari Direksi, Divisi yang memb.idangi SDM melakkan proses rekrutmen melalui, antara lain:
a. Website resmi Perusahaan atau media lainnya,
b. Koordinasi secara langsung dengan pihak Advertensi / Iklan, Lembaga Ketenagakerjaan, Instansi/Lembaga terkait, Lembaga pendidikan, Konsultan atau Badan Penyedia Tenaga Kerja,
c. Bursa kerja (job fair).

2. Pelamar yang akan mengikuti seleksi, diwajibkan melengkapi data sebagai berikut:
a. Riwayat Hidup (RH);
b. Ijazah asli atau fotocopy ijazah yang telah dilegalisir;
c. Transkrip asli atau foto copy transkrip nilai yang telah dilegalisir;
d. Sertifikat kemampuan berbahasa Inggris yang masih berlaku;
e. Kartu Tanda Penduduk (KTP);
f. Surat Keterangan Kerja (apabila ada);
g. Sertifikat Keahlian yang masih berlaku dari Badan Sertifikasi (apabila ada);
h. Surat Keterangan Catatan Kepolisian (SKCK) dari Polres;
i. Surat Keterangan Bebas Narkoba;
j. Surat Pernyataan sebagaimana lampiran "A".

BAB III
SELEKSI

Pasal 8
Tahapan Seleksi

1. Seleksi Administrasi, sebagaimana persyaratan Pasal 6.
2. Tes Potensi Akademik (TPA)
a. Komposisi Tes Potensi Akademik (TPA) terdiri dari soal Verbal, soal Numerik dan soal Figural.
b. Nilai minimal kelulusan TPA adalah 50% dari total skor.
3. Tes Psikologi
a. Aspek-aspek yang diukur dalam Tes Psikologi meliputi aspek kecerdasan, kepribadian, sikap kerja dan interpersonal.
b. Hasil Tes Psikologi terdiri dari 3 kriteria yaitu Disarankan, Dipertimbangkan, atau Tidak Disarankan.
c. Pelamar yang dinyatakan lulus Tes Psikologi berada pada kriteria "Disarankan"
4. Tes Kesehatan
a. Hasil Tes Kesehatan terdiri dari 3 kriteria yaitu Baik, Cukup dan Kurang,
b. Pelamar yang dinyatakan lulus Tes Kesehatan berada pada kriteria "Baik"
5. Penelitian Khusus
a. Aspek-aspek yang diukur dalam Penelitian Khusus meliputi aspek mental, keterpengaruh, kesetiaan terhadap Pancasila, Undang-Undang Dasar 1945, Negara dan Pemerintah (PUNP), serta loyalitas kepada Perusahaan,
b. Hasil Penelitian Khusus terdiri dari 2 kriteria yaitu Memenuhi Persyaratan dan Tidak Memenuhi Persyaratan,
c. Pelamar yang dinyatakan lulus Penelitian Khusus berada pada kriteria "Memenuhi Persyaratan",

6. Wawancara
a. Aspek yang diukur dalam wawancara meliputi :
1) Soft competency yang berlaku di Perusahaan,
2) Wawasan dan keahlian terkait dengan posisi yang dilamar,
3) Motivasi dan sikap kerja
4) Pengalaman kerja (apabila ada),
5) Penggetahuan mengenai bidang kerja
b. Hasil Wawancara terdiri dari 3 kriteria yaitu Disarankan, Dapat Dipertimbangkan dan Tidak Disarankan
c. Pelamar yang dinyatakan lulus Wawancara berada pada kriteria "Disarankan"

Pasal 9
Pelaksanaan Seleksi
1. Pelaksanaan seleksi dapat dilakukan oleh internal perusahaan atau bekerjasama dengan
lembaga independen dan/atau tenaga profesional, yang ditetapkan dalam Sidang Direksi.
2. Penanggung jawab seluruh tahapan seleksi adalah Kepala Divisi yang membidangi SDM.

Pasal 10
Hasil Seleksi
1. Hasil akhir kelulusan seleksi dan dituangkan dalam Berita Acara yang ditandatangani Kepala
Divisi yang Membidangi SDM dan hasilnya dilaporkan kepada Direksi.
2. Pelamar yang Lulus seluruh tahapan seleksi akan ditetapkan menjadi calon pegawai yang
diatur dalam surat keputusan Direksi tersendiri.

BAB IV
PENUTUP
Pasal 11
Penutup
1. Dengan ditetapkannya surat keputusan Direksi ini, maka atas surat keputusan Direksi PT.
Pindad (Persero) nomor: Skeep/17/P/BD/VII/2010 tanggal 26 Juli 2010 beserta perubahannya
nomor:

2. Surat Keputusan ini mulai berlaku terhitung sejak tanggal ditetapkan, dengan ketentuan apabila dikemudian hari terdapat kekeliruan akan diadakan perbaikan sebagaimana mestinya.
Ditetapkan di : B a n d u n g
Pada tanggal : 31 Januari 2018 .
PT PINDAD (PERSERO) DIREKSI
ABRAHAM MOSE DIREKTUR UTAMA

LAMPIRAN "A" SURAT KEPUTUSAN DIREKSI PT PINDAD (PERSERO)  

NOMOR : Skep/ 32 /P/BD/ I /2018  
TANGGAL : 31 Januari 2018  
SURAT PERNYATAAN  
Saya yang bertanda tangan di bawah ini :  
Nama Lengkap : ..................................................................................  
Nomor KTP : ................................................................................

Tempat, tanggal lahir : .......................................................................  
Alamat : ....................................................................................  

Dengan ini menyatakan dengan sesungguhnya, bahwa:  
1. Saya tidak pernah dihukum berdasarkan keputusan pengadilan;  
2. Saya tidak pernah diberhentikan dengan tidak hormat dari perusahaan lain;  
3. Seluruh keterangan dari pernyataan, data dan informasi yang Saya berikan kepada PT PINDAD (PERSERO) adalah benar. Apabila dikemudian hari pernyataan, data dan informasi yang Saya sampaikan terbukti tidak benar, Saya bersedia dijatuhkan sanksi sesuai dengan ketentuan yang berlaku dan/atau bersedia diberhentikan sebagai Calon Pegawai PT PINDAD (PERSERO) maupun dikemudian hari setelah menjadi Pegawai PT PINDAD (PERSERO).  

Demikian pernyataan ini Saya buat dengan sebenarnya, dalam keadaan sadar tanpa adanya paksaan dari pihak manapun.  

Materai 6000  
(..........................)"""

def main():
    print("Testing chunk_skep function with sample SKEP text...")
    print("=" * 60)
    
    sections = chunk_skep(sample_text)
    
    print(f"Total sections found: {len(sections)}")
    print("\nDetailed breakdown:")
    print("-" * 40)
    
    bab_count = 0
    pasal_count = 0
    
    for i, section in enumerate(sections):
        section_type = section["type"]
        title = section["title"]
        content_preview = section["content"][:100] + "..." if len(section["content"]) > 100 else section["content"]
        parent_title = section.get("parent_title", "None")
        
        if section_type == "bab":
            bab_count += 1
        elif section_type == "pasal":
            pasal_count += 1
        
        print(f"{i+1}. Type: {section_type}")
        print(f"   Title: {title}")
        print(f"   Parent: {parent_title}")
        print(f"   Content preview: {content_preview}")
        print()
    
    print(f"Summary: {bab_count} BAB sections, {pasal_count} Pasal sections, {len(sections)} total sections")
    
    # Check if all Pasal have proper parent references
    pasal_without_parents = [s for s in sections if s["type"] == "pasal" and not s.get("parent_title")]
    print(f"Pasal sections without parent: {len(pasal_without_parents)}")
    
    # Check if all BAB have content
    empty_bab = [s for s in sections if s["type"] == "bab" and not s["content"].strip()]
    print(f"BAB sections without content: {len(empty_bab)}")

if __name__ == "__main__":
    main()