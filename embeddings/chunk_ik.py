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
    header_match = re.search(r'(INSTRUKSI\s+KERJA.*?)(\n\s*\d+\.\s+)', main_content, re.IGNORECASE | re.DOTALL)
    if header_match:
        header = header_match.group(1).strip()
        main_content = main_content[header_match.end(1):]

    sections = []

    # Tambahkan header sebagai bagian awal
    if header:
        sections.append({
            "type": "header",
            "title": "Header Instruksi Kerja",
            "content": header,
            "parent_title": None
        })

    # Split berdasarkan bagian utama: 1., 2., 3., 4. (angka 1 digit + titik)
    # Hasil split akan menghasilkan: ['', '1. ', 'TUJUAN\n...', '2. ', 'DEFINISI\n...', '3. ', 'URAIAN INSTRUKSI\n...']
    parts = re.split(r'(\n?\s*\d+\.\s+)', main_content)
    
    # Proses pasangan header dan konten
    i = 1  # Mulai dari indeks 1 karena indeks 0 biasanya string kosong
    while i < len(parts):
        if i + 1 < len(parts):  # Pastikan ada header dan konten
            header_part = parts[i].strip()
            content_part = parts[i + 1].strip()
            
            # Ekstrak nomor dan judul dari header
            title_match = re.match(r'^\s*(\d+)\.\s*(.+)', header_part)
            if title_match:
                number = title_match.group(1)
                title = title_match.group(2).strip()
                section_title = f"{number}. {title}"
                
                sections.append({
                    "type": "bagian",
                    "title": section_title,
                    "content": header_part + content_part,  # Gabungkan header dan konten
                    "parent_title": None
                })
            
            i += 2  # Pindah 2 langkah karena sudah proses pasangan
        else:
            i += 1

    # Tambahkan LEMBAR PENGESAHAN jika ada
    if pengesahan_content:
        sections.append({
            "type": "pengesahan",
            "title": "LEMBAR PENGESAHAN",
            "content": pengesahan_content,
            "parent_title": None
        })

    return sections