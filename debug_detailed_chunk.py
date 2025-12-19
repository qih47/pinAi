#!/usr/bin/env python3
"""
Debug script yang lebih mendetail untuk memahami alur eksekusi chunk_se
"""

import re
from typing import List, Dict, Any

def debug_chunk_se(text: str) -> List[Dict[str, Any]]:
    """
    Versi debug dari chunk_se dengan logging
    """
    print("=== MEMULAI CHUNKING ===")
    
    # Normalisasi
    text = re.sub(r'={5,}\s*PAGE\s+\d+\s*={5,}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Hapus bagian Tembusan
    tembusan_match = re.search(r'\n\s*Tembusan\s*:', text, re.IGNORECASE)
    if tembusan_match:
        text = text[:tembusan_match.start()]

    # Ekstrak blok tanda tangan
    signature_block = ""
    sig_pattern = r'(\n\s*Dikeluarkan\s+di\s*:\s*[^\n]+\s*\n\s*Pada\s+tanggal\s*:\s*[^\n]+(?:\s*\n[^\n]*){0,4})'
    sig_match = re.search(sig_pattern, text, re.IGNORECASE)
    if sig_match:
        signature_block = sig_match.group(1).strip()
        text = text[:sig_match.start()]
    
    if signature_block:
        print(f"Signature block ditemukan: {signature_block[:50]}...")

    lines = text.splitlines()
    sections = []
    current_section = None
    current_sub_items = []
    
    # Counter untuk urutan
    item_counter = 1
    
    # Status untuk melacak apakah kita sedang dalam konteks pasal (baru mulai dari BAB ke atas)
    in_structured_section = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        print(f"Line {i+1}: '{stripped}'")

        # Deteksi BAB: BAB I, BAB II, dll.
        if re.match(r'^BAB\s+[IVX]+', stripped, re.IGNORECASE):
            print(f"  -> Cocok BAB: {stripped}")
            # Simpan section sebelumnya jika ada
            if current_section:
                # Gabungkan sub-items ke main section
                full_content = current_section['content']
                if current_sub_items:
                    full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
                
                current_section['content'] = full_content
                sections.append(current_section)
                print(f"  -> Menyimpan section sebelumnya: {current_section['title']}")
            
            current_section = {
                'type': 'bab',
                'title': stripped,
                'content': line,
                'level': 0,
                'order': item_counter,
                'parent_id': None,
                'metadata': {'section_type': 'bab'}
            }
            current_sub_items = []
            item_counter += 1
            in_structured_section = True  # Mulai dari sini kita anggap dalam konteks struktur hukum
            
        # Deteksi Pasal: Pasal 1, Pasal 2, dll.
        elif re.match(r'^Pasal\s+\d+', stripped, re.IGNORECASE):
            print(f"  -> Cocok Pasal: {stripped}")
            # Simpan section sebelumnya jika ada
            if current_section:
                # Gabungkan sub-items ke main section
                full_content = current_section['content']
                if current_sub_items:
                    full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
                
                current_section['content'] = full_content
                sections.append(current_section)
                print(f"  -> Menyimpan section sebelumnya: {current_section['title']}")
            
            current_section = {
                'type': 'pasal',
                'title': stripped,
                'content': line,
                'level': 1,
                'order': item_counter,
                'parent_id': None,  # Akan diisi di database berdasarkan BAB jika ada
                'metadata': {'section_type': 'pasal', 'pasal_number': re.search(r'\d+', stripped).group()}
            }
            current_sub_items = []
            item_counter += 1
            in_structured_section = True  # Tetap dalam konteks struktur hukum
            
        # Deteksi butir utama: "1.", "2.", "10.", dll. (juga sebagai indikator awal struktur hukum)
        elif (re.match(r'^\s*\d+\.\\s*$', stripped) or re.match(r'^\s*\d+\.\\s+\S', stripped)):
            print(f"  -> Cocok butir utama: {stripped}")
            # Set status bahwa kita sekarang dalam konteks struktur hukum
            in_structured_section = True
            # Simpan section sebelumnya jika ada
            if current_section:
                # Gabungkan sub-items ke main section
                full_content = current_section['content']
                if current_sub_items:
                    full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
                
                current_section['content'] = full_content
                sections.append(current_section)
                print(f"  -> Menyimpan section sebelumnya: {current_section['title']}")
            
            # Ekstrak nomor dan judul
            parts = re.split(r'\.\\s*', stripped, 1)
            number = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else ""
            
            current_section = {
                'type': 'butir',
                'title': f"{number}. {title}".strip(),
                'content': stripped,
                'level': 2,
                'order': item_counter,
                'parent_id': None,  # Akan diisi di database berdasarkan pasal/bab jika ada
                'metadata': {'item_number': number}
            }
            current_sub_items = []
            item_counter += 1
            print(f"  -> Membuat section baru: {current_section['title']}")
            
        elif current_section:  # Jika sedang dalam section
            # Deteksi sub-item (a., b., c., i., ii., dst.)
            if re.match(r'^\s*[a-zA-Z]\.\s', line) or \
               re.match(r'^\s*[ivx]+\)\s', line) or \
               re.match(r'^\s*-\s', line) or \
               re.match(r'^\s*•\s', line):
                
                print(f"  -> Cocok sub-item: {line.strip()}")
                # Simpan sub-item
                sub_item = {
                    'type': 'sub_item',
                    'title': line.strip(),
                    'content': line,
                    'level': current_section['level'] + 1,
                    'order': len(current_sub_items) + 1,
                    'parent_id': current_section['order'],  # Referensi ke order dari parent section
                    'metadata': {'parent_item': current_section.get('metadata', {}).get('item_number') or current_section.get('metadata', {}).get('pasal_number')}
                }
                current_sub_items.append(sub_item)
            else:
                # Tambahkan ke konten dari section saat ini
                print(f"  -> Menambahkan ke section saat ini: {current_section['title'] if current_section else 'None'}")
                if current_section:
                    current_section['content'] += f"\n{line}"
        else:
            print(f"  -> Tidak cocok dengan apapun, current_section={current_section is not None}, in_structured_section={in_structured_section}")

        i += 1

    # Tambahkan section terakhir
    if current_section:
        full_content = current_section['content']
        if current_sub_items:
            full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
        
        current_section['content'] = full_content
        sections.append(current_section)
        print(f"-> Menyimpan section terakhir: {current_section['title']}")
        
        # Tambahkan sub-items
        for sub_item in current_sub_items:
            sections.append(sub_item)
            print(f"-> Menyimpan sub-item: {sub_item['title']}")

    # Jika tidak ada section terstruktur → kembalikan seluruh isi sebagai header/deskripsi
    if not sections:
        print("-> Tidak ada section terstruktur ditemukan, mengembalikan seluruh teks sebagai header")
        body = text.strip()
        if signature_block:
            body += "\n\n" + signature_block
        
        if body:
            sections.append({
                'type': 'header',
                'title': 'Deskripsi Surat Edaran',
                'content': body,
                'level': 0,
                'order': 1,
                'parent_id': None,
                'metadata': {}
            })

    # Tambahkan signature ke section terakhir jika ada
    if signature_block and sections:
        sections[-1]['content'] = sections[-1]['content'].rstrip() + "\n\n" + signature_block
        # Update metadata untuk menunjukkan ini termasuk signature
        if 'includes_signature' not in sections[-1]['metadata']:
            sections[-1]['metadata']['includes_signature'] = True
        print(f"-> Menambahkan signature ke section terakhir")

    print(f"=== SELESAI CHUNKING, Total: {len(sections)} sections ===")
    return sections

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

print("Testing debug_chunk_se function...")
chunks = debug_chunk_se(se_document)

print(f"\nJumlah chunks yang dihasilkan: {len(chunks)}")

print("\nDetail chunks:")
for i, chunk in enumerate(chunks):
    print(f"\nChunk {i+1}:")
    print(f"  Type: {chunk['type']}")
    print(f"  Title: {chunk['title']}")
    print(f"  Level: {chunk['level']}")
    print(f"  Order: {chunk['order']}")
    print(f"  Content preview (first 100 chars): {repr(chunk['content'][:100])}")
    print(f"  Content length: {len(chunk['content'])}")

# Verifikasi bahwa sekarang menghasilkan lebih dari 1 chunk
if len(chunks) > 1:
    print(f"\n✅ SUCCESS: Fungsi sekarang menghasilkan {len(chunks)} chunks (lebih dari 1)")
else:
    print(f"\n❌ ERROR: Fungsi masih hanya menghasilkan {len(chunks)} chunk")