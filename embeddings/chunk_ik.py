import re
from typing import List, Dict

def chunk_ik(text: str) -> List[Dict[str, str]]:
    """
    Chunk Instruksi Kerja dengan struktur:
    - Header (judul, nomor, edisi)
    - Bagian utama (1., 2., 3., 4.) — setiap bagian mencakup semua sub-butir di dalamnya
    - LEMBAR PENGESAHAN sebagai bagian terpisah
    """
    text = re.sub(r'={5,}\s*PAGE\s+\d+\s*={5,}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Pisahkan bagian utama dari LEMBAR PENGESAHAN
    pengesahan_match = re.search(r'(\n\s*LEMBAR\s+PENGESAHAN.*$)', text, re.IGNORECASE | re.DOTALL)
    if pengesahan_match:
        pengesahan_content = pengesahan_match.group(1).strip()
        main_content = text[:pengesahan_match.start()].strip()
    else:
        pengesahan_content = ""
        main_content = text

    # Ekstrak header (judul, nomor, edisi)
    header = ""
    # Cari pola INSTRUKSI KERJA sampai sebelum angka pertama yang diikuti titik
    header_match = re.search(r'(INSTRUKSI\s+KERJA.*?)((?=\n\s*\d+\.\s+)|(?=\n\s*1.\s+))', main_content, re.IGNORECASE | re.DOTALL)
    if header_match:
        header = header_match.group(1).strip()
        main_content = main_content[header_match.end():].strip()

    sections = []

    # Tambahkan header sebagai bagian awal
    if header:
        sections.append({
            "type": "header",
            "title": "Header Instruksi Kerja",
            "content": header,
            "parent_title": None
        })

    # Kita perlu mencari bagian utama: 1., 2., 3., 4. 
    # Tapi kita harus memastikan bahwa bagian-bagian ini adalah bagian utama, bukan sub-bagian
    # Kita akan menggunakan pendekatan yang lebih cermat:
    # Cari pola bagian utama yang diikuti oleh huruf kecil di baris berikutnya (deskripsi)
    
    # Karena header sudah diambil, kita perlu mencari bagian-bagian dalam main_content
    # yang berisi: 1. TUJUAN, 2. DEFINISI, 3. URAIAN INSTRUKSI, 4. REFERENSI DOKUMEN TERKAIT
    # dan memastikan bahwa setelah judul bagian adalah deskripsi, bukan sub-bagian seperti 1), 2), dll.
    
    # Buat pola regex yang mencari angka titik diikuti oleh judul besar dan diikuti oleh 
    # baris dengan huruf kecil atau karakter khusus yang biasanya muncul di deskripsi
    section_pattern = r'\n\s*(1|2|3|4)\.\s+([A-Z\s&]+[A-Z])(?=\n[a-z\(1-9])'
    
    # Kita juga harus menangani kasus di mana bagian 1. TUJUAN mungkin tidak terdeteksi dengan pola di atas
    # Jadi kita tambahkan pencarian untuk pola standar
    section_matches = []
    for match in re.finditer(r'\n\s*(1|2|3|4)\.\s+[A-Z\s&]+', main_content):
        section_matches.append((match.start(), match.end()))
    
    # Filter hanya bagian-bagian utama, bukan sub-bagian
    # Bagian utama biasanya diikuti oleh deskripsi dengan huruf kecil
    filtered_starts = []
    for start, end in section_matches:
        # Ambil sedikit teks setelah posisi end untuk mengecek apakah ini bagian utama
        after_end = main_content[end:end+50]
        # Jika setelah judul bagian ada baris baru diikuti huruf kecil, maka ini bagian utama
        if re.search(r'^[a-z\(]', after_end.strip(), re.MULTILINE):
            filtered_starts.append((start, end))
        # Atau jika dalam 50 karakter setelah judul, kita menemukan huruf kecil di awal baru
        elif re.search(r'\n\s*[a-z\(]', after_end):
            filtered_starts.append((start, end))
        # Atau jika ini adalah bagian 4 (REFERENSI DOKUMEN TERKAIT) yang biasanya di akhir
        elif re.search(r'\n\s*(4)\.', main_content[start:start+20]):
            filtered_starts.append((start, end))

    # Jika filter tidak memberikan hasil, kita gunakan semua hasil pencarian
    if not filtered_starts:
        filtered_starts = section_matches

    # Ekstrak setiap bagian
    section_parts = []
    for i in range(len(filtered_starts)):
        start_pos = filtered_starts[i][0]
        if i < len(filtered_starts) - 1:
            end_pos = filtered_starts[i+1][0]
            content = main_content[start_pos:end_pos].strip()
        else:
            content = main_content[start_pos:].strip()
        section_parts.append(content)
    
    # Proses setiap bagian
    for part in section_parts:
        # Ekstrak nomor dan judul bagian
        title_match = re.match(r'\n\s*(\d+)\.\s+(.+?)(?=\n)', part, re.DOTALL)
        if title_match:
            number = title_match.group(1)
            title = title_match.group(2).strip()
            section_title = f"{number}. {title}"
            
            # Sisanya adalah konten bagian tersebut
            content_start = title_match.end()
            content = part[content_start:].strip()
            
            full_content = f"{number}. {title}\n{content}".strip()
            
            sections.append({
                "type": "bagian",
                "title": section_title,
                "content": full_content,
                "parent_title": None
            })

    # Tambahkan LEMBAR PENGESAHAN jika ada
    if pengesahan_content:
        sections.append({
            "type": "pengesahan",
            "title": "LEMBAR PENGESAHAN",
            "content": pengesahan_content,
            "parent_title": None
        })

    return sections